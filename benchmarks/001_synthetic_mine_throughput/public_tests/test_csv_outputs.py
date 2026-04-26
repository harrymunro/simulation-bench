import csv
from pathlib import Path

REQUIRED_RESULTS_COLUMNS = {
    "scenario_id",
    "replication",
    "random_seed",
    "total_tonnes_delivered",
    "tonnes_per_hour",
}

REQUIRED_EVENT_COLUMNS = {
    "time_min",
    "replication",
    "scenario_id",
    "truck_id",
    "event_type",
}

def _columns(path):
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return set(reader.fieldnames or [])

def test_results_csv_columns(submission_outputs_dir):
    cols = _columns(Path(submission_outputs_dir) / "results.csv")
    missing = REQUIRED_RESULTS_COLUMNS - cols
    assert not missing, f"results.csv missing columns: {missing}"

def test_event_log_csv_columns(submission_outputs_dir):
    cols = _columns(Path(submission_outputs_dir) / "event_log.csv")
    missing = REQUIRED_EVENT_COLUMNS - cols
    assert not missing, f"event_log.csv missing columns: {missing}"

