from pathlib import Path

import pytest

from mine_sim.topology import (
    EDGE_TO_LOCK,
    apply_overrides,
    build_graph,
    compute_shortest_paths,
    load_dump_points,
    load_edges,
    load_loaders,
    load_nodes,
    load_trucks,
)

DATA_DIR = Path(__file__).parent.parent / "data"


def test_load_nodes_returns_dict_keyed_by_id():
    nodes = load_nodes(DATA_DIR / "nodes.csv")
    assert "PARK" in nodes
    assert nodes["PARK"].node_type == "parking"
    assert nodes["LOAD_N"].node_type == "load_ore"
    assert nodes["CRUSH"].node_type == "crusher"
    assert nodes["LOAD_N"].service_time_mean_min == pytest.approx(6.5)


def test_load_edges_returns_dict_keyed_by_id():
    edges = load_edges(DATA_DIR / "edges.csv")
    assert "E03_UP" in edges
    assert edges["E03_UP"].capacity == 1
    assert edges["E03_UP"].max_speed_kph == pytest.approx(18.0)
    assert edges["E03_UP"].closed is False
    assert edges["E01_OUT"].capacity == 999


def test_load_trucks_returns_dict_keyed_by_id():
    trucks = load_trucks(DATA_DIR / "trucks.csv")
    assert "T01" in trucks
    assert trucks["T01"].payload_tonnes == pytest.approx(100.0)
    assert trucks["T01"].empty_speed_factor == pytest.approx(1.0)
    assert trucks["T01"].loaded_speed_factor == pytest.approx(0.85)


def test_load_loaders_returns_dict_keyed_by_id():
    loaders = load_loaders(DATA_DIR / "loaders.csv")
    assert loaders["L_N"].node_id == "LOAD_N"
    assert loaders["L_N"].mean_load_time_min == pytest.approx(6.5)
    assert loaders["L_S"].mean_load_time_min == pytest.approx(4.5)


def test_load_dump_points_returns_dict_keyed_by_id():
    dumps = load_dump_points(DATA_DIR / "dump_points.csv")
    assert dumps["D_CRUSH"].node_id == "CRUSH"
    assert dumps["D_CRUSH"].mean_dump_time_min == pytest.approx(3.5)


def test_edge_to_lock_mapping():
    assert EDGE_TO_LOCK["E03_UP"] == "RAMP"
    assert EDGE_TO_LOCK["E03_DOWN"] == "RAMP"
    assert EDGE_TO_LOCK["E07_TO_LOAD_N"] == "PIT_N"
    assert EDGE_TO_LOCK["E07_FROM_LOAD_N"] == "PIT_N"
    assert EDGE_TO_LOCK["E09_TO_LOAD_S"] == "PIT_S"
    assert EDGE_TO_LOCK["E09_FROM_LOAD_S"] == "PIT_S"
    assert EDGE_TO_LOCK["E05_TO_CRUSH"] == "E05_TO"
    assert EDGE_TO_LOCK["E05_FROM_CRUSH"] == "E05_FROM"
    assert "E01_OUT" not in EDGE_TO_LOCK


def test_apply_overrides_patches_edge_capacity_and_speed():
    edges = load_edges(DATA_DIR / "edges.csv")
    overrides = {"edge_overrides": {"E03_UP": {"capacity": 999, "max_speed_kph": 28}}}
    apply_overrides(edges_dict=edges, nodes_dict={}, dumps_dict={}, config=overrides)
    assert edges["E03_UP"].capacity == 999
    assert edges["E03_UP"].max_speed_kph == pytest.approx(28.0)


def test_apply_overrides_can_close_edges():
    edges = load_edges(DATA_DIR / "edges.csv")
    overrides = {"edge_overrides": {"E03_UP": {"closed": True}}}
    apply_overrides(edges_dict=edges, nodes_dict={}, dumps_dict={}, config=overrides)
    assert edges["E03_UP"].closed is True


def test_apply_overrides_patches_dump_points():
    dumps = load_dump_points(DATA_DIR / "dump_points.csv")
    overrides = {"dump_point_overrides": {"D_CRUSH": {"mean_dump_time_min": 7.0, "sd_dump_time_min": 1.5}}}
    apply_overrides(edges_dict={}, nodes_dict={}, dumps_dict=dumps, config=overrides)
    assert dumps["D_CRUSH"].mean_dump_time_min == pytest.approx(7.0)
    assert dumps["D_CRUSH"].sd_dump_time_min == pytest.approx(1.5)


def test_build_graph_excludes_closed_edges():
    nodes = load_nodes(DATA_DIR / "nodes.csv")
    edges = load_edges(DATA_DIR / "edges.csv")
    edges["E03_UP"].closed = True
    edges["E03_DOWN"].closed = True
    g = build_graph(nodes, edges)
    assert not g.has_edge("J2", "J3")
    assert not g.has_edge("J3", "J2")
    assert g.has_edge("J1", "J2")


def test_build_graph_assigns_travel_time_weight():
    nodes = load_nodes(DATA_DIR / "nodes.csv")
    edges = load_edges(DATA_DIR / "edges.csv")
    g = build_graph(nodes, edges)
    weight = g["J2"]["J3"]["travel_time_min"]
    assert weight == pytest.approx(950 / 1000 / 18 * 60, rel=1e-6)


def test_compute_shortest_paths_baseline_endpoints_correct():
    """Routes are valid and start/end at the right nodes; paths to LOAD_S
    go via the ramp (J3) since that's faster than the bypass for LOAD_S,
    while LOAD_N is closer via the bypass than via the ramp under baseline."""
    nodes = load_nodes(DATA_DIR / "nodes.csv")
    edges = load_edges(DATA_DIR / "edges.csv")
    g = build_graph(nodes, edges)
    paths = compute_shortest_paths(g)
    park_to_load_n = paths["PARK"]["LOAD_N"]
    park_to_load_s = paths["PARK"]["LOAD_S"]
    assert park_to_load_n[0] == "PARK"
    assert park_to_load_n[-1] == "LOAD_N"
    assert park_to_load_s[0] == "PARK"
    assert park_to_load_s[-1] == "LOAD_S"
    # LOAD_S is best reached via the ramp under baseline
    assert "J3" in park_to_load_s


def test_compute_shortest_paths_with_ramp_closed_uses_bypass():
    nodes = load_nodes(DATA_DIR / "nodes.csv")
    edges = load_edges(DATA_DIR / "edges.csv")
    edges["E03_UP"].closed = True
    edges["E03_DOWN"].closed = True
    g = build_graph(nodes, edges)
    paths = compute_shortest_paths(g)
    park_to_crush = paths["PARK"]["CRUSH"]
    assert "J7" in park_to_crush or "J8" in park_to_crush
    assert "J3" not in park_to_crush


def test_compute_shortest_paths_unreachable_raises():
    nodes = load_nodes(DATA_DIR / "nodes.csv")
    edges = load_edges(DATA_DIR / "edges.csv")
    for eid, edge in edges.items():
        if edge.to_node == "LOAD_N":
            edge.closed = True
    g = build_graph(nodes, edges)
    with pytest.raises(Exception) as exc_info:
        compute_shortest_paths(g, required_pairs=[("PARK", "LOAD_N")])
    assert "LOAD_N" in str(exc_info.value)
