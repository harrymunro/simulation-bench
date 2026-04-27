"""Tests for harness.build_dashboard."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import build_dashboard
from scores_db import (
    ScoreRecord,
    SubmissionRecord,
    connect,
    init_schema,
    insert_score,
    upsert_submission,
)


@pytest.fixture
def populated_db(tmp_db_path: Path) -> Path:
    conn = connect(tmp_db_path)
    init_schema(conn)
    sub = SubmissionRecord(
        submission_id="2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking",
        run_date="2026-04-25",
        benchmark_id="001_synthetic_mine_throughput",
        harness="claude-code",
        model="claude-opus-4-7",
        run_tag="max-thinking",
        submission_path="submissions/2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking",
        total_tokens=116900,
        input_tokens=None,
        output_tokens=None,
        token_count_method="reported",
        runtime_seconds=699.0,
        intervention_category="autonomous",
    )
    upsert_submission(conn, sub)
    insert_score(
        conn,
        ScoreRecord(
            submission_id=sub.submission_id,
            reviewer="opus-subagent",
            review_date="2026-04-27",
            conceptual_modelling=18,
            data_topology=14,
            simulation_correctness=18,
            experimental_design=14,
            results_interpretation=14,
            code_quality=9,
            traceability=5,
            recommendation="Strong submission",
            notes="lane-grouping heuristic asserted not validated.",
        ),
    )
    conn.close()
    return tmp_db_path


def test_load_leaderboard_returns_one_row_per_submission(populated_db: Path) -> None:
    rows = build_dashboard.load_leaderboard(populated_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["submission_id"].endswith("max-thinking")
    assert row["totalScore"] == 92
    assert row["totalTokens"] == 116900
    assert row["runtimeSeconds"] == 699.0
    assert row["interventionCategory"] == "autonomous"
    assert row["categoryScores"]["conceptual_modelling"] == 18


def test_write_leaderboard_json_emits_array(populated_db: Path, tmp_path: Path) -> None:
    out = tmp_path / "leaderboard.json"
    build_dashboard.write_leaderboard_json(populated_db, out)
    assert out.exists()
    payload = json.loads(out.read_text())
    assert isinstance(payload, list)
    assert payload[0]["totalScore"] == 92


def test_classify_text_file_under_threshold(tmp_path: Path) -> None:
    f = tmp_path / "sim.py"
    f.write_text("print('hi')\n", encoding="utf-8")
    entry = build_dashboard.classify_file(f, tmp_path)
    assert entry == {"path": "sim.py", "kind": "text", "bytes": 12, "language": "python"}


def test_classify_event_log_is_download(tmp_path: Path) -> None:
    f = tmp_path / "event_log.csv"
    f.write_bytes(b"a,b\n" * 50_000)  # 200 KB > 64 KB threshold
    entry = build_dashboard.classify_file(f, tmp_path)
    assert entry["kind"] == "download"
    assert entry["path"] == "event_log.csv"


def test_classify_animation_is_download(tmp_path: Path) -> None:
    f = tmp_path / "animation.mp4"
    f.write_bytes(b"\x00" * 10)
    entry = build_dashboard.classify_file(f, tmp_path)
    assert entry["kind"] == "download"


def test_classify_unknown_extension_is_skipped(tmp_path: Path) -> None:
    f = tmp_path / "weird.bin"
    f.write_bytes(b"\x00\x01\x02")
    entry = build_dashboard.classify_file(f, tmp_path)
    assert entry is None


def test_walk_submission_skips_pycache(tmp_path: Path) -> None:
    folder = tmp_path / "submission"
    folder.mkdir()
    (folder / "sim.py").write_text("print('hi')\n", encoding="utf-8")
    pycache = folder / "__pycache__"
    pycache.mkdir()
    (pycache / "sim.cpython-311.pyc").write_bytes(b"\x00\x01")
    entries = build_dashboard.walk_submission(folder)
    paths = {e["path"] for e in entries}
    assert "sim.py" in paths
    assert not any(p.startswith("__pycache__") for p in paths)


def test_walk_submission_includes_nested_results(tmp_path: Path) -> None:
    folder = tmp_path / "submission"
    folder.mkdir()
    (folder / "results").mkdir()
    (folder / "results" / "evaluation_report.json").write_text("{}", encoding="utf-8")
    entries = build_dashboard.walk_submission(folder)
    paths = {e["path"] for e in entries}
    assert "results/evaluation_report.json" in paths


def test_emit_submission_writes_frontmatter_and_copies_downloads(
    tmp_path: Path, populated_db: Path
) -> None:
    submissions_root = tmp_path / "submissions"
    folder = submissions_root / "2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("# README\n\nbody\n", encoding="utf-8")
    (folder / "conceptual_model.md").write_text("# Conceptual model\n", encoding="utf-8")
    (folder / "summary.json").write_text("{}", encoding="utf-8")
    (folder / "event_log.csv").write_bytes(b"a,b\n" * 50_000)

    dashboard_root = tmp_path / "dashboard"
    rows = build_dashboard.load_leaderboard(populated_db)
    build_dashboard.emit_submissions(rows, submissions_root, dashboard_root)

    md_path = dashboard_root / "src" / "content" / "submissions" / f"{folder.name}.md"
    assert md_path.exists()
    text = md_path.read_text()
    assert text.startswith("---\n")
    assert f'id: "{folder.name}"' in text
    assert 'interventionCategory: "autonomous"' in text
    assert "files:" in text

    download = dashboard_root / "public" / "submissions" / folder.name / "event_log.csv"
    assert download.exists()
    assert download.stat().st_size == folder.joinpath("event_log.csv").stat().st_size
