import json
from pathlib import Path

REQUIRED_SCENARIOS = {
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
}

def test_summary_json_has_required_structure(submission_outputs_dir):
    summary_path = Path(submission_outputs_dir) / "summary.json"
    data = json.loads(summary_path.read_text(encoding="utf-8"))
    assert "scenarios" in data, "summary.json must contain a scenarios object"
    missing = REQUIRED_SCENARIOS - set(data["scenarios"].keys())
    assert not missing, f"Missing scenarios in summary.json: {missing}"

def test_summary_scenarios_have_key_metrics(submission_outputs_dir):
    data = json.loads((Path(submission_outputs_dir) / "summary.json").read_text(encoding="utf-8"))
    required = ["replications", "shift_length_hours", "total_tonnes_mean", "tonnes_per_hour_mean"]
    for scenario_id, metrics in data["scenarios"].items():
        for key in required:
            assert key in metrics, f"{scenario_id} missing {key}"

