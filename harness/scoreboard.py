"""Print the Simulation Bench scoreboard from scores/scores.db."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scores_db import DEFAULT_DB_PATH, connect, init_schema


def _format_table(rows, headers) -> str:
    widths = [len(h) for h in headers]
    rendered = []
    for row in rows:
        cells = [("" if v is None else str(v)) for v in row]
        for i, cell in enumerate(cells):
            widths[i] = max(widths[i], len(cell))
        rendered.append(cells)
    sep = "  "
    lines = [sep.join(h.ljust(widths[i]) for i, h in enumerate(headers))]
    lines.append(sep.join("-" * w for w in widths))
    for cells in rendered:
        lines.append(sep.join(cells[i].ljust(widths[i]) for i in range(len(headers))))
    return "\n".join(lines)


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--benchmark", help="Filter to one benchmark id")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--detailed", action="store_true", help="Show per-category scores")
    args = parser.parse_args()

    if not args.db.exists():
        print(f"No scores DB at {args.db}", file=sys.stderr)
        return 1

    conn = connect(args.db)
    init_schema(conn)

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

    sql = """
        SELECT s.run_date, s.benchmark_id, s.harness, s.model, s.run_tag,
               sc.total_score, sc.reviewer, sc.recommendation
        FROM submissions s JOIN scores sc USING (submission_id)
    """
    params = []
    if args.benchmark:
        sql += " WHERE s.benchmark_id = ?"
        params.append(args.benchmark)
    sql += " ORDER BY sc.total_score DESC, sc.review_date DESC LIMIT ?"
    params.append(args.limit)
    rows = conn.execute(sql, params).fetchall()
    headers = ["date", "benchmark", "harness", "model", "tag", "score/100", "reviewer", "recommendation"]
    print(_format_table(rows, headers))
    return 0


if __name__ == "__main__":
    sys.exit(main())
