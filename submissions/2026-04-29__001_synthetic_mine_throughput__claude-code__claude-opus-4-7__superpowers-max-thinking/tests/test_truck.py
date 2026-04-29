"""Tests for truck dispatcher and one-cycle smoke test."""
import numpy as np
import simpy

from mine_sim.metrics import MetricsCollector
from mine_sim.resources import build_resources
from mine_sim.scenario import load_scenario
from mine_sim.topology import (
    apply_overrides,
    build_graph,
    compute_shortest_paths,
    load_dump_points,
    load_edges,
    load_loaders,
    load_nodes,
)
from mine_sim.truck import (
    Simulation,
    TruckProcess,
    choose_loader,
    draw_truncated_normal,
)


def _build_sim(data_dir, scenarios_dir, scenario_id, seed=42):
    cfg = load_scenario(scenario_id, scenarios_dir)
    nodes = load_nodes(data_dir / "nodes.csv")
    edges = load_edges(data_dir / "edges.csv")
    loaders = load_loaders(data_dir / "loaders.csv")
    dumps = load_dump_points(data_dir / "dump_points.csv")
    apply_overrides(edges_dict=edges, nodes_dict=nodes, dumps_dict=dumps, config=cfg)
    g = build_graph(nodes, edges)
    paths = compute_shortest_paths(g)
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    rng = np.random.default_rng(seed)
    collector = MetricsCollector(scenario_id=scenario_id, replication=0, shift_minutes=480.0, seed=seed)
    sim = Simulation(env=env, config=cfg, graph=g, edges=edges, nodes=nodes,
                     pool=pool, rng=rng, collector=collector, shortest_paths=paths)
    return sim


def test_draw_truncated_normal_floor_clipped():
    rng = np.random.default_rng(0)
    draws = [draw_truncated_normal(rng, mean=1.0, sd=10.0) for _ in range(1000)]
    assert min(draws) >= 0.1
    assert max(draws) <= 1.0 + 5 * 10.0


def test_draw_truncated_normal_reproducible():
    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)
    draws_a = [draw_truncated_normal(rng_a, 5.0, 1.0) for _ in range(50)]
    draws_b = [draw_truncated_normal(rng_b, 5.0, 1.0) for _ in range(50)]
    assert draws_a == draws_b


def test_draw_truncated_normal_sd_zero():
    rng = np.random.default_rng(0)
    assert draw_truncated_normal(rng, mean=5.0, sd=0.0) == 5.0


def test_choose_loader_returns_known_loader(data_dir, scenarios_dir):
    sim = _build_sim(data_dir, scenarios_dir, "baseline")
    chosen = choose_loader(current_node="PARK", sim=sim)
    assert chosen in {"L_N", "L_S"}


def test_one_truck_completes_at_least_one_cycle(data_dir, scenarios_dir):
    sim = _build_sim(data_dir, scenarios_dir, "baseline")
    TruckProcess(sim, truck_id="T01", payload_tonnes=100.0,
                 empty_speed_factor=1.0, loaded_speed_factor=0.85,
                 start_node="PARK").start()
    sim.env.run(until=480)
    assert sim.collector.total_tonnes() > 0
    dumps = [e for e in sim.collector.event_log_rows()
             if e["event_type"] == "dumping_ended" and e["location"] == "CRUSH"]
    assert len(dumps) >= 1


def test_ramp_closed_truck_uses_bypass(data_dir, scenarios_dir):
    sim = _build_sim(data_dir, scenarios_dir, "ramp_closed")
    TruckProcess(sim, truck_id="T01", payload_tonnes=100.0,
                 empty_speed_factor=1.0, loaded_speed_factor=0.85,
                 start_node="PARK").start()
    sim.env.run(until=480)
    log = sim.collector.event_log_rows()
    traversed = {(e["from_node"], e["to_node"])
                 for e in log if e["event_type"] == "traversal_started"}
    bypass_edges = {("J2", "J7"), ("J7", "J8"), ("J8", "J4")}
    assert traversed & bypass_edges
    assert ("J2", "J3") not in traversed
    assert ("J3", "J2") not in traversed
