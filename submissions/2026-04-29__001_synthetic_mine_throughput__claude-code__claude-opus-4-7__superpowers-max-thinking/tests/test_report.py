"""Tests for output file writers."""
import json

import pandas as pd

from mine_sim.experiment import run_scenario
from mine_sim.report import write_outputs
from mine_sim.scenario import load_scenario


def _smoke_results(data_dir, scenarios_dir, scenarios=("baseline",), reps=2):
    out = []
    for sid in scenarios:
        cfg = load_scenario(sid, scenarios_dir)
        cfg["simulation"]["replications"] = reps
        out.append(run_scenario(cfg, data_dir=data_dir))
    return out


def test_results_csv_columns(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir)
    write_outputs(results, output_dir=tmp_output_dir)
    df = pd.read_csv(tmp_output_dir / "results.csv")
    required = {
        "scenario_id", "replication", "random_seed",
        "total_tonnes_delivered", "tonnes_per_hour",
        "average_truck_cycle_time_min", "average_truck_utilisation",
        "crusher_utilisation",
        "average_loader_queue_time_min", "average_crusher_queue_time_min",
    }
    assert required.issubset(set(df.columns))
    assert len(df) == 2


def test_summary_json_schema(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, scenarios=("baseline", "trucks_4"), reps=2)
    write_outputs(results, output_dir=tmp_output_dir)
    summary = json.loads((tmp_output_dir / "summary.json").read_text())
    assert summary["benchmark_id"] == "001_synthetic_mine_throughput"
    for sid in ("baseline", "trucks_4"):
        s = summary["scenarios"][sid]
        for key in ("replications", "shift_length_hours", "total_tonnes_mean",
                    "total_tonnes_ci95_low", "total_tonnes_ci95_high",
                    "tonnes_per_hour_mean", "tonnes_per_hour_ci95_low",
                    "tonnes_per_hour_ci95_high", "average_cycle_time_min",
                    "truck_utilisation_mean", "loader_utilisation",
                    "crusher_utilisation", "average_loader_queue_time_min",
                    "average_crusher_queue_time_min", "top_bottlenecks"):
            assert key in s, f"missing {key} in {sid}"
        assert isinstance(s["loader_utilisation"], dict)
        assert isinstance(s["top_bottlenecks"], list)
    assert "key_assumptions" in summary
    assert "model_limitations" in summary
    assert "additional_scenarios_proposed" in summary


def test_event_log_combined_has_dumping_ended_for_all_reps(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, reps=3)
    write_outputs(results, output_dir=tmp_output_dir)
    df = pd.read_csv(tmp_output_dir / "event_log.csv")
    dumping = df[df["event_type"] == "dumping_ended"]
    assert set(dumping["replication"].unique()) == {0, 1, 2}
    rep0 = df[df["replication"] == 0]
    assert set(rep0["event_type"]) - {"dumping_ended"}


def test_per_scenario_event_log_rep0_full(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, reps=2)
    write_outputs(results, output_dir=tmp_output_dir)
    df = pd.read_csv(tmp_output_dir / "baseline__event_log.csv")
    assert set(df["replication"].unique()) == {0}
    assert "traversal_started" in set(df["event_type"])


def test_top_bottlenecks_sorted_descending(data_dir, scenarios_dir, tmp_output_dir):
    results = _smoke_results(data_dir, scenarios_dir, reps=2)
    write_outputs(results, output_dir=tmp_output_dir)
    summary = json.loads((tmp_output_dir / "summary.json").read_text())
    bottlenecks = summary["scenarios"]["baseline"]["top_bottlenecks"]
    scores = [b["score"] for b in bottlenecks]
    assert scores == sorted(scores, reverse=True)
