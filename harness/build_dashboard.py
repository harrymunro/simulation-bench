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
    for filename, title in (
        ("SCORING_GUIDE.md", "Scoring guide"),
        ("RUN_PROTOCOL.md", "Run protocol"),
    ):
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
