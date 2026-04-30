"""Command-line entry point for the synthetic mine throughput simulation.

Usage:
    python run.py --scenario all --replications 30
    python run.py --scenario baseline --replications 5
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from src.run_experiments import run_all


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run synthetic mine throughput SimPy simulation."
    )
    parser.add_argument(
        "--scenario",
        default="all",
        help='Scenario id, comma-separated list, or "all" (default: all).',
    )
    parser.add_argument(
        "--replications",
        type=int,
        default=None,
        help="Override replications per scenario (default: from scenario YAML, usually 30).",
    )
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Path to the data directory (default: ./data).",
    )
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Where to write results.csv, summary.json, event_log.csv (default: .).",
    )
    parser.add_argument(
        "--event-log-max-reps",
        type=int,
        default=5,
        help="Maximum replications per scenario to include in event_log.csv (default: 5).",
    )
    parser.add_argument(
        "--warmup-minutes",
        type=float,
        default=None,
        help=(
            "Override simulation.warmup_minutes for every scenario "
            "(default: honour the per-scenario YAML value, currently 0)."
        ),
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-replication progress output.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    data_dir = Path(args.data_dir)
    output_dir = Path(args.output_dir)

    if args.scenario == "all":
        scenarios: list[str] | None = None
    else:
        scenarios = [s.strip() for s in args.scenario.split(",") if s.strip()]

    try:
        run_all(
            data_dir=data_dir,
            output_dir=output_dir,
            scenarios=scenarios,
            replications_override=args.replications,
            event_log_max_reps_per_scenario=args.event_log_max_reps,
            warmup_minutes_override=args.warmup_minutes,
            verbose=not args.quiet,
        )
    except Exception as exc:  # pylint: disable=broad-except
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
