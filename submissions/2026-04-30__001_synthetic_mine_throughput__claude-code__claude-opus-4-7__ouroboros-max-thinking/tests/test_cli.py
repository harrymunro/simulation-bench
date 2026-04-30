"""Tests for the ``python -m mine_sim`` CLI (Sub-AC 4).

The CLI is exercised via :func:`mine_sim.cli.main` (in-process) so we can
assert exit codes and inspect the output filesystem without spawning a
subprocess. Test scope:

* Argument parsing: ``run``, ``run-all``, ``list``, ``--rep-indices``,
  ``--reps``, ``--scenario-ids``, ``--output-dir``.
* Per-scenario directory layout: every scenario gets its own
  ``results.csv``, ``event_log.csv``, ``summary.json``.
* Combined top-level artefacts for ``run-all``.
* Error handling for missing scenario YAMLs.

A compact 2-replication smoke run keeps the suite under a few seconds.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from mine_sim.cli import build_parser, main
from mine_sim.io_writers import RESULTS_CSV_COLUMNS
from mine_sim.events import EVENT_CSV_COLUMNS
from mine_sim.scenarios import REQUIRED_SCENARIO_IDS

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"


# ---------------------------------------------------------------------------
# Argument parser unit tests
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_build_parser_exposes_three_subcommands() -> None:
    parser = build_parser()
    args = parser.parse_args(["run", "baseline"])
    assert args.command == "run"
    assert args.scenario_id == "baseline"

    args = parser.parse_args(["run-all"])
    assert args.command == "run-all"

    args = parser.parse_args(["list"])
    assert args.command == "list"


@pytest.mark.unit
def test_run_parser_accepts_rep_indices() -> None:
    parser = build_parser()
    args = parser.parse_args(
        ["run", "baseline", "--rep-indices", "0,1,2", "--quiet"]
    )
    assert args.rep_indices == "0,1,2"
    assert args.quiet is True


@pytest.mark.unit
def test_run_all_parser_accepts_scenario_ids_and_reps() -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "run-all",
            "--scenario-ids",
            "baseline,trucks_4",
            "--reps",
            "5",
        ]
    )
    assert args.scenario_ids == "baseline,trucks_4"
    assert args.reps == 5


@pytest.mark.unit
def test_parser_requires_command() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


# ---------------------------------------------------------------------------
# Single-scenario `run` integration
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_writes_per_scenario_artefacts(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    output_dir = tmp_path / "out"
    rc = main(
        [
            "run",
            "baseline",
            "--data-dir",
            str(DATA_DIR),
            "--scenarios-dir",
            str(SCENARIOS_DIR),
            "--output-dir",
            str(output_dir),
            "--rep-indices",
            "0,1",
            "--quiet",
        ]
    )
    assert rc == 0
    # Three artefacts present.
    results_csv = output_dir / "results.csv"
    event_log_csv = output_dir / "event_log.csv"
    summary_json = output_dir / "summary.json"
    assert results_csv.exists()
    assert event_log_csv.exists()
    assert summary_json.exists()

    # results.csv: pinned column order, one row per replication.
    rows = _read_csv(results_csv)
    assert len(rows) == 2
    assert tuple(rows[0].keys()) == RESULTS_CSV_COLUMNS
    seeds = sorted(int(row["random_seed"]) for row in rows)
    assert seeds == [12345, 12346]
    for row in rows:
        assert row["scenario_id"] == "baseline"
        assert float(row["total_tonnes_delivered"]) > 0
        assert float(row["tonnes_per_hour"]) > 0

    # event_log.csv: pinned column order, at least one row.
    events = _read_csv(event_log_csv)
    assert len(events) > 0
    assert tuple(events[0].keys()) == EVENT_CSV_COLUMNS

    # summary.json schema:
    summary = _read_json(summary_json)
    assert summary["scenario_id"] == "baseline"
    assert summary["replications"] == 2
    assert summary["shift_length_hours"] == 8.0
    for stat_field in (
        "total_tonnes_delivered",
        "tonnes_per_hour",
        "average_truck_cycle_time_min",
        "average_truck_utilisation",
        "crusher_utilisation",
        "average_loader_queue_time_min",
        "average_crusher_queue_time_min",
    ):
        stat = summary[stat_field]
        for sub in ("mean", "ci95_low", "ci95_high"):
            assert sub in stat, f"Missing {stat_field}.{sub} in summary.json"
            assert isinstance(stat[sub], (int, float))
    assert "loaders" in summary and len(summary["loaders"]) >= 1
    assert "crusher" in summary
    assert "edges" in summary
    assert "top_bottlenecks" in summary and len(summary["top_bottlenecks"]) > 0
    assert "key_assumptions" in summary and len(summary["key_assumptions"]) > 0
    assert "model_limitations" in summary
    assert "additional_scenarios_proposed" in summary


@pytest.mark.integration
def test_run_unknown_scenario_returns_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(
        [
            "run",
            "no_such_scenario",
            "--data-dir",
            str(DATA_DIR),
            "--scenarios-dir",
            str(SCENARIOS_DIR),
            "--output-dir",
            str(tmp_path / "out"),
            "--rep-indices",
            "0",
            "--quiet",
        ]
    )
    assert rc == 2
    err = capsys.readouterr().err
    assert "Scenario YAML not found" in err


# ---------------------------------------------------------------------------
# Multi-scenario `run-all` integration
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_all_writes_per_scenario_dirs_and_combined_files(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "run_all_out"
    rc = main(
        [
            "run-all",
            "--data-dir",
            str(DATA_DIR),
            "--scenarios-dir",
            str(SCENARIOS_DIR),
            "--output-dir",
            str(output_dir),
            "--rep-indices",
            "0,1",
            "--quiet",
        ]
    )
    assert rc == 0

    # Per-scenario directories with artefacts.
    for scenario_id in REQUIRED_SCENARIO_IDS:
        scenario_dir = output_dir / scenario_id
        assert scenario_dir.is_dir(), f"Missing per-scenario dir {scenario_dir}"
        assert (scenario_dir / "results.csv").exists()
        assert (scenario_dir / "event_log.csv").exists()
        assert (scenario_dir / "summary.json").exists()

        # Per-scenario results.csv has 2 reps per scenario.
        rows = _read_csv(scenario_dir / "results.csv")
        assert len(rows) == 2
        for row in rows:
            assert row["scenario_id"] == scenario_id

    # Combined results.csv: 7 scenarios * 2 reps = 14 rows.
    combined_results = _read_csv(output_dir / "results.csv")
    assert len(combined_results) == len(REQUIRED_SCENARIO_IDS) * 2

    # Combined summary.json: contains every scenario.
    combined_summary = _read_json(output_dir / "summary.json")
    assert "scenarios" in combined_summary
    assert set(combined_summary["scenarios"].keys()) == set(REQUIRED_SCENARIO_IDS)
    for scenario_id in REQUIRED_SCENARIO_IDS:
        s = combined_summary["scenarios"][scenario_id]
        assert s["scenario_id"] == scenario_id
        assert s["replications"] == 2
        assert "tonnes_per_hour" in s and "mean" in s["tonnes_per_hour"]

    # Combined event_log.csv contains events from every scenario.
    events = _read_csv(output_dir / "event_log.csv")
    seen_scenarios = {row["scenario_id"] for row in events}
    assert seen_scenarios == set(REQUIRED_SCENARIO_IDS)


@pytest.mark.integration
def test_run_all_subset_via_scenario_ids(tmp_path: Path) -> None:
    output_dir = tmp_path / "subset_out"
    rc = main(
        [
            "run-all",
            "--data-dir",
            str(DATA_DIR),
            "--scenarios-dir",
            str(SCENARIOS_DIR),
            "--output-dir",
            str(output_dir),
            "--scenario-ids",
            "baseline,trucks_4",
            "--rep-indices",
            "0",
            "--quiet",
        ]
    )
    assert rc == 0
    # Only the requested two scenarios get directories.
    assert (output_dir / "baseline").is_dir()
    assert (output_dir / "trucks_4").is_dir()
    # Combined summary includes only these two.
    combined_summary = _read_json(output_dir / "summary.json")
    assert set(combined_summary["scenarios"].keys()) == {"baseline", "trucks_4"}


# ---------------------------------------------------------------------------
# `list` subcommand
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_list_command_prints_known_scenarios(
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["list", "--scenarios-dir", str(SCENARIOS_DIR)])
    assert rc == 0
    out = capsys.readouterr().out
    for scenario_id in REQUIRED_SCENARIO_IDS:
        assert scenario_id in out


@pytest.mark.integration
def test_list_command_missing_dir_returns_error(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rc = main(["list", "--scenarios-dir", str(tmp_path / "no_such_dir")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "not found" in err.lower()


# ---------------------------------------------------------------------------
# Reproducibility contract
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_is_deterministic_across_invocations(tmp_path: Path) -> None:
    """Same scenario, same rep indices -> same per-rep numbers."""
    args_template = [
        "run",
        "baseline",
        "--data-dir",
        str(DATA_DIR),
        "--scenarios-dir",
        str(SCENARIOS_DIR),
        "--rep-indices",
        "0,1",
        "--quiet",
    ]

    out_a = tmp_path / "a"
    out_b = tmp_path / "b"
    main([*args_template, "--output-dir", str(out_a)])
    main([*args_template, "--output-dir", str(out_b)])

    rows_a = _read_csv(out_a / "results.csv")
    rows_b = _read_csv(out_b / "results.csv")
    assert rows_a == rows_b
