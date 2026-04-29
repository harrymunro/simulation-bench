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

def test_get_base_travel_time_zero_or_negative_speed():
    assert get_base_travel_time(1000, 0) == float('inf')
    assert get_base_travel_time(1000, -5) == float('inf')

def test_build_graph_closed_edge_is_skipped():
    nodes_df = pd.DataFrame([
        {"node_id": "N1", "node_type": "junction"},
        {"node_id": "N2", "node_type": "junction"},
        {"node_id": "N3", "node_type": "junction"}
    ])
    edges_df = pd.DataFrame([
        {"edge_id": "E1", "from_node": "N1", "to_node": "N2", "distance_m": 1000, "max_speed_kph": 30, "closed": False},
        {"edge_id": "E2", "from_node": "N2", "to_node": "N3", "distance_m": 500, "max_speed_kph": 30, "closed": True},
        # Testing NaN case with missing value
        {"edge_id": "E3", "from_node": "N1", "to_node": "N3", "distance_m": 200, "max_speed_kph": 30} 
    ])
    
    G = build_graph(nodes_df, edges_df)
    
    assert "N1" in G.nodes
    assert "N2" in G.nodes
    assert "N3" in G.nodes
    
    assert ("N1", "N2") in G.edges
    assert ("N2", "N3") not in G.edges
    assert ("N1", "N3") in G.edges