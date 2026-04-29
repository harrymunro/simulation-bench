import simpy
from .topology import MineTopology
from .config import ScenarioConfig
import pandas as pd

class MineSimulation:
    def __init__(self, config: ScenarioConfig, topology: MineTopology, loaders_df: pd.DataFrame, dump_points_df: pd.DataFrame, random_seed: int):
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
            self.loaders[row['node_id']] = simpy.Resource(self.env, capacity=1)
            
        for _, row in dump_points_df.iterrows():
            if row['type'] == 'crusher':
                self.crusher = simpy.Resource(self.env, capacity=1)
                
        # Setup constrained roads
        for u, v, data in self.topology.graph.edges(data=True):
            if 'capacity' in data and data['capacity'] < 999:
                # Use edge_id as resource key
                self.road_segments[data['edge_id']] = simpy.Resource(self.env, capacity=int(data['capacity']))
