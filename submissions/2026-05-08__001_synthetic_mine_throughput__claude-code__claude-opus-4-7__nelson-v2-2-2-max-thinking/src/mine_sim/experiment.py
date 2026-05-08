"""Multi-replication experiment runner: orchestrates scenarios, summarises results."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import pandas as pd

from .data import StaticData, load_static_data
from .scenarios import ScenarioConfig, list_required_scenarios, load_scenario
from .simulation import ReplicationResult, run_replication
from .stats import mean_ci, mean_or_zero, utilisation
from .topology import ScenarioTopology, build_scenario_topology


@dataclass
class ScenarioSummary:
    scenario_id: str
    description: str
    replications: int
    shift_length_hours: float
    truck_count: int
    total_tonnes_mean: float
    total_tonnes_ci95_low: float
    total_tonnes_ci95_high: float
    tonnes_per_hour_mean: float
    tonnes_per_hour_ci95_low: float
    tonnes_per_hour_ci95_high: float
    average_cycle_time_min: float
    truck_utilisation_mean: float
    loader_utilisation: Dict[str, float]
    crusher_utilisation: float
    average_loader_queue_time_min: float
    average_crusher_queue_time_min: float
    top_bottlenecks: List[Dict[str, Any]] = field(default_factory=list)


def _per_rep_metrics(rep: ReplicationResult, scenario: ScenarioConfig) -> Dict[str, Any]:
    """Distill a ReplicationResult to the columns we want in results.csv."""
    shift_min = scenario.shift_length_minutes
    shift_h = scenario.shift_length_hours

    # Truck-level aggregates.
    n_trucks = max(1, len(rep.truck_stats))
    truck_productive_total = sum(ts.productive_min for ts in rep.truck_stats.values())
    truck_loader_q = sum(ts.loader_queue_min for ts in rep.truck_stats.values())
    truck_crusher_q = sum(ts.crusher_queue_min for ts in rep.truck_stats.values())
    truck_edge_q = sum(ts.edge_queue_min for ts in rep.truck_stats.values())
    cycle_times: List[float] = []
    for ts in rep.truck_stats.values():
        cycle_times.extend(ts.cycle_times)
    avg_cycle = mean_or_zero(cycle_times) if cycle_times else 0.0
    avg_truck_util = (truck_productive_total / n_trucks) / shift_min if shift_min > 0 else 0.0

    # Resource utilisation.
    loader_utils: Dict[str, float] = {}
    crusher_util = 0.0
    crusher_queue_per_truck = (truck_crusher_q / max(1, sum(ts.cycles_completed for ts in rep.truck_stats.values()))) if any(ts.cycles_completed for ts in rep.truck_stats.values()) else 0.0
    loader_queue_per_truck = (truck_loader_q / max(1, sum(ts.cycles_completed for ts in rep.truck_stats.values()))) if any(ts.cycles_completed for ts in rep.truck_stats.values()) else 0.0
    edge_metrics: List[Dict[str, Any]] = []

    for key, rs in rep.resource_stats.items():
        u = utilisation(rs.busy_intervals, shift_min)
        if rs.kind == "loader":
            loader_utils[rs.resource_id] = u
        elif rs.kind == "crusher":
            crusher_util = u
        elif rs.kind == "edge":
            mean_q = mean_or_zero(rs.queue_waits)
            edge_metrics.append({
                "resource_id": rs.resource_id,
                "utilisation": u,
                "mean_queue_wait_min": mean_q,
                "n_traversals": len(rs.queue_waits),
            })

    return {
        "scenario_id": scenario.scenario_id,
        "replication": rep.replication,
        "random_seed": rep.random_seed,
        "total_tonnes_delivered": rep.total_tonnes,
        "tonnes_per_hour": rep.tonnes_per_hour,
        "average_truck_cycle_time_min": avg_cycle,
        "average_truck_utilisation": avg_truck_util,
        "crusher_utilisation": crusher_util,
        "average_loader_queue_time_min": loader_queue_per_truck,
        "average_crusher_queue_time_min": crusher_queue_per_truck,
        "average_edge_queue_time_min_per_truck": (truck_edge_q / max(1, sum(ts.cycles_completed for ts in rep.truck_stats.values()))) if any(ts.cycles_completed for ts in rep.truck_stats.values()) else 0.0,
        **{f"loader_util[{lid}]": u for lid, u in loader_utils.items()},
        "edge_metrics_json": json.dumps(edge_metrics),
    }


def _bottlenecks(rep_summaries: List[Dict[str, Any]], reps: List[ReplicationResult], top_n: int = 5) -> List[Dict[str, Any]]:
    """Composite bottleneck rank: utilisation × mean_queue_wait_min, averaged across reps.

    Considers loaders, the crusher, and capacity-1 edges.
    """
    # Aggregate per resource_id, kind: collect util and mean_queue_wait per rep.
    by_key: Dict[str, Dict[str, Any]] = {}
    if not reps:
        return []
    shift_min = reps[0].shift_length_min
    for rep in reps:
        for key, rs in rep.resource_stats.items():
            u = utilisation(rs.busy_intervals, shift_min)
            mq = mean_or_zero(rs.queue_waits)
            entry = by_key.setdefault(key, {"resource_id": rs.resource_id, "kind": rs.kind, "utilisations": [], "queue_waits": []})
            entry["utilisations"].append(u)
            entry["queue_waits"].append(mq)
    ranked: List[Dict[str, Any]] = []
    for key, entry in by_key.items():
        avg_u = mean_or_zero(entry["utilisations"])
        avg_q = mean_or_zero(entry["queue_waits"])
        score = avg_u * avg_q
        ranked.append({
            "resource_key": key,
            "resource_id": entry["resource_id"],
            "kind": entry["kind"],
            "utilisation_mean": avg_u,
            "mean_queue_wait_min": avg_q,
            "composite_score": score,
        })
    ranked.sort(key=lambda d: d["composite_score"], reverse=True)
    return ranked[:top_n]


def _summarise_scenario(
    scenario: ScenarioConfig, reps: List[ReplicationResult], rows: List[Dict[str, Any]]
) -> ScenarioSummary:
    tonnes = [r.total_tonnes for r in reps]
    tph = [r.tonnes_per_hour for r in reps]
    cycle_times: List[float] = []
    truck_utils: List[float] = []
    crusher_utils: List[float] = []
    loader_q: List[float] = []
    crusher_q: List[float] = []
    loader_utils_per_id: Dict[str, List[float]] = {}
    for row in rows:
        cycle_times.append(row["average_truck_cycle_time_min"])
        truck_utils.append(row["average_truck_utilisation"])
        crusher_utils.append(row["crusher_utilisation"])
        loader_q.append(row["average_loader_queue_time_min"])
        crusher_q.append(row["average_crusher_queue_time_min"])
        for k, v in row.items():
            if k.startswith("loader_util["):
                lid = k[len("loader_util["):-1]
                loader_utils_per_id.setdefault(lid, []).append(v)

    tonnes_mean, tonnes_lo, tonnes_hi = mean_ci(tonnes)
    tph_mean, tph_lo, tph_hi = mean_ci(tph)

    summary = ScenarioSummary(
        scenario_id=scenario.scenario_id,
        description=scenario.description,
        replications=len(reps),
        shift_length_hours=scenario.shift_length_hours,
        truck_count=scenario.truck_count,
        total_tonnes_mean=tonnes_mean,
        total_tonnes_ci95_low=tonnes_lo,
        total_tonnes_ci95_high=tonnes_hi,
        tonnes_per_hour_mean=tph_mean,
        tonnes_per_hour_ci95_low=tph_lo,
        tonnes_per_hour_ci95_high=tph_hi,
        average_cycle_time_min=mean_or_zero(cycle_times),
        truck_utilisation_mean=mean_or_zero(truck_utils),
        loader_utilisation={lid: mean_or_zero(vs) for lid, vs in loader_utils_per_id.items()},
        crusher_utilisation=mean_or_zero(crusher_utils),
        average_loader_queue_time_min=mean_or_zero(loader_q),
        average_crusher_queue_time_min=mean_or_zero(crusher_q),
        top_bottlenecks=_bottlenecks([], reps),
    )
    return summary


def run_scenario(
    static: StaticData,
    scenario: ScenarioConfig,
    *,
    progress: Optional[callable] = None,
) -> tuple[List[Dict[str, Any]], List[ReplicationResult], ScenarioSummary, ScenarioTopology]:
    """Run all replications for a scenario and aggregate results."""
    topology = build_scenario_topology(static, scenario)
    rows: List[Dict[str, Any]] = []
    reps: List[ReplicationResult] = []
    for r_idx in range(scenario.replications):
        rep = run_replication(static=static, scenario=scenario, topology=topology, rep_idx=r_idx)
        reps.append(rep)
        rows.append(_per_rep_metrics(rep, scenario))
        if progress is not None:
            progress(scenario.scenario_id, r_idx + 1, scenario.replications)
    summary = _summarise_scenario(scenario, reps, rows)
    return rows, reps, summary, topology


def run_experiment(
    *,
    data_dir: Path,
    output_dir: Path,
    scenario_ids: Optional[List[str]] = None,
    event_log_reps: Optional[int] = None,
    save_first_rep_events_per_scenario: bool = True,
    progress: Optional[callable] = None,
) -> Dict[str, Any]:
    """Run the full experiment, write all artefacts, return the summary dict."""
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    static = load_static_data(data_dir)
    scenarios = scenario_ids or list_required_scenarios()

    all_rows: List[Dict[str, Any]] = []
    all_summaries: Dict[str, ScenarioSummary] = {}
    all_event_rows: List[Dict[str, Any]] = []
    cached_topologies: Dict[str, ScenarioTopology] = {}

    for sid in scenarios:
        scenario = load_scenario(data_dir / "scenarios", sid)
        rows, reps, summary, topology = run_scenario(static, scenario, progress=progress)
        all_rows.extend(rows)
        all_summaries[sid] = summary
        cached_topologies[sid] = topology
        # Decide which reps to log: by default, log first 3 reps per scenario
        # to keep event_log.csv compact. Use a larger window if event_log_reps is set.
        keep_reps = event_log_reps if event_log_reps is not None else 3
        for rep in reps[:keep_reps]:
            all_event_rows.extend(rep.events)

    # Write results.csv.
    results_df = pd.DataFrame(all_rows)
    # Ensure consistent column ordering — base required columns first.
    base_cols = [
        "scenario_id", "replication", "random_seed",
        "total_tonnes_delivered", "tonnes_per_hour",
        "average_truck_cycle_time_min", "average_truck_utilisation",
        "crusher_utilisation", "average_loader_queue_time_min",
        "average_crusher_queue_time_min", "average_edge_queue_time_min_per_truck",
    ]
    extra_cols = [c for c in results_df.columns if c not in base_cols]
    results_df = results_df[base_cols + extra_cols]
    results_df.to_csv(output_dir / "results.csv", index=False)

    # Write event_log.csv.
    event_df = pd.DataFrame(all_event_rows)
    if not event_df.empty:
        event_df = event_df[
            ["time_min", "replication", "scenario_id", "truck_id", "event_type",
             "from_node", "to_node", "location", "loaded", "payload_tonnes",
             "resource_id", "queue_length"]
        ]
    event_df.to_csv(output_dir / "event_log.csv", index=False)

    # Build summary.json.
    summary_json: Dict[str, Any] = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {sid: asdict(s) for sid, s in all_summaries.items()},
        "key_assumptions": [
            "Hard shift cut at 480 minutes (8h); dumps completing after the cut do not count.",
            "Lognormal travel-time noise (cv=0.10) applied to free-flow edge times.",
            "Normal-truncated load and dump samples; floor max(0.1, sample).",
            "One SimPy Resource per directed capacity-1 edge (mirrors CSV).",
            "Static shortest-time Dijkstra routing per scenario; recomputed under closures.",
            "Dispatch rule: minimise (travel_empty + queue_len * mean_load + own_load).",
            "All trucks dispatched simultaneously at t=0 from PARK.",
            "Per-replication seed = base_random_seed + replication_index.",
            "WASTE and MAINTENANCE excluded from haulage routing.",
            "Truck utilisation = productive minutes (load + dump + travel) / shift; queue waits excluded.",
        ],
        "model_limitations": [
            "Static routing — does not adapt to live congestion; may under-use alternate routes when the chosen path queues up.",
            "Trucks do not refuel / break down (availability=1.0 across the data; no maintenance shifts modelled).",
            "Crusher buffer / stockpile not modelled; backed-up trucks queue at the crusher rather than emptying into a hopper.",
            "Capacity-1 edges in opposite directions modelled as independent resources (per CSV) — not a single bidirectional lane.",
            "Initial all-trucks-at-PARK simultaneous dispatch produces synchronous LOAD_S surge in the first cycle (per design).",
            "Event log retains the first 3 replications per scenario to keep file size manageable.",
        ],
        "additional_scenarios_proposed": [
            {
                "scenario_id": "trucks_12_ramp_upgrade",
                "rationale": "Pairs the largest fleet with the ramp upgrade to test whether the upgrade releases value only when trucks are abundant — disambiguating crusher-bound vs route-bound saturation."
            }
        ],
    }
    with open(output_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary_json, fh, indent=2, default=float)

    return summary_json
