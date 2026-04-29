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
