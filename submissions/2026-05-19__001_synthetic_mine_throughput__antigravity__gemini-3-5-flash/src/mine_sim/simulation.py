import os
import math
import random
from enum import Enum
import pandas as pd
import networkx as nx
import simpy

class TruckState(Enum):
    TRAVELLING_EMPTY = "TRAVELLING_EMPTY"
    QUEUEING_LOADER = "QUEUEING_LOADER"
    LOADING = "LOADING"
    TRAVELLING_LOADED = "TRAVELLING_LOADED"
    QUEUEING_CRUSHER = "QUEUEING_CRUSHER"
    DUMPING = "DUMPING"

class Truck:
    def __init__(self, id, payload_tonnes, empty_speed_factor, loaded_speed_factor, start_node):
        self.id = id
        self.payload_tonnes = payload_tonnes
        self.empty_speed_factor = empty_speed_factor
        self.loaded_speed_factor = loaded_speed_factor
        self.start_node = start_node
        
        # State tracking
        self.current_node = start_node
        self.state = TruckState.TRAVELLING_EMPTY
        self.state_durations = {state: 0.0 for state in TruckState}
        
        # Cycle logs
        self.cycle_times = []
        self.start_cycle_time = None

class Loader:
    def __init__(self, id, node_id, capacity, mean_load_time, sd_load_time, env):
        self.id = id
        self.node_id = node_id
        self.capacity = capacity
        self.mean_load_time = mean_load_time
        self.sd_load_time = sd_load_time
        self.resource = simpy.Resource(env, capacity=capacity)
        
        # Statistics
        self.busy_time = 0.0
        self.queue_times = []

class Crusher:
    def __init__(self, id, node_id, capacity, mean_dump_time, sd_dump_time, env):
        self.id = id
        self.node_id = node_id
        self.capacity = capacity
        self.mean_dump_time = mean_dump_time
        self.sd_dump_time = sd_dump_time
        self.resource = simpy.Resource(env, capacity=capacity)
        
        # Statistics
        self.busy_time = 0.0
        self.queue_times = []

class RoadNetwork:
    def __init__(self, nodes_df, edges_df, road_capacity_enabled, env=None):
        self.nodes_df = nodes_df
        self.edges_df = edges_df.copy()
        self.road_capacity_enabled = road_capacity_enabled
        self.env = env
        
        # Build network graph
        self.G = nx.DiGraph()
        self._build_graph()
        
        # Initialize resources for capacity-constrained edges (capacity < 999)
        self.edge_resources = {}
        self.edge_wait_times = {}
        self.edge_busy_times = {}
        self.edge_request_counts = {}
        
        if self.road_capacity_enabled and self.env is not None:
            for _, row in self.edges_df.iterrows():
                edge_id = row['edge_id']
                cap = row['capacity']
                if cap < 999 and not row.get('closed', False):
                    self.edge_resources[edge_id] = simpy.Resource(self.env, capacity=int(cap))
                    self.edge_wait_times[edge_id] = []
                    self.edge_busy_times[edge_id] = 0.0
                    self.edge_request_counts[edge_id] = 0

    def _build_graph(self):
        # Add nodes with metadata
        for _, row in self.nodes_df.iterrows():
            self.G.add_node(
                row['node_id'],
                node_name=row['node_name'],
                node_type=row['node_type'],
                x_m=row['x_m'],
                y_m=row['y_m'],
                z_m=row['z_m']
            )
            
        # Add edges with metadata
        for _, row in self.edges_df.iterrows():
            if row.get('closed', False):
                continue  # Skip closed edges for routing
            self.G.add_edge(
                row['from_node'],
                row['to_node'],
                edge_id=row['edge_id'],
                distance_m=row['distance_m'],
                max_speed_kph=row['max_speed_kph'],
                road_type=row['road_type'],
                capacity=row['capacity']
            )

    def apply_overrides(self, edge_overrides, node_overrides):
        # Update edges_df
        if edge_overrides:
            for edge_id, overrides in edge_overrides.items():
                idx = self.edges_df[self.edges_df['edge_id'] == edge_id].index
                if not idx.empty:
                    for k, v in overrides.items():
                        self.edges_df.loc[idx, k] = v
                        
        # Re-build graph if overridden
        self.G = nx.DiGraph()
        self._build_graph()

    def check_reachability(self, start_node, target_nodes):
        """Loudly check if target nodes are reachable from start_node."""
        for target in target_nodes:
            if not nx.has_path(self.G, start_node, target):
                raise RuntimeError(
                    f"REACHABILITY CHECK FAILED: No path exists from '{start_node}' to target '{target}'."
                )
            if not nx.has_path(self.G, target, 'CRUSH'):
                raise RuntimeError(
                    f"REACHABILITY CHECK FAILED: No return path exists from target '{target}' to crusher 'CRUSH'."
                )

    def get_edge(self, u, v):
        return self.G[u][v]

    def get_edge_resource(self, edge_id):
        return self.edge_resources.get(edge_id)

    def record_edge_queue_wait(self, edge_id, wait_time):
        if edge_id in self.edge_wait_times:
            self.edge_wait_times[edge_id].append(wait_time)
            self.edge_request_counts[edge_id] += 1

    def record_edge_busy_time(self, edge_id, busy_time):
        if edge_id in self.edge_busy_times:
            self.edge_busy_times[edge_id] += busy_time

    def get_shortest_path(self, start, end, truck_state='empty', truck=None):
        def weight_func(u, v, d):
            speed_factor = truck.empty_speed_factor if truck_state == 'empty' else truck.loaded_speed_factor
            speed_kph = d['max_speed_kph'] * speed_factor
            # Deterministic free-flow travel time in minutes
            return d['distance_m'] * 0.06 / speed_kph

        try:
            return nx.shortest_path(self.G, source=start, target=end, weight=weight_func)
        except nx.NetworkXNoPath:
            raise RuntimeError(f"No path exists between '{start}' and '{end}' for {truck_state} truck.")

    def calculate_path_travel_time(self, path, truck_state='empty', truck=None):
        """Sum deterministic free-flow travel times along a path in minutes."""
        time_min = 0.0
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge = self.get_edge(u, v)
            speed_factor = truck.empty_speed_factor if truck_state == 'empty' else truck.loaded_speed_factor
            speed_kph = edge['max_speed_kph'] * speed_factor
            time_min += edge['distance_m'] * 0.06 / speed_kph
        return time_min


class MineSimulation:
    def __init__(self, scenario_config, data_dir, replication_idx=0):
        self.scenario_config = scenario_config
        self.scenario_id = scenario_config['scenario_id']
        self.replication_idx = replication_idx
        
        # Determine random seed
        self.seed = scenario_config['simulation']['base_random_seed'] + replication_idx
        random.seed(self.seed)
        
        self.shift_length_minutes = scenario_config['simulation']['shift_length_hours'] * 60
        self.env = simpy.Environment()
        
        # Load CSVs
        nodes_df = pd.read_csv(os.path.join(data_dir, 'nodes.csv'))
        edges_df = pd.read_csv(os.path.join(data_dir, 'edges.csv'))
        trucks_df = pd.read_csv(os.path.join(data_dir, 'trucks.csv'))
        loaders_df = pd.read_csv(os.path.join(data_dir, 'loaders.csv'))
        dump_df = pd.read_csv(os.path.join(data_dir, 'dump_points.csv'))
        
        # Parse overrides from scenario config
        edge_overrides = scenario_config.get('edge_overrides', {})
        node_overrides = scenario_config.get('node_overrides', {})
        dump_overrides = scenario_config.get('dump_point_overrides', {})
        loader_overrides = scenario_config.get('loader_overrides', {})
        
        # Initialize RoadNetwork
        road_capacity_enabled = scenario_config['routing']['road_capacity_enabled']
        self.road_network = RoadNetwork(nodes_df, edges_df, road_capacity_enabled, self.env)
        self.road_network.apply_overrides(edge_overrides, node_overrides)
        
        # Determine active ore sources and destination
        self.ore_sources = scenario_config['production']['ore_sources']
        self.dump_destination = scenario_config['production']['dump_destination']
        
        # Perform reachability self-check
        self.road_network.check_reachability('PARK', self.ore_sources)
        
        # Initialize Loaders
        self.loaders = {}
        for _, row in loaders_df.iterrows():
            node_id = row['node_id']
            if node_id not in self.ore_sources:
                continue
            # Handle loader overrides if any
            mean_load = row['mean_load_time_min']
            sd_load = row['sd_load_time_min']
            if loader_overrides and row['loader_id'] in loader_overrides:
                mean_load = loader_overrides[row['loader_id']].get('mean_load_time_min', mean_load)
                sd_load = loader_overrides[row['loader_id']].get('sd_load_time_min', sd_load)
            self.loaders[node_id] = Loader(
                id=row['loader_id'],
                node_id=node_id,
                capacity=int(row['capacity']),
                mean_load_time=mean_load,
                sd_load_time=sd_load,
                env=self.env
            )
            
        # Initialize Crusher
        crush_row = dump_df[dump_df['node_id'] == self.dump_destination].iloc[0]
        mean_dump = crush_row['mean_dump_time_min']
        sd_dump = crush_row['sd_dump_time_min']
        if dump_overrides and crush_row['dump_id'] in dump_overrides:
            mean_dump = dump_overrides[crush_row['dump_id']].get('mean_dump_time_min', mean_dump)
            sd_dump = dump_overrides[crush_row['dump_id']].get('sd_dump_time_min', sd_dump)
        self.crusher = Crusher(
            id=crush_row['dump_id'],
            node_id=self.dump_destination,
            capacity=int(crush_row['capacity']),
            mean_dump_time=mean_dump,
            sd_dump_time=sd_dump,
            env=self.env
        )
        
        # Initialize Truck Fleet
        self.trucks = []
        truck_count = scenario_config['fleet']['truck_count']
        # Slice the trucks_df to get the configured fleet size
        fleet_df = trucks_df.iloc[:truck_count]
        for _, row in fleet_df.iterrows():
            truck = Truck(
                id=row['truck_id'],
                payload_tonnes=float(row['payload_tonnes']),
                empty_speed_factor=float(row['empty_speed_factor']),
                loaded_speed_factor=float(row['loaded_speed_factor']),
                start_node=row['start_node']
            )
            self.trucks.append(truck)
            self.env.process(self.truck_process(truck))
            
        # Operational outputs
        self.total_tonnes_delivered = 0.0
        self.event_log = []

    def sample_lognormal(self, mean_time, cv):
        """Draw a lognormally distributed value with specified mean and CV."""
        if mean_time <= 0:
            return 0.0
        cv2 = cv ** 2
        sigma_log = math.sqrt(math.log(1.0 + cv2))
        mu_log = math.log(mean_time) - 0.5 * sigma_log ** 2
        return random.lognormvariate(mu_log, sigma_log)

    def sample_loading_time(self, loader):
        """Truncated normal loading time, min 0.1 min."""
        val = random.normalvariate(loader.mean_load_time, loader.sd_load_time)
        return max(0.1, val)

    def sample_dumping_time(self):
        """Truncated normal dumping time, min 0.1 min."""
        val = random.normalvariate(self.crusher.mean_dump_time, self.crusher.sd_dump_time)
        return max(0.1, val)

    def decide_loader(self, truck):
        """Scoring-based loader dispatching."""
        best_loader_node = None
        best_score = float('inf')
        
        for loader_node in self.ore_sources:
            loader = self.loaders[loader_node]
            # Calculate shortest path travel time (deterministic free-flow)
            path = self.road_network.get_shortest_path(truck.current_node, loader_node, truck_state='empty', truck=truck)
            travel_time = self.road_network.calculate_path_travel_time(path, truck_state='empty', truck=truck)
            
            # Loader congestion (queuing + active loading)
            queue_len = len(loader.resource.queue) + loader.resource.count
            
            # score = travel + queue_len * mean_load + own_load
            score = travel_time + queue_len * loader.mean_load_time + loader.mean_load_time
            
            if score < best_score:
                best_score = score
                best_loader_node = loader_node
                
        return best_loader_node

    def log_event(self, time_min, truck_id, event_type, from_node=None, to_node=None, location=None, loaded=False, payload_tonnes=0.0, resource_id=None, queue_length=None):
        self.event_log.append({
            'time_min': round(time_min, 4),
            'replication': self.replication_idx,
            'scenario_id': self.scenario_id,
            'truck_id': truck_id,
            'event_type': event_type,
            'from_node': from_node,
            'to_node': to_node,
            'location': location,
            'loaded': loaded,
            'payload_tonnes': payload_tonnes,
            'resource_id': resource_id,
            'queue_length': queue_length
        })

    def travel_path(self, truck, path, truck_state):
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge = self.road_network.get_edge(u, v)
            edge_id = edge['edge_id']
            
            # Deterministic mean travel time
            speed_factor = truck.empty_speed_factor if truck_state == 'empty' else truck.loaded_speed_factor
            speed_kph = edge['max_speed_kph'] * speed_factor
            mean_time = edge['distance_m'] * 0.06 / speed_kph
            
            # Lognormal noise
            cv = self.scenario_config['stochasticity']['travel_time_noise_cv']
            actual_time = self.sample_lognormal(mean_time, cv)
            
            is_constrained = self.road_network.road_capacity_enabled and edge.get('capacity', 999) < 999
            
            if is_constrained:
                edge_resource = self.road_network.get_edge_resource(edge_id)
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='REQUEST_EDGE',
                    from_node=u,
                    to_node=v,
                    location=u,
                    loaded=(truck_state == 'loaded'),
                    payload_tonnes=truck.payload_tonnes if truck_state == 'loaded' else 0.0,
                    resource_id=edge_id,
                    queue_length=len(edge_resource.queue)
                )
                
                queue_start = self.env.now
                with edge_resource.request() as req:
                    yield req
                    
                    wait_time = self.env.now - queue_start
                    self.road_network.record_edge_queue_wait(edge_id, wait_time)
                    
                    self.log_event(
                        time_min=self.env.now,
                        truck_id=truck.id,
                        event_type='ENTER_EDGE',
                        from_node=u,
                        to_node=v,
                        location=u,
                        loaded=(truck_state == 'loaded'),
                        payload_tonnes=truck.payload_tonnes if truck_state == 'loaded' else 0.0,
                        resource_id=edge_id,
                        queue_length=len(edge_resource.queue)
                    )
                    
                    state_key = TruckState.TRAVELLING_EMPTY if truck_state == 'empty' else TruckState.TRAVELLING_LOADED
                    truck.state = state_key
                    
                    yield self.env.timeout(actual_time)
                    
                    truck.state_durations[state_key] += actual_time
                    self.road_network.record_edge_busy_time(edge_id, actual_time)
                    
                    self.log_event(
                        time_min=self.env.now,
                        truck_id=truck.id,
                        event_type='LEAVE_EDGE',
                        from_node=u,
                        to_node=v,
                        location=v,
                        loaded=(truck_state == 'loaded'),
                        payload_tonnes=truck.payload_tonnes if truck_state == 'loaded' else 0.0,
                        resource_id=edge_id,
                        queue_length=len(edge_resource.queue)
                    )
            else:
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='ENTER_EDGE',
                    from_node=u,
                    to_node=v,
                    location=u,
                    loaded=(truck_state == 'loaded'),
                    payload_tonnes=truck.payload_tonnes if truck_state == 'loaded' else 0.0,
                    resource_id=edge_id,
                    queue_length=None
                )
                
                state_key = TruckState.TRAVELLING_EMPTY if truck_state == 'empty' else TruckState.TRAVELLING_LOADED
                truck.state = state_key
                
                yield self.env.timeout(actual_time)
                
                truck.state_durations[state_key] += actual_time
                
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='LEAVE_EDGE',
                    from_node=u,
                    to_node=v,
                    location=v,
                    loaded=(truck_state == 'loaded'),
                    payload_tonnes=truck.payload_tonnes if truck_state == 'loaded' else 0.0,
                    resource_id=edge_id,
                    queue_length=None
                )
                
            truck.current_node = v

    def truck_process(self, truck):
        truck.current_node = truck.start_node
        
        while True:
            # 1. Dispatch decision
            loader_node = self.decide_loader(truck)
            
            self.log_event(
                time_min=self.env.now,
                truck_id=truck.id,
                event_type='DISPATCH',
                from_node=truck.current_node,
                to_node=loader_node,
                location=truck.current_node,
                loaded=False,
                payload_tonnes=0.0,
                resource_id=None,
                queue_length=None
            )
            
            # Reset cycle start time
            truck.start_cycle_time = self.env.now
            
            # 2. Travel to loader
            path = self.road_network.get_shortest_path(truck.current_node, loader_node, truck_state='empty', truck=truck)
            yield from self.travel_path(truck, path, truck_state='empty')
            
            # 3. Queue and loading
            loader = self.loaders[loader_node]
            arrival_time = self.env.now
            
            self.log_event(
                time_min=arrival_time,
                truck_id=truck.id,
                event_type='ARRIVE_LOADER',
                location=loader_node,
                loaded=False,
                payload_tonnes=0.0,
                resource_id=loader.id,
                queue_length=len(loader.resource.queue)
            )
            
            truck.state = TruckState.QUEUEING_LOADER
            queue_start = self.env.now
            
            with loader.resource.request() as req:
                yield req
                
                queue_time = self.env.now - queue_start
                loader.queue_times.append(queue_time)
                
                truck.state = TruckState.LOADING
                
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='START_LOADING',
                    location=loader_node,
                    loaded=False,
                    payload_tonnes=0.0,
                    resource_id=loader.id,
                    queue_length=len(loader.resource.queue)
                )
                
                load_time = self.sample_loading_time(loader)
                yield self.env.timeout(load_time)
                
                loader.busy_time += load_time
                truck.state_durations[TruckState.LOADING] += load_time
                
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='END_LOADING',
                    location=loader_node,
                    loaded=True,
                    payload_tonnes=truck.payload_tonnes,
                    resource_id=loader.id,
                    queue_length=len(loader.resource.queue)
                )
                
            truck.current_node = loader_node
            
            # 4. Travel loaded to crusher
            path = self.road_network.get_shortest_path(truck.current_node, self.dump_destination, truck_state='loaded', truck=truck)
            yield from self.travel_path(truck, path, truck_state='loaded')
            
            # 5. Queue and dump
            arrival_time = self.env.now
            
            self.log_event(
                time_min=arrival_time,
                truck_id=truck.id,
                event_type='ARRIVE_CRUSHER',
                location=self.dump_destination,
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
                resource_id=self.crusher.id,
                queue_length=len(self.crusher.resource.queue)
            )
            
            truck.state = TruckState.QUEUEING_CRUSHER
            queue_start = self.env.now
            
            with self.crusher.resource.request() as req:
                yield req
                
                queue_time = self.env.now - queue_start
                self.crusher.queue_times.append(queue_time)
                
                truck.state = TruckState.DUMPING
                
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='START_DUMPING',
                    location=self.dump_destination,
                    loaded=True,
                    payload_tonnes=truck.payload_tonnes,
                    resource_id=self.crusher.id,
                    queue_length=len(self.crusher.resource.queue)
                )
                
                dump_time = self.sample_dumping_time()
                yield self.env.timeout(dump_time)
                
                self.crusher.busy_time += dump_time
                truck.state_durations[TruckState.DUMPING] += dump_time
                
                # Check hard cut
                if self.env.now <= self.shift_length_minutes:
                    self.total_tonnes_delivered += truck.payload_tonnes
                    cycle_duration = self.env.now - truck.start_cycle_time
                    truck.cycle_times.append(cycle_duration)
                    
                self.log_event(
                    time_min=self.env.now,
                    truck_id=truck.id,
                    event_type='END_DUMPING',
                    location=self.dump_destination,
                    loaded=False,
                    payload_tonnes=0.0,
                    resource_id=self.crusher.id,
                    queue_length=len(self.crusher.resource.queue)
                )
                
            truck.current_node = self.dump_destination

    def run(self):
        """Execute simulation run up to shift_length_minutes."""
        self.env.run(until=self.shift_length_minutes)
        return self.get_results()

    def get_results(self):
        # Calculate truck utilisations
        truck_utils = {}
        for t in self.trucks:
            productive_time = (
                t.state_durations[TruckState.TRAVELLING_EMPTY] +
                t.state_durations[TruckState.LOADING] +
                t.state_durations[TruckState.TRAVELLING_LOADED] +
                t.state_durations[TruckState.DUMPING]
            )
            # Clip at shift length to prevent numerical overshoot (due to float rounding)
            productive_time = min(self.shift_length_minutes, productive_time)
            truck_utils[t.id] = productive_time / self.shift_length_minutes
            
        avg_truck_util = sum(truck_utils.values()) / len(truck_utils) if truck_utils else 0.0
        
        # Calculate crusher utilisation
        crusher_util = min(1.0, self.crusher.busy_time / self.shift_length_minutes)
        
        # Loader utilisations
        loader_utils = {}
        for node, l in self.loaders.items():
            loader_utils[l.id] = min(1.0, l.busy_time / self.shift_length_minutes)
            
        # Loader queue times
        avg_loader_q_times = []
        for l in self.loaders.values():
            if l.queue_times:
                avg_loader_q_times.append(sum(l.queue_times) / len(l.queue_times))
        avg_loader_q = sum(avg_loader_q_times) / len(avg_loader_q_times) if avg_loader_q_times else 0.0
        
        # Crusher queue times
        avg_crusher_q = sum(self.crusher.queue_times) / len(self.crusher.queue_times) if self.crusher.queue_times else 0.0
        
        # Truck cycle times
        all_cycle_times = []
        for t in self.trucks:
            all_cycle_times.extend(t.cycle_times)
        avg_cycle_time = sum(all_cycle_times) / len(all_cycle_times) if all_cycle_times else 0.0
        
        # Bottleneck calculation
        bottleneck_scores = {}
        # Loaders
        for l in self.loaders.values():
            util = min(1.0, l.busy_time / self.shift_length_minutes)
            mean_q = sum(l.queue_times) / len(l.queue_times) if l.queue_times else 0.0
            bottleneck_scores[l.id] = util * mean_q
            
        # Crusher
        crush_util = min(1.0, self.crusher.busy_time / self.shift_length_minutes)
        crush_mean_q = sum(self.crusher.queue_times) / len(self.crusher.queue_times) if self.crusher.queue_times else 0.0
        bottleneck_scores[self.crusher.id] = crush_util * crush_mean_q
        
        # Roads (capacity-constrained)
        if self.road_network.road_capacity_enabled:
            for edge_id, wait_list in self.road_network.edge_wait_times.items():
                busy = self.road_network.edge_busy_times.get(edge_id, 0.0)
                util = min(1.0, busy / self.shift_length_minutes)
                mean_q = sum(wait_list) / len(wait_list) if wait_list else 0.0
                bottleneck_scores[edge_id] = util * mean_q
                
        # Sort bottlenecks by score descending
        sorted_bottlenecks = sorted(bottleneck_scores.items(), key=lambda x: x[1], reverse=True)
        top_bottlenecks = [name for name, score in sorted_bottlenecks if score > 0.0]
        
        return {
            'scenario_id': self.scenario_id,
            'replication': self.replication_idx,
            'random_seed': self.seed,
            'total_tonnes_delivered': self.total_tonnes_delivered,
            'tonnes_per_hour': self.total_tonnes_delivered / (self.shift_length_minutes / 60.0),
            'average_truck_cycle_time_min': avg_cycle_time,
            'average_truck_utilisation': avg_truck_util,
            'crusher_utilisation': crusher_util,
            'loader_utilisation': loader_utils,
            'average_loader_queue_time_min': avg_loader_q,
            'average_crusher_queue_time_min': avg_crusher_q,
            'top_bottlenecks': top_bottlenecks,
            'bottleneck_scores': bottleneck_scores
        }
