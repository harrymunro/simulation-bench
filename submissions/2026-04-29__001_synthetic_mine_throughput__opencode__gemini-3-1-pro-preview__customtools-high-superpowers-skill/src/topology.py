import networkx as nx
import pandas as pd

def build_graph(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    
    for _, row in nodes_df.iterrows():
        G.add_node(row["node_id"], **row.to_dict())
        
    for _, row in edges_df.iterrows():
        # Only add edge if it's not explicitly closed
        if "closed" not in row or not row["closed"]:
            G.add_edge(row["from_node"], row["to_node"], **row.to_dict())
            
    return G

def get_base_travel_time(distance_m: float, speed_kph: float) -> float:
    # return minutes
    if speed_kph <= 0:
        return float('inf')
    return (distance_m / 1000.0) / speed_kph * 60.0