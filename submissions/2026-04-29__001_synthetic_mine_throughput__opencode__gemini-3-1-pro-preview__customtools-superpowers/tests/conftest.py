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
