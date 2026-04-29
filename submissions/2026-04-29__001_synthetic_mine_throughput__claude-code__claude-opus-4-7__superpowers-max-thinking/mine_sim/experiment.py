"""Replication driver: seeds, scenarios, aggregation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import simpy

from mine_sim.metrics import MetricsCollector
from mine_sim.resources import build_resources
from mine_sim.scenario import load_scenario  # re-exported for callers
from mine_sim.topology import (
    apply_overrides,
    build_graph,
    compute_shortest_paths,
    load_dump_points,
    load_edges,
    load_loaders,
    load_nodes,
    load_trucks,
)
from mine_sim.truck import Simulation, TruckProcess


def _select_trucks(all_trucks: dict[str, Any], truck_count: int) -> list[Any]:
    """Take the first `truck_count` trucks in id-sorted order."""
    if truck_count > len(all_trucks):
        raise ValueError(
            f"Scenario asks for {truck_count} trucks but trucks.csv has {len(all_trucks)}."
        )
    ordered = sorted(all_trucks.values(), key=lambda t: t.truck_id)
    return ordered[:truck_count]


def run_replication(
    config: dict[str, Any],
    replication_idx: int,
    data_dir: Path,
) -> MetricsCollector:
    """Run a single replication and return the populated MetricsCollector."""
    base_seed = int(config["simulation"]["base_random_seed"])
    seed = base_seed + replication_idx
    rng = np.random.default_rng(seed)

    shift_minutes = float(config["simulation"]["shift_length_hours"]) * 60.0

    # Fresh data per replication so apply_overrides (mutating) is contained.
    nodes = load_nodes(data_dir / "nodes.csv")
    edges = load_edges(data_dir / "edges.csv")
    loaders = load_loaders(data_dir / "loaders.csv")
    dumps = load_dump_points(data_dir / "dump_points.csv")
    apply_overrides(edges_dict=edges, nodes_dict=nodes, dumps_dict=dumps, config=config)

    g = build_graph(nodes, edges)

    # Reachability validation: every (PARK, loader_node), (loader_node, CRUSH),
    # (CRUSH, loader_node) pair must exist on the graph after overrides.
    crusher_dump = next(d for d in dumps.values() if d.type == "crusher")
    crusher_node = crusher_dump.node_id
    parking_node = "PARK"
    required_pairs: list[tuple[str, str]] = []
    for loader in loaders.values():
        required_pairs.append((parking_node, loader.node_id))
        required_pairs.append((loader.node_id, crusher_node))
        required_pairs.append((crusher_node, loader.node_id))
    paths = compute_shortest_paths(g, required_pairs=required_pairs)

    env = simpy.Environment()
    pool = build_resources(env, config, edges=edges, loaders=loaders, dumps=dumps)

    collector = MetricsCollector(
        scenario_id=str(config["scenario_id"]),
        replication=replication_idx,
        shift_minutes=shift_minutes,
        seed=seed,
    )
    sim = Simulation(
        env=env, config=config, graph=g, edges=edges, nodes=nodes,
        pool=pool, rng=rng, collector=collector, shortest_paths=paths,
    )

    all_trucks = load_trucks(data_dir / "trucks.csv")
    selected = _select_trucks(all_trucks, int(config["fleet"]["truck_count"]))
    for tr in selected:
        TruckProcess(
            sim,
            truck_id=tr.truck_id,
            payload_tonnes=tr.payload_tonnes,
            empty_speed_factor=tr.empty_speed_factor,
            loaded_speed_factor=tr.loaded_speed_factor,
            start_node=tr.start_node,
        ).start()

    env.run(until=shift_minutes)
    return collector


@dataclass
class ScenarioResult:
    scenario_id: str
    config: dict[str, Any]
    replications: list[MetricsCollector]


def run_scenario(config: dict[str, Any], data_dir: Path) -> ScenarioResult:
    """Run N replications as specified in config and return aggregated result."""
    n = int(config["simulation"]["replications"])
    reps = [run_replication(config, i, data_dir) for i in range(n)]
    return ScenarioResult(
        scenario_id=str(config["scenario_id"]),
        config=config,
        replications=reps,
    )
