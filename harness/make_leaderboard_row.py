from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a leaderboard CSV row from an evaluation report.")
    parser.add_argument("--evaluation-report", type=Path, required=True)
    parser.add_argument("--human-score", type=float, default=None)
    parser.add_argument("--agent", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    report = json.loads(args.evaluation_report.read_text(encoding="utf-8"))
    qm = report.get("quantitative_metrics", {})
    loc = qm.get("loc", {})
    token_usage = qm.get("token_usage") or {}
    checks = report.get("automated_checks", {})

    row = {
        "agent": args.agent,
        "model": args.model,
        "benchmark_id": report.get("benchmark_id"),
        "human_score": args.human_score,
        "automated_passed": checks.get("passed"),
        "automated_total": checks.get("total"),
        "automated_pass_rate": checks.get("pass_rate"),
        "runtime_seconds": qm.get("runtime_seconds"),
        "return_code": qm.get("return_code"),
        "python_code_lines": loc.get("code_lines"),
        "python_total_lines": loc.get("total_lines"),
        "python_file_count": loc.get("python_file_count"),
        "input_tokens": token_usage.get("input_tokens"),
        "output_tokens": token_usage.get("output_tokens"),
        "total_tokens": token_usage.get("total_tokens"),
        "token_count_method": token_usage.get("token_count_method"),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    exists = args.out.exists()

    with args.out.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if not exists:
            writer.writeheader()
        writer.writerow(row)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

