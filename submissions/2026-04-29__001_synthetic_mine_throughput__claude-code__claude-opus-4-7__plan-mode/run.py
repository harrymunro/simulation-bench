"""Entry point for the mine throughput benchmark.

Usage::

    python run.py                       # all six required scenarios, 30 reps each
    python run.py --scenario baseline   # single scenario
    python run.py --replications 2      # smoke test
"""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import pandas as pd

from src.analysis import (
    behavioural_self_check,
    build_summary,
    write_event_log_csv,
    write_results_csv,
    write_summary_json,
)
from src.experiment import run_all


REQUIRED_SCENARIOS = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]

KEY_ASSUMPTIONS = [
    "Capacity-constrained edges (E03 ramp segments, E05 crusher approach, E07 north-pit access, E09 south-pit access) are modelled as SimPy resources with capacity 1; capacity-999 edges are unconstrained timeouts.",
    "E03_UP and E03_DOWN are modelled as two independent capacity-1 resources (as encoded in the data); a single shared bidirectional channel would be marginally more conservative.",
    "Loader and dump times follow truncated normal distributions clipped at 10% of the mean to prevent non-physical small samples.",
    "Per-edge travel time is multiplied by an i.i.d. lognormal noise factor with unit mean (CV=0.10), so noise does not bias mean travel times.",
    "Trucks start at PARK with a uniform [0, 60] second random initial stagger to avoid pathological insertion-order resource ordering at t=0.",
    "Dispatching follows the baseline `nearest_available_loader` policy with a `shortest_expected_cycle_time` tie-breaker; the dispatcher is invoked at the start of every empty leg.",
    "Routes are computed by Dijkstra shortest travel time on the directed graph after applying scenario edge overrides; closed edges are removed entirely.",
    "End-of-shift policy: no new loader requests after 480 minutes; in-flight loaded trucks complete travel and dump (tonnes counted only on dump_end events); empty trucks abort at the end of their current edge.",
    "Tonnes-delivered counts only completed dump events; partial loads in flight at shift end are not counted.",
]

MODEL_LIMITATIONS = [
    "No truck breakdowns, refuelling, operator breaks, or shift-change handovers.",
    "Modelling the up-ramp and down-ramp as two independent resources understates contention slightly versus a real single-lane bidirectional ramp.",
    "Speed factors are applied uniformly per edge; gradient and curvature are not modelled separately.",
    "Travel-time noise is i.i.d. per edge traversal; correlated weather or time-of-day effects are not modelled.",
    "Loader and crusher availability are assumed 100% within the shift.",
    "Routes are recomputed from the shortest-time graph at every dispatch; trucks already en route do not re-plan in response to congestion.",
    "Initial conditions: all trucks at PARK and empty; warm-up is not separately discarded (warmup_minutes = 0 in the baseline config).",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scenario", type=str, default=None,
                        help="Run only this scenario (default: all six required).")
    parser.add_argument("--replications", type=int, default=None,
                        help="Override replications per scenario.")
    parser.add_argument("--data-dir", type=Path,
                        default=Path(__file__).parent / "data")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).parent)
    parser.add_argument("--quiet", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    scenarios = [args.scenario] if args.scenario else REQUIRED_SCENARIOS

    print(f"Running scenarios: {scenarios}")
    print(f"Replications: {args.replications or 'from config (30)'}")
    t0 = time.time()
    results_df, events = run_all(
        data_dir=args.data_dir,
        scenario_ids=scenarios,
        replications=args.replications,
        progress=not args.quiet,
    )
    elapsed = time.time() - t0
    print(f"Simulation finished in {elapsed:.1f}s "
          f"({len(results_df)} replications, {len(events)} events).")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    write_results_csv(results_df, output_dir / "results.csv")
    write_event_log_csv(events, output_dir / "event_log.csv")

    summary = build_summary(
        results_df=results_df,
        scenarios=scenarios,
        benchmark_id="001_synthetic_mine_throughput",
        key_assumptions=KEY_ASSUMPTIONS,
        model_limitations=MODEL_LIMITATIONS,
        additional_scenarios_proposed=[],
    )
    write_summary_json(summary, output_dir / "summary.json")

    print()
    print("Per-scenario mean throughput (tonnes, ± 95% CI):")
    print(f"  {'scenario':20s} {'trucks':>7s} {'mean_t':>10s} {'ci_low':>10s} {'ci_high':>10s}")
    for sid, m in summary["scenarios"].items():
        print(f"  {sid:20s} {m['truck_count']:>7d} "
              f"{m['total_tonnes_mean']:>10.0f} "
              f"{m['total_tonnes_ci95_low']:>10.0f} "
              f"{m['total_tonnes_ci95_high']:>10.0f}")

    if len(scenarios) == len(REQUIRED_SCENARIOS):
        print()
        print("Behavioural self-checks:")
        all_passed = True
        for c in behavioural_self_check(summary):
            mark = "PASS" if c["passed"] else "FAIL"
            print(f"  [{mark}] {c['name']}: {c['description']}")
            all_passed = all_passed and c["passed"]
        print()
        print("All behavioural checks passed." if all_passed
              else "WARNING: some behavioural checks failed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
