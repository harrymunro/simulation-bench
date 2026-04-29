# Public Simulation Bench Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a public, read-only Simulation Bench dashboard to fly.io that surfaces the leaderboard (Quality / Tokens / Time), per-submission browsable artefacts, and the methodology docs.

**Architecture:** Python (`harness/build_dashboard.py`) reads `scores/scores.db` plus `submissions/<id>/` artefacts and emits JSON + Markdown into `dashboard/src/`. Astro consumes those inputs at build time and produces a fully-static `dashboard/dist/`. A Caddy container on Fly serves `dist/`; no runtime data layer.

**Tech Stack:** Python 3.11 (stdlib + pyyaml), pytest, SQLite, Astro v5 (Content Collections + Shiki), Caddy 2, Fly.io.

**Plan reference:** `docs/superpowers/specs/2026-04-27-public-dashboard-design.md` is the source-of-truth spec. Each phase below corresponds to §6 in the spec.

---

## File Structure

The plan creates these files (relative to repo root). Each task names exactly which file it touches.

**Python (data layer)**
- `harness/scores_db.py` — modify: add columns to `submissions` table + `leaderboard` view.
- `harness/record_score.py` — modify: read `token_usage.json` + `run_metrics.json` + `submission.yaml.intervention` at ingest time.
- `harness/scoreboard.py` — modify: include tokens/time/intervention columns in CLI output.
- `harness/normalize_tokens.py` — new: one-shot backfill for the four existing submissions.
- `harness/build_dashboard.py` — new: query DB + walk submissions + emit Astro inputs.
- `tests/harness/test_scores_db.py` — new.
- `tests/harness/test_record_score.py` — new.
- `tests/harness/test_normalize_tokens.py` — new.
- `tests/harness/test_build_dashboard.py` — new.
- `tests/conftest.py` — new: shared fixtures (tmp `scores.db`, sample submission tree).

**Documentation & protocol**
- `RUN_PROTOCOL.md` — modify: §4 + §5 become required; §8 gains the structured `intervention.category` field.
- `SCORING_GUIDE.md` — unchanged (referenced from dashboard pages).
- `.claude/skills/create-submission/SKILL.md` — modify: scaffold stub `token_usage.json` + `run_metrics.json`.
- `.claude/skills/evaluate-submission/SKILL.md` — modify: warn when either file is missing or `token_count_method == "unknown"`.

**Backfill (per-submission, four submissions)**
- `submissions/<id>/token_usage.json` — new (one per submission).
- `submissions/<id>/run_metrics.json` — new (one per submission).
- `submissions/<id>/submission.yaml` — modify: add `intervention.category`.

**Astro project (dashboard)**
- `dashboard/package.json` — new.
- `dashboard/astro.config.mjs` — new.
- `dashboard/tsconfig.json` — new.
- `dashboard/.gitignore` — new (node_modules, dist, .astro).
- `dashboard/src/content.config.ts` — new: content collection schemas.
- `dashboard/src/layouts/Layout.astro` — new: site chrome.
- `dashboard/src/components/Header.astro` — new.
- `dashboard/src/components/LeaderboardTable.astro` — new: client-side sort island.
- `dashboard/src/components/InterventionBadge.astro` — new.
- `dashboard/src/components/FileTree.astro` — new.
- `dashboard/src/pages/index.astro` — new: leaderboard.
- `dashboard/src/pages/methodology/index.astro` — new.
- `dashboard/src/pages/methodology/scoring.astro` — new.
- `dashboard/src/pages/methodology/protocol.astro` — new.
- `dashboard/src/pages/methodology/dashboard.astro` — new.
- `dashboard/src/pages/submissions/[id]/index.astro` — new: submission overview.
- `dashboard/src/pages/submissions/[id]/[...file].astro` — new: syntax-highlighted file viewer.
- `dashboard/src/styles/global.css` — new.
- `dashboard/src/data/leaderboard.json` — generated (gitignored).
- `dashboard/src/content/submissions/<id>.md` — generated.
- `dashboard/src/content/methodology/scoring.md` — generated.
- `dashboard/src/content/methodology/protocol.md` — generated.
- `dashboard/public/submissions/<id>/event_log.csv` — generated copies of bulky files.

**Deploy**
- `Dockerfile` — new.
- `Caddyfile` — new.
- `fly.toml` — new.
- `.dockerignore` — new.

**Polish**
- `Makefile` — new: wraps the build + deploy commands.
- `README.md` — modify: add "Updating the dashboard" section.

---

## Setup Task: Pin dependencies and test scaffold

### Task 0: Add pytest fixtures and update requirements

**Files:**
- Create: `tests/__init__.py`
- Create: `tests/harness/__init__.py`
- Create: `tests/conftest.py`
- Modify: `pyproject.toml`
- Modify: `requirements.txt`

- [ ] **Step 1: Verify the current test command works**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest --collect-only 2>&1 | tail -10`
Expected: pytest discovers tests under `benchmarks/` (current `testpaths`).

- [ ] **Step 2: Extend `pyproject.toml` to also discover `tests/`**

Replace the `[tool.pytest.ini_options]` block in `pyproject.toml` with:

```toml
[tool.pytest.ini_options]
testpaths = ["benchmarks", "tests"]
python_files = ["test_*.py"]
```

- [ ] **Step 3: Create empty `__init__.py` files**

Create `tests/__init__.py` with content: empty file.
Create `tests/harness/__init__.py` with content: empty file.

- [ ] **Step 4: Create `tests/conftest.py` with shared fixtures**

```python
"""Shared pytest fixtures for harness tests."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "harness"

# Make `harness/` importable as a package without packaging it.
if str(HARNESS) not in sys.path:
    sys.path.insert(0, str(HARNESS))


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> Path:
    return tmp_path / "scores.db"


@pytest.fixture
def sample_submission(tmp_path: Path) -> Path:
    """Create a minimal submission folder under tmp_path/submissions/<id>/."""
    folder = (
        tmp_path
        / "submissions"
        / "2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking"
    )
    folder.mkdir(parents=True)
    (folder / "submission.yaml").write_text(
        "submission_id: 2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking\n"
        "date: 2026-04-25\n"
        "benchmark_id: 001_synthetic_mine_throughput\n"
        "harness:\n  name: claude-code\n"
        "model:\n  name: claude-opus-4-7\n  vendor: anthropic\n"
        "run_tag: max-thinking\n"
        "intervention:\n  category: autonomous\n  notes: ''\n",
        encoding="utf-8",
    )
    (folder / "token_usage.json").write_text(
        json.dumps(
            {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": 116900,
                "token_count_method": "reported",
                "estimated_cost_usd": None,
            }
        ),
        encoding="utf-8",
    )
    (folder / "run_metrics.json").write_text(
        json.dumps(
            {
                "command": "python run.py",
                "runtime_seconds": 699.0,
                "return_code": 0,
                "timed_out": False,
            }
        ),
        encoding="utf-8",
    )
    (folder / "README.md").write_text("# Submission\n", encoding="utf-8")
    return folder
```

- [ ] **Step 5: Run pytest to verify discovery still works**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest --collect-only 2>&1 | tail -10`
Expected: no errors. Existing benchmark tests still discovered.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml tests/__init__.py tests/harness/__init__.py tests/conftest.py
git commit -m "test: scaffold pytest fixtures and tests/ tree"
```

---

# Phase 1 — Protocol & Data Normalization

Goal: every submission has canonical `token_usage.json` + `run_metrics.json`, the DB carries tokens/time/intervention, and the CLI scoreboard surfaces them. **Exit criterion (per spec §6):** `python harness/scoreboard.py --detailed` shows tokens + time columns for all four existing submissions; `gsd2` shows `—` for both.

### Task 1: Extend `scores.db` schema with token/time/intervention columns

**Files:**
- Modify: `harness/scores_db.py`
- Test: `tests/harness/test_scores_db.py`

- [ ] **Step 1: Write the failing test**

Create `tests/harness/test_scores_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_scores_db.py -v`
Expected: FAIL with assertion errors about missing columns.

- [ ] **Step 3: Modify `harness/scores_db.py` schema**

In `harness/scores_db.py`, replace the `SCHEMA` constant. The new `submissions` table adds six columns; the new `leaderboard` view exposes them. Replace the existing `SCHEMA = """..."""` block with:

```python
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
```

- [ ] **Step 4: Add an in-place column migration to `init_schema`**

`CREATE TABLE IF NOT EXISTS` won't add new columns to an old table. Replace the existing `init_schema` function in `harness/scores_db.py` with:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_scores_db.py -v`
Expected: all five tests PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/scores_db.py tests/harness/test_scores_db.py
git commit -m "feat: add token, time, intervention columns to scores schema"
```

### Task 2: Extend `SubmissionRecord` with the new fields and `upsert_submission`

**Files:**
- Modify: `harness/scores_db.py`
- Test: `tests/harness/test_scores_db.py`

- [ ] **Step 1: Append failing tests**

Append to `tests/harness/test_scores_db.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_scores_db.py -v`
Expected: three new tests FAIL — `SubmissionRecord` has no token/time/intervention fields.

- [ ] **Step 3: Update `SubmissionRecord` and `decode_folder`**

In `harness/scores_db.py`, replace the existing `SubmissionRecord` dataclass with:

```python
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
```

Leave `decode_folder` unchanged — its return value still satisfies the new dataclass because every new field has a default of `None`.

- [ ] **Step 4: Update `upsert_submission` to write all columns**

Replace the existing `upsert_submission` function in `harness/scores_db.py` with:

```python
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_scores_db.py -v`
Expected: all eight tests PASS.

- [ ] **Step 6: Commit**

```bash
git add harness/scores_db.py tests/harness/test_scores_db.py
git commit -m "feat: persist token/time/intervention on SubmissionRecord"
```

### Task 3: Read `token_usage.json`, `run_metrics.json`, and `intervention.category` in `record_score.py`

**Files:**
- Modify: `harness/record_score.py`
- Test: `tests/harness/test_record_score.py`

- [ ] **Step 1: Write the failing test**

Create `tests/harness/test_record_score.py`:

```python
"""End-to-end tests for harness.record_score loading per-submission metadata."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import record_score
from scores_db import connect, init_schema


def _seed_submission(folder: Path, *, with_tokens: bool, with_metrics: bool, intervention: str | None) -> None:
    folder.mkdir(parents=True)
    submission_yaml = (
        f"submission_id: {folder.name}\n"
        f"date: 2026-04-25\n"
        f"benchmark_id: 001_synthetic_mine_throughput\n"
        f"harness:\n  name: claude-code\n"
        f"model:\n  name: claude-opus-4-7\n  vendor: anthropic\n"
        f"run_tag: max-thinking\n"
    )
    if intervention is not None:
        submission_yaml += f"intervention:\n  category: {intervention}\n  notes: ''\n"
    (folder / "submission.yaml").write_text(submission_yaml, encoding="utf-8")
    if with_tokens:
        (folder / "token_usage.json").write_text(
            json.dumps({"input_tokens": 78000, "output_tokens": 21000, "total_tokens": 99000,
                        "token_count_method": "reported", "estimated_cost_usd": None}),
            encoding="utf-8",
        )
    if with_metrics:
        (folder / "run_metrics.json").write_text(
            json.dumps({"command": "python sim.py", "runtime_seconds": 297.0, "return_code": 0,
                        "timed_out": False}),
            encoding="utf-8",
        )


@pytest.fixture
def submissions_root(tmp_path: Path) -> Path:
    root = tmp_path / "submissions"
    root.mkdir()
    return root


def test_record_score_picks_up_token_metric_intervention(tmp_db_path: Path, submissions_root: Path) -> None:
    folder = submissions_root / "2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking"
    _seed_submission(folder, with_tokens=True, with_metrics=True, intervention="autonomous")

    score_payload = {
        "submission_id": folder.name,
        "reviewer": "opus-subagent",
        "review_date": "2026-04-27",
        "conceptual_modelling": 18, "data_topology": 14, "simulation_correctness": 18,
        "experimental_design": 14, "results_interpretation": 14, "code_quality": 9, "traceability": 5,
    }

    conn = connect(tmp_db_path)
    init_schema(conn)
    record_score._record_from_dict(conn, score_payload, submissions_root=submissions_root)

    row = conn.execute(
        "SELECT total_tokens, input_tokens, output_tokens, token_count_method, runtime_seconds, intervention_category "
        "FROM submissions WHERE submission_id = ?",
        (folder.name,),
    ).fetchone()
    assert row == (99000, 78000, 21000, "reported", 297.0, "autonomous")


def test_record_score_handles_missing_files(tmp_db_path: Path, submissions_root: Path) -> None:
    folder = submissions_root / "2026-04-27__001_synthetic_mine_throughput__gsd2__gemini-3-1-pro-preview__customtools"
    _seed_submission(folder, with_tokens=False, with_metrics=False, intervention=None)

    conn = connect(tmp_db_path)
    init_schema(conn)
    record_score._record_from_dict(
        conn,
        {
            "submission_id": folder.name,
            "reviewer": "opus-subagent",
            "review_date": "2026-04-27",
            "conceptual_modelling": 15, "data_topology": 12, "simulation_correctness": 15,
            "experimental_design": 11, "results_interpretation": 12, "code_quality": 6, "traceability": 4,
        },
        submissions_root=submissions_root,
    )

    row = conn.execute(
        "SELECT total_tokens, runtime_seconds, intervention_category, token_count_method "
        "FROM submissions WHERE submission_id = ?",
        (folder.name,),
    ).fetchone()
    assert row == (None, None, "unrecorded", None)


def test_record_score_unknown_intervention_falls_back(tmp_db_path: Path, submissions_root: Path) -> None:
    folder = submissions_root / "2026-04-25__001_synthetic_mine_throughput__codex-cli__gpt-5-5__xhigh"
    _seed_submission(folder, with_tokens=False, with_metrics=False, intervention="not-a-known-category")

    conn = connect(tmp_db_path)
    init_schema(conn)
    record_score._record_from_dict(
        conn,
        {
            "submission_id": folder.name,
            "reviewer": "opus-subagent",
            "review_date": "2026-04-27",
            "conceptual_modelling": 17, "data_topology": 13, "simulation_correctness": 17,
            "experimental_design": 13, "results_interpretation": 13, "code_quality": 7, "traceability": 5,
        },
        submissions_root=submissions_root,
    )
    row = conn.execute(
        "SELECT intervention_category FROM submissions WHERE submission_id = ?",
        (folder.name,),
    ).fetchone()
    assert row == ("unrecorded",)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_record_score.py -v`
Expected: FAIL — `_record_from_dict` does not accept `submissions_root` and does not load token/metric/intervention.

- [ ] **Step 3: Add the loader helpers in `record_score.py`**

In `harness/record_score.py`, add these helper functions just below the imports (after `from scores_db import …`):

```python
import yaml

VALID_INTERVENTION_CATEGORIES = {
    "autonomous",
    "hints",
    "manual_repair",
    "failed",
    "unrecorded",
}


def _read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _read_yaml(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError:
        return None


def _coerce_int(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_float(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _intervention_from_yaml(payload: dict | None) -> str:
    if not payload:
        return "unrecorded"
    intervention = payload.get("intervention")
    if not isinstance(intervention, dict):
        return "unrecorded"
    category = intervention.get("category")
    if category in VALID_INTERVENTION_CATEGORIES:
        return category
    return "unrecorded"


def _enrich_submission(sub, submissions_root: Path):
    """Return a new SubmissionRecord with token/time/intervention loaded from the folder."""
    folder = submissions_root / sub.submission_id
    tokens = _read_json(folder / "token_usage.json") or {}
    metrics = _read_json(folder / "run_metrics.json") or {}
    yaml_payload = _read_yaml(folder / "submission.yaml")

    return type(sub)(
        submission_id=sub.submission_id,
        run_date=sub.run_date,
        benchmark_id=sub.benchmark_id,
        harness=sub.harness,
        model=sub.model,
        run_tag=sub.run_tag,
        submission_path=sub.submission_path,
        total_tokens=_coerce_int(tokens.get("total_tokens")),
        input_tokens=_coerce_int(tokens.get("input_tokens")),
        output_tokens=_coerce_int(tokens.get("output_tokens")),
        token_count_method=tokens.get("token_count_method"),
        runtime_seconds=_coerce_float(metrics.get("runtime_seconds")),
        intervention_category=_intervention_from_yaml(yaml_payload),
    )
```

- [ ] **Step 4: Replace `_record_from_dict` to use the loader**

In `harness/record_score.py`, replace the existing `_record_from_dict` with:

```python
def _record_from_dict(conn, payload: dict, *, submissions_root: Path | None = None) -> int:
    sub = decode_folder(payload["submission_id"])
    if submissions_root is None:
        submissions_root = Path("submissions")
    sub = _enrich_submission(sub, submissions_root)
    upsert_submission(conn, sub)
    score = ScoreRecord(
        submission_id=payload["submission_id"],
        reviewer=payload["reviewer"],
        review_date=payload["review_date"],
        conceptual_modelling=int(payload["conceptual_modelling"]),
        data_topology=int(payload["data_topology"]),
        simulation_correctness=int(payload["simulation_correctness"]),
        experimental_design=int(payload["experimental_design"]),
        results_interpretation=int(payload["results_interpretation"]),
        code_quality=int(payload["code_quality"]),
        traceability=int(payload["traceability"]),
        automated_checks_passed=payload.get("automated_checks_passed"),
        automated_checks_total=payload.get("automated_checks_total"),
        behavioural_checks_passed=payload.get("behavioural_checks_passed"),
        recommendation=payload.get("recommendation"),
        notes=payload.get("notes"),
    )
    return insert_score(conn, score)
```

- [ ] **Step 5: Pass `--submissions-root` through from `main`**

In `harness/record_score.py`, replace the body of `main()` (everything from `parser = argparse.ArgumentParser(...)` to the end of the function) with:

```python
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--from-json", type=Path, help="Bulk-load scores from a JSON list")
    parser.add_argument(
        "--submissions-root",
        type=Path,
        default=Path("submissions"),
        help="Folder containing per-submission directories (default: submissions/)",
    )

    parser.add_argument("--submission")
    parser.add_argument("--reviewer")
    parser.add_argument("--review-date")
    parser.add_argument("--conceptual", type=int)
    parser.add_argument("--data", type=int)
    parser.add_argument("--sim", type=int)
    parser.add_argument("--exp", type=int)
    parser.add_argument("--results", type=int)
    parser.add_argument("--code", type=int)
    parser.add_argument("--trace", type=int)
    parser.add_argument("--automated-passed", type=int)
    parser.add_argument("--automated-total", type=int)
    parser.add_argument("--behavioural-passed", type=int)
    parser.add_argument("--recommendation")
    parser.add_argument("--notes")

    args = parser.parse_args()
    conn = connect(args.db)
    init_schema(conn)

    if args.from_json:
        payload = json.loads(args.from_json.read_text())
        if not isinstance(payload, list):
            print("--from-json must contain a JSON list of score objects", file=sys.stderr)
            return 2
        for entry in payload:
            _record_from_dict(conn, entry, submissions_root=args.submissions_root)
        print(f"Recorded {len(payload)} score(s) into {args.db}")
        return 0

    required = [
        args.submission, args.reviewer, args.review_date,
        args.conceptual, args.data, args.sim, args.exp,
        args.results, args.code, args.trace,
    ]
    if any(v is None for v in required):
        parser.error("All single-submission flags are required when --from-json is not used")

    payload = {
        "submission_id": args.submission,
        "reviewer": args.reviewer,
        "review_date": args.review_date,
        "conceptual_modelling": args.conceptual,
        "data_topology": args.data,
        "simulation_correctness": args.sim,
        "experimental_design": args.exp,
        "results_interpretation": args.results,
        "code_quality": args.code,
        "traceability": args.trace,
        "automated_checks_passed": args.automated_passed,
        "automated_checks_total": args.automated_total,
        "behavioural_checks_passed": args.behavioural_passed,
        "recommendation": args.recommendation,
        "notes": args.notes,
    }
    score_id = _record_from_dict(conn, payload, submissions_root=args.submissions_root)
    print(f"Recorded score #{score_id} for {args.submission} into {args.db}")
    return 0
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_record_score.py -v`
Expected: all three tests PASS.

- [ ] **Step 7: Commit**

```bash
git add harness/record_score.py tests/harness/test_record_score.py
git commit -m "feat: read tokens, runtime, intervention from submission folder at ingest"
```

### Task 4: Update `scoreboard.py` to surface the new columns

**Files:**
- Modify: `harness/scoreboard.py`

- [ ] **Step 1: Replace the `--detailed` SQL and headers**

In `harness/scoreboard.py`, replace the `if args.detailed:` block (the seven lines beginning with `sql = """` through the `print(_format_table(...))` and `return 0`) with:

```python
    if args.detailed:
        sql = """
            SELECT s.benchmark_id, s.harness, s.model, s.run_tag,
                   sc.conceptual_modelling, sc.data_topology, sc.simulation_correctness,
                   sc.experimental_design, sc.results_interpretation,
                   sc.code_quality, sc.traceability, sc.total_score,
                   s.total_tokens, s.runtime_seconds, s.intervention_category,
                   sc.reviewer
            FROM submissions s JOIN scores sc USING (submission_id)
        """
        params: list = []
        if args.benchmark:
            sql += " WHERE s.benchmark_id = ?"
            params.append(args.benchmark)
        sql += " ORDER BY sc.total_score DESC, sc.review_date DESC LIMIT ?"
        params.append(args.limit)
        rows = [
            (*r[:12], _format_tokens(r[12]), _format_seconds(r[13]), r[14] or "—", r[15])
            for r in conn.execute(sql, params).fetchall()
        ]
        headers = ["benchmark", "harness", "model", "tag",
                   "concept/20", "data/15", "sim/20", "exp/15",
                   "results/15", "code/10", "trace/5", "total/100",
                   "tokens", "time", "intervention", "reviewer"]
        print(_format_table(rows, headers))
        return 0
```

- [ ] **Step 2: Add the formatter helpers**

Insert these helpers above `def main()` in `harness/scoreboard.py`:

```python
def _format_tokens(total: int | None) -> str:
    if total is None:
        return "—"
    if total >= 1_000_000:
        return f"{total / 1_000_000:.1f}M"
    if total >= 1_000:
        return f"{total // 1_000}k"
    return str(total)


def _format_seconds(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    minutes, sec = divmod(int(round(seconds)), 60)
    if minutes == 0:
        return f"{sec}s"
    return f"{minutes}m {sec:02d}s"
```

- [ ] **Step 3: Smoke test the CLI against the existing DB**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/record_score.py --from-json scores/seed_scores.json && python harness/scoreboard.py --detailed`
Expected: prints a table that includes `tokens`, `time`, `intervention` columns. All four submissions appear; `gsd2` shows `—` for tokens and time (because no `token_usage.json`/`run_metrics.json` exists yet — Phase 1, Task 6 fixes that). `intervention` is `unrecorded` everywhere until Task 6.

- [ ] **Step 4: Commit**

```bash
git add harness/scoreboard.py
git commit -m "feat: scoreboard --detailed shows tokens, time, intervention"
```

### Task 5: Update `RUN_PROTOCOL.md` — required files + intervention category

**Files:**
- Modify: `RUN_PROTOCOL.md`

- [ ] **Step 1: Tighten §4 wording**

In `RUN_PROTOCOL.md`, replace the entire §4 block (header `## 4. Quantitative measurement` through to `If exact token usage is unavailable, use:` exclusive) with:

```markdown
## 4. Quantitative measurement (required)

Every submission MUST include `run_metrics.json`. Produce it with:

```bash
python harness/measure_run.py \
  --submission-dir path/to/submission \
  --command "python run_experiment.py" \
  --metrics-out path/to/submission/run_metrics.json
```

If the platform does not expose runtime data (e.g. an interactive harness), the file must still exist with `runtime_seconds: null` and a note explaining why.

This records:

- command
- start time
- end time
- runtime seconds
- return code
- stdout/stderr tails
- Python LOC
- file counts
```

- [ ] **Step 2: Tighten §5 wording**

Replace the entire §5 block (header `## 5. Token usage` through to the line before `## 6. Automated evaluation`) with:

```markdown
## 5. Token usage (required)

Every submission MUST include `token_usage.json`. Schema:

```json
{
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "token_count_method": "exact",
  "estimated_cost_usd": null
}
```

`token_count_method` is one of `"exact"`, `"reported"`, `"estimated"`, or `"unknown"`.

If the platform does not expose token usage, write:

```json
{
  "input_tokens": null,
  "output_tokens": null,
  "total_tokens": null,
  "token_count_method": "unknown",
  "estimated_cost_usd": null
}
```

The file must always exist. Do not mix exact and estimated counts without labelling them.
```

- [ ] **Step 3: Add the structured intervention block to §8**

In `RUN_PROTOCOL.md`, replace `## 8. Recording interventions` and its body with:

```markdown
## 8. Recording interventions

Record every human nudge, clarification, manual fix, or rerun.

A good benchmark result should distinguish:

- fully autonomous success
- success after one or more hints
- success after manual repair
- failed run

Capture this in two places:

1. **Narrative** — `interventions.md` or a section of `README.md` describing what happened.
2. **Structured** — add this block to `submission.yaml`:

   ```yaml
   intervention:
     category: autonomous | hints | manual_repair | failed | unrecorded
     notes: "free text; references to interventions.md welcomed"
   ```

   The `category` field drives the leaderboard intervention badge. If the field is missing or contains an unknown value, the dashboard treats the run as `unrecorded`.
```

- [ ] **Step 4: Commit**

```bash
git add RUN_PROTOCOL.md
git commit -m "docs: require token_usage.json + run_metrics.json; add intervention.category"
```

### Task 6: Backfill the four existing submissions via `normalize_tokens.py`

**Files:**
- Create: `harness/normalize_tokens.py`
- Test: `tests/harness/test_normalize_tokens.py`
- Modify (generated): `submissions/*/token_usage.json`, `submissions/*/run_metrics.json`, `submissions/*/submission.yaml`

- [ ] **Step 1: Write the failing test**

Create `tests/harness/test_normalize_tokens.py`:

```python
"""Tests for the one-shot backfill in harness.normalize_tokens."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml

from normalize_tokens import BACKFILL, backfill_one


@pytest.fixture
def submission_with_legacy_yaml(tmp_path: Path) -> Path:
    folder = tmp_path / "2026-04-25__001_synthetic_mine_throughput__pi-agent__gemini-3-1-pro-preview__vanilla-customtools"
    folder.mkdir()
    (folder / "submission.yaml").write_text(
        "submission_id: 2026-04-25__001_synthetic_mine_throughput__pi-agent__gemini-3-1-pro-preview__vanilla-customtools\n"
        "date: 2026-04-25\n"
        "benchmark_id: 001_synthetic_mine_throughput\n"
        "harness:\n  name: pi-agent\n"
        "model:\n  name: gemini-3-1-pro-preview\n  vendor: google\n"
        "run_tag: vanilla-customtools\n"
        "operator: harry\n"
        "status: scaffolded\n"
        "time_s: 297\n"
        "tokens_in: 78000\n"
        "tokens_out: 21000\n",
        encoding="utf-8",
    )
    return folder


def test_backfill_writes_token_usage_and_run_metrics(submission_with_legacy_yaml: Path) -> None:
    spec = BACKFILL[submission_with_legacy_yaml.name]
    backfill_one(submission_with_legacy_yaml, spec)

    tokens = json.loads((submission_with_legacy_yaml / "token_usage.json").read_text())
    assert tokens["total_tokens"] == 99000
    assert tokens["input_tokens"] == 78000
    assert tokens["output_tokens"] == 21000
    assert tokens["token_count_method"] == "reported"

    metrics = json.loads((submission_with_legacy_yaml / "run_metrics.json").read_text())
    assert metrics["runtime_seconds"] == 297.0


def test_backfill_adds_intervention_to_yaml(submission_with_legacy_yaml: Path) -> None:
    spec = BACKFILL[submission_with_legacy_yaml.name]
    backfill_one(submission_with_legacy_yaml, spec)

    payload = yaml.safe_load((submission_with_legacy_yaml / "submission.yaml").read_text())
    assert payload["intervention"]["category"] == spec["intervention"]
    # Legacy fields remain in place; we don't strip them.
    assert payload["time_s"] == 297


def test_backfill_skips_existing_files(submission_with_legacy_yaml: Path) -> None:
    """Running a second time must not overwrite existing token_usage.json content."""
    (submission_with_legacy_yaml / "token_usage.json").write_text(
        json.dumps({"total_tokens": 1, "input_tokens": None, "output_tokens": None,
                    "token_count_method": "exact", "estimated_cost_usd": None}),
        encoding="utf-8",
    )
    spec = BACKFILL[submission_with_legacy_yaml.name]
    backfill_one(submission_with_legacy_yaml, spec)

    tokens = json.loads((submission_with_legacy_yaml / "token_usage.json").read_text())
    assert tokens["total_tokens"] == 1  # untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_normalize_tokens.py -v`
Expected: FAIL — module does not exist yet.

- [ ] **Step 3: Implement `harness/normalize_tokens.py`**

Create `harness/normalize_tokens.py`:

```python
"""One-shot backfill for token_usage.json + run_metrics.json + intervention.

Run from the repo root:

    python harness/normalize_tokens.py

Reads informal token/time fields from each existing submission's submission.yaml
and writes the canonical files defined in RUN_PROTOCOL.md §4 + §5. Idempotent:
existing canonical files are left untouched.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SUBMISSIONS_ROOT = REPO_ROOT / "submissions"

# Source-of-truth values for the four submissions present at design time.
# Per spec §3 backfill table.
BACKFILL: dict[str, dict] = {
    "2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking": {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": 116900,
        "token_count_method": "reported",
        "runtime_seconds": 699.0,
        "intervention": "autonomous",
    },
    "2026-04-25__001_synthetic_mine_throughput__codex-cli__gpt-5-5__xhigh": {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": 503000,
        "token_count_method": "reported",
        "runtime_seconds": 400.0,
        "intervention": "autonomous",
    },
    "2026-04-25__001_synthetic_mine_throughput__pi-agent__gemini-3-1-pro-preview__vanilla-customtools": {
        "input_tokens": 78000,
        "output_tokens": 21000,
        "total_tokens": 99000,
        "token_count_method": "reported",
        "runtime_seconds": 297.0,
        "intervention": "autonomous",
    },
    "2026-04-27__001_synthetic_mine_throughput__gsd2__gemini-3-1-pro-preview__customtools": {
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "token_count_method": "unknown",
        "runtime_seconds": None,
        "intervention": "unrecorded",
    },
}


def _write_if_missing(path: Path, payload: dict) -> bool:
    if path.exists():
        return False
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return True


def _ensure_intervention(yaml_path: Path, category: str) -> None:
    if not yaml_path.exists():
        return
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    if isinstance(payload.get("intervention"), dict) and payload["intervention"].get("category"):
        return
    payload["intervention"] = {"category": category, "notes": ""}
    yaml_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def backfill_one(folder: Path, spec: dict) -> None:
    _write_if_missing(
        folder / "token_usage.json",
        {
            "input_tokens": spec["input_tokens"],
            "output_tokens": spec["output_tokens"],
            "total_tokens": spec["total_tokens"],
            "token_count_method": spec["token_count_method"],
            "estimated_cost_usd": None,
        },
    )
    _write_if_missing(
        folder / "run_metrics.json",
        {
            "command": None,
            "runtime_seconds": spec["runtime_seconds"],
            "return_code": None,
            "timed_out": None,
            "note": "Backfilled from submission.yaml; no live measurement was performed.",
        },
    )
    _ensure_intervention(folder / "submission.yaml", spec["intervention"])


def main() -> int:
    missing: list[str] = []
    for name, spec in BACKFILL.items():
        folder = SUBMISSIONS_ROOT / name
        if not folder.exists():
            missing.append(name)
            continue
        backfill_one(folder, spec)
        print(f"Backfilled {name}")
    if missing:
        print(f"WARNING: {len(missing)} submission(s) not found:", file=sys.stderr)
        for name in missing:
            print(f"  - {name}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_normalize_tokens.py -v`
Expected: all three tests PASS.

- [ ] **Step 5: Run the backfill against the real submissions**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/normalize_tokens.py`
Expected: prints "Backfilled <name>" for all four submissions, exits 0.

- [ ] **Step 6: Verify the canonical files were written**

Run: `cd /Users/harry/Workspace/simulation-bench && for d in submissions/2026-04-2*; do echo "=== $d ==="; ls "$d"/token_usage.json "$d"/run_metrics.json 2>&1; done`
Expected: every directory lists both files.

- [ ] **Step 7: Re-ingest and re-print the scoreboard**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/record_score.py --from-json scores/seed_scores.json && python harness/scoreboard.py --detailed`
Expected: `tokens` shows `116k`, `503k`, `99k`, `—` for the four submissions; `time` shows `11m 39s`, `6m 40s`, `4m 57s`, `—`; `intervention` is `autonomous` for the first three and `unrecorded` for `gsd2`.

- [ ] **Step 8: Commit (code + backfilled files)**

```bash
git add harness/normalize_tokens.py tests/harness/test_normalize_tokens.py \
        submissions/*/token_usage.json submissions/*/run_metrics.json \
        submissions/*/submission.yaml
git commit -m "feat: backfill token_usage.json, run_metrics.json, intervention category"
```

### Task 7: Update the `create-submission` skill to scaffold stub files

**Files:**
- Modify: `.claude/skills/create-submission/SKILL.md`

- [ ] **Step 1: Add the stub-file step in the skill**

In `.claude/skills/create-submission/SKILL.md`, find the Step 3 block beginning with the comment `Use these commands from the project root:`. Immediately after the `cp -R …` line in that bash block, append two new commands:

```bash
cat > submissions/<folder>/token_usage.json <<'JSON'
{
  "input_tokens": null,
  "output_tokens": null,
  "total_tokens": null,
  "token_count_method": "unknown",
  "estimated_cost_usd": null
}
JSON
cat > submissions/<folder>/run_metrics.json <<'JSON'
{
  "command": null,
  "runtime_seconds": null,
  "return_code": null,
  "timed_out": null,
  "note": "Populate via harness/measure_run.py once the run completes."
}
JSON
```

- [ ] **Step 2: Add the intervention block in Step 4 (`submission.yaml`)**

In Step 4 of the skill, replace the existing example YAML block (the eleven lines from `submission_id: …` through `status: scaffolded …`) with:

```yaml
submission_id: <folder name>
date: <YYYY-MM-DD>
benchmark_id: <benchmark_id>
harness:
  name: <harness>
  version: <string or "tbc">
  notes: <free-form, e.g. "vanilla, no skills loaded">
model:
  name: <model>
  vendor: <anthropic | openai | google | …>
  notes: <free-form, e.g. "1M context, default thinking budget">
run_tag: <run_tag or null>
operator: <user's name or env, optional>
status: scaffolded     # scaffolded | running | complete | abandoned
intervention:
  category: unrecorded   # autonomous | hints | manual_repair | failed | unrecorded
  notes: ""
```

Add a sentence directly below the YAML: "Leave `intervention.category` as `unrecorded` until the run completes; update it during evaluation per `RUN_PROTOCOL.md` §8."

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/create-submission/SKILL.md
git commit -m "docs: scaffold token_usage.json, run_metrics.json, intervention in create-submission"
```

### Task 8: Update the `evaluate-submission` skill with warnings

**Files:**
- Modify: `.claude/skills/evaluate-submission/SKILL.md`

- [ ] **Step 1: Tighten Step 4 of the skill**

In `.claude/skills/evaluate-submission/SKILL.md`, replace the entirety of `## Step 4 — Validate token usage shape (optional but preferred)` and its body (down to the line before `## Step 5 — Run the evaluator`) with:

```markdown
## Step 4 — Validate token usage shape (required, soft-fail)

Per `RUN_PROTOCOL.md` §5, every submission MUST contain a `token_usage.json` and a `run_metrics.json`. Schema for `token_usage.json`:

```json
{
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "token_count_method": "exact",
  "estimated_cost_usd": null
}
```

Soft-fail behaviour (do not abort):

- If `token_usage.json` is missing → print a loud warning telling the operator to generate the file (the dashboard treats it as `unrecorded`).
- If `run_metrics.json` is missing → print a loud warning and suggest `harness/measure_run.py`.
- If `token_count_method == "unknown"` → flag it explicitly in the summary so reviewers know the row will show `—` on the leaderboard.

Surface `token_count_method` (`"exact"`, `"reported"`, `"estimated"`, or `"unknown"`) in the report summary regardless.
```

- [ ] **Step 2: Add the intervention check at the end of Step 6**

In the same file, find the bullet `- **Intervention status** — …` inside `## Step 6 — Summarise the report`. Replace that bullet with:

```markdown
- **Intervention status** — read `submission.yaml.intervention.category`. Surface one of: `autonomous`, `hints`, `manual_repair`, `failed`, `unrecorded`. If the field is missing or unrecognised, prompt the operator to fill it in (per `RUN_PROTOCOL.md` §8); the dashboard will render `?` until they do.
```

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/evaluate-submission/SKILL.md
git commit -m "docs: warn on missing token_usage/run_metrics; require intervention.category"
```

### Task 9: Phase 1 exit criterion

- [ ] **Step 1: Re-run the seed ingest end-to-end**

Run:

```bash
cd /Users/harry/Workspace/simulation-bench
python harness/normalize_tokens.py
python harness/record_score.py --from-json scores/seed_scores.json
python harness/scoreboard.py --detailed
```

Expected: detailed scoreboard table includes `tokens`, `time`, `intervention` columns. Three submissions show real values; `gsd2` shows `—` for tokens/time and `unrecorded` for intervention.

- [ ] **Step 2: Run the entire test suite**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/ -v`
Expected: all tests in `tests/harness/` pass.

---

# Phase 2 — Dashboard Scaffold (local only)

Goal: an Astro project under `dashboard/` that renders the leaderboard plus methodology pages, fed by `harness/build_dashboard.py`. **Exit criterion (per spec §6):** `npm run dev` shows the leaderboard and methodology pages locally with all four submissions; sorting works.

### Task 10: Initialise the Astro project

**Files:**
- Create: `dashboard/package.json`
- Create: `dashboard/astro.config.mjs`
- Create: `dashboard/tsconfig.json`
- Create: `dashboard/.gitignore`
- Create: `dashboard/src/styles/global.css`

- [ ] **Step 1: Verify Node is available**

Run: `node --version && npm --version`
Expected: Node ≥ 20 and npm ≥ 10. If not present, install Node 20 LTS before continuing.

- [ ] **Step 2: Create `dashboard/package.json`**

```json
{
  "name": "simulation-bench-dashboard",
  "type": "module",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "astro dev",
    "build": "astro build",
    "preview": "astro preview",
    "astro": "astro"
  },
  "dependencies": {
    "astro": "^5.0.0"
  }
}
```

- [ ] **Step 3: Create `dashboard/astro.config.mjs`**

```js
// @ts-check
import { defineConfig } from "astro/config";

export default defineConfig({
  site: "https://simulation-bench.fly.dev",
  build: {
    format: "directory",
  },
  markdown: {
    shikiConfig: {
      theme: "github-dark",
      wrap: true,
    },
  },
});
```

- [ ] **Step 4: Create `dashboard/tsconfig.json`**

```json
{
  "extends": "astro/tsconfigs/strict",
  "include": ["src/**/*", ".astro/types.d.ts"]
}
```

- [ ] **Step 5: Create `dashboard/.gitignore`**

```gitignore
node_modules/
dist/
.astro/
src/data/leaderboard.json
src/content/submissions/
src/content/methodology/scoring.md
src/content/methodology/protocol.md
public/submissions/
```

- [ ] **Step 6: Create `dashboard/src/styles/global.css`**

```css
:root {
  --bg: #ffffff;
  --fg: #0f172a;
  --muted: #475569;
  --accent: #2563eb;
  --border: #e2e8f0;
  --row-alt: #f8fafc;
  --code-bg: #0f172a;
  --badge-ok: #10b981;
  --badge-warn: #f59e0b;
  --badge-err: #ef4444;
  --badge-unknown: #94a3b8;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0b1120;
    --fg: #e2e8f0;
    --muted: #94a3b8;
    --accent: #60a5fa;
    --border: #1e293b;
    --row-alt: #111827;
    --code-bg: #020617;
  }
}

* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: var(--bg); color: var(--fg); font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; line-height: 1.5; }
main { max-width: 1100px; margin: 0 auto; padding: 1.5rem 1rem 4rem; }
a { color: var(--accent); }
table { width: 100%; border-collapse: collapse; }
th, td { text-align: left; padding: 0.5rem 0.75rem; border-bottom: 1px solid var(--border); }
th { cursor: pointer; user-select: none; font-weight: 600; }
tr:nth-child(even) td { background: var(--row-alt); }
code, pre { font-family: ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace; }
pre { background: var(--code-bg); color: #e2e8f0; padding: 0.75rem 1rem; border-radius: 6px; overflow-x: auto; }
.badge { display: inline-block; padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.75rem; }
.badge-ok { background: var(--badge-ok); color: white; }
.badge-warn { background: var(--badge-warn); color: white; }
.badge-err { background: var(--badge-err); color: white; }
.badge-unknown { background: var(--badge-unknown); color: white; }
```

- [ ] **Step 7: Install dependencies**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npm install`
Expected: lockfile written, `node_modules/` populated, no errors.

- [ ] **Step 8: Smoke-test the Astro CLI**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npx astro --version`
Expected: prints an Astro version ≥ 5.0.0.

- [ ] **Step 9: Commit**

```bash
git add dashboard/package.json dashboard/package-lock.json dashboard/astro.config.mjs dashboard/tsconfig.json dashboard/.gitignore dashboard/src/styles/global.css
git commit -m "feat(dashboard): scaffold Astro project"
```

### Task 11: Define content collections and the layout shell

**Files:**
- Create: `dashboard/src/content.config.ts`
- Create: `dashboard/src/layouts/Layout.astro`
- Create: `dashboard/src/components/Header.astro`

- [ ] **Step 1: Create `dashboard/src/content.config.ts`**

```ts
import { defineCollection, z } from "astro:content";
import { glob } from "astro/loaders";

const submissions = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/submissions" }),
  schema: z.object({
    id: z.string(),
    runDate: z.string(),
    benchmarkId: z.string(),
    harness: z.string(),
    model: z.string(),
    runTag: z.string().nullable(),
    totalScore: z.number().nullable(),
    categoryScores: z.object({
      conceptual_modelling: z.number().nullable(),
      data_topology: z.number().nullable(),
      simulation_correctness: z.number().nullable(),
      experimental_design: z.number().nullable(),
      results_interpretation: z.number().nullable(),
      code_quality: z.number().nullable(),
      traceability: z.number().nullable(),
    }),
    totalTokens: z.number().nullable(),
    inputTokens: z.number().nullable(),
    outputTokens: z.number().nullable(),
    tokenCountMethod: z.string().nullable(),
    runtimeSeconds: z.number().nullable(),
    interventionCategory: z.string(),
    reviewer: z.string().nullable(),
    reviewDate: z.string().nullable(),
    recommendation: z.string().nullable(),
    notes: z.string().nullable(),
    files: z.array(
      z.object({
        path: z.string(),
        kind: z.enum(["text", "binary", "download"]),
        bytes: z.number(),
        language: z.string().nullable(),
      })
    ),
  }),
});

const methodology = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/methodology" }),
  schema: z.object({
    title: z.string(),
    sourcePath: z.string().nullable(),
  }),
});

export const collections = { submissions, methodology };
```

- [ ] **Step 2: Create `dashboard/src/components/Header.astro`**

```astro
---
const { title } = Astro.props;
---

<header>
  <nav>
    <a href="/" class="brand">Simulation Bench</a>
    <a href="/methodology/">Methodology</a>
    <a href="/methodology/scoring/">Scoring</a>
    <a href="/methodology/protocol/">Protocol</a>
    <a href="https://github.com/harrymunro/simulation-bench" rel="noreferrer">GitHub</a>
  </nav>
  {title && <h1>{title}</h1>}
</header>

<style>
  header { border-bottom: 1px solid var(--border); padding: 1rem 0 0.75rem; margin-bottom: 1.5rem; }
  nav { display: flex; flex-wrap: wrap; gap: 1rem; align-items: baseline; }
  nav a { text-decoration: none; }
  .brand { font-weight: 700; font-size: 1.1rem; }
  h1 { margin: 0.75rem 0 0; font-size: 1.5rem; }
</style>
```

- [ ] **Step 3: Create `dashboard/src/layouts/Layout.astro`**

```astro
---
import "../styles/global.css";
import Header from "../components/Header.astro";

interface Props {
  title: string;
  description?: string;
  pageTitle?: string;
}

const { title, description, pageTitle } = Astro.props;
---

<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{title}</title>
    {description && <meta name="description" content={description} />}
  </head>
  <body>
    <main>
      <Header title={pageTitle ?? title} />
      <slot />
      <footer>
        <p>
          Static dashboard built from <code>scores/scores.db</code> and
          <code>submissions/</code>. See <a href="/methodology/dashboard/">build pipeline</a>.
        </p>
      </footer>
    </main>
  </body>
</html>

<style>
  footer { margin-top: 4rem; color: var(--muted); font-size: 0.875rem; border-top: 1px solid var(--border); padding-top: 1rem; }
</style>
```

- [ ] **Step 4: Type-check the Astro project**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npx astro check 2>&1 | tail -20`
Expected: 0 errors. Warnings about missing content collections are acceptable until Task 13.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/content.config.ts dashboard/src/layouts/Layout.astro dashboard/src/components/Header.astro
git commit -m "feat(dashboard): add content collections schema and base layout"
```

### Task 12: Build `harness/build_dashboard.py` v0 — leaderboard JSON only

**Files:**
- Create: `harness/build_dashboard.py`
- Test: `tests/harness/test_build_dashboard.py`

- [ ] **Step 1: Write the failing test**

Create `tests/harness/test_build_dashboard.py`:

```python
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
            conceptual_modelling=18, data_topology=14, simulation_correctness=18,
            experimental_design=14, results_interpretation=14, code_quality=9, traceability=5,
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
    assert row["totalScore"] == 78
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
    assert payload[0]["totalScore"] == 78
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: FAIL — `build_dashboard` does not exist.

- [ ] **Step 3: Implement `harness/build_dashboard.py` v0**

Create `harness/build_dashboard.py`:

```python
"""Generate Astro inputs from scores/scores.db + submissions/.

Run from the repo root:

    python harness/build_dashboard.py

Outputs:

- dashboard/src/data/leaderboard.json — one entry per scored submission.
- dashboard/src/content/submissions/<id>.md — frontmatter + body stub.
- dashboard/src/content/methodology/{scoring,protocol}.md — copies of root docs.
- dashboard/public/submissions/<id>/<file> — bulky download files.

Phase 2 (this v0) only writes leaderboard.json + methodology copies. Phase 3
adds the per-submission file walker.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "scores" / "scores.db"
DEFAULT_DASHBOARD_ROOT = REPO_ROOT / "dashboard"


def load_leaderboard(db_path: Path) -> list[dict]:
    """Return one dict per scored submission, ordered by total score desc."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                s.submission_id, s.run_date, s.benchmark_id, s.harness, s.model, s.run_tag,
                s.total_tokens, s.input_tokens, s.output_tokens, s.token_count_method,
                s.runtime_seconds, s.intervention_category,
                sc.total_score, sc.conceptual_modelling, sc.data_topology, sc.simulation_correctness,
                sc.experimental_design, sc.results_interpretation, sc.code_quality, sc.traceability,
                sc.reviewer, sc.review_date, sc.recommendation, sc.notes
            FROM submissions s
            JOIN scores sc USING (submission_id)
            ORDER BY sc.total_score DESC, sc.review_date DESC
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "submission_id": r["submission_id"],
            "runDate": r["run_date"],
            "benchmarkId": r["benchmark_id"],
            "harness": r["harness"],
            "model": r["model"],
            "runTag": r["run_tag"],
            "totalScore": r["total_score"],
            "categoryScores": {
                "conceptual_modelling": r["conceptual_modelling"],
                "data_topology": r["data_topology"],
                "simulation_correctness": r["simulation_correctness"],
                "experimental_design": r["experimental_design"],
                "results_interpretation": r["results_interpretation"],
                "code_quality": r["code_quality"],
                "traceability": r["traceability"],
            },
            "totalTokens": r["total_tokens"],
            "inputTokens": r["input_tokens"],
            "outputTokens": r["output_tokens"],
            "tokenCountMethod": r["token_count_method"],
            "runtimeSeconds": r["runtime_seconds"],
            "interventionCategory": r["intervention_category"] or "unrecorded",
            "reviewer": r["reviewer"],
            "reviewDate": r["review_date"],
            "recommendation": r["recommendation"],
            "notes": r["notes"],
        }
        for r in rows
    ]


def write_leaderboard_json(db_path: Path, out_path: Path) -> None:
    rows = load_leaderboard(db_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")


def copy_methodology(src_root: Path, dest_root: Path) -> None:
    dest_root.mkdir(parents=True, exist_ok=True)
    for filename, title in (("SCORING_GUIDE.md", "Scoring guide"),
                             ("RUN_PROTOCOL.md", "Run protocol")):
        src = src_root / filename
        if not src.exists():
            continue
        slug = filename.lower().replace("_", "-").replace(".md", "")
        slug = "scoring" if "scoring" in slug else "protocol"
        body = src.read_text(encoding="utf-8")
        frontmatter = f"---\ntitle: {title}\nsourcePath: {filename}\n---\n\n"
        (dest_root / f"{slug}.md").write_text(frontmatter + body, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--dashboard-root", type=Path, default=DEFAULT_DASHBOARD_ROOT)
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No scores DB at {args.db}", file=sys.stderr)
        return 1

    write_leaderboard_json(args.db, args.dashboard_root / "src" / "data" / "leaderboard.json")
    copy_methodology(REPO_ROOT, args.dashboard_root / "src" / "content" / "methodology")
    print(f"Wrote leaderboard.json and methodology to {args.dashboard_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: both tests PASS.

- [ ] **Step 5: Generate inputs against the real DB**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/build_dashboard.py`
Expected: prints "Wrote leaderboard.json and methodology to …". Files appear at `dashboard/src/data/leaderboard.json`, `dashboard/src/content/methodology/scoring.md`, `dashboard/src/content/methodology/protocol.md`.

- [ ] **Step 6: Commit**

```bash
git add harness/build_dashboard.py tests/harness/test_build_dashboard.py
git commit -m "feat: harness/build_dashboard.py v0 — leaderboard JSON + methodology copy"
```

### Task 13: Render the leaderboard table

**Files:**
- Create: `dashboard/src/components/InterventionBadge.astro`
- Create: `dashboard/src/components/LeaderboardTable.astro`
- Create: `dashboard/src/pages/index.astro`

- [ ] **Step 1: Create `dashboard/src/components/InterventionBadge.astro`**

```astro
---
interface Props {
  category: string;
}
const { category } = Astro.props;
const config: Record<string, { label: string; symbol: string; cls: string }> = {
  autonomous:    { label: "Autonomous",    symbol: "✓", cls: "badge-ok" },
  hints:         { label: "Hints",         symbol: "!", cls: "badge-warn" },
  manual_repair: { label: "Manual repair", symbol: "⚙", cls: "badge-warn" },
  failed:        { label: "Failed",        symbol: "✗", cls: "badge-err" },
  unrecorded:    { label: "Unrecorded",    symbol: "?", cls: "badge-unknown" },
};
const entry = config[category] ?? config.unrecorded;
---
<span class={`badge ${entry.cls}`} title={entry.label}>
  {entry.symbol} {entry.label}
</span>
```

- [ ] **Step 2: Create `dashboard/src/components/LeaderboardTable.astro`**

```astro
---
import InterventionBadge from "./InterventionBadge.astro";

interface CategoryScores {
  conceptual_modelling: number | null;
  data_topology: number | null;
  simulation_correctness: number | null;
  experimental_design: number | null;
  results_interpretation: number | null;
  code_quality: number | null;
  traceability: number | null;
}

interface Row {
  submission_id: string;
  runDate: string;
  benchmarkId: string;
  harness: string;
  model: string;
  runTag: string | null;
  totalScore: number | null;
  categoryScores: CategoryScores;
  totalTokens: number | null;
  inputTokens: number | null;
  outputTokens: number | null;
  tokenCountMethod: string | null;
  runtimeSeconds: number | null;
  interventionCategory: string;
}

interface Props {
  rows: Row[];
}

const { rows } = Astro.props;

function formatTokens(n: number | null): string {
  if (n === null || n === undefined) return "—";
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${Math.round(n / 1_000)}k`;
  return String(n);
}

function formatSeconds(s: number | null): string {
  if (s === null || s === undefined) return "—";
  const total = Math.round(s);
  const m = Math.floor(total / 60);
  const r = total % 60;
  return m === 0 ? `${r}s` : `${m}m ${String(r).padStart(2, "0")}s`;
}

function tokenTooltip(r: Row): string {
  const parts: string[] = [];
  if (r.inputTokens !== null) parts.push(`in: ${formatTokens(r.inputTokens)}`);
  if (r.outputTokens !== null) parts.push(`out: ${formatTokens(r.outputTokens)}`);
  parts.push(`method: ${r.tokenCountMethod ?? "unknown"}`);
  return parts.join(" · ");
}
---
<table id="leaderboard">
  <thead>
    <tr>
      <th data-sort="rank" data-type="number">#</th>
      <th data-sort="runDate" data-type="string">Date</th>
      <th data-sort="benchmarkId" data-type="string">Benchmark</th>
      <th data-sort="harness" data-type="string">Harness</th>
      <th data-sort="model" data-type="string">Model</th>
      <th data-sort="runTag" data-type="string">Tag</th>
      <th data-sort="totalScore" data-type="number" data-default-desc="true">
        <a href="/methodology/scoring/">Quality / 100</a>
      </th>
      <th data-sort="totalTokens" data-type="number">
        <a href="/methodology/protocol/#5-token-usage-required">Tokens</a>
      </th>
      <th data-sort="runtimeSeconds" data-type="number">
        <a href="/methodology/protocol/#4-quantitative-measurement-required">Time</a>
      </th>
      <th data-sort="interventionCategory" data-type="string">
        <a href="/methodology/protocol/#8-recording-interventions">Intervention</a>
      </th>
    </tr>
  </thead>
  <tbody>
    {rows.map((row, i) => (
      <tr data-row={JSON.stringify(row)}>
        <td>{i + 1}</td>
        <td>{row.runDate}</td>
        <td>{row.benchmarkId}</td>
        <td>{row.harness}</td>
        <td>{row.model}{row.runTag ? ` / ${row.runTag}` : ""}</td>
        <td>{row.runTag ?? ""}</td>
        <td>
          <a href={`/submissions/${row.submission_id}/`}>{row.totalScore ?? "—"}</a>
        </td>
        <td title={tokenTooltip(row)}>{formatTokens(row.totalTokens)}</td>
        <td>{formatSeconds(row.runtimeSeconds)}</td>
        <td><InterventionBadge category={row.interventionCategory} /></td>
      </tr>
    ))}
  </tbody>
</table>

<script>
  const table = document.getElementById("leaderboard") as HTMLTableElement | null;
  if (table) {
    const tbody = table.querySelector("tbody")!;
    let activeKey: string | null = null;
    let activeDir: 1 | -1 = -1;
    table.querySelectorAll("th[data-sort]").forEach((th) => {
      th.addEventListener("click", () => {
        const key = th.getAttribute("data-sort")!;
        const type = th.getAttribute("data-type") ?? "string";
        const defaultDesc = th.getAttribute("data-default-desc") === "true";
        if (activeKey === key) {
          activeDir = activeDir === 1 ? -1 : 1;
        } else {
          activeKey = key;
          activeDir = defaultDesc ? -1 : 1;
        }
        const rows = Array.from(tbody.querySelectorAll<HTMLTableRowElement>("tr"));
        rows.sort((a, b) => {
          if (key === "rank") return 0;
          const aRow = JSON.parse(a.getAttribute("data-row")!);
          const bRow = JSON.parse(b.getAttribute("data-row")!);
          const aVal = aRow[key];
          const bVal = bRow[key];
          if (aVal === null || aVal === undefined) return 1;
          if (bVal === null || bVal === undefined) return -1;
          if (type === "number") return ((aVal as number) - (bVal as number)) * activeDir;
          return String(aVal).localeCompare(String(bVal)) * activeDir;
        });
        rows.forEach((r, i) => {
          r.querySelector("td")!.textContent = String(i + 1);
          tbody.appendChild(r);
        });
      });
    });
  }
</script>
```

- [ ] **Step 3: Create `dashboard/src/pages/index.astro`**

```astro
---
import Layout from "../layouts/Layout.astro";
import LeaderboardTable from "../components/LeaderboardTable.astro";
import rows from "../data/leaderboard.json";
---
<Layout title="Simulation Bench" pageTitle="Leaderboard">
  <p>
    A reproducible benchmark for AI-assisted discrete-event simulation work.
    Sort by Quality, Tokens, or Time — there is no combined score on purpose.
  </p>
  <LeaderboardTable rows={rows} />
</Layout>
```

- [ ] **Step 4: Run dev server and inspect**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npm run dev -- --host 127.0.0.1 --port 4321`
Open `http://127.0.0.1:4321/` in a browser.
Expected: leaderboard table with four rows. Quality column sorted desc by default. Clicking column headers re-sorts. Intervention badge shows ✓ Autonomous for top three rows, ? Unrecorded for `gsd2`. Stop the dev server with Ctrl+C.

- [ ] **Step 5: Type-check**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npx astro check 2>&1 | tail -10`
Expected: 0 errors.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/components/InterventionBadge.astro dashboard/src/components/LeaderboardTable.astro dashboard/src/pages/index.astro
git commit -m "feat(dashboard): leaderboard table with client-side sorting"
```

### Task 14: Render the methodology pages

**Files:**
- Create: `dashboard/src/pages/methodology/index.astro`
- Create: `dashboard/src/pages/methodology/scoring.astro`
- Create: `dashboard/src/pages/methodology/protocol.astro`
- Create: `dashboard/src/pages/methodology/dashboard.astro`

- [ ] **Step 1: Create `dashboard/src/pages/methodology/index.astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
---
<Layout title="Methodology — Simulation Bench" pageTitle="Methodology">
  <ul>
    <li><a href="/methodology/scoring/">Scoring guide</a> — the 100-point human rubric.</li>
    <li><a href="/methodology/protocol/">Run protocol</a> — required deliverables, token capture, intervention recording.</li>
    <li><a href="/methodology/dashboard/">How this dashboard is built</a> — data sources and pipeline.</li>
  </ul>
</Layout>
```

- [ ] **Step 2: Create `dashboard/src/pages/methodology/scoring.astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
import { getEntry, render } from "astro:content";

const entry = await getEntry("methodology", "scoring");
if (!entry) throw new Error("methodology/scoring.md missing — run python harness/build_dashboard.py");
const { Content } = await render(entry);
---
<Layout title="Scoring guide — Simulation Bench" pageTitle={entry.data.title}>
  <article><Content /></article>
</Layout>
```

- [ ] **Step 3: Create `dashboard/src/pages/methodology/protocol.astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
import { getEntry, render } from "astro:content";

const entry = await getEntry("methodology", "protocol");
if (!entry) throw new Error("methodology/protocol.md missing — run python harness/build_dashboard.py");
const { Content } = await render(entry);
---
<Layout title="Run protocol — Simulation Bench" pageTitle={entry.data.title}>
  <article><Content /></article>
</Layout>
```

- [ ] **Step 4: Create `dashboard/src/pages/methodology/dashboard.astro`**

```astro
---
import Layout from "../../layouts/Layout.astro";
---
<Layout title="How this dashboard is built — Simulation Bench" pageTitle="How this dashboard is built">
  <article>
    <p>
      The dashboard is a static site rebuilt from two sources of truth in the
      <a href="https://github.com/harrymunro/simulation-bench">repository</a>:
    </p>
    <ul>
      <li><code>scores/scores.db</code> — SQLite DB rebuilt from <code>scores/seed_scores.json</code>.</li>
      <li><code>submissions/&lt;id&gt;/</code> — one folder per run, holding code, results, conceptual model, and per-run metadata.</li>
    </ul>
    <h2>Pipeline</h2>
    <pre><code>{`scores/scores.db ─┐
submissions/      ├─→ harness/build_dashboard.py ─→ dashboard/src/  ─→ astro build ─→ dist/  ─→ fly deploy
docs/methodology  ┘`}</code></pre>
    <h2>Where each leaderboard column comes from</h2>
    <ul>
      <li><strong>Quality</strong> — <code>scores.scores.total_score</code>; sourced from <code>seed_scores.json</code>.</li>
      <li><strong>Tokens</strong> — <code>token_usage.json.total_tokens</code> per submission. Method (<code>exact</code>/<code>reported</code>/<code>estimated</code>/<code>unknown</code>) is shown on hover.</li>
      <li><strong>Time</strong> — <code>run_metrics.json.runtime_seconds</code>.</li>
      <li><strong>Intervention</strong> — <code>submission.yaml.intervention.category</code>.</li>
    </ul>
    <p>
      The site is fully baked into a Caddy container — there is no runtime
      database, API, or auth surface. To rebuild:
    </p>
    <pre><code>{`make dashboard   # rebuild from sources
make deploy      # build + push to fly.io`}</code></pre>
  </article>
</Layout>
```

- [ ] **Step 5: Run dev server and confirm methodology pages render**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npm run dev -- --host 127.0.0.1 --port 4321`
Open `http://127.0.0.1:4321/methodology/`, then `/methodology/scoring/`, `/methodology/protocol/`, `/methodology/dashboard/`.
Expected: each page renders. Scoring and Protocol pages display the markdown content from the repo. Dashboard page shows the pipeline diagram. Stop the dev server.

- [ ] **Step 6: Commit**

```bash
git add dashboard/src/pages/methodology/
git commit -m "feat(dashboard): methodology index, scoring, protocol, dashboard pages"
```

### Task 15: Phase 2 exit criterion

- [ ] **Step 1: Full clean rebuild**

Run:

```bash
cd /Users/harry/Workspace/simulation-bench
python harness/record_score.py --from-json scores/seed_scores.json
python harness/build_dashboard.py
cd dashboard
rm -rf dist .astro
npm run build
```

Expected: `astro build` exits 0. `dashboard/dist/index.html`, `dashboard/dist/methodology/index.html`, `dashboard/dist/methodology/scoring/index.html`, `dashboard/dist/methodology/protocol/index.html`, `dashboard/dist/methodology/dashboard/index.html` all exist.

- [ ] **Step 2: Tests still pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/ -v`
Expected: all tests pass.

---

# Phase 3 — Submission Browser

Goal: every submission has its own page listing files, with text files rendered using Shiki and bulky logs offered as downloads. **Exit criterion (per spec §6):** every submission page lists its files; clicking a `.py` shows highlighted code; clicking `event_log.csv` downloads it.

### Task 16: Define the file-walker allowlist + size threshold

**Files:**
- Modify: `harness/build_dashboard.py`
- Test: `tests/harness/test_build_dashboard.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/harness/test_build_dashboard.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: six new tests FAIL — `classify_file` and `walk_submission` are missing.

- [ ] **Step 3: Add the classifier**

Append to `harness/build_dashboard.py`:

```python
TEXT_LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python", ".md": "markdown", ".yaml": "yaml", ".yml": "yaml",
    ".json": "json", ".toml": "toml", ".csv": "csv", ".txt": "text",
    ".sh": "bash", ".cfg": "ini", ".ini": "ini", ".rst": "markdown",
}
DOWNLOAD_FILENAMES: set[str] = {
    "event_log.csv", "animation.gif", "animation.mp4", "topology.png",
}
DOWNLOAD_EXTENSIONS: set[str] = {".gif", ".mp4", ".png", ".jpg", ".jpeg", ".pdf", ".zip"}
TEXT_BYTE_THRESHOLD = 64 * 1024  # 64 KB

ALLOWLIST_TOP_LEVEL: set[str] = {
    "README.md", "conceptual_model.md", "results.csv", "summary.json",
    "event_log.csv", "submission.yaml", "token_usage.json", "run_metrics.json",
    "topology.png", "animation.gif", "animation.mp4", "interventions.md",
    "requirements.txt", "prompt.md",
}
ALLOWLIST_DIRS: set[str] = {"src", "data", "results", "additional_scenarios"}
SKIP_DIRS: set[str] = {"__pycache__", ".pytest_cache", ".venv", "node_modules", ".git"}


def classify_file(path: Path, root: Path) -> dict | None:
    """Return a file-manifest entry, or None to skip."""
    if not path.is_file():
        return None
    rel = path.relative_to(root).as_posix()
    name = path.name
    ext = path.suffix.lower()
    size = path.stat().st_size

    if name in DOWNLOAD_FILENAMES or ext in DOWNLOAD_EXTENSIONS:
        return {"path": rel, "kind": "download", "bytes": size, "language": None}

    if ext in TEXT_LANGUAGE_BY_EXT:
        if size > TEXT_BYTE_THRESHOLD:
            return {"path": rel, "kind": "download", "bytes": size, "language": None}
        return {"path": rel, "kind": "text", "bytes": size, "language": TEXT_LANGUAGE_BY_EXT[ext]}

    return None


def walk_submission(folder: Path) -> list[dict]:
    """Walk a submission folder and return classified entries respecting the allowlist."""
    entries: list[dict] = []
    for child in sorted(folder.rglob("*")):
        if any(part in SKIP_DIRS for part in child.relative_to(folder).parts):
            continue
        if not child.is_file():
            continue
        rel_parts = child.relative_to(folder).parts
        if len(rel_parts) == 1:
            if rel_parts[0] not in ALLOWLIST_TOP_LEVEL:
                # Allow any top-level Python entry-point file (sim.py, run.py, simulate.py, …).
                if not (rel_parts[0].endswith(".py") and not rel_parts[0].startswith("_")):
                    continue
        else:
            if rel_parts[0] not in ALLOWLIST_DIRS:
                continue
        entry = classify_file(child, folder)
        if entry is not None:
            entries.append(entry)
    return entries
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: all eight tests PASS.

- [ ] **Step 5: Commit**

```bash
git add harness/build_dashboard.py tests/harness/test_build_dashboard.py
git commit -m "feat(build): file-walker allowlist + classifier"
```

### Task 17: Emit per-submission `.md` + copy downloads

**Files:**
- Modify: `harness/build_dashboard.py`
- Test: `tests/harness/test_build_dashboard.py`

- [ ] **Step 1: Append the failing test**

Append to `tests/harness/test_build_dashboard.py`:

```python
def test_emit_submission_writes_frontmatter_and_copies_downloads(tmp_path: Path, populated_db: Path) -> None:
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
    assert f"id: {folder.name}" in text
    assert "interventionCategory: autonomous" in text
    assert "files:" in text

    download = dashboard_root / "public" / "submissions" / folder.name / "event_log.csv"
    assert download.exists()
    assert download.stat().st_size == folder.joinpath("event_log.csv").stat().st_size
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: new test FAILs — `emit_submissions` does not exist.

- [ ] **Step 3: Implement `emit_submissions`**

Append to `harness/build_dashboard.py`:

```python
import shutil


def _yaml_scalar(value) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _render_frontmatter(row: dict, files: list[dict]) -> str:
    cs = row["categoryScores"]
    lines = [
        "---",
        f"id: {_yaml_scalar(row['submission_id'])}",
        f"runDate: {_yaml_scalar(row['runDate'])}",
        f"benchmarkId: {_yaml_scalar(row['benchmarkId'])}",
        f"harness: {_yaml_scalar(row['harness'])}",
        f"model: {_yaml_scalar(row['model'])}",
        f"runTag: {_yaml_scalar(row['runTag'])}",
        f"totalScore: {_yaml_scalar(row['totalScore'])}",
        "categoryScores:",
        f"  conceptual_modelling: {_yaml_scalar(cs['conceptual_modelling'])}",
        f"  data_topology: {_yaml_scalar(cs['data_topology'])}",
        f"  simulation_correctness: {_yaml_scalar(cs['simulation_correctness'])}",
        f"  experimental_design: {_yaml_scalar(cs['experimental_design'])}",
        f"  results_interpretation: {_yaml_scalar(cs['results_interpretation'])}",
        f"  code_quality: {_yaml_scalar(cs['code_quality'])}",
        f"  traceability: {_yaml_scalar(cs['traceability'])}",
        f"totalTokens: {_yaml_scalar(row['totalTokens'])}",
        f"inputTokens: {_yaml_scalar(row['inputTokens'])}",
        f"outputTokens: {_yaml_scalar(row['outputTokens'])}",
        f"tokenCountMethod: {_yaml_scalar(row['tokenCountMethod'])}",
        f"runtimeSeconds: {_yaml_scalar(row['runtimeSeconds'])}",
        f"interventionCategory: {_yaml_scalar(row['interventionCategory'])}",
        f"reviewer: {_yaml_scalar(row['reviewer'])}",
        f"reviewDate: {_yaml_scalar(row['reviewDate'])}",
        f"recommendation: {_yaml_scalar(row['recommendation'])}",
        f"notes: {_yaml_scalar(row['notes'])}",
        "files:",
    ]
    for f in files:
        lines.append(f"  - path: {_yaml_scalar(f['path'])}")
        lines.append(f"    kind: {_yaml_scalar(f['kind'])}")
        lines.append(f"    bytes: {_yaml_scalar(f['bytes'])}")
        lines.append(f"    language: {_yaml_scalar(f['language'])}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)


def emit_submissions(rows: list[dict], submissions_root: Path, dashboard_root: Path) -> None:
    md_root = dashboard_root / "src" / "content" / "submissions"
    public_root = dashboard_root / "public" / "submissions"
    md_root.mkdir(parents=True, exist_ok=True)

    for row in rows:
        folder = submissions_root / row["submission_id"]
        if not folder.exists():
            continue
        files = walk_submission(folder)
        body_lines = [
            "<!-- Body kept short by design; the per-submission Astro page composes its own sections. -->",
            "",
            f"# {row['submission_id']}",
            "",
            "See the file index in the frontmatter for code and downloads.",
            "",
        ]
        (md_root / f"{row['submission_id']}.md").write_text(
            _render_frontmatter(row, files) + "\n".join(body_lines), encoding="utf-8"
        )

        public_dest = public_root / row["submission_id"]
        public_dest.mkdir(parents=True, exist_ok=True)
        for entry in files:
            if entry["kind"] == "download":
                src = folder / entry["path"]
                dest = public_dest / entry["path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
```

- [ ] **Step 4: Wire `emit_submissions` into `main`**

In `harness/build_dashboard.py`, replace the body of `main()` with:

```python
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--dashboard-root", type=Path, default=DEFAULT_DASHBOARD_ROOT)
    parser.add_argument("--submissions-root", type=Path, default=REPO_ROOT / "submissions")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No scores DB at {args.db}", file=sys.stderr)
        return 1

    write_leaderboard_json(args.db, args.dashboard_root / "src" / "data" / "leaderboard.json")
    copy_methodology(REPO_ROOT, args.dashboard_root / "src" / "content" / "methodology")

    rows = load_leaderboard(args.db)
    emit_submissions(rows, args.submissions_root, args.dashboard_root)
    print(f"Emitted {len(rows)} submission page(s) to {args.dashboard_root}")
    return 0
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: all nine tests PASS.

- [ ] **Step 6: Run against real data and inspect output**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/build_dashboard.py`
Expected: prints "Emitted 4 submission page(s) …". Files appear at `dashboard/src/content/submissions/*.md` (four files) and `dashboard/public/submissions/<id>/event_log.csv` for at least the three submissions whose event logs exist.

- [ ] **Step 7: Commit**

```bash
git add harness/build_dashboard.py tests/harness/test_build_dashboard.py
git commit -m "feat(build): emit per-submission .md + copy bulky downloads"
```

### Task 17b: Embed rendered sections (conceptual model, README, reviewer form, evaluation report)

Spec §4 says the submission overview page must render the conceptual model, README, reviewer form, and an evaluation-report summary inline. The cleanest split is: `emit_submissions` writes those bodies into the per-submission `.md` body, and the Astro page renders the body via `<Content />` plus a structured eval-report block from frontmatter.

**Files:**
- Modify: `harness/build_dashboard.py`
- Test: `tests/harness/test_build_dashboard.py`

- [ ] **Step 1: Append the failing tests**

Append to `tests/harness/test_build_dashboard.py`:

```python
def test_emit_submission_embeds_rendered_sections(tmp_path: Path, populated_db: Path) -> None:
    submissions_root = tmp_path / "submissions"
    folder = submissions_root / "2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("# Run notes\n\nWe used Opus 4.7.\n", encoding="utf-8")
    (folder / "conceptual_model.md").write_text("# Conceptual model\n\nTrucks are entities.\n", encoding="utf-8")
    (folder / "results").mkdir()
    (folder / "results" / "reviewer_form.md").write_text(
        "# Reviewer form\n\n- Score: 78/100\n", encoding="utf-8"
    )
    (folder / "results" / "evaluation_report.json").write_text(
        json.dumps(
            {
                "benchmark_id": "001_synthetic_mine_throughput",
                "automated_checks": {"passed": 57, "total": 57, "pass_rate": 1.0},
                "behavioural_checks": {"passed": 6, "total": 6, "details": []},
                "summary": {"scenario_total_tonnes_means": {"baseline": 12345.0}},
                "quantitative_metrics": {"runtime_seconds": 699.0, "return_code": 0},
            }
        ),
        encoding="utf-8",
    )

    dashboard_root = tmp_path / "dashboard"
    rows = build_dashboard.load_leaderboard(populated_db)
    build_dashboard.emit_submissions(rows, submissions_root, dashboard_root)

    text = (dashboard_root / "src" / "content" / "submissions" / f"{folder.name}.md").read_text()
    assert "## Conceptual model" in text
    assert "Trucks are entities." in text
    assert "## README" in text
    assert "We used Opus 4.7." in text
    assert "## Reviewer form" in text
    assert "Score: 78/100" in text
    # The full evaluation_report JSON is linked, not pasted; we only embed selected fields
    # in frontmatter so the page can render a structured summary.
    assert "evaluationReport:" in text
    assert "automatedChecksPassed: 57" in text
    assert "behaviouralChecksPassed: 6" in text


def test_emit_submission_omits_missing_sections(tmp_path: Path, populated_db: Path) -> None:
    submissions_root = tmp_path / "submissions"
    folder = submissions_root / "2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking"
    folder.mkdir(parents=True)
    (folder / "README.md").write_text("# README\n\nbody\n", encoding="utf-8")  # only README

    dashboard_root = tmp_path / "dashboard"
    rows = build_dashboard.load_leaderboard(populated_db)
    build_dashboard.emit_submissions(rows, submissions_root, dashboard_root)

    text = (dashboard_root / "src" / "content" / "submissions" / f"{folder.name}.md").read_text()
    assert "## README" in text
    assert "## Conceptual model" not in text
    assert "## Reviewer form" not in text
    assert "evaluationReport: null" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: two new tests FAIL.

- [ ] **Step 3: Add the section-reader and evaluation-report parser**

In `harness/build_dashboard.py`, append:

```python
def _read_text_section(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return None


def _summarise_evaluation_report(folder: Path) -> dict | None:
    """Return a small dict of selected fields from results/evaluation_report.json, or None."""
    candidates = [folder / "results" / "evaluation_report.json", folder / "evaluation_report.json"]
    report_path = next((p for p in candidates if p.exists()), None)
    if report_path is None:
        return None
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    automated = report.get("automated_checks") or {}
    behavioural = report.get("behavioural_checks") or {}
    summary = report.get("summary") or {}
    return {
        "automatedChecksPassed": automated.get("passed"),
        "automatedChecksTotal": automated.get("total"),
        "automatedPassRate": automated.get("pass_rate"),
        "behaviouralChecksPassed": behavioural.get("passed"),
        "behaviouralChecksTotal": behavioural.get("total"),
        "scenarioTotalTonnesMeans": summary.get("scenario_total_tonnes_means") or {},
        "reportRelativePath": report_path.relative_to(folder).as_posix(),
    }
```

- [ ] **Step 4: Extend `_render_frontmatter` to emit `evaluationReport`**

In `harness/build_dashboard.py`, replace the existing `_render_frontmatter` function with:

```python
def _render_frontmatter(row: dict, files: list[dict], evaluation_report: dict | None) -> str:
    cs = row["categoryScores"]
    lines = [
        "---",
        f"id: {_yaml_scalar(row['submission_id'])}",
        f"runDate: {_yaml_scalar(row['runDate'])}",
        f"benchmarkId: {_yaml_scalar(row['benchmarkId'])}",
        f"harness: {_yaml_scalar(row['harness'])}",
        f"model: {_yaml_scalar(row['model'])}",
        f"runTag: {_yaml_scalar(row['runTag'])}",
        f"totalScore: {_yaml_scalar(row['totalScore'])}",
        "categoryScores:",
        f"  conceptual_modelling: {_yaml_scalar(cs['conceptual_modelling'])}",
        f"  data_topology: {_yaml_scalar(cs['data_topology'])}",
        f"  simulation_correctness: {_yaml_scalar(cs['simulation_correctness'])}",
        f"  experimental_design: {_yaml_scalar(cs['experimental_design'])}",
        f"  results_interpretation: {_yaml_scalar(cs['results_interpretation'])}",
        f"  code_quality: {_yaml_scalar(cs['code_quality'])}",
        f"  traceability: {_yaml_scalar(cs['traceability'])}",
        f"totalTokens: {_yaml_scalar(row['totalTokens'])}",
        f"inputTokens: {_yaml_scalar(row['inputTokens'])}",
        f"outputTokens: {_yaml_scalar(row['outputTokens'])}",
        f"tokenCountMethod: {_yaml_scalar(row['tokenCountMethod'])}",
        f"runtimeSeconds: {_yaml_scalar(row['runtimeSeconds'])}",
        f"interventionCategory: {_yaml_scalar(row['interventionCategory'])}",
        f"reviewer: {_yaml_scalar(row['reviewer'])}",
        f"reviewDate: {_yaml_scalar(row['reviewDate'])}",
        f"recommendation: {_yaml_scalar(row['recommendation'])}",
        f"notes: {_yaml_scalar(row['notes'])}",
    ]
    if evaluation_report is None:
        lines.append("evaluationReport: null")
    else:
        lines.append("evaluationReport:")
        lines.append(f"  automatedChecksPassed: {_yaml_scalar(evaluation_report['automatedChecksPassed'])}")
        lines.append(f"  automatedChecksTotal: {_yaml_scalar(evaluation_report['automatedChecksTotal'])}")
        lines.append(f"  automatedPassRate: {_yaml_scalar(evaluation_report['automatedPassRate'])}")
        lines.append(f"  behaviouralChecksPassed: {_yaml_scalar(evaluation_report['behaviouralChecksPassed'])}")
        lines.append(f"  behaviouralChecksTotal: {_yaml_scalar(evaluation_report['behaviouralChecksTotal'])}")
        lines.append(f"  reportRelativePath: {_yaml_scalar(evaluation_report['reportRelativePath'])}")
        lines.append("  scenarioTotalTonnesMeans:")
        for k, v in (evaluation_report["scenarioTotalTonnesMeans"] or {}).items():
            lines.append(f"    {_yaml_scalar(k)}: {_yaml_scalar(v)}")
    lines.append("files:")
    for f in files:
        lines.append(f"  - path: {_yaml_scalar(f['path'])}")
        lines.append(f"    kind: {_yaml_scalar(f['kind'])}")
        lines.append(f"    bytes: {_yaml_scalar(f['bytes'])}")
        lines.append(f"    language: {_yaml_scalar(f['language'])}")
    lines.append("---")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 5: Replace `emit_submissions` to assemble the body**

Replace the existing `emit_submissions` function in `harness/build_dashboard.py` with:

```python
def emit_submissions(rows: list[dict], submissions_root: Path, dashboard_root: Path) -> None:
    md_root = dashboard_root / "src" / "content" / "submissions"
    public_root = dashboard_root / "public" / "submissions"
    md_root.mkdir(parents=True, exist_ok=True)

    for row in rows:
        folder = submissions_root / row["submission_id"]
        if not folder.exists():
            continue
        files = walk_submission(folder)
        evaluation_report = _summarise_evaluation_report(folder)

        body_parts: list[str] = []
        conceptual = _read_text_section(folder / "conceptual_model.md")
        readme = _read_text_section(folder / "README.md")
        reviewer = _read_text_section(folder / "results" / "reviewer_form.md")
        if reviewer is None:
            reviewer = _read_text_section(folder / "reviewer_form.md")

        if conceptual:
            body_parts.append("## Conceptual model\n\n" + conceptual)
        if readme:
            body_parts.append("## README\n\n" + readme)
        if reviewer:
            body_parts.append("## Reviewer form\n\n" + reviewer)

        body = "\n\n".join(body_parts) if body_parts else "_No rendered sections; see file index above._"

        (md_root / f"{row['submission_id']}.md").write_text(
            _render_frontmatter(row, files, evaluation_report) + body + "\n",
            encoding="utf-8",
        )

        public_dest = public_root / row["submission_id"]
        public_dest.mkdir(parents=True, exist_ok=True)
        for entry in files:
            if entry["kind"] == "download":
                src = folder / entry["path"]
                dest = public_dest / entry["path"]
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)
        # Also copy the full evaluation_report.json into public/ so the page can link it.
        if evaluation_report is not None:
            src = folder / evaluation_report["reportRelativePath"]
            dest = public_dest / evaluation_report["reportRelativePath"]
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/harness/test_build_dashboard.py -v`
Expected: all 11 tests PASS (including the older ones, which still match because their assertions are subsets of the new output).

- [ ] **Step 7: Update content collection schema for `evaluationReport`**

In `dashboard/src/content.config.ts`, replace the `submissions` collection schema with:

```ts
const submissions = defineCollection({
  loader: glob({ pattern: "**/*.md", base: "./src/content/submissions" }),
  schema: z.object({
    id: z.string(),
    runDate: z.string(),
    benchmarkId: z.string(),
    harness: z.string(),
    model: z.string(),
    runTag: z.string().nullable(),
    totalScore: z.number().nullable(),
    categoryScores: z.object({
      conceptual_modelling: z.number().nullable(),
      data_topology: z.number().nullable(),
      simulation_correctness: z.number().nullable(),
      experimental_design: z.number().nullable(),
      results_interpretation: z.number().nullable(),
      code_quality: z.number().nullable(),
      traceability: z.number().nullable(),
    }),
    totalTokens: z.number().nullable(),
    inputTokens: z.number().nullable(),
    outputTokens: z.number().nullable(),
    tokenCountMethod: z.string().nullable(),
    runtimeSeconds: z.number().nullable(),
    interventionCategory: z.string(),
    reviewer: z.string().nullable(),
    reviewDate: z.string().nullable(),
    recommendation: z.string().nullable(),
    notes: z.string().nullable(),
    evaluationReport: z
      .object({
        automatedChecksPassed: z.number().nullable(),
        automatedChecksTotal: z.number().nullable(),
        automatedPassRate: z.number().nullable(),
        behaviouralChecksPassed: z.number().nullable(),
        behaviouralChecksTotal: z.number().nullable(),
        reportRelativePath: z.string(),
        scenarioTotalTonnesMeans: z.record(z.string(), z.number()),
      })
      .nullable(),
    files: z.array(
      z.object({
        path: z.string(),
        kind: z.enum(["text", "binary", "download"]),
        bytes: z.number(),
        language: z.string().nullable(),
      })
    ),
  }),
});
```

- [ ] **Step 8: Regenerate inputs and confirm the schema validates**

Run:

```bash
cd /Users/harry/Workspace/simulation-bench
python harness/build_dashboard.py
cd dashboard
npx astro check 2>&1 | tail -10
```

Expected: 0 errors. The generated `.md` files validate against the new schema.

- [ ] **Step 9: Commit**

```bash
git add harness/build_dashboard.py tests/harness/test_build_dashboard.py dashboard/src/content.config.ts
git commit -m "feat(build): embed conceptual model, README, reviewer form, eval report"
```

### Task 18: Submission overview page

**Files:**
- Create: `dashboard/src/components/FileTree.astro`
- Create: `dashboard/src/pages/submissions/[id]/index.astro`

- [ ] **Step 1: Create `dashboard/src/components/FileTree.astro`**

```astro
---
interface FileEntry {
  path: string;
  kind: "text" | "binary" | "download";
  bytes: number;
  language: string | null;
}
interface Props {
  files: FileEntry[];
  submissionId: string;
}
const { files, submissionId } = Astro.props;

function formatBytes(b: number): string {
  if (b < 1024) return `${b} B`;
  if (b < 1024 * 1024) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / (1024 * 1024)).toFixed(1)} MB`;
}

const text = files.filter((f) => f.kind === "text");
const downloads = files.filter((f) => f.kind === "download");
---
{text.length > 0 && (
  <section>
    <h3>Source files</h3>
    <ul>
      {text.map((f) => (
        <li>
          <a href={`/submissions/${submissionId}/${f.path}/`}>{f.path}</a>
          <span class="meta">{f.language ?? ""} · {formatBytes(f.bytes)}</span>
        </li>
      ))}
    </ul>
  </section>
)}
{downloads.length > 0 && (
  <section>
    <h3>Downloads</h3>
    <ul>
      {downloads.map((f) => (
        <li>
          <a href={`/submissions/${submissionId}/${f.path}`} download>{f.path}</a>
          <span class="meta">{formatBytes(f.bytes)}</span>
        </li>
      ))}
    </ul>
  </section>
)}

<style>
  ul { padding-left: 1.25rem; }
  li { margin: 0.15rem 0; }
  .meta { color: var(--muted); font-size: 0.85rem; margin-left: 0.5rem; }
</style>
```

- [ ] **Step 2: Create `dashboard/src/pages/submissions/[id]/index.astro`**

```astro
---
import Layout from "../../../layouts/Layout.astro";
import FileTree from "../../../components/FileTree.astro";
import InterventionBadge from "../../../components/InterventionBadge.astro";
import { getCollection, getEntry, render } from "astro:content";

export async function getStaticPaths() {
  const submissions = await getCollection("submissions");
  return submissions.map((s) => ({ params: { id: s.data.id } }));
}

const { id } = Astro.params;
const entry = await getEntry("submissions", id!);
if (!entry) throw new Error(`No submission entry for ${id}`);
const data = entry.data;
const cs = data.categoryScores;
const evalReport = data.evaluationReport;
const { Content } = await render(entry);
---
<Layout title={`${data.harness} / ${data.model} — Simulation Bench`} pageTitle={data.id}>
  <section>
    <p>
      <strong>Date:</strong> {data.runDate} ·
      <strong>Benchmark:</strong> {data.benchmarkId} ·
      <strong>Harness:</strong> {data.harness} ·
      <strong>Model:</strong> {data.model}{data.runTag ? ` (${data.runTag})` : ""} ·
      <InterventionBadge category={data.interventionCategory} />
    </p>
  </section>

  <section>
    <h2>Scores</h2>
    <table>
      <thead><tr><th>Category</th><th>Points</th><th>Max</th></tr></thead>
      <tbody>
        <tr><td>Conceptual modelling</td><td>{cs.conceptual_modelling ?? "—"}</td><td>20</td></tr>
        <tr><td>Data and topology</td><td>{cs.data_topology ?? "—"}</td><td>15</td></tr>
        <tr><td>Simulation correctness</td><td>{cs.simulation_correctness ?? "—"}</td><td>20</td></tr>
        <tr><td>Experimental design</td><td>{cs.experimental_design ?? "—"}</td><td>15</td></tr>
        <tr><td>Results & interpretation</td><td>{cs.results_interpretation ?? "—"}</td><td>15</td></tr>
        <tr><td>Code quality</td><td>{cs.code_quality ?? "—"}</td><td>10</td></tr>
        <tr><td>Traceability</td><td>{cs.traceability ?? "—"}</td><td>5</td></tr>
        <tr><th>Total</th><th>{data.totalScore ?? "—"}</th><th>100</th></tr>
      </tbody>
    </table>
  </section>

  <section>
    <h2>Run metrics</h2>
    <ul>
      <li>Total tokens: <code>{data.totalTokens ?? "—"}</code> (method: <code>{data.tokenCountMethod ?? "unknown"}</code>)</li>
      <li>Input / output tokens: <code>{data.inputTokens ?? "—"}</code> / <code>{data.outputTokens ?? "—"}</code></li>
      <li>Runtime: <code>{data.runtimeSeconds ?? "—"} s</code></li>
      <li>Reviewer: <code>{data.reviewer ?? "—"}</code> on <code>{data.reviewDate ?? "—"}</code></li>
      {data.recommendation && <li>Recommendation: {data.recommendation}</li>}
      {data.notes && <li>Notes: {data.notes}</li>}
    </ul>
  </section>

  {evalReport && (
    <section>
      <h2>Evaluation report</h2>
      <ul>
        <li>Automated checks: {evalReport.automatedChecksPassed ?? "—"} / {evalReport.automatedChecksTotal ?? "—"}
          {evalReport.automatedPassRate !== null && ` (${(evalReport.automatedPassRate * 100).toFixed(0)}%)`}
        </li>
        <li>Behavioural checks: {evalReport.behaviouralChecksPassed ?? "—"} / {evalReport.behaviouralChecksTotal ?? "—"}</li>
        <li>
          <a href={`/submissions/${data.id}/${evalReport.reportRelativePath}`} download>
            Download full evaluation_report.json
          </a>
        </li>
      </ul>
      {Object.keys(evalReport.scenarioTotalTonnesMeans).length > 0 && (
        <table>
          <thead><tr><th>Scenario</th><th>Mean total tonnes</th></tr></thead>
          <tbody>
            {Object.entries(evalReport.scenarioTotalTonnesMeans).map(([scenario, mean]) => (
              <tr><td>{scenario}</td><td>{mean.toLocaleString()}</td></tr>
            ))}
          </tbody>
        </table>
      )}
    </section>
  )}

  <FileTree files={data.files} submissionId={data.id} />

  <section class="rendered-body">
    <Content />
  </section>

  <p><a href="/">← Back to leaderboard</a></p>
</Layout>

<style>
  .rendered-body { margin-top: 2rem; padding-top: 1.5rem; border-top: 1px solid var(--border); }
  .rendered-body :global(h2) { margin-top: 2rem; }
</style>
```

- [ ] **Step 3: Run dev server and click through**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npm run dev -- --host 127.0.0.1 --port 4321`
Open `http://127.0.0.1:4321/`, click any submission row.
Expected: lands on `/submissions/<id>/`, shows score table, run metrics, source file list, downloads list. Stop the dev server.

- [ ] **Step 4: Type-check**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npx astro check 2>&1 | tail -10`
Expected: 0 errors.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/components/FileTree.astro dashboard/src/pages/submissions/
git commit -m "feat(dashboard): submission overview page"
```

### Task 19: Syntax-highlighted file viewer

**Files:**
- Create: `dashboard/src/pages/submissions/[id]/[...file].astro`

- [ ] **Step 1: Create `dashboard/src/pages/submissions/[id]/[...file].astro`**

```astro
---
import Layout from "../../../layouts/Layout.astro";
import { getCollection } from "astro:content";
import { codeToHtml } from "shiki";
import fs from "node:fs/promises";
import path from "node:path";

export async function getStaticPaths() {
  const submissions = await getCollection("submissions");
  const paths: { params: { id: string; file: string }; props: { language: string | null; submissionPath: string } }[] = [];
  for (const s of submissions) {
    for (const f of s.data.files) {
      if (f.kind === "text") {
        paths.push({
          params: { id: s.data.id, file: f.path },
          props: { language: f.language, submissionPath: f.path },
        });
      }
    }
  }
  return paths;
}

const { id, file } = Astro.params;
const { language, submissionPath } = Astro.props;

const repoRoot = path.resolve(process.cwd(), "..");
const absolutePath = path.join(repoRoot, "submissions", id!, submissionPath);
const source = await fs.readFile(absolutePath, "utf-8");
const html = await codeToHtml(source, { lang: language ?? "text", theme: "github-dark" });
const githubUrl = `https://github.com/harrymunro/simulation-bench/blob/main/submissions/${id}/${submissionPath}`;
---
<Layout title={`${file} — ${id}`} pageTitle={file ?? ""}>
  <p>
    <a href={`/submissions/${id}/`}>← Back to submission</a> ·
    <a href={githubUrl} rel="noreferrer">View raw on GitHub</a>
  </p>
  <article set:html={html} />
</Layout>
```

- [ ] **Step 2: Confirm Shiki is available**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npm ls shiki 2>&1 | head -5`
Expected: shiki is listed as a transitive dependency of Astro. If `npm ls shiki` shows it missing, run `npm install shiki@latest`.

- [ ] **Step 3: Run dev server and open a file**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npm run dev -- --host 127.0.0.1 --port 4321`
Visit a submission page, click a `.py` link.
Expected: opens `/submissions/<id>/sim.py/`, shows syntax-highlighted code in a dark theme. The "View raw on GitHub" link points to `github.com/harrymunro/simulation-bench/blob/main/submissions/<id>/sim.py`. Click an `event_log.csv` link from the submission page; expected: file downloads. Stop the dev server.

- [ ] **Step 4: Type-check + production build**

Run: `cd /Users/harry/Workspace/simulation-bench/dashboard && npx astro check && npm run build 2>&1 | tail -20`
Expected: 0 errors. `dashboard/dist/submissions/<id>/<path>/index.html` exists for each text file. `dashboard/dist/submissions/<id>/event_log.csv` exists for download files.

- [ ] **Step 5: Commit**

```bash
git add dashboard/src/pages/submissions/
git commit -m "feat(dashboard): Shiki-highlighted file viewer"
```

### Task 20: Phase 3 exit criterion

- [ ] **Step 1: Confirm every submission page lists files and downloads work**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/build_dashboard.py && cd dashboard && npm run build && npx http-server dist -p 8080 --silent &`
Run (in another shell): `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/submissions/2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking/`
Expected: `200`.
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/submissions/2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking/event_log.csv`
Expected: `200`. Then `kill %1` to stop the local server.

- [ ] **Step 2: Tests pass**

Run: `cd /Users/harry/Workspace/simulation-bench && python -m pytest tests/ -v`
Expected: all tests pass.

---

# Phase 4 — Deploy to fly.io

Goal: a public URL serves the static dashboard out of a Caddy container. **Exit criterion (per spec §6):** public URL serves the dashboard; methodology page links resolve; downloads work.

### Task 21: Dockerfile, Caddyfile, .dockerignore

**Files:**
- Create: `Dockerfile`
- Create: `Caddyfile`
- Create: `.dockerignore`

- [ ] **Step 1: Create `Caddyfile`**

```caddy
{
    auto_https off
    admin off
}

:80 {
    root * /srv
    encode gzip
    file_server

    header {
        Strict-Transport-Security "max-age=31536000; includeSubDomains"
        X-Content-Type-Options "nosniff"
        Referrer-Policy "strict-origin-when-cross-origin"
        Content-Security-Policy "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; script-src 'self'; object-src 'none'; base-uri 'self'"
        -Server
    }

    @notFound {
        not file
        not path *.css *.js *.png *.svg *.gif *.mp4 *.csv *.json *.txt *.ico *.woff *.woff2
    }
    rewrite @notFound /index.html
}
```

- [ ] **Step 2: Create `Dockerfile`**

```dockerfile
# syntax=docker/dockerfile:1.6
FROM node:20-alpine AS build
WORKDIR /app
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci
COPY dashboard/ ./
COPY SCORING_GUIDE.md RUN_PROTOCOL.md /app/repo-docs/
# At this point we expect Python-generated inputs (leaderboard.json, content/) to already
# exist on disk inside the build context (the Makefile runs build_dashboard.py first).
RUN npm run build

FROM caddy:2-alpine
COPY --from=build /app/dist /srv
COPY Caddyfile /etc/caddy/Caddyfile
EXPOSE 80
CMD ["caddy", "run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
```

- [ ] **Step 3: Create `.dockerignore`**

```dockerignore
# Top-level — nothing should leak into the build context except dashboard/ and the two methodology docs.
*
!dashboard/
!Caddyfile
!SCORING_GUIDE.md
!RUN_PROTOCOL.md

# Inside dashboard/, exclude build output and node_modules from the context.
dashboard/dist/
dashboard/node_modules/
dashboard/.astro/
**/__pycache__/
**/.DS_Store
.beads/
.dolt/
.beads-credential-key
.git/
```

- [ ] **Step 4: Build the image locally and inspect contents**

Run: `cd /Users/harry/Workspace/simulation-bench && docker build -t simulation-bench-dashboard:dev .`
Expected: build succeeds.

Run: `docker run --rm --entrypoint sh simulation-bench-dashboard:dev -c "ls /srv && find /srv -name '*.html' | head -5"`
Expected: `index.html`, `methodology/`, `submissions/`, plus a few HTML files. No `.beads`, `.dolt`, or `.git` content visible.

- [ ] **Step 5: Run the container and verify HTTP response**

Run: `docker run -d --rm -p 8080:80 --name sb-dash simulation-bench-dashboard:dev`
Run: `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/ && curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8080/methodology/scoring/`
Expected: `200` for both.
Run: `docker stop sb-dash`

- [ ] **Step 6: Commit**

```bash
git add Dockerfile Caddyfile .dockerignore
git commit -m "feat(deploy): Dockerfile and Caddy config for static dashboard"
```

### Task 22: `fly.toml` and first deploy

**Files:**
- Create: `fly.toml`

- [ ] **Step 1: Verify `flyctl` is available**

Run: `flyctl version`
Expected: prints a version. If missing, install with `brew install flyctl`.

- [ ] **Step 2: Create `fly.toml`**

```toml
app = "simulation-bench"
primary_region = "lhr"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 80
  force_https = true
  auto_start_machines = true
  auto_stop_machines = "stop"
  min_machines_running = 0

[[vm]]
  size = "shared-cpu-1x"
  memory = "256mb"
```

- [ ] **Step 3: One-time app launch (only if the app does not already exist)**

Run: `flyctl apps list 2>&1 | grep simulation-bench || echo "needs-launch"`
If `needs-launch` is printed, run: `flyctl apps create simulation-bench`. If the name is taken, pick another and update `app =` in `fly.toml` accordingly. Re-run `flyctl apps list` to confirm.

- [ ] **Step 4: Deploy**

Run: `cd /Users/harry/Workspace/simulation-bench && python harness/build_dashboard.py && flyctl deploy --remote-only`
Expected: build succeeds remotely, machine starts, deployment reports a public URL like `https://simulation-bench.fly.dev/`.

- [ ] **Step 5: Smoke-test the live site**

Run:

```bash
curl -s -o /dev/null -w "%{http_code}\n" https://simulation-bench.fly.dev/
curl -s -o /dev/null -w "%{http_code}\n" https://simulation-bench.fly.dev/methodology/scoring/
curl -s -o /dev/null -w "%{http_code}\n" https://simulation-bench.fly.dev/methodology/protocol/
curl -s -o /dev/null -w "%{http_code}\n" https://simulation-bench.fly.dev/submissions/2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking/
curl -s -o /dev/null -w "%{http_code}\n" https://simulation-bench.fly.dev/submissions/2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking/event_log.csv
```

Expected: every line prints `200`.

- [ ] **Step 6: Commit**

```bash
git add fly.toml
git commit -m "feat(deploy): fly.toml + first deploy of public dashboard"
```

---

# Phase 5 — Polish & Documentation

Goal: a single-command rebuild + deploy and a README section explaining how. **Exit criterion (per spec §6):** a new operator can add a submission + score and ship a refreshed dashboard in <10 minutes following the README.

### Task 23: Top-level Makefile

**Files:**
- Create: `Makefile`

- [ ] **Step 1: Create `Makefile`**

```makefile
.PHONY: ingest dashboard preview deploy test clean

ingest:
	python harness/normalize_tokens.py
	python harness/record_score.py --from-json scores/seed_scores.json

dashboard: ingest
	python harness/build_dashboard.py
	cd dashboard && npm install --no-audit --no-fund
	cd dashboard && npm run build

preview: dashboard
	cd dashboard && npm run preview -- --host 127.0.0.1 --port 4321

deploy: dashboard
	flyctl deploy --remote-only

test:
	python -m pytest tests/ -v

clean:
	rm -rf dashboard/dist dashboard/.astro
	rm -f dashboard/src/data/leaderboard.json
	rm -rf dashboard/src/content/submissions
	rm -rf dashboard/public/submissions
	rm -f dashboard/src/content/methodology/scoring.md dashboard/src/content/methodology/protocol.md
```

- [ ] **Step 2: Verify each target works**

Run: `cd /Users/harry/Workspace/simulation-bench && make clean && make dashboard`
Expected: completes with no errors; `dashboard/dist/` is rebuilt.

Run: `make test`
Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add Makefile
git commit -m "chore: add top-level Makefile for ingest/dashboard/deploy"
```

### Task 24: README — "Updating the dashboard" section

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Read the current README**

Run: `cd /Users/harry/Workspace/simulation-bench && wc -l README.md && tail -20 README.md`
Note where the file ends; the new section is appended after the existing content.

- [ ] **Step 2: Append the new section**

Append to the end of `README.md`:

```markdown
## Public dashboard

The leaderboard at <https://simulation-bench.fly.dev/> is built from this repository:

- `scores/seed_scores.json` — source of truth for human review scores.
- `submissions/<id>/token_usage.json` and `submissions/<id>/run_metrics.json` — per-run tokens and time.
- `SCORING_GUIDE.md` and `RUN_PROTOCOL.md` — methodology pages.

### Refreshing the dashboard after adding a submission or score

```bash
# 1. Add the new submission folder under submissions/ (use the create-submission skill)
# 2. Append the new review block to scores/seed_scores.json
# 3. Rebuild and deploy:
make deploy
```

`make deploy` runs:

1. `python harness/normalize_tokens.py` — ensures every submission has `token_usage.json` + `run_metrics.json`.
2. `python harness/record_score.py --from-json scores/seed_scores.json` — refreshes `scores/scores.db`.
3. `python harness/build_dashboard.py` — emits `dashboard/src/data/leaderboard.json` and per-submission `.md` files.
4. `cd dashboard && npm run build` — produces `dashboard/dist/`.
5. `flyctl deploy --remote-only` — ships the Caddy container to fly.io.

For a local preview before deploying: `make preview` (serves `dashboard/dist/` on `http://127.0.0.1:4321/`).
```

- [ ] **Step 3: Commit**

```bash
git add README.md
git commit -m "docs: README section for refreshing the public dashboard"
```

### Task 25: Phase 5 + final exit criterion

- [ ] **Step 1: Walk-through as a fresh operator**

Run, in order:

```bash
cd /Users/harry/Workspace/simulation-bench
make clean
make test
make deploy
```

Expected: every command exits 0. The deployed site reflects the current state of `seed_scores.json` and `submissions/`.

- [ ] **Step 2: Update `bd` issues**

Close any beads issues that track this rollout (e.g. `bd close simulation-bench-tjf` if it captured this work). The plan is the source of truth from here.

- [ ] **Step 3: Final commit / push**

```bash
git status
git push
```

Expected: working tree clean; remote tracking branch up to date.

---

## Self-review checklist (run before handing off)

- **Spec coverage:**
  - §1 Goals — three independent sort columns (Quality, Tokens, Time) ✓ Task 13. Methodology pages reachable ✓ Task 14. Per-submission file viewer ✓ Tasks 18–19. No combined meta-score ✓ (no such column anywhere).
  - §2 Architecture — Python emits JSON + Markdown, Astro consumes them, Caddy serves `dist/` ✓ Tasks 12, 17, 17b, 21–22.
  - §3 Data model — `token_usage.json` + `run_metrics.json` required, schema additions, intervention category ✓ Tasks 1–6.
  - §4 Pages & UX — leaderboard with hover-tooltip showing input/output split + token method ✓ Task 13. Submission overview with rendered conceptual model / README / reviewer form / evaluation report ✓ Tasks 17b + 18. File viewer with Shiki + raw GitHub fallback ✓ Task 19. Methodology pages ✓ Task 14.
  - §5 Build/deploy/security — Caddy CSP, no env vars, allowlisted artefacts only ✓ Tasks 16, 21–22. `.dockerignore` excludes `.beads`, `.dolt`, `.beads-credential-key`, `.git` ✓ Task 21.
  - §6 Rollout — five phases preserved ✓.
  - §7 Open questions — explicitly out of scope, not in plan ✓.
- **Placeholder scan:** no `TBD`, `TODO`, "implement later", "fill in details", "similar to Task N", or hand-wavy "add validation". All test code, all production code, and all command-line invocations are spelled out.
- **Type consistency:** `SubmissionRecord`, `ScoreRecord`, the leaderboard JSON shape (`submission_id`, `runDate`, `categoryScores.*`, `totalTokens`, `tokenCountMethod`, `runtimeSeconds`, `interventionCategory`), and the Astro `submissions` collection schema all use the same field names. The intervention category vocabulary (`autonomous | hints | manual_repair | failed | unrecorded`) is identical in `RUN_PROTOCOL.md`, `record_score.py`, `normalize_tokens.py`, and `InterventionBadge.astro`.
