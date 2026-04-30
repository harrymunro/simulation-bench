"""Aggregate per-replication and per-scenario metrics from SimResult objects."""
from __future__ import annotations

from statistics import mean
from typing import Any

import numpy as np
from scipy import stats

from .simulation import SimResult


def _safe_mean(values: list[float]) -> float:
    return float(mean(values)) if values else 0.0


def _ci95(values: list[float]) -> tuple[float, float]:
    """Return 95% confidence interval (lo, hi) for a list of replication values."""
    n = len(values)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        v = float(values[0])
        return (v, v)
    arr = np.asarray(values, dtype=float)
    m = float(np.mean(arr))
    sem = float(stats.sem(arr))
    if sem == 0.0:
        return (m, m)
    lo, hi = stats.t.interval(0.95, df=n - 1, loc=m, scale=sem)
    return (float(lo), float(hi))


def _waits_after(
    waits: list[tuple[float, float]], threshold: float
) -> list[float]:
    """Return only the wait durations whose request_time >= ``threshold``."""
    return [w for (req_t, w) in waits if req_t >= threshold]


def aggregate_replication(sim_result: SimResult) -> dict[str, Any]:
    """Compute per-replication KPIs from a SimResult.

    Strict shift + warmup counting:
    - Only cycles with ``warmup_minutes <= dump_start < shift_minutes`` contribute
      to delivered tonnes (a cycle started in the warmup window is excluded).
    - ``tonnes_per_hour`` denominator is the post-warmup window
      ``(shift_minutes - warmup_minutes) / 60``.
    - Loader/crusher/edge queue means use only requests issued at or after the
      warmup boundary.
    - Utilisation accumulators are already gated to the post-warmup window
      inside the simulation's _ResourceTracker.
    """
    shift_min = sim_result.shift_minutes
    warmup_min = sim_result.warmup_minutes
    measurement_min = max(0.0, shift_min - warmup_min)

    counted_cycles = [
        c
        for c in sim_result.cycles
        if warmup_min <= c["dump_start"] < shift_min
    ]

    total_tonnes = sum(c["payload_tonnes"] for c in counted_cycles)
    tonnes_per_hour = (
        total_tonnes / (measurement_min / 60.0) if measurement_min > 0 else 0.0
    )

    cycle_times = [c["cycle_time_min"] for c in counted_cycles]
    avg_cycle_time = _safe_mean(cycle_times)

    # Truck utilisation: per-truck busy ratio across the post-warmup window.
    truck_utilisations: list[float] = []
    if sim_result.truck_busy_min and measurement_min > 0:
        for _tid, busy in sim_result.truck_busy_min.items():
            ratio = busy / measurement_min
            truck_utilisations.append(min(1.0, max(0.0, ratio)))
    avg_truck_util = _safe_mean(truck_utilisations)

    # Crusher utilisation.
    crusher_util = (
        sim_result.crusher_busy_min / measurement_min if measurement_min > 0 else 0.0
    )

    # Loader utilisations (per-loader).
    loader_utils: dict[str, float] = {}
    for lid, busy in sim_result.loader_busy_min.items():
        loader_utils[lid] = busy / measurement_min if measurement_min > 0 else 0.0

    # Loader queue waits, post-warmup only.
    all_loader_waits: list[float] = []
    loader_wait_means: dict[str, float] = {}
    for lid, waits in sim_result.loader_queue_waits.items():
        post_waits = _waits_after(waits, warmup_min)
        all_loader_waits.extend(post_waits)
        loader_wait_means[lid] = _safe_mean(post_waits)
    avg_loader_queue_wait = _safe_mean(all_loader_waits)

    avg_crusher_queue_wait = _safe_mean(
        _waits_after(sim_result.crusher_queue_waits, warmup_min)
    )

    # Constrained edge queue waits (per edge), post-warmup only.
    edge_wait_means: dict[str, float] = {}
    for eid, waits in sim_result.edge_queue_waits.items():
        edge_wait_means[eid] = _safe_mean(_waits_after(waits, warmup_min))

    return {
        "scenario_id": sim_result.scenario_id,
        "replication": sim_result.replication,
        "random_seed": sim_result.seed,
        "warmup_minutes": float(warmup_min),
        "measurement_minutes": float(measurement_min),
        "total_tonnes_delivered": float(total_tonnes),
        "tonnes_per_hour": float(tonnes_per_hour),
        "average_truck_cycle_time_min": float(avg_cycle_time),
        "average_truck_utilisation": float(avg_truck_util),
        "crusher_utilisation": float(crusher_util),
        "average_loader_queue_time_min": float(avg_loader_queue_wait),
        "average_crusher_queue_time_min": float(avg_crusher_queue_wait),
        "loader_utilisation": loader_utils,
        "loader_queue_time_min_by_loader": loader_wait_means,
        "edge_queue_time_min_by_edge": edge_wait_means,
        "edge_utilisation_by_edge": {
            eid: (busy / measurement_min if measurement_min > 0 else 0.0)
            for eid, busy in sim_result.edge_busy_min.items()
        },
        "completed_cycles": int(len(counted_cycles)),
    }


def aggregate_scenario(rep_results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate per-replication metrics into per-scenario summary statistics."""
    if not rep_results:
        return {}

    scenario_id = rep_results[0]["scenario_id"]
    replications = len(rep_results)

    def col(name: str) -> list[float]:
        return [float(r[name]) for r in rep_results]

    tonnes = col("total_tonnes_delivered")
    tph = col("tonnes_per_hour")
    cycle = col("average_truck_cycle_time_min")
    truck_u = col("average_truck_utilisation")
    crusher_u = col("crusher_utilisation")
    loader_q = col("average_loader_queue_time_min")
    crusher_q = col("average_crusher_queue_time_min")

    tonnes_lo, tonnes_hi = _ci95(tonnes)
    tph_lo, tph_hi = _ci95(tph)

    # Per-loader utilisation means
    loader_ids: set[str] = set()
    for r in rep_results:
        loader_ids.update(r.get("loader_utilisation", {}).keys())
    loader_util_mean = {
        lid: _safe_mean(
            [float(r.get("loader_utilisation", {}).get(lid, 0.0)) for r in rep_results]
        )
        for lid in sorted(loader_ids)
    }
    loader_queue_mean_by_id = {
        lid: _safe_mean(
            [
                float(r.get("loader_queue_time_min_by_loader", {}).get(lid, 0.0))
                for r in rep_results
            ]
        )
        for lid in sorted(loader_ids)
    }

    # Per-edge mean queue time and utilisation
    edge_ids: set[str] = set()
    for r in rep_results:
        edge_ids.update(r.get("edge_queue_time_min_by_edge", {}).keys())
    edge_queue_mean = {
        eid: _safe_mean(
            [
                float(r.get("edge_queue_time_min_by_edge", {}).get(eid, 0.0))
                for r in rep_results
            ]
        )
        for eid in sorted(edge_ids)
    }
    edge_util_mean = {
        eid: _safe_mean(
            [
                float(r.get("edge_utilisation_by_edge", {}).get(eid, 0.0))
                for r in rep_results
            ]
        )
        for eid in sorted(edge_ids)
    }

    # Top bottlenecks: rank constrained resources (loaders, crusher, constrained edges).
    # Primary key utilisation, secondary key queue time, both descending. This puts
    # steady-state binding constraints (e.g. 95% util crusher) ahead of pure startup
    # transients (e.g. ramp queue caused by all trucks dispatching at t=0).
    bottleneck_candidates: list[dict[str, Any]] = []
    for lid, qt in loader_queue_mean_by_id.items():
        bottleneck_candidates.append(
            {
                "resource_id": lid,
                "mean_queue_time_min": float(qt),
                "mean_utilisation": float(loader_util_mean.get(lid, 0.0)),
            }
        )
    bottleneck_candidates.append(
        {
            "resource_id": "D_CRUSH",
            "mean_queue_time_min": float(_safe_mean(crusher_q)),
            "mean_utilisation": float(_safe_mean(crusher_u)),
        }
    )
    for eid, qt in edge_queue_mean.items():
        bottleneck_candidates.append(
            {
                "resource_id": eid,
                "mean_queue_time_min": float(qt),
                "mean_utilisation": float(edge_util_mean.get(eid, 0.0)),
            }
        )
    bottleneck_candidates.sort(
        key=lambda x: (x["mean_utilisation"], x["mean_queue_time_min"]),
        reverse=True,
    )
    top_bottlenecks = bottleneck_candidates[:5]

    return {
        "scenario_id": scenario_id,
        "replications": replications,
        "shift_length_hours": float(rep_results[0].get("shift_length_hours", 8.0)),
        "total_tonnes_mean": float(_safe_mean(tonnes)),
        "total_tonnes_ci95_low": float(tonnes_lo),
        "total_tonnes_ci95_high": float(tonnes_hi),
        "tonnes_per_hour_mean": float(_safe_mean(tph)),
        "tonnes_per_hour_ci95_low": float(tph_lo),
        "tonnes_per_hour_ci95_high": float(tph_hi),
        "average_cycle_time_min": float(_safe_mean(cycle)),
        "truck_utilisation_mean": float(_safe_mean(truck_u)),
        "loader_utilisation": loader_util_mean,
        "crusher_utilisation": float(_safe_mean(crusher_u)),
        "average_loader_queue_time_min": float(_safe_mean(loader_q)),
        "average_crusher_queue_time_min": float(_safe_mean(crusher_q)),
        "edge_mean_queue_time_min": edge_queue_mean,
        "edge_mean_utilisation": edge_util_mean,
        "top_bottlenecks": top_bottlenecks,
    }
