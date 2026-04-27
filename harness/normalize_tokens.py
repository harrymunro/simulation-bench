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
