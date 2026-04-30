"""Command-line interface for the mine throughput simulation.

Two subcommands are exposed::

    python -m mine_sim run <scenario_id>     # one scenario
    python -m mine_sim run-all               # every required scenario

Both write per-scenario artefacts to ``<output-dir>/<scenario_id>/``:

* ``results.csv``    — per-replication KPI row (Seed-pinned columns).
* ``event_log.csv``  — every :class:`~mine_sim.events.EventRecord` from
  every replication for that scenario.
* ``summary.json``   — the cross-replication
  :class:`~mine_sim.aggregate.ScenarioSummary` plus narrative fields.

The ``run-all`` command additionally writes *combined* artefacts at the
top level of ``<output-dir>``:

* ``results.csv``    — every replication from every scenario, sorted by
  ``(scenario_id, replication)``.
* ``event_log.csv``  — the concatenated event stream.
* ``summary.json``   — a single :class:`~mine_sim.aggregate.RunSummary`
  with one entry per scenario.

Design contracts:

* Inputs default to the canonical paths inside the submission folder
  (``data/`` for CSVs, ``data/scenarios/`` for YAMLs, ``runs/<timestamp>``
  for outputs) but every path is overridable on the command line.
* Each replication uses ``random_seed = base + replication_index`` —
  the contract enforced by :mod:`mine_sim.scenario_runner` and
  :mod:`mine_sim.runner`. The CLI never mutates seeds.
* The CLI is *side-effect-only* at the boundary: every business
  decision lives in :mod:`mine_sim.scenario_runner` /
  :mod:`mine_sim.aggregate` / :mod:`mine_sim.io_writers`, so the same
  calls can be driven from a notebook or a test harness.
"""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from mine_sim.aggregate import (
    RunSummary,
    ScenarioSummary,
    aggregate_run,
    aggregate_scenario,
)
from mine_sim.io_writers import (
    DEFAULT_BENCHMARK_ID,
    collect_events,
    write_event_log_csv,
    write_results_csv,
    write_run_summary_json,
    write_scenario_summary_json,
)
from mine_sim.scenario_runner import (
    MultiScenarioRunResult,
    ReplicationProgress,
    ScenarioRunResult,
    run_all_scenarios,
    run_scenario,
)
from mine_sim.scenarios import (
    REQUIRED_SCENARIO_IDS,
    ScenarioConfig,
    load_all_scenarios,
    load_scenario,
)


# ---------------------------------------------------------------------------
# Default paths — relative to the current working directory.
# ---------------------------------------------------------------------------
DEFAULT_DATA_DIR = Path("data")
DEFAULT_SCENARIOS_DIR = Path("data") / "scenarios"
DEFAULT_OUTPUT_DIR = Path("runs")


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construct the top-level :class:`argparse.ArgumentParser`."""
    parser = argparse.ArgumentParser(
        prog="python -m mine_sim",
        description=(
            "SimPy mine throughput simulation. Use 'run' for one scenario "
            "or 'run-all' for every required scenario in one batch."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    _add_run_parser(subparsers)
    _add_run_all_parser(subparsers)
    _add_list_parser(subparsers)

    return parser


def _add_common_args(sub: argparse.ArgumentParser) -> None:
    sub.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help=(
            "Directory containing input CSVs (nodes.csv, edges.csv, "
            "trucks.csv, loaders.csv, dump_points.csv). Default: ./data"
        ),
    )
    sub.add_argument(
        "--scenarios-dir",
        type=Path,
        default=DEFAULT_SCENARIOS_DIR,
        help="Directory containing scenario YAMLs. Default: ./data/scenarios",
    )
    sub.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Root directory for run artefacts. Default: ./runs/<timestamp> "
            "for run-all, or ./runs/<scenario_id> for run."
        ),
    )
    sub.add_argument(
        "--reps",
        type=int,
        default=None,
        help=(
            "Override the replication count from the scenario YAML "
            "(useful for smoke tests). When omitted, uses 30."
        ),
    )
    sub.add_argument(
        "--rep-indices",
        type=str,
        default=None,
        help=(
            "Comma-separated explicit replication indices to run "
            "(e.g. '0,1,2'). Overrides --reps if provided."
        ),
    )
    sub.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-replication progress output.",
    )


def _add_run_parser(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    sub = subparsers.add_parser(
        "run",
        help="Run a single scenario (30 reps by default).",
        description=(
            "Run every replication for a single scenario and persist "
            "results.csv, event_log.csv, summary.json under "
            "<output-dir>/<scenario_id>/."
        ),
    )
    sub.add_argument(
        "scenario_id",
        help="Scenario ID to run (e.g. 'baseline', 'trucks_12_ramp_upgrade').",
    )
    _add_common_args(sub)


def _add_run_all_parser(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    sub = subparsers.add_parser(
        "run-all",
        help="Run every required scenario (30 reps each by default).",
        description=(
            "Run every scenario listed in mine_sim.scenarios.REQUIRED_SCENARIO_IDS "
            "(default: the canonical 7) and persist per-scenario artefacts "
            "plus combined artefacts at the top level of <output-dir>."
        ),
    )
    sub.add_argument(
        "--scenario-ids",
        type=str,
        default=None,
        help=(
            "Optional comma-separated subset of scenario IDs to run "
            "(default: all required scenarios in canonical order)."
        ),
    )
    _add_common_args(sub)


def _add_list_parser(
    subparsers: argparse._SubParsersAction,  # type: ignore[type-arg]
) -> None:
    sub = subparsers.add_parser(
        "list",
        help="List available scenario IDs found in --scenarios-dir.",
    )
    sub.add_argument(
        "--scenarios-dir",
        type=Path,
        default=DEFAULT_SCENARIOS_DIR,
        help="Directory containing scenario YAMLs. Default: ./data/scenarios",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _parse_rep_indices(raw: str | None) -> tuple[int, ...] | None:
    if raw is None or raw.strip() == "":
        return None
    indices = []
    for token in raw.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            indices.append(int(token))
        except ValueError as exc:
            raise SystemExit(
                f"Invalid replication index '{token}' in --rep-indices."
            ) from exc
    return tuple(indices)


def _parse_scenario_ids(raw: str | None) -> tuple[str, ...] | None:
    if raw is None or raw.strip() == "":
        return None
    ids = tuple(token.strip() for token in raw.split(",") if token.strip())
    return ids if ids else None


def _resolve_replication_indices(
    rep_indices_str: str | None,
    reps: int | None,
) -> tuple[int, ...] | None:
    """Decide the explicit replication index sequence (or ``None``)."""
    explicit = _parse_rep_indices(rep_indices_str)
    if explicit is not None:
        return explicit
    if reps is not None:
        if reps <= 0:
            raise SystemExit(f"--reps must be > 0 (got {reps}).")
        return tuple(range(reps))
    return None


def _override_replications_for_scenarios(
    scenarios: dict[str, ScenarioConfig],
    reps: int | None,
) -> dict[str, ScenarioConfig]:
    """Apply ``--reps`` to every scenario's :class:`SimulationParams`.

    Only used when ``--rep-indices`` is *not* supplied. When neither
    option is supplied each scenario keeps its YAML-defined count.
    """
    if reps is None:
        return scenarios
    from dataclasses import replace

    out: dict[str, ScenarioConfig] = {}
    for scenario_id, scenario in scenarios.items():
        new_sim = replace(scenario.simulation, replications=reps)
        out[scenario_id] = replace(scenario, simulation=new_sim)
    return out


def _override_replications_for_scenario(
    scenario: ScenarioConfig,
    reps: int | None,
) -> ScenarioConfig:
    if reps is None:
        return scenario
    from dataclasses import replace

    new_sim = replace(scenario.simulation, replications=reps)
    return replace(scenario, simulation=new_sim)


def _make_progress_printer(quiet: bool):
    """Return a :class:`ProgressCallback` that writes to stdout, or ``None``."""
    if quiet:
        return None
    start_time = [time.monotonic()]

    def _printer(event: ReplicationProgress) -> None:
        elapsed = time.monotonic() - start_time[0]
        completed = event.replication_index + 1
        rep_total = event.replication_total
        scenario_label = (
            f"[{event.scenario_index + 1}/{event.scenario_total}] "
            f"{event.scenario_id}"
        )
        rep_label = f"rep {event.replication_index + 1}/{rep_total}"
        tonnes = event.result.metrics.total_tonnes_delivered
        tph = event.result.metrics.tonnes_per_hour
        sys.stdout.write(
            f"  {scenario_label} {rep_label} "
            f"tonnes={tonnes:.0f} tph={tph:.1f} "
            f"({elapsed:.1f}s elapsed)\n"
        )
        sys.stdout.flush()

    return _printer


def _resolve_output_dir(
    output_dir: Path | None,
    *,
    label: str,
    timestamp_prefix: bool,
) -> Path:
    """Pick the output directory.

    * ``timestamp_prefix=True`` (run-all): default is ``runs/<UTC>__<label>``.
    * ``timestamp_prefix=False`` (run): default is ``runs/<label>``.

    An explicit ``--output-dir`` is honoured verbatim.
    """
    if output_dir is not None:
        return output_dir
    if timestamp_prefix:
        stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
        return DEFAULT_OUTPUT_DIR / f"{stamp}__{label}"
    return DEFAULT_OUTPUT_DIR / label


# ---------------------------------------------------------------------------
# Per-scenario writer
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScenarioOutputPaths:
    """Paths written for a single scenario's directory."""

    directory: Path
    results_csv: Path
    event_log_csv: Path
    summary_json: Path


def write_scenario_outputs(
    scenario_result: ScenarioRunResult,
    scenario_summary: ScenarioSummary,
    scenario_dir: Path,
) -> ScenarioOutputPaths:
    """Persist all three artefacts for a single scenario."""
    scenario_dir.mkdir(parents=True, exist_ok=True)

    results_path = write_results_csv(
        scenario_result.replications, scenario_dir / "results.csv"
    )
    event_log_path = write_event_log_csv(
        collect_events(scenario_result.replications),
        scenario_dir / "event_log.csv",
    )
    summary_path = write_scenario_summary_json(
        scenario_summary, scenario_dir / "summary.json"
    )

    return ScenarioOutputPaths(
        directory=scenario_dir,
        results_csv=results_path,
        event_log_csv=event_log_path,
        summary_json=summary_path,
    )


# ---------------------------------------------------------------------------
# Run-level writer
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RunOutputPaths:
    """Paths written for a multi-scenario run (combined artefacts)."""

    directory: Path
    results_csv: Path
    event_log_csv: Path
    summary_json: Path
    scenarios: dict[str, ScenarioOutputPaths]


def write_run_outputs(
    multi: MultiScenarioRunResult,
    run_summary: RunSummary,
    output_dir: Path,
    *,
    expected_scenario_ids: Sequence[str] | None = None,
    expected_replications: int | None = None,
    expected_shift_length_hours: float | None = None,
) -> RunOutputPaths:
    """Persist per-scenario artefacts plus combined top-level artefacts.

    The combined ``summary.json`` is validated against the expected run
    shape (``expected_replications``, ``expected_shift_length_hours``,
    ``expected_scenario_ids``) before being written. When invoked from
    the canonical ``run-all`` CLI path these default to the Seed AC's
    fixed values (30 replications, 8 hours, all required scenario ids).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    scenario_paths: dict[str, ScenarioOutputPaths] = {}
    all_replications = []
    all_events = []

    for scenario_id, scenario_result in multi.results.items():
        scenario_summary = run_summary.scenarios[scenario_id]
        scenario_dir = output_dir / scenario_id
        paths = write_scenario_outputs(
            scenario_result, scenario_summary, scenario_dir
        )
        scenario_paths[scenario_id] = paths
        all_replications.extend(scenario_result.replications)
        all_events.extend(collect_events(scenario_result.replications))

    # Combined top-level artefacts -----------------------------------------
    combined_results = write_results_csv(all_replications, output_dir / "results.csv")
    combined_events = write_event_log_csv(all_events, output_dir / "event_log.csv")
    combined_summary = write_run_summary_json(
        run_summary,
        output_dir / "summary.json",
        expected_scenario_ids=expected_scenario_ids,
        expected_replications=expected_replications,
        expected_shift_length_hours=expected_shift_length_hours,
        expected_benchmark_id=DEFAULT_BENCHMARK_ID,
    )

    return RunOutputPaths(
        directory=output_dir,
        results_csv=combined_results,
        event_log_csv=combined_events,
        summary_json=combined_summary,
        scenarios=scenario_paths,
    )


# ---------------------------------------------------------------------------
# Command handlers
# ---------------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    """Execute the ``run <scenario_id>`` subcommand."""
    scenario_yaml = args.scenarios_dir / f"{args.scenario_id}.yaml"
    if not scenario_yaml.exists():
        sys.stderr.write(
            f"Scenario YAML not found: {scenario_yaml}\n"
            f"Use 'python -m mine_sim list --scenarios-dir {args.scenarios_dir}' "
            "to inspect available scenarios.\n"
        )
        return 2

    scenario = load_scenario(scenario_yaml)
    scenario = _override_replications_for_scenario(scenario, args.reps)

    rep_indices = _resolve_replication_indices(args.rep_indices, args.reps)

    output_dir = _resolve_output_dir(
        args.output_dir,
        label=scenario.scenario_id,
        timestamp_prefix=False,
    )

    progress = _make_progress_printer(args.quiet)

    sys.stdout.write(
        f"Running scenario '{scenario.scenario_id}' from {scenario_yaml} ...\n"
    )
    if rep_indices is not None:
        sys.stdout.write(f"  replication indices: {list(rep_indices)}\n")
    else:
        sys.stdout.write(
            f"  replications: {scenario.simulation.replications} "
            f"(seed = {scenario.simulation.base_random_seed} + rep_idx)\n"
        )
    sys.stdout.write(f"  output directory: {output_dir}\n")
    sys.stdout.flush()

    start = time.monotonic()
    scenario_result = run_scenario(
        scenario=scenario,
        data_dir=args.data_dir,
        replication_indices=rep_indices,
        progress=progress,
    )
    elapsed = time.monotonic() - start

    scenario_summary = aggregate_scenario(scenario_result.replications)
    paths = write_scenario_outputs(scenario_result, scenario_summary, output_dir)

    _print_scenario_summary(scenario_summary, paths, elapsed)
    return 0


def cmd_run_all(args: argparse.Namespace) -> int:
    """Execute the ``run-all`` subcommand."""
    scenario_ids = _parse_scenario_ids(args.scenario_ids)
    requested_ids: tuple[str, ...] = (
        scenario_ids if scenario_ids is not None else REQUIRED_SCENARIO_IDS
    )

    sys.stdout.write(
        f"Running {len(requested_ids)} scenarios from {args.scenarios_dir} ...\n"
    )

    scenarios_map = load_all_scenarios(
        args.scenarios_dir, required=requested_ids
    )
    scenarios_map = _override_replications_for_scenarios(scenarios_map, args.reps)

    rep_indices = _resolve_replication_indices(args.rep_indices, args.reps)

    output_dir = _resolve_output_dir(
        args.output_dir,
        label="run_all",
        timestamp_prefix=True,
    )

    sys.stdout.write(f"  output directory: {output_dir}\n")
    if rep_indices is not None:
        sys.stdout.write(f"  shared replication indices: {list(rep_indices)}\n")
    sys.stdout.flush()

    progress = _make_progress_printer(args.quiet)

    start = time.monotonic()
    multi = run_all_scenarios(
        scenarios_map,
        data_dir=args.data_dir,
        scenario_ids=requested_ids,
        replication_indices=rep_indices,
        progress=progress,
    )
    elapsed = time.monotonic() - start

    run_summary = aggregate_run(
        {sid: r.replications for sid, r in multi.results.items()}
    )
    # When the user did not override --reps / --rep-indices we are running
    # the canonical Seed shape (30 reps × 8 h shift) and validate against
    # those expected values; with overrides we simply skip the strict
    # equality checks (replications/shift length still required to be
    # positive, structure still validated end-to-end).
    expected_replications = (
        30 if (rep_indices is None and args.reps is None) else None
    )
    expected_shift_length_hours = 8.0
    expected_scenario_ids = (
        REQUIRED_SCENARIO_IDS if scenario_ids is None else None
    )
    paths = write_run_outputs(
        multi,
        run_summary,
        output_dir,
        expected_scenario_ids=expected_scenario_ids,
        expected_replications=expected_replications,
        expected_shift_length_hours=expected_shift_length_hours,
    )

    _print_run_summary(run_summary, paths, elapsed)
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    """Execute the ``list`` subcommand."""
    scenarios_dir = args.scenarios_dir
    if not scenarios_dir.is_dir():
        sys.stderr.write(f"Scenarios directory not found: {scenarios_dir}\n")
        return 2

    yaml_files = sorted(scenarios_dir.glob("*.yaml"))
    if not yaml_files:
        sys.stderr.write(f"No scenario YAMLs found in {scenarios_dir}\n")
        return 2

    sys.stdout.write(f"Scenarios in {scenarios_dir}:\n")
    for yaml_path in yaml_files:
        try:
            scenario = load_scenario(yaml_path)
        except Exception as exc:  # pragma: no cover - defensive UX
            sys.stdout.write(
                f"  - {yaml_path.stem}: <error loading: {exc.__class__.__name__}>\n"
            )
            continue
        marker = " *" if scenario.scenario_id in REQUIRED_SCENARIO_IDS else "  "
        sys.stdout.write(
            f"  {marker}{scenario.scenario_id:<28} "
            f"reps={scenario.simulation.replications:<3}  "
            f"trucks={scenario.fleet.truck_count:<3}  "
            f"{scenario.description}\n"
        )
    sys.stdout.write(
        "\n  * = part of REQUIRED_SCENARIO_IDS (default for run-all)\n"
    )
    return 0


# ---------------------------------------------------------------------------
# Pretty-printers (keep stdout terse but useful)
# ---------------------------------------------------------------------------
def _print_scenario_summary(
    summary: ScenarioSummary,
    paths: ScenarioOutputPaths,
    elapsed_seconds: float,
) -> None:
    sys.stdout.write(
        "\n"
        f"Scenario '{summary.scenario_id}' complete in "
        f"{elapsed_seconds:.1f}s ({summary.replications} reps).\n"
        f"  total_tonnes_delivered: {summary.total_tonnes_delivered.mean:.0f} "
        f"[{summary.total_tonnes_delivered.ci95_low:.0f}, "
        f"{summary.total_tonnes_delivered.ci95_high:.0f}] (95% CI)\n"
        f"  tonnes_per_hour:        {summary.tonnes_per_hour.mean:.1f} "
        f"[{summary.tonnes_per_hour.ci95_low:.1f}, "
        f"{summary.tonnes_per_hour.ci95_high:.1f}]\n"
        f"  crusher_utilisation:    {summary.crusher_utilisation.mean:.3f}\n"
        f"  truck_utilisation:      {summary.average_truck_utilisation.mean:.3f}\n"
        f"  artefacts:\n"
        f"    {paths.results_csv}\n"
        f"    {paths.event_log_csv}\n"
        f"    {paths.summary_json}\n"
    )
    sys.stdout.flush()


def _print_run_summary(
    summary: RunSummary,
    paths: RunOutputPaths,
    elapsed_seconds: float,
) -> None:
    sys.stdout.write(
        f"\nrun-all complete in {elapsed_seconds:.1f}s "
        f"({len(summary.scenarios)} scenarios).\n"
    )
    header = f"{'scenario_id':<28} {'tonnes_mean':>12} {'tph_mean':>9} {'tph_ci95':>20}"
    sys.stdout.write(header + "\n")
    sys.stdout.write("-" * len(header) + "\n")
    for scenario_id, scenario_summary in summary.scenarios.items():
        tonnes = scenario_summary.total_tonnes_delivered.mean
        tph = scenario_summary.tonnes_per_hour.mean
        tph_low = scenario_summary.tonnes_per_hour.ci95_low
        tph_high = scenario_summary.tonnes_per_hour.ci95_high
        sys.stdout.write(
            f"{scenario_id:<28} {tonnes:>12.0f} {tph:>9.1f} "
            f"[{tph_low:>7.1f}, {tph_high:>7.1f}]\n"
        )
    sys.stdout.write(f"\nCombined artefacts:\n  {paths.results_csv}\n")
    sys.stdout.write(f"  {paths.event_log_csv}\n  {paths.summary_json}\n")
    sys.stdout.write(
        f"Per-scenario artefacts under: {paths.directory}/<scenario_id>/\n"
    )
    sys.stdout.flush()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main(argv: Sequence[str] | None = None) -> int:
    """Top-level CLI entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "run":
        return cmd_run(args)
    if args.command == "run-all":
        return cmd_run_all(args)
    if args.command == "list":
        return cmd_list(args)

    parser.error(f"Unknown command: {args.command}")
    return 2  # unreachable; parser.error raises SystemExit


__all__ = [
    "DEFAULT_DATA_DIR",
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_SCENARIOS_DIR",
    "RunOutputPaths",
    "ScenarioOutputPaths",
    "build_parser",
    "cmd_list",
    "cmd_run",
    "cmd_run_all",
    "main",
    "write_run_outputs",
    "write_scenario_outputs",
]
