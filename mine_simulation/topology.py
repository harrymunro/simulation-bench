import networkx as nx
import pandas as pd

class MineTopology:
    def __init__(self, nodes_csv_path, edges_csv_path):
        self.graph = nx.DiGraph()
        self._load_data(nodes_csv_path, edges_csv_path)

    def _load_data(self, nodes_path, edges_path):
        nodes_df = pd.read_csv(nodes_path)
        for _, row in nodes_df.iterrows():
            self.graph.add_node(row['node_id'], **row.to_dict())

        edges_df = pd.read_csv(edges_path)
        for _, row in edges_df.iterrows():
            if row.get('closed', False):
                continue
            
            # distance in meters, speed in km/h -> time in minutes
            # (distance / 1000) / speed * 60 = distance / speed * 0.06
            travel_time_min = (row['distance_m'] / row['max_speed_kph']) * 0.06
            
            self.graph.add_edge(
                row['from_node'], 
                row['to_node'], 
                travel_time_min=travel_time_min,
                **row.to_dict()
            )
            
    def get_shortest_path(self, source, target):
        return nx.shortest_path(self.graph, source=source, target=target, weight='travel_time_min')
