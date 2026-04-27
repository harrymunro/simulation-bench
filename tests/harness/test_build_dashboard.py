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
