import simpy
import random
import numpy as np
from .topology import MineTopology
from .config import ScenarioConfig
import pandas as pd

class MineSimulation:
    def __init__(self, config: ScenarioConfig, topology: MineTopology, loaders_df: pd.DataFrame, dump_points_df: pd.DataFrame, random_seed: int):
        random.seed(random_seed)
        np.random.seed(random_seed)
        self.env = simpy.Environment()
        self.config = config
        self.topology = topology
        self.event_log = []
        self.metrics = {"total_tonnes_delivered": 0}
        
        # Resources
        self.loaders = {}
        self.crusher = None
        self.road_segments = {}
        
        self._setup_resources(loaders_df, dump_points_df)

    def _setup_resources(self, loaders_df, dump_points_df):
        for _, row in loaders_df.iterrows():
            self.loaders[row['node_id']] = simpy.Resource(self.env, capacity=int(row['capacity']))
            
        for _, row in dump_points_df.iterrows():
            if row['type'] == 'crusher':
                self.crusher = simpy.Resource(self.env, capacity=int(row['capacity']))
                
        # Setup constrained roads
        for u, v, data in self.topology.graph.edges(data=True):
            if 'capacity' in data and data['capacity'] < 999:
                # Use edge_id as resource key
                self.road_segments[data['edge_id']] = simpy.Resource(self.env, capacity=int(data['capacity']))

    def get_best_loader(self, current_node):
        available_loaders = []
        all_loaders = []
        
        for loader in self.config.ore_sources:
            path = self.topology.get_shortest_path(current_node, loader)
            # Sum base travel time
            travel_time = sum(self.topology.graph[path[i]][path[i+1]]['travel_time_min'] for i in range(len(path)-1))
            
            queue_len = len(self.loaders[loader].queue)
            node_data = self.topology.graph.nodes[loader]
            mean_service_time = node_data.get('service_time_mean_min', 5.0)
            
            all_loaders.append({
                'loader': loader,
                'travel_time': travel_time,
                'queue_len': queue_len,
                'mean_service_time': mean_service_time
            })
            
            if queue_len == 0:
                available_loaders.append({
                    'loader': loader,
                    'travel_time': travel_time
                })
                
        if available_loaders:
            # Pick the closest available loader (queue = 0)
            best = min(available_loaders, key=lambda x: x['travel_time'])
            return best['loader']
            
        # Fall back to score tie-breaker if all loaders have queues
        best_loader = None
        best_score = float('inf')
        
        for l in all_loaders:
            expected_queue_time = l['queue_len'] * l['mean_service_time']
            score = l['travel_time'] + expected_queue_time + l['mean_service_time']
            if score < best_score:
                best_score = score
                best_loader = l['loader']
                
        return best_loader
