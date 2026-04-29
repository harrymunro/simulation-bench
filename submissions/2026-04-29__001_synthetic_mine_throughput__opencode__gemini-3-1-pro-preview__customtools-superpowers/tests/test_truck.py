import pytest
import numpy as np
import pandas as pd
from mine_simulation.simulation import MineSimulation
from mine_simulation.topology import MineTopology
from mine_simulation.config import ScenarioConfig
from mine_simulation.truck import Truck
from mine_simulation.utils import truncated_normal

def test_truncated_normal():
    rs = np.random.RandomState(42)
    # Mean 1.0, SD 10.0, lower bound 0.1
    # Should always return >= 0.1
    for _ in range(100):
        val = truncated_normal(1.0, 10.0, rs, lower_bound=0.1)
        assert val >= 0.1

def test_truck_init(tmp_path):
    nodes_csv = tmp_path / "nodes.csv"
    nodes_csv.write_text("node_id,node_name\nN1,Node 1\nN2,Node 2")
    edges_csv = tmp_path / "edges.csv"
    edges_csv.write_text("edge_id,from_node,to_node,distance_m,max_speed_kph,capacity\nE1,N1,N2,1000,60,1")
    
    top = MineTopology(nodes_csv, edges_csv)
    # travel_time_noise_cv=0.1
    cfg = ScenarioConfig("test", 8, 1, 42, 4, ["N1"], "N2", 0.1)
    
    ld_df = pd.DataFrame([{"node_id": "N1", "capacity": 1}])
    dp_df = pd.DataFrame([{"node_id": "N2", "type": "crusher", "capacity": 1}])
    
    sim = MineSimulation(cfg, top, ld_df, dp_df, 42)
    truck = Truck(sim, "T1", 200.0)
    
    assert truck.truck_id == "T1"
    assert truck.payload == 200.0
    assert truck.current_node == "PARK"
    assert not truck.loaded
    assert truck.action is not None
