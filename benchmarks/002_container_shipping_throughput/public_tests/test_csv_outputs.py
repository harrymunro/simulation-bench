"""Tolerant CSV checks for benchmark 002.

002 runs under reduced hand-holding: the agent chooses its own column names, so
these tests accept synonyms and locate the throughput column by regex rather than
demanding exact strings. They assert machine-readability, not a fixed schema.
"""
import csv
import re
from pathlib import Path


def _columns(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [c for c in (reader.fieldnames or [])]


def _has_any(cols, options):
    lower = {c.lower() for c in cols}
    return any(opt in lower for opt in options)


def test_results_csv_is_machine_readable(submission_outputs_dir):
    cols = _columns(Path(submission_outputs_dir) / "results.csv")
    lower = [c.lower() for c in cols]
    assert "scenario_id" in lower, "results.csv must identify the scenario (scenario_id)"
    assert "replication" in lower, "results.csv must identify the replication"
    assert _has_any(cols, {"random_seed", "seed", "rng_seed"}), "results.csv must record the random seed"
    throughput_re = re.compile(r"teu.*deliver|deliver.*teu|total_teu|teu_per_day", re.I)
    assert any(throughput_re.search(c) for c in cols), (
        f"results.csv must contain a locatable throughput column (TEU delivered / per day); got {cols}"
    )


def test_event_log_csv_is_auditable(submission_outputs_dir):
    cols = _columns(Path(submission_outputs_dir) / "event_log.csv")
    lower = [c.lower() for c in cols]
    assert "scenario_id" in lower, "event_log.csv must identify the scenario"
    assert "replication" in lower, "event_log.csv must identify the replication"
    assert "event_type" in lower, "event_log.csv must record an event_type"
    assert _has_any(cols, {"time_days", "time_hours", "time_min", "time", "timestamp"}), (
        "event_log.csv must record an event time"
    )
    assert _has_any(cols, {"vessel_id", "ship_id", "entity_id", "vehicle_id"}), (
        "event_log.csv must identify the moving entity (vessel)"
    )
