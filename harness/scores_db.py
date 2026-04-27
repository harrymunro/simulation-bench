"""SQLite schema and helpers for the Simulation Bench scores database.

The DB persists per-reviewer scores against the 100-point rubric in
SCORING_GUIDE.md so we can rank submissions, track score drift across reviews,
and surface a scoreboard for the project README.

Default path: <repo_root>/scores/scores.db.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "scores" / "scores.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS submissions (
    submission_id         TEXT PRIMARY KEY,
    run_date              TEXT NOT NULL,
    benchmark_id          TEXT NOT NULL,
    harness               TEXT NOT NULL,
    model                 TEXT NOT NULL,
    run_tag               TEXT,
    submission_path       TEXT NOT NULL,
    total_tokens          INTEGER,
    input_tokens          INTEGER,
    output_tokens         INTEGER,
    token_count_method    TEXT,
    runtime_seconds       REAL,
    intervention_category TEXT,
    created_at            TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS scores (
    score_id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    submission_id             TEXT NOT NULL REFERENCES submissions(submission_id) ON DELETE CASCADE,
    reviewer                  TEXT NOT NULL,
    review_date               TEXT NOT NULL,
    conceptual_modelling      INTEGER NOT NULL CHECK (conceptual_modelling BETWEEN 0 AND 20),
    data_topology             INTEGER NOT NULL CHECK (data_topology BETWEEN 0 AND 15),
    simulation_correctness    INTEGER NOT NULL CHECK (simulation_correctness BETWEEN 0 AND 20),
    experimental_design       INTEGER NOT NULL CHECK (experimental_design BETWEEN 0 AND 15),
    results_interpretation    INTEGER NOT NULL CHECK (results_interpretation BETWEEN 0 AND 15),
    code_quality              INTEGER NOT NULL CHECK (code_quality BETWEEN 0 AND 10),
    traceability              INTEGER NOT NULL CHECK (traceability BETWEEN 0 AND 5),
    total_score               INTEGER NOT NULL CHECK (total_score BETWEEN 0 AND 100),
    automated_checks_passed   INTEGER,
    automated_checks_total    INTEGER,
    behavioural_checks_passed INTEGER,
    recommendation            TEXT,
    notes                     TEXT,
    created_at                TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(submission_id, reviewer, review_date)
);

CREATE INDEX IF NOT EXISTS idx_scores_submission ON scores(submission_id);
CREATE INDEX IF NOT EXISTS idx_scores_total      ON scores(total_score);

DROP VIEW IF EXISTS leaderboard;
CREATE VIEW leaderboard AS
SELECT
    s.submission_id,
    s.run_date,
    s.benchmark_id,
    s.harness,
    s.model,
    s.run_tag,
    s.total_tokens,
    s.input_tokens,
    s.output_tokens,
    s.token_count_method,
    s.runtime_seconds,
    s.intervention_category,
    sc.total_score,
    sc.conceptual_modelling,
    sc.data_topology,
    sc.simulation_correctness,
    sc.experimental_design,
    sc.results_interpretation,
    sc.code_quality,
    sc.traceability,
    sc.reviewer,
    sc.review_date,
    sc.recommendation,
    sc.notes
FROM submissions s
JOIN scores sc USING (submission_id)
ORDER BY sc.total_score DESC, sc.review_date DESC;
"""


@dataclass(frozen=True)
class SubmissionRecord:
    submission_id: str
    run_date: str
    benchmark_id: str
    harness: str
    model: str
    run_tag: Optional[str]
    submission_path: str
    total_tokens: Optional[int] = None
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    token_count_method: Optional[str] = None
    runtime_seconds: Optional[float] = None
    intervention_category: Optional[str] = None


@dataclass(frozen=True)
class ScoreRecord:
    submission_id: str
    reviewer: str
    review_date: str
    conceptual_modelling: int
    data_topology: int
    simulation_correctness: int
    experimental_design: int
    results_interpretation: int
    code_quality: int
    traceability: int
    automated_checks_passed: Optional[int] = None
    automated_checks_total: Optional[int] = None
    behavioural_checks_passed: Optional[int] = None
    recommendation: Optional[str] = None
    notes: Optional[str] = None

    @property
    def total_score(self) -> int:
        return (
            self.conceptual_modelling
            + self.data_topology
            + self.simulation_correctness
            + self.experimental_design
            + self.results_interpretation
            + self.code_quality
            + self.traceability
        )


def decode_folder(folder_name: str) -> SubmissionRecord:
    """Parse a submission folder name into a SubmissionRecord.

    Format: <YYYY-MM-DD>__<benchmark_id>__<harness>__<model>[__<run_tag>]
    """
    parts = folder_name.split("__")
    if len(parts) < 4 or len(parts) > 5:
        raise ValueError(
            f"Submission folder name must have 4 or 5 segments separated by '__'; got {folder_name!r}"
        )
    run_date, benchmark_id, harness, model = parts[:4]
    run_tag = parts[4] if len(parts) == 5 else None
    return SubmissionRecord(
        submission_id=folder_name,
        run_date=run_date,
        benchmark_id=benchmark_id,
        harness=harness,
        model=model,
        run_tag=run_tag,
        submission_path=f"submissions/{folder_name}",
    )


def connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


_NEW_SUBMISSION_COLUMNS = (
    ("total_tokens", "INTEGER"),
    ("input_tokens", "INTEGER"),
    ("output_tokens", "INTEGER"),
    ("token_count_method", "TEXT"),
    ("runtime_seconds", "REAL"),
    ("intervention_category", "TEXT"),
)


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    existing = {row[1] for row in conn.execute("PRAGMA table_info(submissions)")}
    for name, sql_type in _NEW_SUBMISSION_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE submissions ADD COLUMN {name} {sql_type}")
    conn.commit()


def upsert_submission(conn: sqlite3.Connection, sub: SubmissionRecord) -> None:
    conn.execute(
        """
        INSERT INTO submissions
            (submission_id, run_date, benchmark_id, harness, model, run_tag, submission_path,
             total_tokens, input_tokens, output_tokens, token_count_method,
             runtime_seconds, intervention_category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(submission_id) DO UPDATE SET
            run_date              = excluded.run_date,
            benchmark_id          = excluded.benchmark_id,
            harness               = excluded.harness,
            model                 = excluded.model,
            run_tag               = excluded.run_tag,
            submission_path       = excluded.submission_path,
            total_tokens          = excluded.total_tokens,
            input_tokens          = excluded.input_tokens,
            output_tokens         = excluded.output_tokens,
            token_count_method    = excluded.token_count_method,
            runtime_seconds       = excluded.runtime_seconds,
            intervention_category = excluded.intervention_category
        """,
        (
            sub.submission_id,
            sub.run_date,
            sub.benchmark_id,
            sub.harness,
            sub.model,
            sub.run_tag,
            sub.submission_path,
            sub.total_tokens,
            sub.input_tokens,
            sub.output_tokens,
            sub.token_count_method,
            sub.runtime_seconds,
            sub.intervention_category,
        ),
    )
    conn.commit()


def insert_score(conn: sqlite3.Connection, score: ScoreRecord) -> int:
    cursor = conn.execute(
        """
        INSERT INTO scores (
            submission_id, reviewer, review_date,
            conceptual_modelling, data_topology, simulation_correctness,
            experimental_design, results_interpretation, code_quality, traceability,
            total_score,
            automated_checks_passed, automated_checks_total, behavioural_checks_passed,
            recommendation, notes
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(submission_id, reviewer, review_date) DO UPDATE SET
            conceptual_modelling      = excluded.conceptual_modelling,
            data_topology             = excluded.data_topology,
            simulation_correctness    = excluded.simulation_correctness,
            experimental_design       = excluded.experimental_design,
            results_interpretation    = excluded.results_interpretation,
            code_quality              = excluded.code_quality,
            traceability              = excluded.traceability,
            total_score               = excluded.total_score,
            automated_checks_passed   = excluded.automated_checks_passed,
            automated_checks_total    = excluded.automated_checks_total,
            behavioural_checks_passed = excluded.behavioural_checks_passed,
            recommendation            = excluded.recommendation,
            notes                     = excluded.notes
        """,
        (
            score.submission_id,
            score.reviewer,
            score.review_date,
            score.conceptual_modelling,
            score.data_topology,
            score.simulation_correctness,
            score.experimental_design,
            score.results_interpretation,
            score.code_quality,
            score.traceability,
            score.total_score,
            score.automated_checks_passed,
            score.automated_checks_total,
            score.behavioural_checks_passed,
            score.recommendation,
            score.notes,
        ),
    )
    conn.commit()
    return cursor.lastrowid or 0
