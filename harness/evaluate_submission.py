from __future__ import annotations

import argparse
import csv
import json
import math
import re
from pathlib import Path
from typing import Any

import yaml

from loc_counter import count_all_files, count_python_loc


# --------------------------------------------------------------------------- #
# Legacy defaults (used only if a benchmark has no expected/scoring_rules.yaml).
# Benchmark-specific behaviour is otherwise read entirely from that file so the
# harness is not hard-coded to any single benchmark.
# --------------------------------------------------------------------------- #
LEGACY_001 = {
    "benchmark_id": "001_synthetic_mine_throughput",
    "required_output_files": ["conceptual_model.md", "README.md", "results.csv", "summary.json", "event_log.csv"],
    "required_scenarios": ["baseline", "trucks_4", "trucks_12", "ramp_upgrade", "crusher_slowdown", "ramp_closed"],
    "required_results_columns": ["scenario_id", "replication", "random_seed", "total_tonnes_delivered", "tonnes_per_hour"],
    "required_event_log_columns": ["time_min", "replication", "scenario_id", "truck_id", "event_type"],
    "summary_required_scenario_keys": ["replications", "shift_length_hours", "total_tonnes_mean", "tonnes_per_hour_mean"],
    "primary_metric": {
        "summary_mean_keys": ["total_tonnes_mean"],
        "results_value_columns": ["total_tonnes_delivered", "total_tonnes_mean"],
        "results_column_regex": None,
    },
    "behavioural_checks": [
        {"name": "trucks_12_gt_trucks_4", "type": "gt", "left": "trucks_12", "right": "trucks_4",
         "description": "Higher fleet should usually outperform lower fleet."},
        {"name": "baseline_gt_trucks_4", "type": "gt", "left": "baseline", "right": "trucks_4",
         "description": "Baseline 8-truck case should usually outperform 4-truck case."},
        {"name": "ramp_upgrade_ge_baseline", "type": "ge_factor", "left": "ramp_upgrade", "right": "baseline", "factor": 0.95,
         "description": "Ramp upgrade should usually improve or maintain throughput."},
        {"name": "crusher_slowdown_lt_baseline", "type": "lt", "left": "crusher_slowdown", "right": "baseline",
         "description": "Slower crusher should usually reduce throughput."},
        {"name": "ramp_closed_le_baseline", "type": "le_factor", "left": "ramp_closed", "right": "baseline", "factor": 1.05,
         "description": "Ramp closure should usually not improve throughput."},
        {"name": "truck_count_saturation_plausible", "type": "saturation",
         "low": "trucks_4", "mid": "baseline", "high": "trucks_12", "factor": 1.25,
         "description": "Throughput should show some saturation as trucks increase."},
    ],
    "cross_check": {"enabled": False},
}


# --------------------------------------------------------------------------- #
# Config loading + small helpers
# --------------------------------------------------------------------------- #
def load_scoring_rules(benchmark_dir: Path) -> dict[str, Any]:
    path = benchmark_dir / "expected" / "scoring_rules.yaml"
    if not path.exists():
        return dict(LEGACY_001)
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    # Fill any missing top-level keys from the legacy defaults so older benchmark
    # configs keep working.
    for key, default in LEGACY_001.items():
        cfg.setdefault(key, default)
    return cfg


def _normalise_requirement(entry: Any) -> dict[str, Any]:
    """Normalise a required-column/key entry to {name, synonyms}.

    A plain string ``"x"`` -> {name: "x", synonyms: ["x"]} (reproduces the legacy
    ``<thing>_has_x`` check names exactly). A mapping ``{any: [a, b]}`` ->
    {name: "a", synonyms: ["a", "b"]} (passes if ANY synonym is present).
    """
    if isinstance(entry, str):
        return {"name": entry, "synonyms": [entry]}
    if isinstance(entry, dict):
        syns = entry.get("any") or entry.get("synonyms") or []
        name = entry.get("as") or (syns[0] if syns else "field")
        return {"name": name, "synonyms": list(syns)}
    return {"name": str(entry), "synonyms": [str(entry)]}


def load_json(path: Path | None) -> dict[str, Any] | None:
    if not path or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def csv_columns(path: Path) -> list[str]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8", errors="ignore") as f:
        return list(csv.DictReader(f).fieldnames or [])


def check_condition(name: str, value: bool, description: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(value), "description": description}


# --------------------------------------------------------------------------- #
# Primary-metric extraction (config-driven, tolerant)
# --------------------------------------------------------------------------- #
def extract_summary_scenario_means(summary: dict[str, Any] | None, mean_keys: list[str]) -> dict[str, float]:
    if not summary:
        return {}
    means: dict[str, float] = {}
    for sid, metrics in (summary.get("scenarios") or {}).items():
        if not isinstance(metrics, dict):
            continue
        for key in mean_keys:
            if key in metrics:
                try:
                    means[sid] = float(metrics[key])
                    break
                except (TypeError, ValueError):
                    continue
    return means


def read_results_means(results_path: Path, value_columns: list[str], regex: str | None) -> dict[str, float]:
    if not results_path.exists():
        return {}
    pattern = re.compile(regex, re.I) if regex else None
    totals: dict[str, list[float]] = {}
    with results_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        chosen = next((c for c in value_columns if c in fieldnames), None)
        if chosen is None and pattern is not None:
            chosen = next((c for c in fieldnames if pattern.search(c)), None)
        if chosen is None:
            return {}
        for row in reader:
            sid = row.get("scenario_id")
            if not sid:
                continue
            try:
                totals.setdefault(sid, []).append(float(row[chosen]))
            except (TypeError, ValueError, KeyError):
                continue
    return {k: sum(v) / len(v) for k, v in totals.items() if v}


def read_results_per_rep(results_path: Path, total_columns: list[str]) -> dict[str, dict[str, float]]:
    """Return {scenario: {replication: total}} using the first matching TOTAL column.

    Rate columns (e.g. teu_per_day) are intentionally excluded by the caller, since
    the event-log reconstruction yields a total, not a rate.
    """
    if not results_path.exists():
        return {}
    out: dict[str, dict[str, float]] = {}
    with results_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        chosen = next((c for c in total_columns if c in fields), None)
        if chosen is None:
            return {}
        for row in reader:
            sid = row.get("scenario_id")
            rep = row.get("replication")
            if not sid or rep is None:
                continue
            try:
                out.setdefault(sid, {})[str(rep)] = float(row[chosen])
            except (TypeError, ValueError, KeyError):
                continue
    return out


# --------------------------------------------------------------------------- #
# Behavioural checks (config-driven by type)
# --------------------------------------------------------------------------- #
def behavioural_checks(means: dict[str, float], specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def has(*keys: str) -> bool:
        return all(k in means and math.isfinite(means[k]) for k in keys)

    out: list[dict[str, Any]] = []
    for spec in specs:
        name = spec["name"]
        desc = spec.get("description", "")
        ctype = spec.get("type")
        if ctype in {"gt", "lt", "ge_factor", "le_factor"}:
            left, right = spec["left"], spec["right"]
            factor = float(spec.get("factor", 1.0))
            if not has(left, right):
                out.append(check_condition(name, False, desc))
                continue
            lv, rv = means[left], means[right]
            passed = {
                "gt": lv > rv,
                "lt": lv < rv,
                "ge_factor": lv >= factor * rv,
                "le_factor": lv <= factor * rv,
            }[ctype]
            out.append(check_condition(name, passed, desc))
        elif ctype == "saturation":
            low, mid, high = spec["low"], spec["mid"], spec["high"]
            factor = float(spec.get("factor", 1.25))
            if has(low, mid, high):
                gain_low = means[mid] - means[low]
                gain_high = means[high] - means[mid]
                passed = gain_high <= factor * gain_low
            else:
                passed = False
            out.append(check_condition(name, passed, desc))
        else:
            out.append(check_condition(name, False, f"Unknown check type {ctype!r}"))
    return out


# --------------------------------------------------------------------------- #
# Summary / column structure checks (config-driven, exact legacy names)
# --------------------------------------------------------------------------- #
def summary_structure_checks(summary: dict[str, Any] | None, required_scenarios: list[str],
                             scenario_key_reqs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not summary:
        return [check_condition("summary_json_parseable", False, "summary.json should parse as JSON.")]
    checks = [
        check_condition("summary_has_benchmark_id", "benchmark_id" in summary, "summary.json should include benchmark_id."),
    ]
    scenarios = summary.get("scenarios")
    checks.append(check_condition("summary_has_scenarios_object", isinstance(scenarios, dict),
                                  "summary.json should include a scenarios object."))
    if isinstance(scenarios, dict):
        present = set(scenarios.keys())
        for sid in required_scenarios:
            checks.append(check_condition(f"scenario_present_{sid}", sid in present,
                                          f"summary.json should include scenario {sid}."))
        for sid, metrics in scenarios.items():
            keys = set(metrics.keys()) if isinstance(metrics, dict) else set()
            for req in scenario_key_reqs:
                ok = isinstance(metrics, dict) and bool(keys & set(req["synonyms"]))
                checks.append(check_condition(f"{sid}_has_{req['name']}", ok, f"{sid} should include {req['name']}."))
    return checks


def column_checks(cols: list[str], reqs: list[dict[str, Any]], prefix: str, label: str) -> list[dict[str, Any]]:
    present = {c.lower() for c in cols}
    out = []
    for req in reqs:
        ok = any(s.lower() in present for s in req["synonyms"])
        out.append(check_condition(f"{prefix}_has_{req['name']}", ok, f"{label} should include {req['name']}."))
    return out


# --------------------------------------------------------------------------- #
# Execute-and-cross-check: re-derive throughput from the event log
# --------------------------------------------------------------------------- #
def cross_check(outputs_dir: Path, summary_means: dict[str, float],
                results_per_rep: dict[str, dict[str, float]], cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Re-derive delivered throughput from the event log and check it is supported.

    Primary check (fair to partial logs): for each scenario, compare the event-log
    delivered total for each replication PRESENT in the log against that same
    replication's total in results.csv. This is apples-to-apples, so an agent who
    logs only a subset of replications is not penalised for it.

    Fallback (only when results.csv exposes no per-replication total): compare the
    event-log mean over logged reps against the summary mean with a wider tolerance.
    """
    if not cfg or not cfg.get("enabled"):
        return []
    event_path = outputs_dir / "event_log.csv"
    if not event_path.exists():
        return [check_condition("cross_check_event_log_reconstructable", False,
                                "event_log.csv should allow throughput reconstruction.")]

    delivered_types = {t.lower() for t in cfg.get("delivered_event_types", [])}
    teu_candidates = [c.lower() for c in cfg.get("teu_column_candidates", [])]
    tol = float(cfg.get("tolerance_fraction", 0.15))
    ftol = float(cfg.get("fallback_tolerance_fraction", 0.25))

    with event_path.open(newline="", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        cols = {c.lower(): c for c in (reader.fieldnames or [])}
        teu_col = next((cols[c] for c in teu_candidates if c in cols), None)
        et_col = cols.get("event_type")
        sid_col = cols.get("scenario_id")
        rep_col = cols.get("replication")
        if not (teu_col and et_col and sid_col):
            return [check_condition("cross_check_event_log_reconstructable", False,
                                    "event_log.csv lacks an event_type / scenario_id / TEU column to reconstruct throughput.")]
        derived: dict[str, dict[str, float]] = {}
        for row in reader:
            if (row.get(et_col) or "").strip().lower() not in delivered_types:
                continue
            sid = row.get(sid_col)
            rep = str(row.get(rep_col)) if rep_col else "0"
            try:
                val = float(row[teu_col])
            except (TypeError, ValueError, KeyError):
                continue
            derived.setdefault(sid, {}).setdefault(rep, 0.0)
            derived[sid][rep] += val

    if not derived:
        return [check_condition("cross_check_event_log_reconstructable", False,
                                "No delivery events found in event_log.csv; throughput cannot be reconstructed.")]

    checks = [check_condition("cross_check_event_log_reconstructable", True,
                              "event_log.csv contains reconstructable delivery events.")]
    for sid, by_rep in sorted(derived.items()):
        res = results_per_rep.get(sid, {})
        matched = [r for r in by_rep if r in res and res[r] != 0]
        if matched:
            errs = [abs(by_rep[r] - res[r]) / abs(res[r]) for r in matched]
            mean_err = sum(errs) / len(errs)
            checks.append(check_condition(
                f"cross_check_{sid}", mean_err <= tol,
                f"{sid}: {len(matched)} replication(s) reconciled event log vs results.csv; "
                f"mean error {mean_err*100:.1f}% (tol {int(tol*100)}%).",
            ))
            continue
        claimed = summary_means.get(sid)
        if claimed is not None and claimed != 0:
            derived_mean = sum(by_rep.values()) / len(by_rep)
            checks.append(check_condition(
                f"cross_check_{sid}", abs(derived_mean - claimed) <= ftol * abs(claimed),
                f"{sid}: no per-replication results match; event-log mean ({derived_mean:.0f}) vs "
                f"summary mean ({claimed:.0f}) within {int(ftol*100)}% (fallback).",
            ))
    return checks


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
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
    cfg = load_scoring_rules(args.benchmark_dir)

    required_files = cfg["required_output_files"]
    required_scenarios = cfg["required_scenarios"]
    results_reqs = [_normalise_requirement(e) for e in cfg["required_results_columns"]]
    event_reqs = [_normalise_requirement(e) for e in cfg["required_event_log_columns"]]
    scenario_key_reqs = [_normalise_requirement(e) for e in cfg["summary_required_scenario_keys"]]
    primary = cfg["primary_metric"]

    output_file_checks = [
        check_condition(f"output_exists_{name}", (args.outputs_dir / name).exists(),
                        f"Required output file {name} should exist.")
        for name in required_files
    ]

    summary = load_json(args.outputs_dir / "summary.json")
    summary_checks = summary_structure_checks(summary, required_scenarios, scenario_key_reqs)
    results_column_checks = column_checks(csv_columns(args.outputs_dir / "results.csv"), results_reqs, "results", "results.csv")
    event_column_checks = column_checks(csv_columns(args.outputs_dir / "event_log.csv"), event_reqs, "event_log", "event_log.csv")

    means = extract_summary_scenario_means(summary, primary.get("summary_mean_keys", []))
    if not means:
        means = read_results_means(args.outputs_dir / "results.csv",
                                   primary.get("results_value_columns", []),
                                   primary.get("results_column_regex"))

    behaviour = behavioural_checks(means, cfg["behavioural_checks"])
    cc_cfg = cfg.get("cross_check") or {}
    total_cols = cc_cfg.get("results_total_columns") or primary.get("results_value_columns", [])
    results_per_rep = read_results_per_rep(args.outputs_dir / "results.csv", total_cols)
    cross = cross_check(args.outputs_dir, means, results_per_rep, cc_cfg)

    run_metrics = load_json(args.run_metrics)
    token_usage = load_json(args.token_usage)
    if token_usage is None and run_metrics:
        token_usage = run_metrics.get("token_usage")

    all_checks = (output_file_checks + summary_checks + results_column_checks
                  + event_column_checks + behaviour + cross)
    passed = sum(1 for c in all_checks if c["passed"])
    total = len(all_checks)

    report = {
        "benchmark_id": cfg["benchmark_id"],
        "submission_dir": str(args.submission_dir),
        "outputs_dir": str(args.outputs_dir),
        "automated_checks": {
            "passed": passed,
            "total": total,
            "pass_rate": passed / total if total else None,
            "checks": all_checks,
        },
        "scenario_metric_means": means,
        "scenario_total_tonnes_means": means,  # back-compat alias for the dashboard ingestor
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
            "Cross-checks re-derive throughput from the event log; a mismatch warrants investigation.",
            "Token usage is reported only if supplied by the benchmark runner.",
        ],
    }

    args.report_out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
