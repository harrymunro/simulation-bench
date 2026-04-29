import pytest
import pandas as pd
from mine_simulation.simulation import MineSimulation
from mine_simulation.topology import MineTopology
from mine_simulation.config import ScenarioConfig

def test_simulation_init(tmp_path):
    nodes_csv = tmp_path / "nodes.csv"
    nodes_csv.write_text("node_id,node_name\nN1,Node 1\nN2,Node 2")
    edges_csv = tmp_path / "edges.csv"
    edges_csv.write_text("edge_id,from_node,to_node,distance_m,max_speed_kph,capacity\nE1,N1,N2,1000,60,1")
    
    top = MineTopology(nodes_csv, edges_csv)
    cfg = ScenarioConfig("test", 8, 1, 42, 4, ["N1"], "N2", 0.1)
    
    ld_df = pd.DataFrame([{"node_id": "N1", "capacity": 1}])
    dp_df = pd.DataFrame([{"node_id": "N2", "type": "crusher", "capacity": 1}])
    
    sim = MineSimulation(cfg, top, ld_df, dp_df, 42)
    assert "E1" in sim.road_segments
    assert "N1" in sim.loaders
    assert sim.crusher is not None
