"""Tests for replication-driven experiments and reproducibility."""
import pandas as pd

from mine_sim.experiment import run_replication, run_scenario
from mine_sim.scenario import load_scenario


def test_run_replication_returns_collector(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    collector = run_replication(cfg, replication_idx=0, data_dir=data_dir)
    assert collector.scenario_id == "baseline"
    assert collector.replication == 0
    assert collector.total_tonnes() > 0


def test_same_seed_reproducible(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    a = run_replication(cfg, replication_idx=3, data_dir=data_dir)
    b = run_replication(cfg, replication_idx=3, data_dir=data_dir)
    df_a = pd.DataFrame(a.event_log_rows())
    df_b = pd.DataFrame(b.event_log_rows())
    pd.testing.assert_frame_equal(df_a, df_b)


def test_different_seeds_differ(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    a = run_replication(cfg, replication_idx=0, data_dir=data_dir)
    b = run_replication(cfg, replication_idx=1, data_dir=data_dir)
    # tonnes are quantised in 100t increments; seed change should alter at least the event log
    assert a.event_log_rows() != b.event_log_rows()


def test_run_scenario_runs_all_replications(data_dir, scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    cfg["simulation"]["replications"] = 3
    result = run_scenario(cfg, data_dir=data_dir)
    assert result.scenario_id == "baseline"
    assert len(result.replications) == 3
    assert all(r.total_tonnes() > 0 for r in result.replications)


def test_run_replication_truck_count_respected(data_dir, scenarios_dir):
    cfg = load_scenario("trucks_4", scenarios_dir)
    collector = run_replication(cfg, replication_idx=0, data_dir=data_dir)
    truck_ids = {row["truck_id"] for row in collector.event_log_rows()}
    assert truck_ids == {"T01", "T02", "T03", "T04"}
