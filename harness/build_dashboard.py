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

from scipy.stats import spearmanr

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = REPO_ROOT / "scores" / "scores.db"
DEFAULT_DASHBOARD_ROOT = REPO_ROOT / "dashboard"

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


# Variables included in the correlation matrix. Ordered for display: rubric
# categories first, then the composite total, then runtime/token signals.
CORRELATION_VARIABLES: list[tuple[str, str]] = [
    ("conceptual_modelling", "Conceptual modelling"),
    ("data_topology", "Data & topology"),
    ("simulation_correctness", "Simulation correctness"),
    ("experimental_design", "Experimental design"),
    ("results_interpretation", "Results interpretation"),
    ("code_quality", "Code quality"),
    ("traceability", "Traceability"),
    ("totalScore", "Total score"),
    ("totalTokens", "Total tokens"),
    ("runtimeSeconds", "Runtime (s)"),
]
MIN_PAIRS_FOR_CORRELATION = 3


def _extract_value(row: dict, key: str) -> float | None:
    """Return a numeric field from a leaderboard row, looking inside categoryScores."""
    if key in row:
        value = row[key]
    elif key in row.get("categoryScores", {}):
        value = row["categoryScores"][key]
    else:
        return None
    if value is None:
        return None
    return float(value)


def _spearman_pair(x: list[float], y: list[float]) -> float | None:
    """Spearman rank correlation. Returns None if undefined (constant input or NaN)."""
    if len(x) < MIN_PAIRS_FOR_CORRELATION:
        return None
    if len(set(x)) == 1 or len(set(y)) == 1:
        return None
    rho = spearmanr(x, y).statistic
    if rho is None:
        return None
    rho = float(rho)
    if rho != rho:  # NaN guard
        return None
    return rho


def compute_correlations(rows: list[dict]) -> dict:
    """Build a Spearman correlation matrix across the configured variables.

    Each cell holds the rank correlation computed from rows where both variables
    are non-null. Returns ``{"variables", "matrix", "n_pairs", "sample_size"}``.
    """
    keys = [k for k, _ in CORRELATION_VARIABLES]
    series: dict[str, list[tuple[int, float]]] = {
        k: [(idx, v) for idx, row in enumerate(rows) if (v := _extract_value(row, k)) is not None]
        for k in keys
    }

    matrix: list[list[float | None]] = []
    n_pairs: list[list[int]] = []
    for key_a in keys:
        row_rho: list[float | None] = []
        row_n: list[int] = []
        a_by_idx = dict(series[key_a])
        for key_b in keys:
            b_by_idx = dict(series[key_b])
            shared = sorted(set(a_by_idx) & set(b_by_idx))
            xs = [a_by_idx[i] for i in shared]
            ys = [b_by_idx[i] for i in shared]
            row_rho.append(_spearman_pair(xs, ys))
            row_n.append(len(shared))
        matrix.append(row_rho)
        n_pairs.append(row_n)

    return {
        "variables": [{"key": k, "label": label} for k, label in CORRELATION_VARIABLES],
        "matrix": matrix,
        "n_pairs": n_pairs,
        "sample_size": len(rows),
        "method": "spearman",
        "min_pairs": MIN_PAIRS_FOR_CORRELATION,
    }


def write_correlations_json(db_path: Path, out_path: Path) -> None:
    rows = load_leaderboard(db_path)
    payload = compute_correlations(rows)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


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


def _yaml_scalar(value) -> str:  # type: ignore[no-untyped-def]
    """Escape a value for use in YAML scalar context."""
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{text}"'


def _read_text_section(path: Path) -> str | None:
    """Read a text file and return its stripped content, or None if missing/unreadable."""
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


def _render_frontmatter(row: dict, files: list[dict], evaluation_report: dict | None) -> str:
    """Render YAML frontmatter for a submission page."""
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


def emit_submissions(rows: list[dict], submissions_root: Path, dashboard_root: Path) -> None:
    """Emit per-submission markdown files and copy downloads to public."""
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
    write_correlations_json(args.db, args.dashboard_root / "src" / "data" / "correlations.json")
    copy_methodology(REPO_ROOT, args.dashboard_root / "src" / "content" / "methodology")

    rows = load_leaderboard(args.db)
    emit_submissions(rows, args.submissions_root, args.dashboard_root)
    print(f"Emitted {len(rows)} submission page(s) to {args.dashboard_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
