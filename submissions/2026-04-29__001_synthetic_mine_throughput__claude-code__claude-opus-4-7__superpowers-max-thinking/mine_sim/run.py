"""CLI entry point: `python -m mine_sim.run`."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from mine_sim.experiment import run_scenario
from mine_sim.report import write_outputs
from mine_sim.scenario import load_scenario


REQUIRED_SCENARIOS = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]


def _here() -> Path:
    """Submission root (the directory containing the `mine_sim/` package)."""
    return Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Mine throughput simulation.")
    parser.add_argument(
        "--scenario", action="append", dest="scenarios",
        help="Scenario id to run (repeatable). Default: all six required scenarios.",
    )
    parser.add_argument(
        "--replications", type=int, default=None,
        help="Override replications count (e.g. 5 for smoke testing).",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=_here() / "data",
        help="Path to data/ directory.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=_here() / "results",
        help="Path to results/ directory.",
    )
    args = parser.parse_args(argv)

    scenarios_dir = args.data_dir / "scenarios"
    scenario_ids = args.scenarios or REQUIRED_SCENARIOS

    results = []
    for sid in scenario_ids:
        cfg = load_scenario(sid, scenarios_dir)
        if args.replications is not None:
            cfg["simulation"]["replications"] = args.replications
        n = cfg["simulation"]["replications"]
        print(f"[{sid}] running {n} replications...", flush=True)
        t0 = time.perf_counter()
        result = run_scenario(cfg, data_dir=args.data_dir)
        dt = time.perf_counter() - t0
        tonnes = [r.total_tonnes() for r in result.replications]
        mean_t = sum(tonnes) / len(tonnes) if tonnes else 0.0
        print(f"[{sid}] done in {dt:.1f}s; mean total_tonnes = {mean_t:.0f}", flush=True)
        results.append(result)

    write_outputs(results, output_dir=args.output_dir)
    print(f"Wrote outputs to {args.output_dir}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
