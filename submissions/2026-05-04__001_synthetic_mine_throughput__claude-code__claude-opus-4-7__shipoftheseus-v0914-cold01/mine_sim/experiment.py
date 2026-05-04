"""Single replication driver and multi-scenario orchestrator."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import simpy

from .entities import TruckMetrics, truck_process
from .event_log import EventRecorder
from .resources import build_resource_pool
from .topology import Topology


def _resolve_paths(topology: Topology, g, scenario_cfg: dict, loaders_df: pd.DataFrame,
                    trucks_df: pd.DataFrame) -> Tuple[Dict[Tuple[str, str], list],
                                                     Dict[Tuple[str, str], list]]:
    """Pre-compute shortest paths used by trucks (start/CRUSH ↔ each loader)."""
    loader_nodes = list(loaders_df["node_id"].unique())
    sources = sorted(set(list(trucks_df["start_node"].unique()) + ["CRUSH"]))
    loader_paths: Dict[Tuple[str, str], list] = {}
    for s in sources:
        for ln in loader_nodes:
            loader_paths[(s, ln)] = topology.shortest_path(g, s, ln)
    crusher_paths: Dict[Tuple[str, str], list] = {}
    for ln in loader_nodes:
        crusher_paths[(ln, "CRUSH")] = topology.shortest_path(g, ln, "CRUSH")
    return loader_paths, crusher_paths


def run_replication(scenario_cfg: dict,
                    nodes_df: pd.DataFrame,
                    edges_df: pd.DataFrame,
                    trucks_df: pd.DataFrame,
                    loaders_df: pd.DataFrame,
                    dump_df: pd.DataFrame,
                    base_seed: int,
                    scenario_idx: int,
                    replication_idx: int) -> Tuple[Dict, List[tuple]]:
    """Run a single replication and return (metrics_row, event_rows)."""
    seed = base_seed + 1000 * scenario_idx + replication_idx
    rng = np.random.default_rng(seed)

    shift_hours = float(scenario_cfg.get("simulation", {}).get("shift_length_hours", 8))
    shift_end_min = shift_hours * 60.0

    fleet_count = int(scenario_cfg.get("fleet", {}).get("truck_count", len(trucks_df)))
    truck_subset = trucks_df.head(fleet_count).copy()

    topology = Topology(nodes_df, edges_df)
    edge_overrides = scenario_cfg.get("edge_overrides", {}) or {}
    g, applied_edges_df = topology.graph_for_scenario(edge_overrides)

    env = simpy.Environment()
    res = build_resource_pool(env, loaders_df, dump_df, applied_edges_df, scenario_cfg)

    loader_paths, crusher_paths = _resolve_paths(topology, g, scenario_cfg, loaders_df,
                                                  truck_subset)

    recorder = EventRecorder(scenario_id=scenario_cfg["scenario_id"],
                              replication=replication_idx)

    truck_metrics: List[TruckMetrics] = []
    for _, t in truck_subset.iterrows():
        tm = TruckMetrics(truck_id=t["truck_id"])
        truck_metrics.append(tm)
        env.process(truck_process(env, t["truck_id"], float(t["payload_tonnes"]),
                                   float(t["empty_speed_factor"]),
                                   float(t["loaded_speed_factor"]),
                                   t["start_node"],
                                   topology, g, loader_paths, crusher_paths,
                                   res, scenario_cfg, shift_end_min, recorder, rng, tm))

    # Run until shift_end + 30 minutes drain (let in-flight trucks finish if they can)
    env.run(until=shift_end_min + 30.0)

    # Aggregate metrics
    total_tonnes = sum(tm.tonnes_delivered for tm in truck_metrics)
    total_cycles = sum(tm.cycles_completed for tm in truck_metrics)
    cycle_times = [c for tm in truck_metrics for c in tm.cycle_times_min]
    avg_cycle = float(np.mean(cycle_times)) if cycle_times else 0.0

    truck_busy = [min(tm.busy_time_min / shift_end_min, 1.0) for tm in truck_metrics]
    avg_truck_util = float(np.mean(truck_busy)) if truck_busy else 0.0

    crusher_util = min(res.crusher_busy_time / shift_end_min, 1.0)

    loader_util = {lid: min(t / shift_end_min, 1.0) for lid, t in res.loader_busy_time.items()}

    avg_loader_q = float(np.mean([tm.loader_queue_time_min for tm in truck_metrics])) if truck_metrics else 0.0
    avg_crusher_q = float(np.mean([tm.crusher_queue_time_min for tm in truck_metrics])) if truck_metrics else 0.0

    row = {
        "scenario_id": scenario_cfg["scenario_id"],
        "replication": replication_idx,
        "random_seed": seed,
        "fleet_size": fleet_count,
        "total_tonnes_delivered": total_tonnes,
        "tonnes_per_hour": total_tonnes / shift_hours,
        "average_truck_cycle_time_min": avg_cycle,
        "average_truck_utilisation": avg_truck_util,
        "crusher_utilisation": crusher_util,
        "loader_utilisation_L_N": loader_util.get("L_N", 0.0),
        "loader_utilisation_L_S": loader_util.get("L_S", 0.0),
        "average_loader_queue_time_min": avg_loader_q,
        "average_crusher_queue_time_min": avg_crusher_q,
        "total_cycles_completed": total_cycles,
    }
    return row, recorder.rows
