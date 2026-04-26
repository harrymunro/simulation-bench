from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any

from loc_counter import count_all_files, count_python_loc


REQUIRED_OUTPUT_FILES = [
    "conceptual_model.md",
    "README.md",
    "results.csv",
    "summary.json",
    "event_log.csv",
]

REQUIRED_SCENARIOS = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]

REQUIRED_RESULTS_COLUMNS = [
    "scenario_id",
    "replication",
    "random_seed",
    "total_tonnes_delivered",
    "tonnes_per_hour",
]

REQUIRED_EVENT_LOG_COLUMNS = [
    "time_min",
    "replication",
    "scenario_id",
    "truck_id",
    "event_type",
]


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def csv_columns(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        return list(reader.fieldnames or [])


def read_results_means(results_path: Path) -> dict[str, float]:
    if not results_path.exists():
        return {}

    totals: dict[str, list[float]] = {}
    with results_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scenario = row.get("scenario_id")
            if not scenario:
                continue
            value = row.get("total_tonnes_delivered") or row.get("total_tonnes_mean")
            try:
                val = float(value)
            except (TypeError, ValueError):
                continue
            totals.setdefault(scenario, []).append(val)

    return {k: sum(v) / len(v) for k, v in totals.items() if v}


def extract_summary_scenario_means(summary: dict[str, Any] | None) -> dict[str, float]:
    if not summary:
        return {}
    scenarios = summary.get("scenarios", {})
    means = {}
    for sid, metrics in scenarios.items():
        try:
            means[sid] = float(metrics.get("total_tonnes_mean"))
        except (TypeError, ValueError):
            pass
    return means


def check_condition(name: str, value: bool, description: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(value),
        "description": description,
    }


def behavioural_checks(means: dict[str, float]) -> list[dict[str, Any]]:
    def has(*keys):
        return all(k in means and math.isfinite(means[k]) for k in keys)

    checks = []

    checks.append(check_condition(
        "trucks_12_gt_trucks_4",
        has("trucks_12", "trucks_4") and means["trucks_12"] > means["trucks_4"],
        "Higher fleet should usually outperform lower fleet.",
    ))

    checks.append(check_condition(
        "baseline_gt_trucks_4",
        has("baseline", "trucks_4") and means["baseline"] > means["trucks_4"],
        "Baseline 8-truck case should usually outperform 4-truck case.",
    ))

    checks.append(check_condition(
        "ramp_upgrade_ge_baseline",
        has("ramp_upgrade", "baseline") and means["ramp_upgrade"] >= 0.95 * means["baseline"],
        "Ramp upgrade should usually improve or maintain throughput.",
    ))

    checks.append(check_condition(
        "crusher_slowdown_lt_baseline",
        has("crusher_slowdown", "baseline") and means["crusher_slowdown"] < means["baseline"],
        "Slower crusher should usually reduce throughput.",
    ))

    checks.append(check_condition(
        "ramp_closed_le_baseline",
        has("ramp_closed", "baseline") and means["ramp_closed"] <= 1.05 * means["baseline"],
        "Ramp closure should usually not improve throughput.",
    ))

    if has("trucks_4", "baseline", "trucks_12"):
        increase_4_to_8 = means["baseline"] - means["trucks_4"]
        increase_8_to_12 = means["trucks_12"] - means["baseline"]
        saturation = increase_8_to_12 <= 1.25 * increase_4_to_8
    else:
        saturation = False

    checks.append(check_condition(
        "truck_count_saturation_plausible",
        saturation,
        "Throughput should show some saturation as trucks increase.",
    ))

    return checks


def summary_structure_checks(summary: dict[str, Any] | None) -> list[dict[str, Any]]:
    checks = []
    if not summary:
        return [check_condition("summary_json_parseable", False, "summary.json should parse as JSON.")]

    checks.append(check_condition(
        "summary_has_benchmark_id",
        "benchmark_id" in summary,
        "summary.json should include benchmark_id.",
    ))

    scenarios = summary.get("scenarios")
    checks.append(check_condition(
        "summary_has_scenarios_object",
        isinstance(scenarios, dict),
        "summary.json should include a scenarios object.",
    ))

    if isinstance(scenarios, dict):
        present = set(scenarios.keys())
        for sid in REQUIRED_SCENARIOS:
            checks.append(check_condition(
                f"scenario_present_{sid}",
                sid in present,
                f"summary.json should include scenario {sid}.",
            ))

        for sid, metrics in scenarios.items():
            for key in ["replications", "shift_length_hours", "total_tonnes_mean", "tonnes_per_hour_mean"]:
                checks.append(check_condition(
                    f"{sid}_has_{key}",
                    isinstance(metrics, dict) and key in metrics,
                    f"{sid} should include {key}.",
                ))

    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate a Simulation Bench submission.")
    parser.add_argument("--benchmark-dir", type=Path, required=True)
    parser.add_argument("--submission-dir", type=Path, required=True)
    parser.add_argument("--outputs-dir", type=Path, required=True)
    parser.add_argument("--run-metrics", type=Path, default=None)
    parser.add_argument("--token-usage", type=Path, default=None)
    parser.add_argument("--report-out", type=Path, required=True)
    args = parser.parse_args()

    args.report_out.parent.mkdir(parents=True, exist_ok=True)

    output_file_checks = []
    for name in REQUIRED_OUTPUT_FILES:
        exists = (args.outputs_dir / name).exists()
        output_file_checks.append(check_condition(
            f"output_exists_{name}",
            exists,
            f"Required output file {name} should exist.",
        ))

    summary_path = args.outputs_dir / "summary.json"
    summary = load_json(summary_path)
    summary_checks = summary_structure_checks(summary)

    results_cols = csv_columns(args.outputs_dir / "results.csv")
    results_column_checks = [
        check_condition(
            f"results_has_{col}",
            col in results_cols,
            f"results.csv should include {col}.",
        )
        for col in REQUIRED_RESULTS_COLUMNS
    ]

    event_cols = csv_columns(args.outputs_dir / "event_log.csv")
    event_column_checks = [
        check_condition(
            f"event_log_has_{col}",
            col in event_cols,
            f"event_log.csv should include {col}.",
        )
        for col in REQUIRED_EVENT_LOG_COLUMNS
    ]

    means = extract_summary_scenario_means(summary)
    if not means:
        means = read_results_means(args.outputs_dir / "results.csv")

    behaviour = behavioural_checks(means)

    run_metrics = load_json(args.run_metrics)
    token_usage = load_json(args.token_usage)

    if token_usage is None and run_metrics:
        token_usage = run_metrics.get("token_usage")

    all_checks = output_file_checks + summary_checks + results_column_checks + event_column_checks + behaviour
    passed = sum(1 for c in all_checks if c["passed"])
    total = len(all_checks)

    report = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "submission_dir": str(args.submission_dir),
        "outputs_dir": str(args.outputs_dir),
        "automated_checks": {
            "passed": passed,
            "total": total,
            "pass_rate": passed / total if total else None,
            "checks": all_checks,
        },
        "scenario_total_tonnes_means": means,
        "quantitative_metrics": {
            "loc": count_python_loc(args.submission_dir),
            "files": count_all_files(args.submission_dir),
            "runtime_seconds": run_metrics.get("runtime_seconds") if run_metrics else None,
            "return_code": run_metrics.get("return_code") if run_metrics else None,
            "timed_out": run_metrics.get("timed_out") if run_metrics else None,
            "token_usage": token_usage,
        },
        "notes": [
            "Automated checks are not a substitute for human review.",
            "Behavioural checks are broad sanity checks, not exact answer keys.",
            "Token usage is reported only if supplied by the benchmark runner.",
        ],
    }

    args.report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))

    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())

