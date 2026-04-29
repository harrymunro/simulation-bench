import simpy
import pandas as pd
import networkx as nx
from src.simulation import MineSimulation
from src.config import Config
from src.topology import build_graph
from src.routing import get_shortest_path_time

def test_simulation_init():
    env = simpy.Environment()
    config = Config("test", 8, 1, 123, 1)
    
    nodes = pd.DataFrame([
        {"node_id": "CRUSH", "node_type": "crusher", "capacity": 1, "service_time_mean_min": 3.0, "service_time_sd_min": 0.5}
    ])
    edges = pd.DataFrame([
        {"edge_id": "E1", "from_node": "A", "to_node": "B", "distance_m": 100, "max_speed_kph": 10, "capacity": 1}
    ])
    
    G = build_graph(nodes, edges)
    sim = MineSimulation(env, config, G, 1)
    
    # Should have instantiated resources
    assert "CRUSH" in sim.resources
    assert "E1" in sim.edge_resources
    assert sim.resources["CRUSH"].capacity == 1

def test_routing():
    G = nx.DiGraph()
    G.add_edge("A", "B", distance_m=1000, max_speed_kph=30) # 2 mins
    G.add_edge("B", "C", distance_m=500, max_speed_kph=30)  # 1 min
    
    time = get_shortest_path_time(G, "A", "C", 1.0)
    assert time == 3.0
    
    path = nx.shortest_path(G, "A", "C")
    assert path == ["A", "B", "C"]
