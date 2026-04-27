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
