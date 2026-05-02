import os
import yaml
import pandas as pd
import numpy as np
import simpy
import networkx as nx
from scipy import stats
import json
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(message)s')

class MineSimulation:
    def __init__(self, data_dir: str, scenario_path: str, replication: int, seed: int):
        self.data_dir = data_dir
        self.scenario_config = self._load_scenario(scenario_path)
        self.replication = replication
        self.seed = seed
        self.rng = np.random.default_rng(seed)
        
        self.env = simpy.Environment()
        self.data = self._load_data()
        self.graph = self._build_graph()
        
        self.resources = {}
        self._setup_resources()
        
        self.trucks = []
        self._setup_trucks()
        
        self.event_log = []
        self.total_tonnes = 0.0
        self.completed_cycles = 0
        self.cycle_times = []
        
        # Performance monitoring
        self.truck_stats = [] # Will store utilization, etc.
        self.resource_stats = {} # Will store busy times
        
    def _load_scenario(self, path: str):
        with open(path, 'r') as f:
            config = yaml.safe_load(f)
        
        # Handle inheritance (simple version)
        if 'inherits' in config and config['inherits'] == 'baseline':
            baseline_path = os.path.join(os.path.dirname(path), 'baseline.yaml')
            if path != baseline_path:
                with open(baseline_path, 'r') as f:
                    base = yaml.safe_load(f)
                # Deep merge overrides for dictionaries
                for k, v in config.items():
                    if k == 'edge_overrides' and k in base:
                        base[k].update(v)
                    elif k == 'node_overrides' and k in base:
                        base[k].update(v)
                    elif k == 'dump_point_overrides' and k in base:
                        base[k].update(v)
                    elif k != 'inherits':
                        base[k] = v
                config = base
        return config

    def _load_data(self):
        nodes = pd.read_csv(os.path.join(self.data_dir, 'nodes.csv'))
        edges = pd.read_csv(os.path.join(self.data_dir, 'edges.csv'))
        trucks = pd.read_csv(os.path.join(self.data_dir, 'trucks.csv'))
        loaders = pd.read_csv(os.path.join(self.data_dir, 'loaders.csv'))
        dump_points = pd.read_csv(os.path.join(self.data_dir, 'dump_points.csv'))
        
        # Ensure 'closed' is boolean
        if 'closed' in edges.columns:
            edges['closed'] = edges['closed'].map(lambda x: str(x).lower() == 'true' if not isinstance(x, bool) else x)
        
        # Apply overrides from scenario
        if 'edge_overrides' in self.scenario_config:
            for eid, overrides in self.scenario_config['edge_overrides'].items():
                for col, val in overrides.items():
                    edges.loc[edges['edge_id'] == eid, col] = val
                    
        if 'node_overrides' in self.scenario_config:
            for nid, overrides in self.scenario_config['node_overrides'].items():
                for col, val in overrides.items():
                    nodes.loc[nodes['node_id'] == nid, col] = val

        if 'dump_point_overrides' in self.scenario_config:
            for did, overrides in self.scenario_config['dump_point_overrides'].items():
                for col, val in overrides.items():
                    dump_points.loc[dump_points['dump_id'] == did, col] = val

        # Handle fleet size
        if 'fleet' in self.scenario_config:
            count = self.scenario_config['fleet'].get('truck_count')
            if count:
                # If we need more trucks than in trucks.csv, we'll need to duplicate or assume same specs
                if count > len(trucks):
                    extra = count - len(trucks)
                    last_truck = trucks.iloc[-1]
                    for i in range(extra):
                        new_truck = last_truck.copy()
                        new_truck['truck_id'] = f"T{len(trucks)+i+1:02d}"
                        trucks = pd.concat([trucks, pd.DataFrame([new_truck])], ignore_index=True)
                else:
                    trucks = trucks.head(count)

        return {
            'nodes': nodes,
            'edges': edges,
            'trucks': trucks,
            'loaders': loaders,
            'dump_points': dump_points
        }

    def _build_graph(self):
        G = nx.DiGraph()
        for _, edge in self.data['edges'].iterrows():
            if edge['closed']:
                continue
            # Calculate base travel time in minutes
            speed_mpm = (edge['max_speed_kph'] * 1000) / 60
            base_time = edge['distance_m'] / speed_mpm
            
            G.add_edge(edge['from_node'], edge['to_node'], 
                       weight=base_time, 
                       distance=edge['distance_m'],
                       max_speed=edge['max_speed_kph'],
                       capacity=edge['capacity'],
                       edge_id=edge['edge_id'])
        return G

    def _setup_resources(self):
        # Loaders
        for _, loader in self.data['loaders'].iterrows():
            res = simpy.Resource(self.env, capacity=int(loader['capacity']))
            self.resources[loader['node_id']] = {
                'resource': res,
                'type': 'loader',
                'id': loader['loader_id'],
                'mean_time': loader['mean_load_time_min'],
                'sd_time': loader['sd_load_time_min'],
                'busy_time': 0.0,
                'queue_time_total': 0.0,
                'entries': 0
            }
            
        # Dump Points
        for _, dp in self.data['dump_points'].iterrows():
            res = simpy.Resource(self.env, capacity=int(dp['capacity']))
            self.resources[dp['node_id']] = {
                'resource': res,
                'type': 'dump',
                'id': dp['dump_id'],
                'mean_time': dp['mean_dump_time_min'],
                'sd_time': dp['sd_dump_time_min'],
                'busy_time': 0.0,
                'queue_time_total': 0.0,
                'entries': 0
            }
            
        # Capacity constrained edges
        for _, edge in self.data['edges'].iterrows():
            if edge['capacity'] < 100: # Assuming 999 is infinite
                res = simpy.Resource(self.env, capacity=int(edge['capacity']))
                self.resources[f"edge_{edge['edge_id']}"] = {
                    'resource': res,
                    'type': 'edge',
                    'id': edge['edge_id'],
                    'busy_time': 0.0
                }

    def _setup_trucks(self):
        for _, truck in self.data['trucks'].iterrows():
            t = Truck(self, truck)
            self.trucks.append(t)
            self.env.process(t.run())

    def log_event(self, truck_id, event_type, from_node=None, to_node=None, location=None, loaded=False, payload=0, resource_id=None, queue_length=0):
        self.event_log.append({
            'time_min': self.env.now,
            'replication': self.replication,
            'scenario_id': self.scenario_config['scenario_id'],
            'truck_id': truck_id,
            'event_type': event_type,
            'from_node': from_node,
            'to_node': to_node,
            'location': location,
            'loaded': loaded,
            'payload_tonnes': payload,
            'resource_id': resource_id,
            'queue_length': queue_length
        })

    def get_shortest_path(self, start, end):
        try:
            path = nx.shortest_path(self.graph, start, end, weight='weight')
            return path
        except nx.NetworkXNoPath:
            return None

    def run(self, duration_hours):
        self.env.run(until=duration_hours * 60)
        
class Truck:
    def __init__(self, sim: MineSimulation, data: pd.Series):
        self.sim = sim
        self.truck_id = data['truck_id']
        self.payload_capacity = data['payload_tonnes']
        self.empty_speed_factor = data['empty_speed_factor']
        self.loaded_speed_factor = data['loaded_speed_factor']
        self.current_node = data['start_node']
        self.loaded = False
        self.current_payload = 0
        
        self.total_moving_time = 0.0
        self.total_queue_time = 0.0
        self.total_service_time = 0.0
        self.start_cycle_time = 0.0

    def run(self):
        while True:
            # 1. Dispatch
            target_loader_node = self.dispatch()
            if not target_loader_node:
                break # Should not happen in this simulation
            
            self.start_cycle_time = self.sim.env.now
            
            # 2. Travel to loader
            yield from self.travel_to(target_loader_node)
            
            # 3. Load
            yield from self.service_at(target_loader_node)
            self.loaded = True
            self.current_payload = self.payload_capacity
            
            # 4. Travel to crusher
            crusher_node = self.sim.scenario_config['production']['dump_destination']
            yield from self.travel_to(crusher_node)
            
            # 5. Dump
            yield from self.service_at(crusher_node)
            
            # Record cycle
            cycle_time = self.sim.env.now - self.start_cycle_time
            self.sim.cycle_times.append(cycle_time)
            self.sim.total_tonnes += self.current_payload
            self.sim.completed_cycles += 1
            
            self.loaded = False
            self.current_payload = 0

    def dispatch(self):
        # Policy: nearest_available_loader
        loaders = self.sim.scenario_config['production']['ore_sources']
        
        # Check available first
        available_loaders = [l for l in loaders if self.sim.resources[l]['resource'].count < self.sim.resources[l]['resource'].capacity]
        
        candidates = available_loaders if available_loaders else loaders
        
        best_loader = None
        min_score = float('inf')
        
        for l_node in candidates:
            path = self.sim.get_shortest_path(self.current_node, l_node)
            if path:
                # Travel time
                travel_time = sum(self.sim.graph[u][v]['weight'] for u, v in zip(path[:-1], path[1:]))
                
                # Expected wait time (simplified: queue length * mean service time)
                res_info = self.sim.resources[l_node]
                wait_time = len(res_info['resource'].queue) * res_info['mean_time']
                
                score = travel_time + wait_time
                if score < min_score:
                    min_score = score
                    best_loader = l_node
        
        return best_loader

    def travel_to(self, destination):
        path = self.sim.get_shortest_path(self.current_node, destination)
        if not path:
            logging.error(f"Truck {self.truck_id} cannot find path from {self.current_node} to {destination}")
            return
            
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_data = self.sim.graph[u][v]
            
            edge_id = edge_data['edge_id']
            res_key = f"edge_{edge_id}"
            
            speed_factor = self.loaded_speed_factor if self.loaded else self.empty_speed_factor
            speed_mpm = (edge_data['max_speed'] * 1000) / 60 * speed_factor
            
            # Add stochasticity to travel time if config says so
            base_travel_time = edge_data['distance'] / speed_mpm
            cv = self.sim.scenario_config['stochasticity'].get('travel_time_noise_cv', 0)
            if cv > 0:
                # Using lognormal for positive values
                sigma = np.sqrt(np.log(1 + cv**2))
                mu = np.log(base_travel_time) - 0.5 * sigma**2
                travel_time = self.sim.rng.lognormal(mu, sigma)
            else:
                travel_time = base_travel_time
            
            self.sim.log_event(self.truck_id, "travel_start", from_node=u, to_node=v, loaded=self.loaded)
            
            if res_key in self.sim.resources:
                res = self.sim.resources[res_key]['resource']
                with res.request() as req:
                    yield req
                    start_wait = self.sim.env.now
                    yield self.sim.env.timeout(travel_time)
                    self.sim.resources[res_key]['busy_time'] += travel_time
            else:
                yield self.sim.env.timeout(travel_time)
            
            self.total_moving_time += travel_time
            self.current_node = v
            self.sim.log_event(self.truck_id, "travel_end", location=v, loaded=self.loaded)

    def service_at(self, node):
        res_info = self.sim.resources[node]
        res = res_info['resource']
        
        self.sim.log_event(self.truck_id, f"{res_info['type']}_arrive", location=node, loaded=self.loaded, queue_length=len(res.queue))
        
        arrival_time = self.sim.env.now
        with res.request() as req:
            yield req
            wait_time = self.sim.env.now - arrival_time
            self.total_queue_time += wait_time
            res_info['queue_time_total'] += wait_time
            res_info['entries'] += 1
            
            self.sim.log_event(self.truck_id, f"{res_info['type']}_start", location=node, loaded=self.loaded)
            
            # Stochastic service time
            mean = res_info['mean_time']
            sd = res_info['sd_time']
            # Normal truncated at 0
            service_time = max(0.1, self.sim.rng.normal(mean, sd))
            
            yield self.sim.env.timeout(service_time)
            self.total_service_time += service_time
            res_info['busy_time'] += service_time
            
            self.sim.log_event(self.truck_id, f"{res_info['type']}_end", location=node, loaded=self.loaded)

def run_experiment():
    data_dir = "/Users/harry/Workspace/simulation-bench/benchmarks/001_synthetic_mine_throughput/data"
    scenarios_dir = os.path.join(data_dir, "scenarios")
    
    scenario_files = [f for f in os.listdir(scenarios_dir) if f.endswith('.yaml')]
    all_results = []
    all_logs = []
    
    for sc_file in scenario_files:
        sc_path = os.path.join(scenarios_dir, sc_file)
        # Load config to get replications
        with open(sc_path, 'r') as f:
            sc_config = yaml.safe_load(f)
        
        replications = sc_config.get('simulation', {}).get('replications', 30)
        base_seed = sc_config.get('simulation', {}).get('base_random_seed', 12345)
        duration_hours = sc_config.get('simulation', {}).get('shift_length_hours', 8)
        
        logging.info(f"Running scenario: {sc_file} ({replications} replications)")
        
        for r in range(replications):
            seed = base_seed + r
            sim = MineSimulation(data_dir, sc_path, r, seed)
            sim.run(duration_hours)
            
            # Collect results
            total_tonnes = sim.total_tonnes
            tph = total_tonnes / duration_hours
            avg_cycle = np.mean(sim.cycle_times) if sim.cycle_times else 0
            
            # Truck utilization
            utils = []
            for t in sim.trucks:
                util = (t.total_moving_time + t.total_service_time) / (duration_hours * 60)
                utils.append(util)
            avg_truck_util = np.mean(utils)
            
            # Crusher utilization
            crush_node = sim.scenario_config['production']['dump_destination']
            crush_util = sim.resources[crush_node]['busy_time'] / (duration_hours * 60)
            
            # Queue times
            avg_loader_q = sum(res['queue_time_total'] for res in sim.resources.values() if res['type'] == 'loader') / \
                           max(1, sum(res['entries'] for res in sim.resources.values() if res['type'] == 'loader'))
            avg_crush_q = sim.resources[crush_node]['queue_time_total'] / max(1, sim.resources[crush_node]['entries'])
            
            all_results.append({
                'scenario_id': sim.scenario_config['scenario_id'],
                'replication': r,
                'random_seed': seed,
                'total_tonnes_delivered': total_tonnes,
                'tonnes_per_hour': tph,
                'average_truck_cycle_time_min': avg_cycle,
                'average_truck_utilisation': avg_truck_util,
                'crusher_utilisation': crush_util,
                'average_loader_queue_time_min': avg_loader_q,
                'average_crusher_queue_time_min': avg_crush_q
            })
            
            if r == 0: # Only keep log for first replication to keep file size reasonable
                all_logs.extend(sim.event_log)
                
    # Save results
    results_df = pd.DataFrame(all_results)
    results_df.to_csv("results.csv", index=False)
    
    logs_df = pd.DataFrame(all_logs)
    logs_df.to_csv("event_log.csv", index=False)
    
    # Generate summary.json
    summary = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": [
            "Trucks follow shortest-time path",
            "Truncated normal distribution for service times",
            "Lognormal noise for travel times"
        ],
        "model_limitations": [
            "No maintenance or breakdowns modeled",
            "Simplified traffic interactions"
        ],
        "additional_scenarios_proposed": [
            {
                "scenario_id": "crusher_expansion",
                "description": "Adding a second crusher lane (capacity: 2) to alleviate the primary bottleneck."
            }
        ]
    }
    
    for sc_id in results_df['scenario_id'].unique():
        sc_res = results_df[results_df['scenario_id'] == sc_id]
        
        def get_ci95(data):
            if len(data) < 2: return (0, 0)
            mean = np.mean(data)
            sem = stats.sem(data)
            h = sem * stats.t.ppf((1 + 0.95) / 2., len(data)-1)
            return mean - h, mean + h

        tonnes_mean = sc_res['total_tonnes_delivered'].mean()
        tonnes_ci = get_ci95(sc_res['total_tonnes_delivered'])
        
        tph_mean = sc_res['tonnes_per_hour'].mean()
        tph_ci = get_ci95(sc_res['tonnes_per_hour'])
        
        # Identify bottlenecks
        bottlenecks = []
        if sc_res['crusher_utilisation'].mean() > 0.85:
            bottlenecks.append("Crusher Capacity")
        if sc_res['average_crusher_queue_time_min'].mean() > 10:
            bottlenecks.append("Crusher Queueing")
        if sc_res['average_loader_queue_time_min'].mean() > 5:
            bottlenecks.append("Loader Capacity")
        if sc_res['average_truck_utilisation'].mean() > 0.90:
            bottlenecks.append("Truck Fleet Size")
            
        summary["scenarios"][sc_id] = {
            "replications": int(len(sc_res)),
            "shift_length_hours": 8,
            "total_tonnes_mean": float(tonnes_mean),
            "total_tonnes_ci95_low": float(tonnes_ci[0]),
            "total_tonnes_ci95_high": float(tonnes_ci[1]),
            "tonnes_per_hour_mean": float(tph_mean),
            "tonnes_per_hour_ci95_low": float(tph_ci[0]),
            "tonnes_per_hour_ci95_high": float(tph_ci[1]),
            "average_cycle_time_min": float(sc_res['average_truck_cycle_time_min'].mean()),
            "truck_utilisation_mean": float(sc_res['average_truck_utilisation'].mean()),
            "crusher_utilisation": float(sc_res['crusher_utilisation'].mean()),
            "average_loader_queue_time_min": float(sc_res['average_loader_queue_time_min'].mean()),
            "average_crusher_queue_time_min": float(sc_res['average_crusher_queue_time_min'].mean()),
            "top_bottlenecks": bottlenecks
        }
        
    with open("summary.json", "w") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    run_experiment()
