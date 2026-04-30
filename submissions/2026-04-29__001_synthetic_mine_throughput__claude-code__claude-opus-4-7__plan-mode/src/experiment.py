"""Replication driver and scenario sweep.

Wires the static :mod:`model` data + scenario config into one :class:`MineSim`
per replication, collects per-rep metrics, and concatenates event logs.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import simpy

from .model import (
    InputData,
    apply_dump_point_overrides,
    apply_edge_overrides,
    build_graph,
    load_inputs,
    load_scenario,
)
from .simulation import MineSim, aggregate_truck_metrics


@dataclass
class ScenarioConfig:
    """Resolved scenario config + the input slices it applies to."""
    scenario_id: str
    cfg: dict[str, Any]
    edges: pd.DataFrame
    trucks: pd.DataFrame
    dump_points: pd.DataFrame


def _scenario_seed(base_seed: int, scenario_id: str, replication: int) -> int:
    """Derive a deterministic 64-bit seed from base seed + scenario + rep."""
    h = hashlib.sha256(f"{base_seed}::{scenario_id}::{replication}".encode()).digest()
    return int.from_bytes(h[:8], "big", signed=False)


def resolve_scenario(scenarios_dir: Path, scenario_id: str,
                     inputs: InputData) -> ScenarioConfig:
    """Apply scenario overrides to the inputs and return a ready-to-run config."""
    cfg = load_scenario(scenarios_dir, scenario_id)

    edges = apply_edge_overrides(inputs.edges, cfg.get("edge_overrides"))
    dump_points = apply_dump_point_overrides(inputs.dump_points, cfg.get("dump_point_overrides"))

    truck_count = int(cfg.get("fleet", {}).get("truck_count", len(inputs.trucks)))
    trucks = inputs.trucks.head(truck_count).reset_index(drop=True)
    if len(trucks) < truck_count:
        raise ValueError(
            f"Scenario {scenario_id} needs {truck_count} trucks but only "
            f"{len(trucks)} are defined in trucks.csv"
        )

    return ScenarioConfig(scenario_id=scenario_id, cfg=cfg, edges=edges,
                          trucks=trucks, dump_points=dump_points)


def run_replication(scenario: ScenarioConfig, replication: int,
                    inputs: InputData,
                    base_seed: int) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Run a single replication; return (metrics_dict, event_rows)."""
    seed = _scenario_seed(base_seed, scenario.scenario_id, replication)
    rng = np.random.default_rng(seed)

    graph = build_graph(scenario.edges)
    env = simpy.Environment()
    sim = MineSim(
        env=env,
        scenario_cfg=scenario.cfg,
        graph=graph,
        trucks_df=scenario.trucks,
        loaders_df=inputs.loaders,
        dump_points_df=scenario.dump_points,
        edges_df=scenario.edges,
        rng=rng,
        scenario_id=scenario.scenario_id,
        replication=replication,
    )
    sim.run()

    metrics = aggregate_truck_metrics(sim)
    metrics["scenario_id"] = scenario.scenario_id
    metrics["replication"] = replication
    metrics["random_seed"] = seed
    metrics["truck_count"] = len(scenario.trucks)
    metrics["shift_length_hours"] = float(scenario.cfg["simulation"]["shift_length_hours"])

    # Collect per-resource queue stats for bottleneck analysis later.
    metrics["per_resource_queue_stats"] = {
        "loaders": {
            lid: {
                "mean_queue_wait_min": s.mean_queue_wait(),
                "queue_events": s.queue_wait_count,
                "busy_time_min": s.busy_time,
            }
            for lid, s in sim.loader_stats.items()
        },
        "crusher": {
            "mean_queue_wait_min": sim.crusher_stats.mean_queue_wait(),
            "queue_events": sim.crusher_stats.queue_wait_count,
            "busy_time_min": sim.crusher_stats.busy_time,
        },
        "edges": {
            eid: {
                "mean_queue_wait_min": s.mean_queue_wait(),
                "queue_events": s.queue_wait_count,
                "busy_time_min": s.busy_time,
            }
            for eid, s in sim.edge_stats.items()
        },
    }

    return metrics, sim.event_log


def run_scenario(scenarios_dir: Path, scenario_id: str,
                 inputs: InputData,
                 replications: int | None = None,
                 base_seed: int | None = None) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Run all replications for one scenario.

    Returns a per-rep dataframe plus the concatenated event log rows.
    """
    scenario = resolve_scenario(scenarios_dir, scenario_id, inputs)
    n = int(replications if replications is not None
            else scenario.cfg["simulation"]["replications"])
    seed = int(base_seed if base_seed is not None
               else scenario.cfg["simulation"]["base_random_seed"])

    rows: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    for r in range(n):
        metrics, ev = run_replication(scenario, r, inputs, seed)
        rows.append(metrics)
        events.extend(ev)
    return pd.DataFrame(rows), events


def run_all(data_dir: Path, scenario_ids: list[str],
            replications: int | None = None,
            base_seed: int | None = None,
            progress: bool = True) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    """Run every scenario in ``scenario_ids`` sequentially."""
    inputs = load_inputs(data_dir)
    scenarios_dir = Path(data_dir) / "scenarios"

    all_rows: list[pd.DataFrame] = []
    all_events: list[dict[str, Any]] = []
    for sid in scenario_ids:
        if progress:
            print(f"  ... running scenario {sid}", flush=True)
        df, events = run_scenario(scenarios_dir, sid, inputs,
                                  replications=replications, base_seed=base_seed)
        all_rows.append(df)
        all_events.extend(events)
    return pd.concat(all_rows, ignore_index=True), all_events
