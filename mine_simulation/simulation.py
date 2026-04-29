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
        best_loader = None
        best_score = float('inf')
        
        for loader in self.config.ore_sources:
            path = self.topology.get_shortest_path(current_node, loader)
            # Sum base travel time
            travel_time = sum(self.topology.graph[path[i]][path[i+1]]['travel_time_min'] for i in range(len(path)-1))
            
            queue_len = len(self.loaders[loader].queue)
            
            # Simplified score: travel_time + queue penalty
            # Assuming mean service time is ~5 min for tie breaking
            expected_queue_time = queue_len * 5.0
            
            score = travel_time + expected_queue_time
            if score < best_score:
                best_score = score
                best_loader = loader
                
        return best_loader
