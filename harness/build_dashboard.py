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
import shutil
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


TEXT_LANGUAGE_BY_EXT: dict[str, str] = {
    ".py": "python",
    ".md": "markdown",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".json": "json",
    ".toml": "toml",
    ".csv": "csv",
    ".txt": "text",
    ".sh": "bash",
    ".cfg": "ini",
    ".ini": "ini",
    ".rst": "markdown",
}
DOWNLOAD_FILENAMES: set[str] = {
    "event_log.csv",
    "animation.gif",
    "animation.mp4",
    "topology.png",
}
DOWNLOAD_EXTENSIONS: set[str] = {".gif", ".mp4", ".png", ".jpg", ".jpeg", ".pdf", ".zip"}
TEXT_BYTE_THRESHOLD = 64 * 1024  # 64 KB

ALLOWLIST_TOP_LEVEL: set[str] = {
    "README.md",
    "conceptual_model.md",
    "results.csv",
    "summary.json",
    "event_log.csv",
    "submission.yaml",
    "token_usage.json",
    "run_metrics.json",
    "topology.png",
    "animation.gif",
    "animation.mp4",
    "interventions.md",
    "requirements.txt",
    "prompt.md",
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
        return {
            "path": rel,
            "kind": "text",
            "bytes": size,
            "language": TEXT_LANGUAGE_BY_EXT[ext],
        }

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
