"""Replication runner that drives all required scenarios and writes outputs.

Reads scenario YAML files, applies them to the topology, runs N replications per
scenario, aggregates per-replication and per-scenario metrics, and writes:

- ``results.csv``    one row per (scenario, replication)
- ``summary.json``   aggregated per-scenario summary statistics
- ``event_log.csv``  trace of state transitions (capped to first M reps per scenario)
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import pandas as pd

from .metrics import aggregate_replication, aggregate_scenario
from .scenario import list_scenarios, load_scenario
from .simulation import run_simulation
from .topology import apply_scenario, load_topology


_DEFAULT_SCENARIOS_ORDER = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]

_KEY_ASSUMPTIONS = [
    "Loader and crusher service times are truncated normal (mean and SD from input data).",
    "Travel time per edge has multiplicative log-symmetric noise with CV=0.10.",
    "Routing uses shortest-time Dijkstra over open edges; edge weights = distance / (max_speed * speed_factor) with empty=1.0 and loaded=0.85.",
    "Dispatch policy is nearest_available_loader with tie-break by lowest expected cycle time including queue wait estimate.",
    "Capacity-constrained edges (capacity<999) are modelled as SimPy Resources; per-direction counters.",
    "All trucks start at PARK at t=0; the runner honours simulation.warmup_minutes (0 in shipped scenarios) by excluding pre-warmup events from utilisation, queue-time means, tonnes counting, and the tonnes/h denominator.",
    "A cycle is counted toward delivered tonnes if warmup_minutes <= dump_start < shift_end (480 min); in-flight dumps complete during a 60-minute grace window so trucks already at the crusher record their delivery.",
    "Per-replication seed is base_random_seed + replication_index for reproducibility.",
    "Top bottlenecks are ranked by (mean utilisation desc, mean queue time desc) so high-utilisation steady-state constraints rank above pure startup transients.",
]

_MODEL_LIMITATIONS = [
    "No equipment breakdowns, maintenance interruptions, or operator unavailability.",
    "No shift changes, refuelling, or operator breaks during the 8-hour window.",
    "Loaded and empty travel are modelled as separate directional resources; opposing traffic on a physically single-lane segment does not interact via meet-and-pass logic.",
    "Bypass route capacity (E15-E17) is treated as unconstrained; in reality bypasses may have width or speed limits not captured here.",
    "Ore is delivered in discrete 100-tonne payloads; partial deliveries are not modelled.",
    "Truck acceleration/deceleration profiles and switchback effects are not represented; speed factor is constant per edge.",
    "Loader and crusher service times use a simple truncated normal; bimodal or heavy-tailed effects (e.g. blocked chutes) are not captured.",
    "Warmup support is implemented; current scenarios use warmup=0 so startup effects (e.g. all trucks dispatching from PARK at t=0 and converging on the ramp) remain visible. Use --warmup-minutes on the CLI for ad-hoc analysis under non-default warmup.",
]


def run_all(
    data_dir: Path | str,
    output_dir: Path | str,
    scenarios: list[str] | None = None,
    replications_override: int | None = None,
    event_log_max_reps_per_scenario: int = 5,
    warmup_minutes_override: float | None = None,
    verbose: bool = True,
) -> dict[str, Any]:
    """Run all requested scenarios and write results.csv, summary.json, event_log.csv.

    ``warmup_minutes_override`` (CLI knob) replaces the per-scenario
    ``simulation.warmup_minutes`` value when not None. Use ``0`` to disable
    warmup explicitly; leave ``None`` to honour the YAML config (currently 0
    in every shipped scenario).
    """
    data_dir = Path(data_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    topology = load_topology(data_dir)
    scenarios_dir = data_dir / "scenarios"

    if scenarios is None or (len(scenarios) == 1 and scenarios[0] == "all"):
        # Default to canonical order then append any extras the user dropped in.
        available = list_scenarios(scenarios_dir)
        ordered = [s for s in _DEFAULT_SCENARIOS_ORDER if s in available]
        extras = [s for s in available if s not in _DEFAULT_SCENARIOS_ORDER]
        scenario_ids = ordered + extras
    else:
        scenario_ids = list(scenarios)

    all_rep_rows: list[dict[str, Any]] = []
    summary: dict[str, Any] = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": list(_KEY_ASSUMPTIONS),
        "model_limitations": list(_MODEL_LIMITATIONS),
        "additional_scenarios_proposed": [],
    }
    event_log_rows: list[dict[str, Any]] = []

    overall_start = time.perf_counter()

    for scenario_id in scenario_ids:
        scenario = load_scenario(scenarios_dir, scenario_id)
        if warmup_minutes_override is not None:
            scenario = _with_warmup_override(scenario, float(warmup_minutes_override))
        scenario_topology = apply_scenario(topology, scenario)

        sim_cfg = scenario.get("simulation", {})
        shift_hours = float(sim_cfg.get("shift_length_hours", 8))
        warmup_min_used = float(sim_cfg.get("warmup_minutes", 0) or 0)
        replications = int(replications_override or sim_cfg.get("replications", 30))
        base_seed = int(sim_cfg.get("base_random_seed", 12345))

        rep_metrics_list: list[dict[str, Any]] = []

        scen_start = time.perf_counter()
        for rep in range(replications):
            seed = base_seed + rep
            sim_result = run_simulation(
                scenario_topology, scenario, replication=rep, seed=seed
            )
            rep_metrics = aggregate_replication(sim_result)
            rep_metrics["shift_length_hours"] = shift_hours
            rep_metrics_list.append(rep_metrics)

            row = _flatten_results_row(rep_metrics)
            all_rep_rows.append(row)

            if rep < event_log_max_reps_per_scenario:
                event_log_rows.extend(sim_result.events)

            if verbose:
                print(
                    f"  [{scenario_id}] rep {rep+1}/{replications}  "
                    f"tonnes={rep_metrics['total_tonnes_delivered']:.0f}  "
                    f"t/h={rep_metrics['tonnes_per_hour']:.1f}",
                    flush=True,
                )

        scen_elapsed = time.perf_counter() - scen_start

        scenario_summary = aggregate_scenario(rep_metrics_list)
        scenario_summary["shift_length_hours"] = shift_hours
        scenario_summary["warmup_minutes"] = warmup_min_used
        scenario_summary["wallclock_seconds"] = round(scen_elapsed, 2)
        summary["scenarios"][scenario_id] = scenario_summary

        if verbose:
            print(
                f"[{scenario_id}] {replications} reps in {scen_elapsed:.1f}s  "
                f"t/h mean={scenario_summary['tonnes_per_hour_mean']:.1f} "
                f"95% CI=[{scenario_summary['tonnes_per_hour_ci95_low']:.1f}, "
                f"{scenario_summary['tonnes_per_hour_ci95_high']:.1f}]",
                flush=True,
            )

    summary["wallclock_seconds_total"] = round(time.perf_counter() - overall_start, 2)

    # Write outputs
    results_df = pd.DataFrame(all_rep_rows)
    results_df = _order_results_columns(results_df)
    # Edges/loaders that are absent in some scenarios (e.g. closed or unconstrained
    # in that scenario) appear as NaN; fill with 0 for legibility while keeping
    # the union of columns across scenarios.
    fill_cols = [c for c in results_df.columns if c.startswith(("edge_", "loader_"))]
    results_df[fill_cols] = results_df[fill_cols].fillna(0.0)
    results_path = output_dir / "results.csv"
    results_df.to_csv(results_path, index=False)

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=_json_default)

    event_log_df = pd.DataFrame(event_log_rows)
    event_log_path = output_dir / "event_log.csv"
    if not event_log_df.empty:
        event_log_df = _order_event_log_columns(event_log_df)
    event_log_df.to_csv(event_log_path, index=False)

    if verbose:
        print(f"\nWrote {results_path}")
        print(f"Wrote {summary_path}")
        print(f"Wrote {event_log_path} ({len(event_log_df)} rows)")

    return summary


def _with_warmup_override(scenario: dict[str, Any], warmup_minutes: float) -> dict[str, Any]:
    """Return a scenario copy with simulation.warmup_minutes overridden (immutable)."""
    new_scenario = dict(scenario)
    new_sim = dict(scenario.get("simulation", {}))
    new_sim["warmup_minutes"] = float(warmup_minutes)
    new_scenario["simulation"] = new_sim
    return new_scenario


def _flatten_results_row(rep_metrics: dict[str, Any]) -> dict[str, Any]:
    """Flatten dict-valued metrics into named columns for the results CSV."""
    row: dict[str, Any] = {
        "scenario_id": rep_metrics["scenario_id"],
        "replication": rep_metrics["replication"],
        "random_seed": rep_metrics["random_seed"],
        "total_tonnes_delivered": rep_metrics["total_tonnes_delivered"],
        "tonnes_per_hour": rep_metrics["tonnes_per_hour"],
        "average_truck_cycle_time_min": rep_metrics["average_truck_cycle_time_min"],
        "average_truck_utilisation": rep_metrics["average_truck_utilisation"],
        "crusher_utilisation": rep_metrics["crusher_utilisation"],
        "average_loader_queue_time_min": rep_metrics["average_loader_queue_time_min"],
        "average_crusher_queue_time_min": rep_metrics["average_crusher_queue_time_min"],
        "completed_cycles": rep_metrics.get("completed_cycles", 0),
    }
    for lid, util in rep_metrics.get("loader_utilisation", {}).items():
        row[f"loader_{lid}_utilisation"] = util
    for lid, qt in rep_metrics.get("loader_queue_time_min_by_loader", {}).items():
        row[f"loader_{lid}_queue_time_min"] = qt
    for eid, qt in rep_metrics.get("edge_queue_time_min_by_edge", {}).items():
        row[f"edge_{eid}_queue_time_min"] = qt
    for eid, util in rep_metrics.get("edge_utilisation_by_edge", {}).items():
        row[f"edge_{eid}_utilisation"] = util
    return row


_PRIMARY_RESULT_COLUMNS = [
    "scenario_id",
    "replication",
    "random_seed",
    "total_tonnes_delivered",
    "tonnes_per_hour",
    "average_truck_cycle_time_min",
    "average_truck_utilisation",
    "crusher_utilisation",
    "average_loader_queue_time_min",
    "average_crusher_queue_time_min",
    "completed_cycles",
]


def _order_results_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _PRIMARY_RESULT_COLUMNS if c in df.columns]
    other = sorted(c for c in df.columns if c not in cols)
    return df[cols + other]


_EVENT_LOG_COLUMNS = [
    "time_min",
    "replication",
    "scenario_id",
    "truck_id",
    "event_type",
    "from_node",
    "to_node",
    "location",
    "loaded",
    "payload_tonnes",
    "resource_id",
    "queue_length",
]


def _order_event_log_columns(df: pd.DataFrame) -> pd.DataFrame:
    cols = [c for c in _EVENT_LOG_COLUMNS if c in df.columns]
    other = [c for c in df.columns if c not in cols]
    return df[cols + other]


def _json_default(obj: Any) -> Any:
    """Make numpy types JSON-serialisable."""
    try:
        import numpy as np

        if isinstance(obj, (np.integer,)):
            return int(obj)
        if isinstance(obj, (np.floating,)):
            return float(obj)
        if isinstance(obj, (np.ndarray,)):
            return obj.tolist()
    except Exception:
        pass
    if hasattr(obj, "item"):
        try:
            return obj.item()
        except Exception:
            pass
    return str(obj)
