import simpy
import pandas as pd
from src.simulation import MineSimulation
from src.config import Config
from src.topology import build_graph

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
