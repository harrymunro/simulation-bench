"""Aggregation analysis: 95% CI Student-t and bottleneck identification."""
from __future__ import annotations

from typing import Dict, List

import numpy as np
import pandas as pd
from scipy import stats


def ci95_student_t(values: List[float]) -> Dict[str, float]:
    """Return mean, ci95_low, ci95_high using Student-t (df = n-1)."""
    arr = np.array(values, dtype=float)
    n = len(arr)
    mean = float(arr.mean()) if n else 0.0
    if n < 2:
        return {"mean": mean, "ci95_low": mean, "ci95_high": mean, "std": 0.0, "n": n}
    sd = float(arr.std(ddof=1))
    se = sd / np.sqrt(n)
    tcrit = float(stats.t.ppf(0.975, df=n - 1))
    return {
        "mean": mean,
        "ci95_low": mean - tcrit * se,
        "ci95_high": mean + tcrit * se,
        "std": sd,
        "n": n,
    }


def aggregate_scenario(rows: pd.DataFrame, scenario_cfg: dict) -> Dict:
    """Build the per-scenario block of summary.json."""
    block: Dict = {
        "replications": int(len(rows)),
        "shift_length_hours": float(scenario_cfg.get("simulation", {}).get("shift_length_hours", 8)),
        "fleet_size": int(rows["fleet_size"].iloc[0]) if len(rows) else 0,
    }
    block["total_tonnes"] = ci95_student_t(rows["total_tonnes_delivered"].tolist())
    block["tonnes_per_hour"] = ci95_student_t(rows["tonnes_per_hour"].tolist())
    block["average_cycle_time_min"] = ci95_student_t(rows["average_truck_cycle_time_min"].tolist())
    block["truck_utilisation"] = ci95_student_t(rows["average_truck_utilisation"].tolist())
    block["crusher_utilisation"] = ci95_student_t(rows["crusher_utilisation"].tolist())
    block["loader_utilisation"] = {
        "L_N": ci95_student_t(rows["loader_utilisation_L_N"].tolist()),
        "L_S": ci95_student_t(rows["loader_utilisation_L_S"].tolist()),
    }
    block["average_loader_queue_time_min"] = ci95_student_t(rows["average_loader_queue_time_min"].tolist())
    block["average_crusher_queue_time_min"] = ci95_student_t(rows["average_crusher_queue_time_min"].tolist())

    # Flat aliases for upstream evaluator (simulation-bench prompt's recommended schema)
    block["total_tonnes_mean"] = block["total_tonnes"]["mean"]
    block["total_tonnes_ci95_low"] = block["total_tonnes"]["ci95_low"]
    block["total_tonnes_ci95_high"] = block["total_tonnes"]["ci95_high"]
    block["tonnes_per_hour_mean"] = block["tonnes_per_hour"]["mean"]
    block["tonnes_per_hour_ci95_low"] = block["tonnes_per_hour"]["ci95_low"]
    block["tonnes_per_hour_ci95_high"] = block["tonnes_per_hour"]["ci95_high"]
    block["truck_utilisation_mean"] = block["truck_utilisation"]["mean"]
    block["crusher_utilisation_mean"] = block["crusher_utilisation"]["mean"]
    block["average_loader_queue_time_min_mean"] = block["average_loader_queue_time_min"]["mean"]
    block["average_crusher_queue_time_min_mean"] = block["average_crusher_queue_time_min"]["mean"]

    # Bottleneck heuristic: rank resources by utilisation, then by avg queue time
    bottlenecks = []
    bottlenecks.append({"resource": "crusher", "utilisation_mean": block["crusher_utilisation"]["mean"],
                        "queue_min_mean": block["average_crusher_queue_time_min"]["mean"]})
    bottlenecks.append({"resource": "loader_L_N", "utilisation_mean": block["loader_utilisation"]["L_N"]["mean"],
                        "queue_min_mean": block["average_loader_queue_time_min"]["mean"]})
    bottlenecks.append({"resource": "loader_L_S", "utilisation_mean": block["loader_utilisation"]["L_S"]["mean"],
                        "queue_min_mean": block["average_loader_queue_time_min"]["mean"]})
    bottlenecks.sort(key=lambda b: (b["utilisation_mean"], b["queue_min_mean"]), reverse=True)
    block["top_bottlenecks"] = bottlenecks[:3]
    return block
