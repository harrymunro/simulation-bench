"""Topology tests: graph build, scenario overrides, routing validity."""
from pathlib import Path

import pandas as pd
import pytest

from mine_sim.topology import Topology

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture
def topo():
    nodes_df = pd.read_csv(DATA / "nodes.csv", dtype={"node_id": str})
    edges_df = pd.read_csv(DATA / "edges.csv", dtype={"edge_id": str, "from_node": str,
                                                        "to_node": str})
    return Topology(nodes_df, edges_df)


def test_baseline_graph_has_ramp(topo):
    g, df = topo.graph_for_scenario({})
    edge_ids = {d["edge_id"] for _, _, d in g.edges(data=True)}
    assert "E03_UP" in edge_ids
    assert "E03_DOWN" in edge_ids


def test_ramp_closed_graph_excludes_ramp(topo):
    overrides = {"E03_UP": {"closed": True}, "E03_DOWN": {"closed": True}}
    g, df = topo.graph_for_scenario(overrides)
    edge_ids = {d["edge_id"] for _, _, d in g.edges(data=True)}
    assert "E03_UP" not in edge_ids
    assert "E03_DOWN" not in edge_ids


def test_ramp_closed_route_via_bypass(topo):
    overrides = {"E03_UP": {"closed": True}, "E03_DOWN": {"closed": True}}
    g, df = topo.graph_for_scenario(overrides)
    path = topo.shortest_path(g, "PARK", "LOAD_N")
    assert path is not None, "must reroute via bypass"
    assert "J3" not in path or "J7" in path  # at least passes through bypass junction
    # J3 alone via ramp is no longer reachable directly from J2; check J7 is in path:
    assert "J7" in path


def test_ramp_upgrade_increases_speed(topo):
    base_g, _ = topo.graph_for_scenario({})
    upg_g, _ = topo.graph_for_scenario({"E03_UP": {"capacity": 999, "max_speed_kph": 28}})
    # find E03_UP weight
    base_w = base_g["J2"]["J3"]["weight"]
    upg_w = upg_g["J2"]["J3"]["weight"]
    assert upg_w < base_w, f"upgrade should lower travel time: base={base_w}, upg={upg_w}"


def test_path_to_crusher_exists(topo):
    g, _ = topo.graph_for_scenario({})
    for src in ("LOAD_N", "LOAD_S"):
        path = topo.shortest_path(g, src, "CRUSH")
        assert path is not None and path[0] == src and path[-1] == "CRUSH"
