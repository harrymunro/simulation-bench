"""Run multi-scenario, multi-replication experiments and produce outputs."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd
from scipy import stats as scistats

from .scenario import load_scenario
from .simulation import load_input_dataframes, run_replication


# ---------- Statistics ---------------------------------------------------------


def ci95(values: List[float]) -> Dict[str, float]:
    """95% confidence interval for the mean using a t-distribution."""
    arr = np.asarray(values, dtype=float)
    n = arr.size
    if n == 0:
        return {"mean": 0.0, "ci95_low": 0.0, "ci95_high": 0.0, "n": 0}
    mean = float(arr.mean())
    if n == 1:
        return {"mean": mean, "ci95_low": mean, "ci95_high": mean, "n": 1}
    sem = float(arr.std(ddof=1) / np.sqrt(n))
    t_crit = float(scistats.t.ppf(0.975, df=n - 1))
    half = t_crit * sem
    return {"mean": mean, "ci95_low": mean - half, "ci95_high": mean + half, "n": n}


def aggregate_scenario(replication_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not replication_results:
        return {}
    tonnes = [r["total_tonnes_delivered"] for r in replication_results]
    tph = [r["tonnes_per_hour"] for r in replication_results]
    cycle = [r["average_truck_cycle_time_min"] for r in replication_results]
    truck_util = [r["average_truck_utilisation"] for r in replication_results]
    crusher_util = [r["crusher_utilisation"] for r in replication_results]
    loader_q = [r["average_loader_queue_time_min"] for r in replication_results]
    crusher_q = [r["average_crusher_queue_time_min"] for r in replication_results]
    cycles_completed = [r["cycles_completed"] for r in replication_results]

    # Per-loader utilisation: average across reps.
    loader_ids = sorted({lid for r in replication_results for lid in r["loader_utilisation"].keys()})
    loader_util_mean: Dict[str, float] = {}
    for lid in loader_ids:
        loader_util_mean[lid] = float(np.mean([r["loader_utilisation"].get(lid, 0.0)
                                               for r in replication_results]))

    lane_ids = sorted({lid for r in replication_results for lid in r["lane_utilisation"].keys()})
    lane_util_mean: Dict[str, float] = {}
    lane_queue_mean: Dict[str, float] = {}
    for lid in lane_ids:
        lane_util_mean[lid] = float(np.mean([r["lane_utilisation"].get(lid, 0.0)
                                              for r in replication_results]))
        lane_queue_mean[lid] = float(np.mean([r["lane_queue_wait_min"].get(lid, 0.0)
                                               for r in replication_results]))

    tonnes_ci = ci95(tonnes)
    tph_ci = ci95(tph)
    cycle_ci = ci95(cycle)
    truck_util_ci = ci95(truck_util)
    crusher_util_ci = ci95(crusher_util)
    loader_q_ci = ci95(loader_q)
    crusher_q_ci = ci95(crusher_q)

    # Bottleneck heuristic: highest mean utilisation among (loaders, crusher, lanes).
    bottlenecks: List[Dict[str, Any]] = []
    for lid, u in loader_util_mean.items():
        bottlenecks.append({"resource": f"loader:{lid}", "type": "loader", "utilisation": u})
    bottlenecks.append({"resource": "crusher", "type": "crusher", "utilisation": float(crusher_util_ci["mean"])})
    for lid, u in lane_util_mean.items():
        bottlenecks.append({"resource": f"lane:{lid}", "type": "lane", "utilisation": u,
                            "queue_wait_mean_min": lane_queue_mean.get(lid, 0.0)})
    bottlenecks.sort(key=lambda b: b["utilisation"], reverse=True)
    top_bottlenecks = bottlenecks[:5]

    return {
        "scenario_id": replication_results[0]["scenario_id"],
        "replications": len(replication_results),
        "shift_length_hours": replication_results[0]["shift_minutes"] / 60.0,
        "truck_count": replication_results[0]["truck_count"],
        "total_tonnes_mean": tonnes_ci["mean"],
        "total_tonnes_ci95_low": tonnes_ci["ci95_low"],
        "total_tonnes_ci95_high": tonnes_ci["ci95_high"],
        "tonnes_per_hour_mean": tph_ci["mean"],
        "tonnes_per_hour_ci95_low": tph_ci["ci95_low"],
        "tonnes_per_hour_ci95_high": tph_ci["ci95_high"],
        "average_cycle_time_min": cycle_ci["mean"],
        "average_cycle_time_ci95_low": cycle_ci["ci95_low"],
        "average_cycle_time_ci95_high": cycle_ci["ci95_high"],
        "truck_utilisation_mean": truck_util_ci["mean"],
        "truck_utilisation_ci95_low": truck_util_ci["ci95_low"],
        "truck_utilisation_ci95_high": truck_util_ci["ci95_high"],
        "loader_utilisation": loader_util_mean,
        "crusher_utilisation": crusher_util_ci["mean"],
        "crusher_utilisation_ci95_low": crusher_util_ci["ci95_low"],
        "crusher_utilisation_ci95_high": crusher_util_ci["ci95_high"],
        "average_loader_queue_time_min": loader_q_ci["mean"],
        "average_loader_queue_time_ci95_low": loader_q_ci["ci95_low"],
        "average_loader_queue_time_ci95_high": loader_q_ci["ci95_high"],
        "average_crusher_queue_time_min": crusher_q_ci["mean"],
        "average_crusher_queue_time_ci95_low": crusher_q_ci["ci95_low"],
        "average_crusher_queue_time_ci95_high": crusher_q_ci["ci95_high"],
        "lane_utilisation": lane_util_mean,
        "lane_queue_wait_min": lane_queue_mean,
        "cycles_completed_mean": float(np.mean(cycles_completed)),
        "top_bottlenecks": top_bottlenecks,
    }


# ---------- Experiment runner --------------------------------------------------


def run_scenario(
    *,
    scenario_id: str,
    data_dir: Path,
    scenario_dir: Path,
    capture_event_log_reps: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """Run all replications for a scenario.

    Returns the aggregated summary plus the list of replication-level results
    and a concatenated event log for the captured replications.
    """
    scenario = load_scenario(scenario_dir, scenario_id)
    nodes, edges, trucks, loaders, dump_points = load_input_dataframes(data_dir)

    sim_cfg = scenario.get("simulation", {})
    replications = int(sim_cfg.get("replications", 30))
    base_seed = int(sim_cfg.get("base_random_seed", 12345))

    if capture_event_log_reps is None:
        capture_event_log_reps = [0]

    rep_results: List[Dict[str, Any]] = []
    event_log_rows: List[Dict[str, Any]] = []

    for rep in range(replications):
        capture = rep in capture_event_log_reps
        result = run_replication(
            scenario=scenario,
            nodes=nodes, edges=edges,
            truck_records=trucks,
            loader_records=loaders,
            dump_records=dump_points,
            replication_index=rep,
            base_seed=base_seed,
            capture_event_log=capture,
        )
        if capture and result.get("event_log"):
            event_log_rows.extend(result["event_log"])
        # Drop event_log from the lightweight rep result for memory.
        result_lite = {k: v for k, v in result.items() if k != "event_log"}
        rep_results.append(result_lite)

    summary = aggregate_scenario(rep_results)
    return {
        "scenario_id": scenario_id,
        "summary": summary,
        "replications": rep_results,
        "event_log_rows": event_log_rows,
    }


def replications_to_dataframe(rep_results: List[Dict[str, Any]]) -> pd.DataFrame:
    """Flatten replication-level results into a wide DataFrame."""
    rows = []
    for r in rep_results:
        row = {
            "scenario_id": r["scenario_id"],
            "replication": r["replication"],
            "random_seed": r["random_seed"],
            "shift_minutes": r["shift_minutes"],
            "truck_count": r["truck_count"],
            "total_tonnes_delivered": r["total_tonnes_delivered"],
            "tonnes_per_hour": r["tonnes_per_hour"],
            "average_truck_cycle_time_min": r["average_truck_cycle_time_min"],
            "average_truck_utilisation": r["average_truck_utilisation"],
            "crusher_utilisation": r["crusher_utilisation"],
            "average_loader_queue_time_min": r["average_loader_queue_time_min"],
            "average_crusher_queue_time_min": r["average_crusher_queue_time_min"],
            "cycles_completed": r["cycles_completed"],
        }
        for lid, u in r["loader_utilisation"].items():
            row[f"loader_util_{lid}"] = u
        for lid, q in r["loader_queue_waits"].items():
            row[f"loader_queue_min_{lid}"] = q
        for lid, u in r["lane_utilisation"].items():
            row[f"lane_util_{lid}"] = u
        for lid, q in r["lane_queue_wait_min"].items():
            row[f"lane_queue_min_{lid}"] = q
        rows.append(row)
    return pd.DataFrame(rows)


def write_outputs(
    *,
    out_dir: Path,
    scenarios: List[Dict[str, Any]],
    benchmark_id: str = "001_synthetic_mine_throughput",
    key_assumptions: List[str] | None = None,
    model_limitations: List[str] | None = None,
    additional_scenarios_proposed: List[str] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    all_reps: List[Dict[str, Any]] = []
    all_events: List[Dict[str, Any]] = []
    summary_dict: Dict[str, Any] = {
        "benchmark_id": benchmark_id,
        "scenarios": {},
        "key_assumptions": list(key_assumptions or []),
        "model_limitations": list(model_limitations or []),
        "additional_scenarios_proposed": list(additional_scenarios_proposed or []),
    }
    for s in scenarios:
        summary_dict["scenarios"][s["scenario_id"]] = s["summary"]
        all_reps.extend(s["replications"])
        all_events.extend(s["event_log_rows"])

    df = replications_to_dataframe(all_reps)
    df.to_csv(out_dir / "results.csv", index=False)

    with (out_dir / "summary.json").open("w") as fh:
        json.dump(summary_dict, fh, indent=2, default=_json_default)

    # Event log
    event_columns = [
        "time_min", "replication", "scenario_id", "truck_id", "event_type",
        "from_node", "to_node", "location", "loaded", "payload_tonnes",
        "resource_id", "queue_length",
    ]
    if all_events:
        ev_df = pd.DataFrame(all_events)
        for c in event_columns:
            if c not in ev_df.columns:
                ev_df[c] = ""
        ev_df = ev_df[event_columns]
    else:
        ev_df = pd.DataFrame(columns=event_columns)
    ev_df.to_csv(out_dir / "event_log.csv", index=False)


def _json_default(obj):
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.ndarray,)):
        return obj.tolist()
    raise TypeError(f"Not serialisable: {type(obj)}")
