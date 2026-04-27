"""Record a reviewer score for a submission into scores/scores.db.

Two ways to use:

1. Bulk JSON file (preferred for batch ingestion):

    python harness/record_score.py --from-json scores/seed_scores.json

   The JSON is a list of objects with keys matching ScoreRecord plus the
   submission folder name in `submission_id`.

2. Single submission via CLI flags:

    python harness/record_score.py \
        --submission 2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking \
        --reviewer "opus-subagent" --review-date 2026-04-27 \
        --conceptual 18 --data 14 --sim 18 --exp 14 --results 14 --code 9 --trace 5 \
        --automated-passed 57 --automated-total 57 --behavioural-passed 6 \
        --recommendation "Strong submission"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from scores_db import (
    DEFAULT_DB_PATH,
    ScoreRecord,
    connect,
    decode_folder,
    init_schema,
    insert_score,
    upsert_submission,
)

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


if __name__ == "__main__":
    sys.exit(main())
