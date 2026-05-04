"""Conservation tests: tonnes only credited on dump_end; utilisations <= 1."""
from pathlib import Path

import pandas as pd
import pytest

from mine_sim.experiment import run_replication
from mine_sim.scenario import load_scenarios

DATA = Path(__file__).resolve().parents[1] / "data"


@pytest.fixture(scope="module")
def baseline_replication():
    nodes_df = pd.read_csv(DATA / "nodes.csv", dtype={"node_id": str})
    edges_df = pd.read_csv(DATA / "edges.csv", dtype={"edge_id": str, "from_node": str,
                                                        "to_node": str})
    trucks_df = pd.read_csv(DATA / "trucks.csv", dtype={"truck_id": str})
    loaders_df = pd.read_csv(DATA / "loaders.csv", dtype={"loader_id": str, "node_id": str})
    dump_df = pd.read_csv(DATA / "dump_points.csv", dtype={"dump_id": str, "node_id": str})
    scn = load_scenarios(DATA / "scenarios", ["baseline"])
    row, evs = run_replication(scn["baseline"], nodes_df, edges_df, trucks_df, loaders_df,
                                 dump_df, base_seed=12345, scenario_idx=0, replication_idx=0)
    return row, evs


def test_tonnes_match_dump_end_count(baseline_replication):
    row, evs = baseline_replication
    dump_ends = [e for e in evs if e[4] == "dump_end"]
    expected = sum(e[9] for e in dump_ends)  # payload_tonnes column
    assert abs(row["total_tonnes_delivered"] - expected) < 1e-6


def test_utilisations_in_range(baseline_replication):
    row, _ = baseline_replication
    assert 0.0 <= row["crusher_utilisation"] <= 1.0
    assert 0.0 <= row["loader_utilisation_L_N"] <= 1.0
    assert 0.0 <= row["loader_utilisation_L_S"] <= 1.0
    assert 0.0 <= row["average_truck_utilisation"] <= 1.0


def test_tonnes_below_crusher_capacity(baseline_replication):
    row, _ = baseline_replication
    # crusher capacity bound = 100 t / 3.5 min × 60 = 1714.3 t/h
    assert row["tonnes_per_hour"] <= 1714.3 + 1e-6
