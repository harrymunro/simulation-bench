"""Analysis: confidence intervals, bottleneck identification, output writers."""

from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats


# Columns we expose in results.csv (top-level, scalar). Per-resource details
# live in summary.json; trying to flatten them into CSV produces a pile of
# scenario-specific columns nobody can read.
RESULTS_CSV_COLUMNS = [
    "scenario_id",
    "replication",
    "random_seed",
    "truck_count",
    "shift_length_hours",
    "total_tonnes_delivered",
    "tonnes_per_hour",
    "average_truck_cycle_time_min",
    "average_truck_utilisation",
    "crusher_utilisation",
    "loader_utilisation_L_N",
    "loader_utilisation_L_S",
    "average_loader_queue_time_min",
    "average_crusher_queue_time_min",
    "dump_events",
]


def _ci95(values: np.ndarray) -> tuple[float, float]:
    """Two-sided 95% CI via Student's t-distribution."""
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if len(arr) < 2:
        m = float(arr.mean()) if len(arr) else float("nan")
        return m, m
    mean = float(arr.mean())
    sem = float(stats.sem(arr))
    h = float(stats.t.ppf(0.975, df=len(arr) - 1)) * sem
    return mean - h, mean + h


def flatten_loader_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Pull the dict in ``loader_utilisation`` into per-loader columns."""
    df = df.copy()
    if "loader_utilisation" not in df.columns:
        return df
    loaders = sorted({k for d in df["loader_utilisation"] for k in d.keys()})
    for lid in loaders:
        df[f"loader_utilisation_{lid}"] = df["loader_utilisation"].apply(
            lambda d: d.get(lid, float("nan"))
        )
    return df


def write_results_csv(results_df: pd.DataFrame, path: Path) -> None:
    """Write ``results.csv`` with one row per (scenario, replication)."""
    df = flatten_loader_columns(results_df)
    cols = [c for c in RESULTS_CSV_COLUMNS if c in df.columns]
    df[cols].to_csv(path, index=False)


def write_event_log_csv(events: list[dict[str, Any]], path: Path) -> None:
    """Write the concatenated event log."""
    if not events:
        path.write_text("", encoding="utf-8")
        return
    cols = [
        "time_min", "replication", "scenario_id", "truck_id", "event_type",
        "from_node", "to_node", "location", "loaded", "payload_tonnes",
        "resource_id", "queue_length",
    ]
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for e in events:
            row = {c: e.get(c) for c in cols}
            w.writerow(row)


def identify_bottlenecks(per_resource_stats_list: list[dict[str, Any]],
                         top_n: int = 3) -> list[dict[str, Any]]:
    """Identify the resources that, on average across replications, had the
    longest queueing waits.

    Returns a list of dicts ordered by descending mean queue wait, including
    loaders, edges, and the crusher.
    """
    accum: dict[tuple[str, str], list[float]] = {}

    for prs in per_resource_stats_list:
        for lid, s in prs.get("loaders", {}).items():
            accum.setdefault(("loader", lid), []).append(s["mean_queue_wait_min"])
        c = prs.get("crusher", {})
        if c:
            accum.setdefault(("crusher", "D_CRUSH"), []).append(c["mean_queue_wait_min"])
        for eid, s in prs.get("edges", {}).items():
            accum.setdefault(("edge", eid), []).append(s["mean_queue_wait_min"])

    rows = []
    for (kind, rid), vals in accum.items():
        arr = np.array(vals, dtype=float)
        rows.append({
            "resource_kind": kind,
            "resource_id": rid,
            "mean_queue_wait_min": float(arr.mean()),
            "max_queue_wait_min": float(arr.max()),
        })
    rows.sort(key=lambda r: r["mean_queue_wait_min"], reverse=True)
    return rows[:top_n]


def summarise_scenario(scenario_id: str, df: pd.DataFrame) -> dict[str, Any]:
    """Compute mean + 95% CI per metric for one scenario's replications."""
    df = df[df["scenario_id"] == scenario_id]
    n = len(df)
    if n == 0:
        return {}

    tonnes = df["total_tonnes_delivered"].to_numpy(dtype=float)
    tph = df["tonnes_per_hour"].to_numpy(dtype=float)

    tonnes_lo, tonnes_hi = _ci95(tonnes)
    tph_lo, tph_hi = _ci95(tph)

    # Loader utilisation: mean across reps, per loader.
    loader_keys = sorted({k for d in df["loader_utilisation"] for k in d.keys()})
    loader_util = {
        lid: float(np.mean([d.get(lid, float("nan")) for d in df["loader_utilisation"]]))
        for lid in loader_keys
    }

    bottlenecks = identify_bottlenecks(df["per_resource_queue_stats"].tolist())

    return {
        "replications": int(n),
        "shift_length_hours": float(df["shift_length_hours"].iloc[0]),
        "truck_count": int(df["truck_count"].iloc[0]),
        "total_tonnes_mean": float(tonnes.mean()),
        "total_tonnes_ci95_low": float(tonnes_lo),
        "total_tonnes_ci95_high": float(tonnes_hi),
        "total_tonnes_std": float(tonnes.std(ddof=1)) if n > 1 else 0.0,
        "tonnes_per_hour_mean": float(tph.mean()),
        "tonnes_per_hour_ci95_low": float(tph_lo),
        "tonnes_per_hour_ci95_high": float(tph_hi),
        "average_cycle_time_min": float(df["average_truck_cycle_time_min"].mean()),
        "truck_utilisation_mean": float(df["average_truck_utilisation"].mean()),
        "loader_utilisation": loader_util,
        "crusher_utilisation": float(df["crusher_utilisation"].mean()),
        "average_loader_queue_time_min": float(df["average_loader_queue_time_min"].mean()),
        "average_crusher_queue_time_min": float(df["average_crusher_queue_time_min"].mean()),
        "top_bottlenecks": bottlenecks,
    }


def build_summary(results_df: pd.DataFrame,
                  scenarios: list[str],
                  *,
                  benchmark_id: str,
                  key_assumptions: list[str],
                  model_limitations: list[str],
                  additional_scenarios_proposed: list[str] | None = None) -> dict[str, Any]:
    """Build the full ``summary.json`` payload."""
    return {
        "benchmark_id": benchmark_id,
        "scenarios": {
            sid: summarise_scenario(sid, results_df)
            for sid in scenarios
        },
        "key_assumptions": key_assumptions,
        "model_limitations": model_limitations,
        "additional_scenarios_proposed": additional_scenarios_proposed or [],
    }


def write_summary_json(summary: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(summary, indent=2, default=_json_default), encoding="utf-8")


def _json_default(o: Any) -> Any:
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    raise TypeError(f"Cannot serialise type {type(o)} ({o!r})")


def behavioural_self_check(summary: dict[str, Any]) -> list[dict[str, Any]]:
    """Reproduce the harness behavioural checks so we see them at run time."""
    sc = summary.get("scenarios", {})

    def m(sid: str) -> float | None:
        v = sc.get(sid, {}).get("total_tonnes_mean")
        return float(v) if v is not None else None

    checks: list[dict[str, Any]] = []
    pairs = [
        ("trucks_12_gt_trucks_4",
         lambda: m("trucks_12") is not None and m("trucks_4") is not None
                 and m("trucks_12") > m("trucks_4"),
         "Higher fleet should usually outperform lower fleet."),
        ("baseline_gt_trucks_4",
         lambda: m("baseline") is not None and m("trucks_4") is not None
                 and m("baseline") > m("trucks_4"),
         "Baseline should usually outperform 4-truck case."),
        ("ramp_upgrade_ge_baseline",
         lambda: m("ramp_upgrade") is not None and m("baseline") is not None
                 and m("ramp_upgrade") >= 0.95 * m("baseline"),
         "Ramp upgrade should usually improve or maintain throughput."),
        ("crusher_slowdown_lt_baseline",
         lambda: m("crusher_slowdown") is not None and m("baseline") is not None
                 and m("crusher_slowdown") < m("baseline"),
         "Slower crusher should usually reduce throughput."),
        ("ramp_closed_le_baseline",
         lambda: m("ramp_closed") is not None and m("baseline") is not None
                 and m("ramp_closed") <= 1.05 * m("baseline"),
         "Ramp closure should usually not improve throughput."),
    ]
    for name, predicate, desc in pairs:
        try:
            ok = bool(predicate())
        except Exception:
            ok = False
        checks.append({"name": name, "passed": ok, "description": desc})

    if all(m(s) is not None for s in ("trucks_4", "baseline", "trucks_12")):
        increase_4_to_8 = m("baseline") - m("trucks_4")
        increase_8_to_12 = m("trucks_12") - m("baseline")
        sat = increase_8_to_12 <= 1.25 * increase_4_to_8
    else:
        sat = False
    checks.append({
        "name": "truck_count_saturation_plausible",
        "passed": bool(sat),
        "description": "Throughput should show some saturation as trucks increase.",
    })
    return checks
