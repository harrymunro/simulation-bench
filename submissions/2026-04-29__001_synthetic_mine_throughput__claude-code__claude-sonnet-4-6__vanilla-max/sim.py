"""sim.py — Scenario runner for mine haulage discrete-event simulation.

Usage:
    python sim.py                          # run all scenarios
    python sim.py --scenario baseline      # single scenario
    python sim.py --replications 10        # override replications
    python sim.py --plot                   # also generate topology.png
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
import yaml
from scipy import stats

from sim_core import (
    build_graph,
    extract_metrics,
    run_replication,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SCENARIOS_DIR = DATA / "scenarios"


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data():
    nodes = pd.read_csv(DATA / "nodes.csv")
    edges = pd.read_csv(DATA / "edges.csv")
    trucks = pd.read_csv(DATA / "trucks.csv")
    loaders = pd.read_csv(DATA / "loaders.csv")
    dump_points = pd.read_csv(DATA / "dump_points.csv")
    return nodes, edges, trucks, loaders, dump_points


def load_scenario_yaml(path: Path) -> Dict:
    with open(path) as f:
        return yaml.safe_load(f)


def resolve_scenario(yaml_path: Path, all_yamls: Dict[str, Dict]) -> Dict:
    """Merge inherited base with overrides, returning a flat config dict."""
    raw = load_scenario_yaml(yaml_path)
    base: Dict = {}

    if "inherits" in raw:
        parent_id = raw["inherits"]
        parent_path = SCENARIOS_DIR / f"{parent_id}.yaml"
        base = resolve_scenario(parent_path, all_yamls)

    # Deep merge raw into base
    merged = _deep_merge(base, raw)
    return merged


def _deep_merge(base: Dict, override: Dict) -> Dict:
    result = dict(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(result.get(k), dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def flatten_scenario(merged: Dict) -> Dict:
    """Extract flat config values from nested YAML structure."""
    sim = merged.get("simulation", {})
    routing = merged.get("routing", {})
    stoch = merged.get("stochasticity", {})
    fleet = merged.get("fleet", {})
    production = merged.get("production", {})

    return {
        "scenario_id": merged.get("scenario_id", "unknown"),
        "description": merged.get("description", ""),
        "shift_length_min": sim.get("shift_length_hours", 8) * 60.0,
        "replications": sim.get("replications", 30),
        "base_seed": sim.get("base_random_seed", 12345),
        "noise_cv": stoch.get("travel_time_noise_cv", 0.10),
        "dump_destination": production.get("dump_destination", "CRUSH"),
        "truck_count": fleet.get("truck_count", 8),
        "edge_overrides": merged.get("edge_overrides", {}),
        "node_overrides": merged.get("node_overrides", {}),
        "dump_point_overrides": merged.get("dump_point_overrides", {}),
    }


# ---------------------------------------------------------------------------
# Confidence intervals
# ---------------------------------------------------------------------------

def ci95(values: List[float]) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        v = values[0] if values else 0.0
        return v, v
    m = np.mean(values)
    se = stats.sem(values)
    h = se * stats.t.ppf(0.975, df=n - 1)
    return float(m - h), float(m + h)


# ---------------------------------------------------------------------------
# Run one scenario
# ---------------------------------------------------------------------------

def run_scenario(
    cfg: Dict,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    trucks: pd.DataFrame,
    loaders_df: pd.DataFrame,
    dump_points_df: pd.DataFrame,
    rep_override: Optional[int] = None,
) -> tuple[List[Dict], List[Dict]]:
    scenario_id = cfg["scenario_id"]
    n_reps = rep_override if rep_override is not None else cfg["replications"]
    base_seed = cfg["base_seed"]

    G = build_graph(
        nodes, edges,
        edge_overrides=cfg.get("edge_overrides"),
        node_overrides=cfg.get("node_overrides"),
    )

    # Apply dump point overrides
    dp_overrides = cfg.get("dump_point_overrides", {})
    dump_rows = []
    for _, row in dump_points_df.iterrows():
        d = row.to_dict()
        if row["dump_id"] in dp_overrides:
            d.update(dp_overrides[row["dump_id"]])
        dump_rows.append(d)
    dump_points_resolved = pd.DataFrame(dump_rows)

    dump_node = cfg["dump_destination"]
    dump_point_row = dump_points_resolved[dump_points_resolved["node_id"] == dump_node].iloc[0]
    dump_point = dump_point_row.to_dict()

    loaders = [
        row.to_dict()
        for _, row in loaders_df.iterrows()
        if row["node_id"] in cfg.get("ore_sources",
                                     ["LOAD_N", "LOAD_S"])
        or True  # include all loaders
    ]

    # Only include loaders reachable from PARK
    reachable_loaders = []
    for loader in loaders:
        try:
            import networkx as nx
            nx.shortest_path(G, "PARK", loader["node_id"])
            reachable_loaders.append(loader)
        except Exception:
            pass
    if not reachable_loaders:
        print(f"  WARNING: no loaders reachable in {scenario_id}!", file=sys.stderr)
        reachable_loaders = loaders

    rep_results = []
    all_events = []
    print(f"  Running {n_reps} replications", end="", flush=True)

    for rep in range(n_reps):
        rng = np.random.default_rng(base_seed + rep)
        log_events = (rep == 0)  # only log first replication to keep file size manageable

        state = run_replication(
            cfg, G, reachable_loaders, dump_point, trucks,
            rng, rep, scenario_id, log_events=log_events,
        )

        metrics = extract_metrics(state, cfg, trucks)
        seed_used = base_seed + rep

        rep_results.append({
            "scenario_id": scenario_id,
            "replication": rep + 1,
            "random_seed": seed_used,
            "total_tonnes_delivered": round(metrics["total_tonnes"], 2),
            "tonnes_per_hour": round(metrics["tph"], 3),
            "average_truck_cycle_time_min": round(metrics["avg_cycle_min"], 3),
            "average_truck_utilisation": round(metrics["avg_truck_util"], 4),
            "crusher_utilisation": round(metrics["crusher_util"], 4),
            "average_loader_queue_time_min": round(metrics["avg_loader_q_min"], 3),
            "average_crusher_queue_time_min": round(metrics["avg_crusher_q_min"], 3),
            "n_dumps": metrics["n_dumps"],
        })

        all_events.extend(state.event_log)
        print(".", end="", flush=True)

    print()
    return rep_results, all_events


# ---------------------------------------------------------------------------
# Aggregate scenario results into summary stats
# ---------------------------------------------------------------------------

def aggregate_scenario(rep_results: List[Dict], cfg: Dict) -> Dict:
    tonnes = [r["total_tonnes_delivered"] for r in rep_results]
    tph = [r["tonnes_per_hour"] for r in rep_results]
    cycle = [r["average_truck_cycle_time_min"] for r in rep_results]
    util = [r["average_truck_utilisation"] for r in rep_results]
    crusher_u = [r["crusher_utilisation"] for r in rep_results]
    lq = [r["average_loader_queue_time_min"] for r in rep_results]
    cq = [r["average_crusher_queue_time_min"] for r in rep_results]

    tonnes_lo, tonnes_hi = ci95(tonnes)
    tph_lo, tph_hi = ci95(tph)

    return {
        "replications": len(rep_results),
        "shift_length_hours": cfg["shift_length_min"] / 60.0,
        "total_tonnes_mean": round(float(np.mean(tonnes)), 2),
        "total_tonnes_ci95_low": round(tonnes_lo, 2),
        "total_tonnes_ci95_high": round(tonnes_hi, 2),
        "tonnes_per_hour_mean": round(float(np.mean(tph)), 3),
        "tonnes_per_hour_ci95_low": round(tph_lo, 3),
        "tonnes_per_hour_ci95_high": round(tph_hi, 3),
        "average_cycle_time_min": round(float(np.mean(cycle)), 3),
        "truck_utilisation_mean": round(float(np.mean(util)), 4),
        "crusher_utilisation": round(float(np.mean(crusher_u)), 4),
        "average_loader_queue_time_min": round(float(np.mean(lq)), 3),
        "average_crusher_queue_time_min": round(float(np.mean(cq)), 3),
        "top_bottlenecks": _identify_bottlenecks(
            float(np.mean(crusher_u)), float(np.mean(lq)), float(np.mean(cq)),
            float(np.mean(util))
        ),
    }


def _identify_bottlenecks(crusher_u, lq, cq, truck_u) -> List[str]:
    bottlenecks = []
    if crusher_u > 0.80:
        bottlenecks.append(f"Crusher highly utilised ({crusher_u:.1%})")
    if cq > 2.0:
        bottlenecks.append(f"Long crusher queue (avg {cq:.1f} min wait)")
    if lq > 2.0:
        bottlenecks.append(f"Long loader queue (avg {lq:.1f} min wait)")
    if truck_u > 0.90:
        bottlenecks.append(f"Trucks near saturation (avg util {truck_u:.1%})")
    if not bottlenecks:
        bottlenecks.append("No severe bottleneck detected")
    return bottlenecks


# ---------------------------------------------------------------------------
# Write outputs
# ---------------------------------------------------------------------------

def write_results_csv(all_rep_results: List[Dict]) -> None:
    df = pd.DataFrame(all_rep_results)
    df.to_csv(ROOT / "results.csv", index=False)
    print(f"  Written results.csv ({len(df)} rows)")


def write_summary_json(scenario_summaries: Dict, scenario_cfgs: Dict) -> None:
    key_assumptions = [
        "Trucks follow shortest travel-time routes recalculated at each dispatch decision",
        "Loading and dumping service times are truncated-normal (truncated at zero)",
        "Travel time noise is lognormal with CV=0.10 (mean preserved at 1.0x)",
        "Capacity-constrained road segments (capacity=1) are SimPy Resources; only one truck traverses at a time",
        "Loaders and crusher have capacity 1 (single-server queues, FIFO)",
        "All trucks are identical (100 t payload, loaded speed factor 0.85)",
        "Shift warmup is zero; trucks depart from PARK at time 0",
        "Trucks that complete a dump after shift_end are not counted (strict cutoff)",
        "Dispatching: nearest-available-loader with queue-length penalty",
        "All 12 trucks available; fleet scenarios select the first N from trucks.csv",
    ]
    model_limitations = [
        "No fuel or shift-change delays modelled",
        "No truck breakdowns or maintenance schedules",
        "Dispatch does not account for congestion on capacity-1 roads",
        "Travel noise is independent between edges (no correlated delays)",
        "Loader availability is 100% throughout the shift",
        "Waste haulage not modelled (all ore goes to crusher)",
        "Parking delays at shift start not modelled",
    ]

    payload = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": scenario_summaries,
        "key_assumptions": key_assumptions,
        "model_limitations": model_limitations,
        "additional_scenarios_proposed": [
            {
                "id": "loader_upgrade",
                "description": "Reduce LOAD_N service time mean from 6.5 to 4.5 min (match LOAD_S) "
                               "to test whether loader speed at North Pit limits throughput.",
            }
        ],
    }

    with open(ROOT / "summary.json", "w") as f:
        json.dump(payload, f, indent=2)
    print("  Written summary.json")


def write_event_log(all_events: List[Dict]) -> None:
    if not all_events:
        pd.DataFrame(
            columns=["time_min", "replication", "scenario_id", "truck_id",
                     "event_type", "from_node", "to_node", "location",
                     "loaded", "payload_tonnes", "resource_id", "queue_length"]
        ).to_csv(ROOT / "event_log.csv", index=False)
    else:
        df = pd.DataFrame(all_events)
        df.to_csv(ROOT / "event_log.csv", index=False)
    print(f"  Written event_log.csv ({len(all_events)} events)")


# ---------------------------------------------------------------------------
# Topology visualisation
# ---------------------------------------------------------------------------

def plot_topology(nodes: pd.DataFrame, edges: pd.DataFrame) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
    except ImportError:
        print("  matplotlib not available, skipping topology plot")
        return

    fig, ax = plt.subplots(figsize=(14, 10))

    color_map = {
        "parking": "#888888",
        "junction": "#4A90D9",
        "load_ore": "#E67E22",
        "crusher": "#E74C3C",
        "waste_dump": "#95A5A6",
        "maintenance": "#8E44AD",
    }

    pos = {row["node_id"]: (row["x_m"], row["y_m"]) for _, row in nodes.iterrows()}

    # Draw edges
    for _, row in edges.iterrows():
        x0, y0 = pos[row["from_node"]]
        x1, y1 = pos[row["to_node"]]
        cap = int(row["capacity"])
        lw = 3.0 if cap < 10 else 1.0
        color = "#E74C3C" if cap < 10 else "#BDC3C7"
        ax.annotate(
            "", xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(arrowstyle="-|>", color=color, lw=lw,
                            connectionstyle="arc3,rad=0.05"),
        )

    # Draw nodes
    for _, row in nodes.iterrows():
        x, y = pos[row["node_id"]]
        c = color_map.get(row["node_type"], "#2ECC71")
        ax.scatter(x, y, s=300, c=c, zorder=5, edgecolors="white", linewidths=1.5)
        ax.text(x, y + 80, row["node_name"], ha="center", va="bottom", fontsize=7,
                fontweight="bold")

    # Legend
    patches = [
        mpatches.Patch(color=v, label=k.replace("_", " ").title())
        for k, v in color_map.items()
    ]
    patches.append(mpatches.Patch(color="#E74C3C", label="Constrained road (cap=1)"))
    patches.append(mpatches.Patch(color="#BDC3C7", label="Unconstrained road"))
    ax.legend(handles=patches, loc="upper left", fontsize=8)

    ax.set_title("Mine Topology — Node and Road Network", fontsize=13, fontweight="bold")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal")
    ax.grid(True, alpha=0.2)

    plt.tight_layout()
    plt.savefig(ROOT / "topology.png", dpi=150, bbox_inches="tight")
    plt.close()
    print("  Written topology.png")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

SCENARIO_ORDER = [
    "baseline", "trucks_4", "trucks_12",
    "ramp_upgrade", "crusher_slowdown", "ramp_closed",
]


def main():
    parser = argparse.ArgumentParser(description="Mine haulage DES runner")
    parser.add_argument("--scenario", default=None, help="Single scenario to run")
    parser.add_argument("--replications", type=int, default=None,
                        help="Override number of replications")
    parser.add_argument("--plot", action="store_true", help="Generate topology.png")
    args = parser.parse_args()

    t0 = time.time()
    print("Loading data...")
    nodes, edges, trucks, loaders_df, dump_points_df = load_data()

    if args.plot:
        print("Generating topology plot...")
        plot_topology(nodes, edges)

    scenarios_to_run = [args.scenario] if args.scenario else SCENARIO_ORDER

    all_rep_results: List[Dict] = []
    all_events: List[Dict] = []
    scenario_summaries: Dict = {}
    scenario_cfgs: Dict = {}

    for sid in scenarios_to_run:
        yaml_path = SCENARIOS_DIR / f"{sid}.yaml"
        if not yaml_path.exists():
            print(f"  Scenario file not found: {yaml_path}", file=sys.stderr)
            continue

        print(f"\nScenario: {sid}")
        merged = resolve_scenario(yaml_path, {})
        cfg = flatten_scenario(merged)
        scenario_cfgs[sid] = cfg

        rep_results, events = run_scenario(
            cfg, nodes, edges, trucks, loaders_df, dump_points_df,
            rep_override=args.replications,
        )
        all_rep_results.extend(rep_results)
        all_events.extend(events)

        summary = aggregate_scenario(rep_results, cfg)
        scenario_summaries[sid] = summary

        mean_t = summary["total_tonnes_mean"]
        ci_lo = summary["total_tonnes_ci95_low"]
        ci_hi = summary["total_tonnes_ci95_high"]
        tph = summary["tonnes_per_hour_mean"]
        print(f"  Throughput: {mean_t:.0f} t  [{ci_lo:.0f}–{ci_hi:.0f}]  ({tph:.1f} t/h)")

    print("\nWriting outputs...")
    write_results_csv(all_rep_results)
    write_summary_json(scenario_summaries, scenario_cfgs)
    write_event_log(all_events)

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.1f}s")
    _print_summary(scenario_summaries)


def _print_summary(summaries: Dict) -> None:
    print("\n" + "=" * 72)
    print(f"{'Scenario':<20} {'Mean t':>8} {'95% CI':>16} {'t/h':>7} "
          f"{'Crusher%':>9} {'CrusherQ min':>13}")
    print("-" * 72)
    for sid, s in summaries.items():
        ci_str = f"[{s['total_tonnes_ci95_low']:.0f}–{s['total_tonnes_ci95_high']:.0f}]"
        print(f"{sid:<20} {s['total_tonnes_mean']:>8.0f} {ci_str:>16} "
              f"{s['tonnes_per_hour_mean']:>7.1f} "
              f"{s['crusher_utilisation']:>9.1%} "
              f"{s['average_crusher_queue_time_min']:>13.2f}")
    print("=" * 72)


if __name__ == "__main__":
    main()
