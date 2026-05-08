"""Command-line entry point for the mine throughput simulation.

Usage::

    python -m mine_sim run [--scenarios baseline,trucks_4,...|all] \
        [--data-dir data] [--output-dir .] [--event-log-reps 3]

    python -m mine_sim viz [--data-dir data] [--output-dir .] [--scenario baseline]

    python -m mine_sim all   # equivalent to run + viz with defaults
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

from .experiment import run_experiment
from .scenarios import list_required_scenarios


def _print_progress(scenario_id: str, done: int, total: int) -> None:
    sys.stderr.write(f"\r[{scenario_id}] rep {done}/{total}")
    sys.stderr.flush()
    if done == total:
        sys.stderr.write("\n")


def cmd_run(args: argparse.Namespace) -> int:
    if args.scenarios in (None, "all", ""):
        scenario_ids: Optional[List[str]] = None
    else:
        scenario_ids = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    t0 = time.time()
    run_experiment(
        data_dir=Path(args.data_dir),
        output_dir=Path(args.output_dir),
        scenario_ids=scenario_ids,
        event_log_reps=args.event_log_reps,
        progress=_print_progress if not args.quiet else None,
    )
    elapsed = time.time() - t0
    sys.stderr.write(f"Experiment complete in {elapsed:.1f}s. Outputs in {args.output_dir}\n")
    return 0


def cmd_viz(args: argparse.Namespace) -> int:
    from . import visualise
    visualise.write_topology_png(
        data_dir=Path(args.data_dir),
        output_path=Path(args.output_dir) / "topology.png",
        scenario_id=args.scenario,
    )
    if args.animation:
        visualise.write_animation_gif(
            data_dir=Path(args.data_dir),
            event_log_path=Path(args.output_dir) / "event_log.csv",
            output_path=Path(args.output_dir) / "animation.gif",
            scenario_id=args.scenario,
            replication=args.replication,
            fps=args.fps,
            step_min=args.step_min,
        )
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    rc = cmd_run(args)
    if rc != 0:
        return rc
    args.animation = True
    return cmd_viz(args)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m mine_sim", description="Synthetic mine throughput simulation")
    sub = p.add_subparsers(dest="command", required=True)

    p_run = sub.add_parser("run", help="Run the experiment")
    p_run.add_argument("--data-dir", default="data")
    p_run.add_argument("--output-dir", default=".")
    p_run.add_argument("--scenarios", default="all", help="Comma-separated list, or 'all'")
    p_run.add_argument("--event-log-reps", type=int, default=3,
                       help="Number of replications to record in event_log.csv per scenario")
    p_run.add_argument("--quiet", action="store_true")
    p_run.set_defaults(func=cmd_run)

    p_viz = sub.add_parser("viz", help="Generate topology + animation visualisations")
    p_viz.add_argument("--data-dir", default="data")
    p_viz.add_argument("--output-dir", default=".")
    p_viz.add_argument("--scenario", default="baseline")
    p_viz.add_argument("--replication", type=int, default=0)
    p_viz.add_argument("--animation", action="store_true",
                       help="Also produce animation.gif (requires existing event_log.csv)")
    p_viz.add_argument("--fps", type=int, default=10)
    p_viz.add_argument("--step-min", type=float, default=2.0)
    p_viz.set_defaults(func=cmd_viz)

    p_all = sub.add_parser("all", help="Run experiment then produce all visualisations")
    p_all.add_argument("--data-dir", default="data")
    p_all.add_argument("--output-dir", default=".")
    p_all.add_argument("--scenarios", default="all")
    p_all.add_argument("--event-log-reps", type=int, default=3)
    p_all.add_argument("--quiet", action="store_true")
    p_all.add_argument("--scenario", default="baseline", help="Scenario to animate")
    p_all.add_argument("--replication", type=int, default=0)
    p_all.add_argument("--fps", type=int, default=10)
    p_all.add_argument("--step-min", type=float, default=2.0)
    p_all.set_defaults(func=cmd_all)

    p_list = sub.add_parser("list-scenarios", help="List the seven scenarios this submission runs")
    p_list.set_defaults(func=lambda a: (print("\n".join(list_required_scenarios())), 0)[1])

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
