"""Output writers: results.csv, summary.json, event_log.csv."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from mine_sim.experiment import ScenarioResult
from mine_sim.metrics import MetricsCollector, ci95_t


KEY_ASSUMPTIONS = [
    "Capacity-1 ramp E03 and pit-access roads E07/E09 are modelled as paired bidirectional resources (one truck on the physical road regardless of direction). Crusher approach E05 keeps per-direction locks.",
    "Loading and dumping times follow Normal(mean, sd) truncated to [0.1 min, mean + 5 sd].",
    "Travel-time noise is multiplicative Normal(1.0, cv=0.10) per truck per edge per traversal, with effective speed floored at 10% of edge max_speed_kph.",
    "Routing uses pre-computed travel-time-weighted shortest paths (NetworkX Dijkstra). Loader choice is dynamic via nearest_available_loader with shortest_expected_cycle_time tiebreaker.",
    "Throughput is attributed at dumping_ended events at the crusher only; in-progress dumps at shift end are not counted.",
    "All trucks start at PARK at t=0 and are dispatched simultaneously.",
]

MODEL_LIMITATIONS = [
    "No truck breakdowns, refuelling, shift handover, or operator skill variation are modelled.",
    "No weather, blasting, or grade-resistance effects on travel speed beyond the loaded/empty speed factor.",
    "Dispatching does not preempt or re-route mid-cycle; loader choice is fixed at cycle start.",
    "Trucks finish their current state transition at shift end (no mid-traversal kill); only completed dumps count toward throughput.",
    "Initial dispatch from PARK is simultaneous, which may overstate loader contention in the first cycle relative to staggered start-up in practice.",
]


def _per_replication_row(coll: MetricsCollector) -> dict[str, Any]:
    loader_resource_ids = [rid for rid in coll.resource_ids() if rid.startswith("loader_")]
    if loader_resource_ids:
        avg_loader_queue = sum(coll.avg_queue_wait(rid) for rid in loader_resource_ids) / len(loader_resource_ids)
    else:
        avg_loader_queue = 0.0
    row: dict[str, Any] = {
        "scenario_id": coll.scenario_id,
        "replication": coll.replication,
        "random_seed": coll.seed,
        "total_tonnes_delivered": coll.total_tonnes(),
        "tonnes_per_hour": coll.tonnes_per_hour(),
        "average_truck_cycle_time_min": coll.average_cycle_time_min(),
        "average_truck_utilisation": coll.average_truck_utilisation(),
        "crusher_utilisation": coll.utilisation("crusher"),
        "average_loader_queue_time_min": avg_loader_queue,
        "average_crusher_queue_time_min": coll.avg_queue_wait("crusher"),
    }
    for rid in loader_resource_ids:
        # rid like "loader_L_N" → column "loader_L_N_utilisation"
        row[f"{rid}_utilisation"] = coll.utilisation(rid)
    return row


def _scenario_summary(result: ScenarioResult) -> dict[str, Any]:
    reps = result.replications
    n = len(reps)
    total_tonnes = [r.total_tonnes() for r in reps]
    tph = [r.tonnes_per_hour() for r in reps]
    cycle = [r.average_cycle_time_min() for r in reps]
    truck_util = [r.average_truck_utilisation() for r in reps]
    crusher_util = [r.utilisation("crusher") for r in reps]
    crusher_queue = [r.avg_queue_wait("crusher") for r in reps]

    # Loader-specific utilisation (means across reps).
    loader_resource_ids = sorted({rid for r in reps for rid in r.resource_ids() if rid.startswith("loader_")})
    loader_utilisation: dict[str, float] = {}
    for rid in loader_resource_ids:
        # rid is "loader_L_N" → key "L_N"
        key = rid[len("loader_"):]
        utils = [r.utilisation(rid) for r in reps]
        loader_utilisation[key] = ci95_t(utils)[0]

    # Loader queue time average (mean across loader resources, per rep, then mean across reps).
    loader_queue_per_rep: list[float] = []
    for r in reps:
        ids = [rid for rid in r.resource_ids() if rid.startswith("loader_")]
        if ids:
            loader_queue_per_rep.append(sum(r.avg_queue_wait(rid) for rid in ids) / len(ids))
        else:
            loader_queue_per_rep.append(0.0)

    tt_mean, tt_lo, tt_hi = ci95_t(total_tonnes)
    tph_mean, tph_lo, tph_hi = ci95_t(tph)

    # Bottleneck ranking across all observed resources (union).
    resource_ids: set[str] = set()
    for r in reps:
        resource_ids.update(r.resource_ids())
    rankings: list[dict[str, Any]] = []
    for rid in sorted(resource_ids):
        utils = [r.utilisation(rid) for r in reps]
        waits = [r.avg_queue_wait(rid) for r in reps]
        u_mean, _, _ = ci95_t(utils)
        w_mean, _, _ = ci95_t(waits)
        rankings.append({
            "resource_id": rid,
            "utilisation": u_mean,
            "avg_queue_wait_min": w_mean,
            "score": u_mean * w_mean,
        })
    rankings.sort(key=lambda x: x["score"], reverse=True)

    return {
        "replications": n,
        "shift_length_hours": float(result.config["simulation"]["shift_length_hours"]),
        "total_tonnes_mean": tt_mean,
        "total_tonnes_ci95_low": tt_lo,
        "total_tonnes_ci95_high": tt_hi,
        "tonnes_per_hour_mean": tph_mean,
        "tonnes_per_hour_ci95_low": tph_lo,
        "tonnes_per_hour_ci95_high": tph_hi,
        "average_cycle_time_min": ci95_t(cycle)[0],
        "truck_utilisation_mean": ci95_t(truck_util)[0],
        "loader_utilisation": loader_utilisation,
        "crusher_utilisation": ci95_t(crusher_util)[0],
        "average_loader_queue_time_min": ci95_t(loader_queue_per_rep)[0],
        "average_crusher_queue_time_min": ci95_t(crusher_queue)[0],
        "top_bottlenecks": rankings[:5],
    }


def _filter_event_log_for_combined(coll: MetricsCollector) -> list[dict[str, Any]]:
    if coll.replication == 0:
        return coll.event_log_rows()
    return [e for e in coll.event_log_rows() if e["event_type"] == "dumping_ended"]


def write_outputs(
    results: list[ScenarioResult],
    output_dir: Path,
    *,
    additional_scenarios_proposed: list[str] | None = None,
) -> None:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # results.csv
    rows = [
        _per_replication_row(rep)
        for result in results
        for rep in result.replications
    ]
    pd.DataFrame(rows).to_csv(output_dir / "results.csv", index=False)

    # summary.json
    summary: dict[str, Any] = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {r.scenario_id: _scenario_summary(r) for r in results},
        "key_assumptions": KEY_ASSUMPTIONS,
        "model_limitations": MODEL_LIMITATIONS,
        "additional_scenarios_proposed": additional_scenarios_proposed or [],
    }
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2))

    # combined event_log.csv
    combined: list[dict[str, Any]] = []
    for result in results:
        for rep in result.replications:
            combined.extend(_filter_event_log_for_combined(rep))
    pd.DataFrame(combined).to_csv(output_dir / "event_log.csv", index=False)

    # per-scenario rep-0 traces
    for result in results:
        rep0 = next((r for r in result.replications if r.replication == 0), None)
        if rep0 is None:
            continue
        pd.DataFrame(rep0.event_log_rows()).to_csv(
            output_dir / f"{result.scenario_id}__event_log.csv",
            index=False,
        )
