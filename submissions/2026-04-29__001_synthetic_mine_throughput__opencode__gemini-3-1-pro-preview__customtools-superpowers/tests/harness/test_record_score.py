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
