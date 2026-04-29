import networkx as nx
import pandas as pd

class MineTopology:
    def __init__(self, nodes_csv_path, edges_csv_path, config=None):
        self.graph = nx.DiGraph()
        self._load_data(nodes_csv_path, edges_csv_path, config)

    def _load_data(self, nodes_path, edges_path, config):
        nodes_df = pd.read_csv(nodes_path)
        for _, row in nodes_df.iterrows():
            node_data = row.to_dict()
            if config and row['node_id'] in config.node_overrides:
                node_data.update(config.node_overrides[row['node_id']])
            self.graph.add_node(row['node_id'], **node_data)

        edges_df = pd.read_csv(edges_path)
        for _, row in edges_df.iterrows():
            edge_data = row.to_dict()
            if config and row['edge_id'] in config.edge_overrides:
                edge_data.update(config.edge_overrides[row['edge_id']])
                
            if edge_data.get('closed', False):
                continue
            
            # distance in meters, speed in km/h -> time in minutes
            # (distance / 1000) / speed * 60 = distance / speed * 0.06
            travel_time_min = (edge_data['distance_m'] / edge_data['max_speed_kph']) * 0.06
            edge_data['travel_time_min'] = travel_time_min
            
            self.graph.add_edge(
                row['from_node'], 
                row['to_node'], 
                **edge_data
            )
            
    def get_shortest_path(self, source, target):
        return nx.shortest_path(self.graph, source=source, target=target, weight='travel_time_min')
