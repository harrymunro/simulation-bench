"""Tolerant summary.json checks for benchmark 002.

Accepts agent-chosen key names via synonym sets, consistent with the reduced
hand-holding posture and expected/scoring_rules.yaml.
"""
import json
from pathlib import Path

REQUIRED_SCENARIOS = {
    "baseline",
    "fleet_small",
    "fleet_large",
    "canal_upgrade",
    "port_slowdown",
    "canal_closed",
}

# Each concept is satisfied by any one synonym in its set.
CONCEPT_SYNONYMS = [
    ("replications", {"replications"}),
    ("horizon", {"horizon_days", "planning_horizon_days", "horizon", "shift_length_hours"}),
    ("total_teu", {"total_teu_mean", "total_teu_delivered_mean", "teu_delivered_mean", "total_teu"}),
    ("per_day", {"teu_per_day_mean", "teu_per_day", "throughput_teu_per_day_mean"}),
]


def _load(submission_outputs_dir):
    return json.loads((Path(submission_outputs_dir) / "summary.json").read_text(encoding="utf-8"))


def test_summary_has_required_scenarios(submission_outputs_dir):
    data = _load(submission_outputs_dir)
    assert "scenarios" in data, "summary.json must contain a scenarios object"
    missing = REQUIRED_SCENARIOS - set(data["scenarios"].keys())
    assert not missing, f"Missing scenarios in summary.json: {missing}"


def test_summary_scenarios_expose_throughput(submission_outputs_dir):
    data = _load(submission_outputs_dir)
    for scenario_id, metrics in data["scenarios"].items():
        keys = {k.lower() for k in metrics.keys()}
        for concept, synonyms in CONCEPT_SYNONYMS:
            assert keys & synonyms, (
                f"{scenario_id} is missing a '{concept}' field (any of {sorted(synonyms)})"
            )
