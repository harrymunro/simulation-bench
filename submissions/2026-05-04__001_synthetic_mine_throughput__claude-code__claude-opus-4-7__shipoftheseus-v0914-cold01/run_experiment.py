"""CLI driver — runs all scenarios, all replications, and writes outputs.

Usage:
    python run_experiment.py [--data-dir PATH] [--out-dir PATH] [--scenarios a,b,c]

Reproduces results.csv, summary.json, event_log.csv.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List

import pandas as pd

from mine_sim.analysis import aggregate_scenario
from mine_sim.event_log import EVENT_COLUMNS, write_event_log
from mine_sim.experiment import run_replication
from mine_sim.scenario import load_scenarios

ROOT = Path(__file__).resolve().parent
DEFAULT_DATA = ROOT / "data"
DEFAULT_OUT = ROOT / "outputs"
DEFAULT_SCENARIOS = [
    "baseline", "trucks_4", "trucks_12",
    "ramp_upgrade", "crusher_slowdown", "ramp_closed",
]


def parse_args(argv: List[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", default=str(DEFAULT_DATA))
    p.add_argument("--out-dir", default=str(DEFAULT_OUT))
    p.add_argument("--scenarios", default=",".join(DEFAULT_SCENARIOS),
                    help="Comma-separated scenario names")
    p.add_argument("--replications", type=int, default=None,
                    help="Override per-scenario replications (default: from baseline yaml)")
    return p.parse_args(argv)


def main(argv: List[str]) -> int:
    t_start = time.time()
    args = parse_args(argv)
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    event_log_path = out_dir / "event_log.csv"
    if event_log_path.exists():
        event_log_path.unlink()

    nodes_df = pd.read_csv(data_dir / "nodes.csv", dtype={"node_id": str})
    edges_df = pd.read_csv(data_dir / "edges.csv", dtype={"edge_id": str, "from_node": str,
                                                             "to_node": str})
    trucks_df = pd.read_csv(data_dir / "trucks.csv", dtype={"truck_id": str})
    loaders_df = pd.read_csv(data_dir / "loaders.csv", dtype={"loader_id": str, "node_id": str})
    dump_df = pd.read_csv(data_dir / "dump_points.csv", dtype={"dump_id": str, "node_id": str})

    scenario_names = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    scenarios = load_scenarios(data_dir / "scenarios", scenario_names)

    all_rows = []
    summary = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "harness": "theseus-orchestrator-v0.9.14",
        "run_label": "v0914_cold01",
        "scenarios": {},
        "key_assumptions": [
            "Trucks are homogeneous (100 t payload, empty_speed_factor=1.00, loaded=0.85).",
            "Routing: shortest-time Dijkstra on directed graph; recomputed per scenario after applying overrides.",
            "Dispatching: nearest-available-loader by expected (path_time + queue_wait); tie-break shortest expected cycle.",
            "Stochasticity: load/dump times truncated normal (clamped 0.5×–2.0× mean); travel-time multiplicative lognormal with sigma = scenario.stochasticity.travel_time_noise_cv (default 0.10).",
            "Capacity-bounded edges (cap <= 10) modelled as SimPy Resources; high-capacity haul roads bypass resource holds.",
            "Tonnes credited only on dump_end event at the crusher.",
            "Shift length = 8 hours; trucks may complete an in-flight cycle up to 30 min past shift_end (drain) but no new dispatch occurs.",
            "Random seed per (scenario_index, replication) = 12345 + 1000 × scenario_idx + replication_idx.",
        ],
        "model_limitations": [
            "No truck breakdowns / refuelling / shift changes.",
            "Waste haulage not modelled (ore-only baseline; no scenario specifies waste delivery).",
            "Truncated normal clamping is symmetric and may under-represent extreme delays.",
            "Edge resources are FIFO without preemption; reality may include passing on wide haul roads — not modelled.",
            "Crusher hopper capacity is treated as 1 (one truck at a time); no queue buffer modelled separately from the SimPy queue.",
        ],
        "additional_scenarios_proposed": [
            {
                "scenario_id": "trucks_10_ramp_upgrade",
                "rationale": "Combined fleet sensitivity with ramp upgrade — would isolate whether ramp is binding for >8 trucks.",
            },
        ],
    }

    scenario_idx_map = {name: i for i, name in enumerate(scenario_names)}
    repl_override = args.replications

    print(f"[run_experiment] starting {len(scenario_names)} scenarios", flush=True)
    for name in scenario_names:
        cfg = scenarios[name]
        cfg.setdefault("scenario_id", name)
        sim_cfg = cfg.get("simulation", {})
        base_seed = int(sim_cfg.get("base_random_seed", 12345))
        replications = int(repl_override or sim_cfg.get("replications", 30))
        scenario_idx = scenario_idx_map[name]
        t_scn0 = time.time()
        scn_rows = []
        scn_event_rows = []
        for r in range(replications):
            row, ev_rows = run_replication(cfg, nodes_df, edges_df, trucks_df, loaders_df,
                                            dump_df, base_seed, scenario_idx, r)
            scn_rows.append(row)
            scn_event_rows.extend(ev_rows)
        # Stream per-scenario event rows
        write_event_log(scn_event_rows, event_log_path,
                         append=(scenario_idx > 0))
        all_rows.extend(scn_rows)
        scn_df = pd.DataFrame(scn_rows)
        summary["scenarios"][name] = aggregate_scenario(scn_df, cfg)
        elapsed = time.time() - t_scn0
        mean_tph = summary["scenarios"][name]["tonnes_per_hour"]["mean"]
        print(f"  {name}: {replications} reps, {len(scn_event_rows)} events, "
              f"mean t/h={mean_tph:.1f}, elapsed={elapsed:.1f}s", flush=True)

    results_df = pd.DataFrame(all_rows)
    results_df.to_csv(out_dir / "results.csv", index=False)

    summary["wall_clock_seconds"] = round(time.time() - t_start, 2)
    summary["results_csv_rows"] = int(len(results_df))
    summary["event_log_rows"] = sum(1 for _ in open(event_log_path, "r", encoding="utf-8")) - 1

    with open(out_dir / "summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, indent=2)

    print(f"[run_experiment] done in {time.time()-t_start:.1f}s "
          f"({len(results_df)} result rows, {summary['event_log_rows']} event rows)",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
