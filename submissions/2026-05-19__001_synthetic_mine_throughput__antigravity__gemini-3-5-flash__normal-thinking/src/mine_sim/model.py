import simpy
import numpy as np
import pandas as pd

def sample_travel_time(base_time, cv, generator):
    if cv <= 0.0:
        return base_time
    sigma_log = np.sqrt(np.log(1.0 + cv**2))
    mu_log = np.log(base_time) - 0.5 * sigma_log**2
    return generator.lognormal(mu_log, sigma_log)

def sample_truncated_normal(mean, sd, generator, min_val=0.1):
    return max(min_val, generator.normal(mean, sd))

class SimulationModel:
    def __init__(self, scenario_cfg, mine_graph, replication_idx):
        self.scenario_cfg = scenario_cfg
        self.mine_graph = mine_graph
        self.replication_idx = replication_idx
        
        # Seed control
        self.base_seed = scenario_cfg["simulation"]["base_random_seed"]
        self.seed = self.base_seed + replication_idx
        self.rng = np.random.default_rng(self.seed)
        
        # SimPy environment
        self.env = simpy.Environment()
        
        # Shift configuration
        self.shift_length_hours = scenario_cfg["simulation"]["shift_length_hours"]
        self.shift_length_min = self.shift_length_hours * 60.0
        
        # Stochasticity configuration
        self.travel_time_noise_cv = scenario_cfg["stochasticity"]["travel_time_noise_cv"]
        
        # Dispatching factors (identical across trucks)
        self.empty_speed_factor = 1.0
        self.loaded_speed_factor = 0.85
        
        # Initialize SimPy resources
        self.loader_resources = {}
        self.loaders_data = {}
        for node_id, node_attr in self.mine_graph.G.nodes(data=True):
            if node_attr['node_type'] == 'load_ore':
                loader_id = "L_N" if node_id == "LOAD_N" else "L_S"
                mean_load = node_attr['service_time_mean_min']
                sd_load = node_attr['service_time_sd_min']
                
                self.loaders_data[loader_id] = {
                    "node_id": node_id,
                    "mean_load_time_min": mean_load,
                    "sd_load_time_min": sd_load,
                    "capacity": 1
                }
                self.loader_resources[loader_id] = simpy.Resource(self.env, capacity=1)
                
        # Crusher resource
        crusher_node_attr = self.mine_graph.G.nodes['CRUSH']
        self.dump_points_data = {
            "D_CRUSH": {
                "node_id": "CRUSH",
                "mean_dump_time_min": crusher_node_attr['service_time_mean_min'],
                "sd_dump_time_min": crusher_node_attr['service_time_sd_min'],
                "capacity": 1
            }
        }
        self.crusher_resource = simpy.Resource(self.env, capacity=1)
        
        # Capacity-constrained edges
        self.edge_resources = {}
        for u, v, d in self.mine_graph.G.edges(data=True):
            if d['capacity'] == 1:
                edge_id = d['edge_id']
                self.edge_resources[edge_id] = simpy.Resource(self.env, capacity=1)
                
        # Fleet setup
        self.truck_count = scenario_cfg["fleet"]["truck_count"]
        # Find first truck_count rows in trucks.csv
        # All trucks in the synthetic dataset have payload=100, empty_speed_factor=1.0, loaded_speed_factor=0.85
        
        # State variables and metrics
        self.total_tonnes_delivered = 0.0
        self.event_log = []
        
        # Truck metrics tracking
        # States: 'TRAVEL_EMPTY', 'TRAVEL_LOADED', 'LOADING', 'DUMPING', 'QUEUE_LOADER', 'QUEUE_CRUSHER', 'QUEUE_EDGE'
        self.truck_stats = {}
        self.truck_states = {} # truck_id -> (current_state, start_time)
        
        # Resource stats
        self.loader_stats = {
            "L_N": {"busy_time": 0.0, "state": "IDLE", "state_start": 0.0, "queue_times": [], "queue_lens": []},
            "L_S": {"busy_time": 0.0, "state": "IDLE", "state_start": 0.0, "queue_times": [], "queue_lens": []}
        }
        self.crusher_stats = {"busy_time": 0.0, "state": "IDLE", "state_start": 0.0, "queue_times": [], "queue_lens": []}
        
        self.edge_stats = {}
        for edge_id in self.edge_resources:
            self.edge_stats[edge_id] = {
                "busy_time": 0.0,
                "state": "IDLE",
                "state_start": 0.0,
                "queue_times": [],
                "queue_lens": []
            }
            
    def log_event(self, time_min, truck_id, event_type, from_node, to_node, location, loaded, payload, resource_id, queue_length):
        self.event_log.append({
            "time_min": round(time_min, 4),
            "replication": self.replication_idx,
            "scenario_id": self.scenario_cfg["scenario_id"],
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": loaded,
            "payload_tonnes": payload,
            "resource_id": resource_id,
            "queue_length": queue_length
        })
        
    def transition_truck_state(self, truck_id, new_state, now):
        old_state, start_time = self.truck_states[truck_id]
        duration = now - start_time
        if duration > 0:
            self.truck_stats[truck_id][old_state] += duration
        self.truck_states[truck_id] = (new_state, now)
        
    def transition_loader_state(self, loader_id, new_state, now):
        old_state = self.loader_stats[loader_id]["state"]
        start_time = self.loader_stats[loader_id]["state_start"]
        duration = now - start_time
        if duration > 0:
            if old_state == "BUSY":
                self.loader_stats[loader_id]["busy_time"] += duration
        self.loader_stats[loader_id]["state"] = new_state
        self.loader_stats[loader_id]["state_start"] = now
        
    def transition_crusher_state(self, new_state, now):
        old_state = self.crusher_stats["state"]
        start_time = self.crusher_stats["state_start"]
        duration = now - start_time
        if duration > 0:
            if old_state == "BUSY":
                self.crusher_stats["busy_time"] += duration
        self.crusher_stats["state"] = new_state
        self.crusher_stats["state_start"] = now
        
    def transition_edge_state(self, edge_id, new_state, now):
        old_state = self.edge_stats[edge_id]["state"]
        start_time = self.edge_stats[edge_id]["state_start"]
        duration = now - start_time
        if duration > 0:
            if old_state == "BUSY":
                self.edge_stats[edge_id]["busy_time"] += duration
        self.edge_stats[edge_id]["state"] = new_state
        self.edge_stats[edge_id]["state_start"] = now

    def dispatch_truck(self, truck_id, current_node, now):
        """
        Implements: dispatch = min(travel + queue_len * mean_load + own_load)
        """
        best_loader_id = None
        best_loader_node = None
        best_score = float('inf')
        
        for loader_id, loader_info in self.loaders_data.items():
            loader_node = loader_info['node_id']
            
            # Calculate shortest path travel time from current_node to loader_node
            _, _, travel_time = self.mine_graph.compute_shortest_path(
                current_node, loader_node, is_loaded=False,
                empty_speed_factor=self.empty_speed_factor,
                loaded_speed_factor=self.loaded_speed_factor
            )
            
            # Calculate current queue length at loader (waiting + in-service)
            res = self.loader_resources[loader_id]
            queue_len = len(res.queue) + res.count
            
            mean_load = loader_info['mean_load_time_min']
            
            # Dispatch Formula: travel + queue_len * mean_load + own_load (which is mean_load)
            score = travel_time + queue_len * mean_load + mean_load
            
            if score < best_score:
                best_score = score
                best_loader_id = loader_id
                best_loader_node = loader_node
                
        return best_loader_id, best_loader_node

    def truck_process(self, truck_id):
        current_node = "PARK"
        is_loaded = False
        payload = 100.0 # Standard from trucks.csv
        
        # Register in stats
        self.truck_stats[truck_id] = {
            "TRAVEL_EMPTY": 0.0,
            "TRAVEL_LOADED": 0.0,
            "LOADING": 0.0,
            "DUMPING": 0.0,
            "QUEUE_LOADER": 0.0,
            "QUEUE_CRUSHER": 0.0,
            "QUEUE_EDGE": 0.0,
            "completed_cycles": []
        }
        self.truck_states[truck_id] = ("PARKED", 0.0)
        
        # Simultaneous t=0 dispatch
        loader_id, loader_node = self.dispatch_truck(truck_id, current_node, self.env.now)
        self.log_event(self.env.now, truck_id, "dispatch", current_node, loader_node, current_node, is_loaded, 0.0, loader_id, 0)
        self.transition_truck_state(truck_id, "TRAVEL_EMPTY", self.env.now)
        
        cycle_start_time = self.env.now
        target_node = loader_node
        
        while True:
            # 1. Travel from current_node to target_node edge-by-edge
            path_nodes, path_edges, _ = self.mine_graph.compute_shortest_path(
                current_node, target_node, is_loaded, self.empty_speed_factor, self.loaded_speed_factor
            )
            
            for i in range(len(path_nodes) - 1):
                u, v = path_nodes[i], path_nodes[i+1]
                edge_data = self.mine_graph.get_edge_details(u, v)
                edge_id = edge_data['edge_id']
                is_constrained = (edge_data['capacity'] == 1)
                
                # Base free flow travel time on this edge
                edge_base_time = self.mine_graph.calculate_free_flow_travel_time(
                    u, v, is_loaded, self.empty_speed_factor, self.loaded_speed_factor
                )
                # Sample with lognormal noise
                edge_time = sample_travel_time(edge_base_time, self.travel_time_noise_cv, self.rng)
                
                if is_constrained:
                    res = self.edge_resources[edge_id]
                    self.log_event(self.env.now, truck_id, "edge_queue_start", u, v, u, is_loaded, payload if is_loaded else 0.0, edge_id, len(res.queue))
                    self.transition_truck_state(truck_id, "QUEUE_EDGE", self.env.now)
                    
                    queue_start = self.env.now
                    with res.request() as req:
                        yield req
                        
                        queue_wait = self.env.now - queue_start
                        self.edge_stats[edge_id]["queue_times"].append(queue_wait)
                        
                        self.log_event(self.env.now, truck_id, "edge_enter", u, v, u, is_loaded, payload if is_loaded else 0.0, edge_id, len(res.queue))
                        self.transition_truck_state(truck_id, "TRAVEL_LOADED" if is_loaded else "TRAVEL_EMPTY", self.env.now)
                        
                        # Edge becomes busy
                        self.transition_edge_state(edge_id, "BUSY", self.env.now)
                        
                        yield self.env.timeout(edge_time)
                        
                        self.transition_edge_state(edge_id, "IDLE", self.env.now)
                        self.log_event(self.env.now, truck_id, "edge_leave", u, v, v, is_loaded, payload if is_loaded else 0.0, edge_id, len(res.queue))
                else:
                    self.log_event(self.env.now, truck_id, "travel_start", u, v, u, is_loaded, payload if is_loaded else 0.0, edge_id, 0)
                    self.transition_truck_state(truck_id, "TRAVEL_LOADED" if is_loaded else "TRAVEL_EMPTY", self.env.now)
                    
                    yield self.env.timeout(edge_time)
                    
                    self.log_event(self.env.now, truck_id, "travel_end", u, v, v, is_loaded, payload if is_loaded else 0.0, edge_id, 0)
                    
            current_node = target_node
            
            # 2. Arrived at target loader node
            if current_node in ["LOAD_N", "LOAD_S"]:
                loader_id = "L_N" if current_node == "LOAD_N" else "L_S"
                res = self.loader_resources[loader_id]
                loader_info = self.loaders_data[loader_id]
                
                self.log_event(self.env.now, truck_id, "loader_queue_start", current_node, current_node, current_node, is_loaded, 0.0, loader_id, len(res.queue))
                self.transition_truck_state(truck_id, "QUEUE_LOADER", self.env.now)
                
                queue_start = self.env.now
                with res.request() as req:
                    yield req
                    
                    queue_wait = self.env.now - queue_start
                    self.loader_stats[loader_id]["queue_times"].append(queue_wait)
                    
                    self.log_event(self.env.now, truck_id, "load_start", current_node, current_node, current_node, is_loaded, 0.0, loader_id, len(res.queue))
                    self.transition_truck_state(truck_id, "LOADING", self.env.now)
                    
                    # Loader becomes busy
                    self.transition_loader_state(loader_id, "BUSY", self.env.now)
                    
                    load_time = sample_truncated_normal(loader_info['mean_load_time_min'], loader_info['sd_load_time_min'], self.rng)
                    yield self.env.timeout(load_time)
                    
                    self.transition_loader_state(loader_id, "IDLE", self.env.now)
                    is_loaded = True
                    self.log_event(self.env.now, truck_id, "load_end", current_node, current_node, current_node, is_loaded, payload, loader_id, len(res.queue))
                    
                # Dispatch loaded truck to crusher
                target_node = "CRUSH"
                self.transition_truck_state(truck_id, "TRAVEL_LOADED", self.env.now)
                
            # 3. Arrived at crusher node
            elif current_node == "CRUSH":
                res = self.crusher_resource
                dump_info = self.dump_points_data["D_CRUSH"]
                
                self.log_event(self.env.now, truck_id, "crusher_queue_start", current_node, current_node, current_node, is_loaded, payload, "D_CRUSH", len(res.queue))
                self.transition_truck_state(truck_id, "QUEUE_CRUSHER", self.env.now)
                
                queue_start = self.env.now
                with res.request() as req:
                    yield req
                    
                    queue_wait = self.env.now - queue_start
                    self.crusher_stats["queue_times"].append(queue_wait)
                    
                    self.log_event(self.env.now, truck_id, "dump_start", current_node, current_node, current_node, is_loaded, payload, "D_CRUSH", len(res.queue))
                    self.transition_truck_state(truck_id, "DUMPING", self.env.now)
                    
                    # Crusher becomes busy
                    self.transition_crusher_state("BUSY", self.env.now)
                    
                    dump_time = sample_truncated_normal(dump_info['mean_dump_time_min'], dump_info['sd_dump_time_min'], self.rng)
                    yield self.env.timeout(dump_time)
                    
                    self.transition_crusher_state("IDLE", self.env.now)
                    self.total_tonnes_delivered += payload
                    is_loaded = False
                    
                    # Complete cycle
                    cycle_time = self.env.now - cycle_start_time
                    self.truck_stats[truck_id]["completed_cycles"].append(cycle_time)
                    
                    self.log_event(self.env.now, truck_id, "dump_end", current_node, current_node, current_node, is_loaded, payload, "D_CRUSH", len(res.queue))
                    
                # After dump completion, dispatch back to a loader empty
                loader_id, loader_node = self.dispatch_truck(truck_id, current_node, self.env.now)
                self.log_event(self.env.now, truck_id, "dispatch", current_node, loader_node, current_node, is_loaded, 0.0, loader_id, 0)
                self.transition_truck_state(truck_id, "TRAVEL_EMPTY", self.env.now)
                
                cycle_start_time = self.env.now
                target_node = loader_node

    def run(self):
        """
        Runs the simulation up to shift_length_min.
        """
        # Periodic recorder for queue lengths
        def queue_recorder():
            while True:
                # Loaders
                for loader_id, res in self.loader_resources.items():
                    self.loader_stats[loader_id]["queue_lens"].append(len(res.queue))
                # Crusher
                self.crusher_stats["queue_lens"].append(len(self.crusher_resource.queue))
                # Constrained edges
                for edge_id, res in self.edge_resources.items():
                    self.edge_stats[edge_id]["queue_lens"].append(len(res.queue))
                yield self.env.timeout(1.0) # record every minute
                
        self.env.process(queue_recorder())
        
        # Start truck processes
        for i in range(self.truck_count):
            truck_id = f"T{i+1:02d}"
            self.env.process(self.truck_process(truck_id))
            
        # Run environment
        self.env.run(until=self.shift_length_min)
        
        # 4. Finalize state timers up to exactly 480.0 minutes
        now = self.shift_length_min
        for truck_id in self.truck_stats:
            old_state, start_time = self.truck_states[truck_id]
            duration = now - start_time
            if duration > 0:
                self.truck_stats[truck_id][old_state] += duration
                
        for loader_id in self.loader_stats:
            self.transition_loader_state(loader_id, "IDLE", now)
            
        self.transition_crusher_state("IDLE", now)
        
        for edge_id in self.edge_stats:
            self.transition_edge_state(edge_id, "IDLE", now)
            
    def get_summary_metrics(self):
        """
        Computes summary statistics for this replication.
        """
        now = self.shift_length_min
        
        # Truck utilization (productive only = TRAVEL_EMPTY + TRAVEL_LOADED + LOADING + DUMPING)
        truck_utilisations = []
        cycle_times = []
        for truck_id, stats in self.truck_stats.items():
            productive_time = stats["TRAVEL_EMPTY"] + stats["TRAVEL_LOADED"] + stats["LOADING"] + stats["DUMPING"]
            truck_utilisations.append(productive_time / now)
            cycle_times.extend(stats["completed_cycles"])
            
        avg_truck_util = np.mean(truck_utilisations) if truck_utilisations else 0.0
        avg_cycle_time = np.mean(cycle_times) if cycle_times else 0.0
        
        # Resource utilisations
        loader_utils = {}
        for loader_id, stats in self.loader_stats.items():
            loader_utils[loader_id] = stats["busy_time"] / now
            
        crusher_util = self.crusher_stats["busy_time"] / now
        
        # Mean queue waits
        avg_loader_q_waits = []
        for loader_id, stats in self.loader_stats.items():
            if stats["queue_times"]:
                avg_loader_q_waits.append(np.mean(stats["queue_times"]))
            else:
                avg_loader_q_waits.append(0.0)
        avg_loader_queue_time = np.mean(avg_loader_q_waits) if avg_loader_q_waits else 0.0
        
        avg_crusher_queue_time = np.mean(self.crusher_stats["queue_times"]) if self.crusher_stats["queue_times"] else 0.0
        
        # Return dict of metrics
        return {
            "replication": self.replication_idx,
            "random_seed": self.seed,
            "total_tonnes_delivered": self.total_tonnes_delivered,
            "tonnes_per_hour": self.total_tonnes_delivered / (self.shift_length_hours),
            "average_truck_cycle_time_min": avg_cycle_time,
            "average_truck_utilisation": avg_truck_util,
            "crusher_utilisation": crusher_util,
            "loader_utilisation": loader_utils,
            "average_loader_queue_time_min": avg_loader_queue_time,
            "average_crusher_queue_time_min": avg_crusher_queue_time,
            "raw_truck_stats": self.truck_stats,
            "raw_loader_stats": self.loader_stats,
            "raw_crusher_stats": self.crusher_stats,
            "raw_edge_stats": self.edge_stats
        }
