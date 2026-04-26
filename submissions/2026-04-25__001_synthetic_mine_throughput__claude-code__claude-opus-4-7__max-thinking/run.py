"""Top-level runner: execute all scenarios and write outputs."""
from __future__ import annotations

import argparse
import time
from pathlib import Path
from typing import List

from src.experiment import run_scenario, write_outputs


REQUIRED_SCENARIOS: List[str] = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]


KEY_ASSUMPTIONS = [
    "Trucks start the shift at PARK and dispatch immediately.",
    "Loading and dumping times are normal-truncated using means/SDs from the data; "
    "lower bound = max(0.05 min, mean - 3 SD).",
    "Travel times are nominal distance/speed adjusted by truck loaded/empty speed factor, "
    "perturbed multiplicatively by a lognormal noise with CV from scenario stochasticity.travel_time_noise_cv.",
    "Edges with capacity < 999 are modelled as SimPy resources. Edges sharing a lane id "
    "(same prefix before the first underscore, e.g. E03_UP and E03_DOWN) share a single "
    "physical-lane resource because the data flags them as the same physical constraint.",
    "Routing uses NetworkX shortest-time paths over the directed road graph. Closed edges "
    "are removed from the graph before routing.",
    "Dispatch policy: nearest_available_loader; tiebreaker: shortest expected cycle time. "
    "Expected cycle time considers travel, service, and queue at the candidate loader.",
    "Throughput counts only completed dump events at CRUSH within the 8-hour shift.",
    "Trucks do not refuel or visit maintenance during the shift; the MAINT node is in the "
    "topology but unused under baseline dispatching.",
    "Waste haulage is excluded from baseline analysis (no waste cycles dispatched).",
    "Fleet is homogeneous: 100 t payload, 1.00 empty / 0.85 loaded speed factors.",
]


MODEL_LIMITATIONS = [
    "No truck breakdowns or maintenance interruptions.",
    "No driver shift changes or breaks within the 8-hour shift.",
    "Crusher is always available; no crusher downtime / chute-blocked events.",
    "No congestion model on uncapacitated edges (capacity=999); only single-lane segments queue.",
    "Loaders are always available; no operator changes or refuelling.",
    "Truck cycles are assumed to start at PARK and end mid-cycle when the shift clock expires; "
    "tonnes in-flight at shift end are not counted.",
    "Routing is static (computed once on the open graph); no dynamic re-routing in response to congestion.",
]


ADDITIONAL_SCENARIOS_PROPOSED = [
    "trucks_10: an interpolated fleet point between 8 and 12 to confirm saturation, "
    "executed alongside the required scenarios when --extras is passed.",
]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run mine throughput simulation")
    parser.add_argument("--data-dir", default="data", help="Path to data directory")
    parser.add_argument("--scenario-dir", default=None,
                        help="Path to scenario directory (default: <data-dir>/scenarios)")
    parser.add_argument("--out-dir", default=".", help="Output directory")
    parser.add_argument("--scenarios", nargs="+", default=None,
                        help="Subset of scenario IDs to run (default: required six)")
    parser.add_argument("--event-log-reps", type=int, default=1,
                        help="Number of replications per scenario for which to capture the full event log")
    parser.add_argument("--extras", action="store_true",
                        help="Also run optional extra scenarios (e.g. trucks_10)")
    args = parser.parse_args(argv)

    data_dir = Path(args.data_dir)
    scenario_dir = Path(args.scenario_dir) if args.scenario_dir else data_dir / "scenarios"
    out_dir = Path(args.out_dir)

    scenarios_to_run = list(args.scenarios) if args.scenarios else list(REQUIRED_SCENARIOS)
    if args.extras and "trucks_10" not in scenarios_to_run:
        scenarios_to_run.append("trucks_10")

    capture_reps = list(range(min(args.event_log_reps, 30)))

    results = []
    t0 = time.time()
    for sid in scenarios_to_run:
        ts = time.time()
        print(f"[run] {sid}: starting...", flush=True)
        result = run_scenario(
            scenario_id=sid,
            data_dir=data_dir,
            scenario_dir=scenario_dir,
            capture_event_log_reps=capture_reps,
        )
        s = result["summary"]
        elapsed = time.time() - ts
        print(
            f"[run] {sid}: done in {elapsed:.1f}s | "
            f"tonnes mean={s['total_tonnes_mean']:.1f} "
            f"[{s['total_tonnes_ci95_low']:.1f}, {s['total_tonnes_ci95_high']:.1f}] | "
            f"tph mean={s['tonnes_per_hour_mean']:.1f} | "
            f"crusher_util={s['crusher_utilisation']:.2f}",
            flush=True,
        )
        results.append(result)

    write_outputs(
        out_dir=out_dir,
        scenarios=results,
        benchmark_id="001_synthetic_mine_throughput",
        key_assumptions=KEY_ASSUMPTIONS,
        model_limitations=MODEL_LIMITATIONS,
        additional_scenarios_proposed=ADDITIONAL_SCENARIOS_PROPOSED,
    )
    print(f"[run] all done in {time.time() - t0:.1f}s", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
