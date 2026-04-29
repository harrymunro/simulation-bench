"""Tests for the SimPy resource pool."""
import simpy

from mine_sim.resources import build_resources
from mine_sim.scenario import load_scenario
from mine_sim.topology import (
    apply_overrides,
    load_dump_points,
    load_edges,
    load_loaders,
    load_nodes,
)


def _load_all(data_dir, scenarios_dir, scenario_id):
    cfg = load_scenario(scenario_id, scenarios_dir)
    nodes = load_nodes(data_dir / "nodes.csv")
    edges = load_edges(data_dir / "edges.csv")
    loaders = load_loaders(data_dir / "loaders.csv")
    dumps = load_dump_points(data_dir / "dump_points.csv")
    apply_overrides(edges_dict=edges, nodes_dict=nodes, dumps_dict=dumps, config=cfg)
    return cfg, nodes, edges, loaders, dumps


def test_build_resources_baseline_creates_all_locks(data_dir, scenarios_dir):
    cfg, nodes, edges, loaders, dumps = _load_all(data_dir, scenarios_dir, "baseline")
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    assert "RAMP" in pool.road_locks
    assert "PIT_N" in pool.road_locks
    assert "PIT_S" in pool.road_locks
    assert "E05_TO" in pool.road_locks
    assert "E05_FROM" in pool.road_locks
    assert set(pool.loaders.keys()) == {"L_N", "L_S"}
    assert pool.crusher.capacity == 1


def test_build_resources_ramp_upgrade_skips_ramp_lock(data_dir, scenarios_dir):
    cfg, nodes, edges, loaders, dumps = _load_all(data_dir, scenarios_dir, "ramp_upgrade")
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    assert "RAMP" not in pool.road_locks
    assert "PIT_N" in pool.road_locks
    assert "PIT_S" in pool.road_locks


def test_build_resources_ramp_closed_drops_ramp_lock(data_dir, scenarios_dir):
    """When edges are closed, the lock factory should not create a lock for them."""
    cfg, nodes, edges, loaders, dumps = _load_all(data_dir, scenarios_dir, "ramp_closed")
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    assert "RAMP" not in pool.road_locks


def test_build_resources_loader_service_times(data_dir, scenarios_dir):
    cfg, nodes, edges, loaders, dumps = _load_all(data_dir, scenarios_dir, "baseline")
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    assert pool.loader_service[("L_N", "mean")] == 6.5
    assert pool.loader_service[("L_N", "sd")] == 1.2
    assert pool.loader_service[("L_S", "mean")] == 4.5
    assert pool.loader_node["L_N"] == "LOAD_N"
    assert pool.loader_node["L_S"] == "LOAD_S"
    assert pool.bucket_capacity_tonnes["L_N"] == 100.0


def test_build_resources_crusher_slowdown_override(data_dir, scenarios_dir):
    cfg, nodes, edges, loaders, dumps = _load_all(data_dir, scenarios_dir, "crusher_slowdown")
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    assert pool.crusher_service["mean"] == 7.0
    assert pool.crusher_service["sd"] == 1.5
    assert pool.crusher_node == "CRUSH"


def test_paired_lock_blocks_opposing_direction(data_dir, scenarios_dir):
    """A truck holding RAMP via E03_UP must block another truck wanting E03_DOWN."""
    cfg, nodes, edges, loaders, dumps = _load_all(data_dir, scenarios_dir, "baseline")
    env = simpy.Environment()
    pool = build_resources(env, cfg, edges=edges, loaders=loaders, dumps=dumps)
    ramp = pool.road_locks["RAMP"]

    log: list[tuple[str, float]] = []

    def truck_a():
        with ramp.request() as req:
            yield req
            log.append(("A_acquired", env.now))
            yield env.timeout(5.0)
            log.append(("A_released", env.now))

    def truck_b():
        yield env.timeout(0.1)
        with ramp.request() as req:
            log.append(("B_requested", env.now))
            yield req
            log.append(("B_acquired", env.now))

    env.process(truck_a())
    env.process(truck_b())
    env.run(until=20)
    events = dict(log)
    assert events["B_acquired"] >= events["A_released"]
