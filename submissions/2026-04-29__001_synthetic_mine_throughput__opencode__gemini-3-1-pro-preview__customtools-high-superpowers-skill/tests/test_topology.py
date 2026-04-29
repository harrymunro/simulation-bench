import pytest
import pandas as pd
import networkx as nx
from src.topology import build_graph, get_base_travel_time

def test_build_graph():
    nodes_df = pd.DataFrame([
        {"node_id": "N1", "node_type": "junction", "capacity": None, "service_time_mean_min": None, "service_time_sd_min": None},
        {"node_id": "N2", "node_type": "load_ore", "capacity": 1, "service_time_mean_min": 5.0, "service_time_sd_min": 1.0}
    ])
    edges_df = pd.DataFrame([
        {"edge_id": "E1", "from_node": "N1", "to_node": "N2", "distance_m": 1000, "max_speed_kph": 30, "capacity": 999}
    ])
    
    G = build_graph(nodes_df, edges_df)
    
    assert isinstance(G, nx.DiGraph)
    assert "N1" in G.nodes
    assert "N2" in G.nodes
    assert G.nodes["N2"]["capacity"] == 1
    assert G.edges["N1", "N2"]["distance_m"] == 1000
    assert "E1" in [edge[2]["edge_id"] for edge in G.edges(data=True)]

def test_get_base_travel_time():
    # 1000m at 30kph = 2 minutes
    time_min = get_base_travel_time(1000, 30)
    assert time_min == 2.0