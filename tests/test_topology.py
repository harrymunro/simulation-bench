import pytest
import pandas as pd
from mine_simulation.topology import MineTopology

def test_topology_loading(tmp_path):
    # Setup dummy data
    nodes_csv = tmp_path / "nodes.csv"
    nodes_csv.write_text("node_id,node_name,node_type,x_m,y_m,z_m,capacity,service_time_mean_min,service_time_sd_min\nN1,Node 1,parking,0,0,0,,,\nN2,Node 2,crusher,0,0,0,,,")
    
    edges_csv = tmp_path / "edges.csv"
    edges_csv.write_text("edge_id,from_node,to_node,distance_m,max_speed_kph,road_type,capacity,closed\nE1,N1,N2,1000,60,flat,999,false")

    topology = MineTopology(nodes_csv, edges_csv)
    
    assert "N1" in topology.graph
    # 1000m at 60kph = 1 min
    assert topology.graph["N1"]["N2"]["travel_time_min"] == 1.0
