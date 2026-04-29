import simpy
import networkx as nx
import pandas as pd
from typing import Dict
from src.config import Config
from src.metrics import EventLogger, SimulationMetrics

class MineSimulation:
    def __init__(self, env: simpy.Environment, config: Config, graph: nx.DiGraph, replication: int):
        self.env = env
        self.config = config
        self.graph = graph
        self.replication = replication
        self.logger = EventLogger()
        self.metrics = SimulationMetrics()
        
        self.resources: Dict[str, simpy.Resource] = {}
        self.edge_resources: Dict[str, simpy.Resource] = {}
        
        self._init_resources()
        
    def _init_resources(self):
        # Init node resources (loaders, crushers)
        for node_id, data in self.graph.nodes(data=True):
            if pd.notna(data.get('capacity')):
                cap = int(data['capacity'])
                self.resources[node_id] = simpy.Resource(self.env, capacity=cap)
                
        # Init edge resources (narrow ramps)
        for u, v, data in self.graph.edges(data=True):
            if pd.notna(data.get('capacity')) and data['capacity'] < 999:
                self.edge_resources[data['edge_id']] = simpy.Resource(self.env, capacity=int(data['capacity']))
