"""Schema migration tests for harness.scores_db."""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from scores_db import (
    ScoreRecord,
    SubmissionRecord,
    connect,
    init_schema,
    insert_score,
    upsert_submission,
)


def _columns(conn: sqlite3.Connection, table: str) -> list[str]:
    return [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]


def test_submissions_table_has_token_and_time_columns(tmp_db_path: Path) -> None:
    conn = connect(tmp_db_path)
    init_schema(conn)
    cols = _columns(conn, "submissions")
    for expected in (
        "total_tokens",
        "input_tokens",
        "output_tokens",
        "token_count_method",
        "runtime_seconds",
        "intervention_category",
    ):
        assert expected in cols, f"missing column {expected}; got {cols}"


def test_existing_columns_remain(tmp_db_path: Path) -> None:
    conn = connect(tmp_db_path)
    init_schema(conn)
    cols = _columns(conn, "submissions")
    for legacy in ("submission_id", "run_date", "benchmark_id", "harness", "model", "run_tag"):
        assert legacy in cols


def test_leaderboard_view_includes_new_columns(tmp_db_path: Path) -> None:
    conn = connect(tmp_db_path)
    init_schema(conn)
    sql = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name='leaderboard'"
    ).fetchone()[0]
    for col in ("total_tokens", "runtime_seconds", "intervention_category"):
        assert col in sql, f"leaderboard view missing {col}"


def test_init_schema_is_idempotent(tmp_db_path: Path) -> None:
    conn = connect(tmp_db_path)
    init_schema(conn)
    init_schema(conn)  # must not raise
    init_schema(conn)


def test_init_schema_migrates_existing_database(tmp_db_path: Path) -> None:
    """A pre-existing DB without the new columns must be migrated in place."""
    legacy_ddl = (
        "CREATE TABLE submissions ("
        "submission_id TEXT PRIMARY KEY, run_date TEXT NOT NULL, "
        "benchmark_id TEXT NOT NULL, harness TEXT NOT NULL, model TEXT NOT NULL, "
        "run_tag TEXT, submission_path TEXT NOT NULL, "
        "created_at TEXT NOT NULL DEFAULT (datetime('now')))"
    )
    conn = sqlite3.connect(tmp_db_path)
    conn.executescript(legacy_ddl)
    conn.commit()
    conn.close()

    conn = connect(tmp_db_path)
    init_schema(conn)
    cols = _columns(conn, "submissions")
    assert "total_tokens" in cols
    assert "intervention_category" in cols


def test_upsert_submission_persists_token_and_time(tmp_db_path: Path) -> None:
    conn = connect(tmp_db_path)
    init_schema(conn)
    sub = SubmissionRecord(
        submission_id="2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking",
        run_date="2026-04-25",
        benchmark_id="001_synthetic_mine_throughput",
        harness="claude-code",
        model="claude-opus-4-7",
        run_tag="max-thinking",
        submission_path="submissions/x",
        total_tokens=116900,
        input_tokens=None,
        output_tokens=None,
        token_count_method="reported",
        runtime_seconds=699.0,
        intervention_category="autonomous",
    )
    upsert_submission(conn, sub)
    row = conn.execute(
        "SELECT total_tokens, runtime_seconds, intervention_category, token_count_method "
        "FROM submissions WHERE submission_id = ?",
        (sub.submission_id,),
    ).fetchone()
    assert row == (116900, 699.0, "autonomous", "reported")


def test_upsert_submission_overwrites_token_and_time(tmp_db_path: Path) -> None:
    conn = connect(tmp_db_path)
    init_schema(conn)
    base = SubmissionRecord(
        submission_id="2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking",
        run_date="2026-04-25",
        benchmark_id="001_synthetic_mine_throughput",
        harness="claude-code",
        model="claude-opus-4-7",
        run_tag="max-thinking",
        submission_path="submissions/x",
        total_tokens=100,
        input_tokens=40,
        output_tokens=60,
        token_count_method="exact",
        runtime_seconds=100.0,
        intervention_category="autonomous",
    )
    upsert_submission(conn, base)
    updated = SubmissionRecord(**{**base.__dict__, "total_tokens": 200, "runtime_seconds": 200.0})
    upsert_submission(conn, updated)
    row = conn.execute(
        "SELECT total_tokens, runtime_seconds FROM submissions WHERE submission_id = ?",
        (base.submission_id,),
    ).fetchone()
    assert row == (200, 200.0)


def test_decode_folder_unaffected() -> None:
    from scores_db import decode_folder

    s = decode_folder("2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking")
    assert s.benchmark_id == "001_synthetic_mine_throughput"
    assert s.run_tag == "max-thinking"
    # Six new fields default to None.
    assert s.total_tokens is None
    assert s.runtime_seconds is None
    assert s.intervention_category is None
