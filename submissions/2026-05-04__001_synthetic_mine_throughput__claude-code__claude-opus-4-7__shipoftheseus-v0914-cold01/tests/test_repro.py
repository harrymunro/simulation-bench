"""Reproducibility test: same seed -> identical output."""
from pathlib import Path

import pandas as pd

from mine_sim.experiment import run_replication
from mine_sim.scenario import load_scenarios

DATA = Path(__file__).resolve().parents[1] / "data"


def _setup():
    nodes_df = pd.read_csv(DATA / "nodes.csv", dtype={"node_id": str})
    edges_df = pd.read_csv(DATA / "edges.csv", dtype={"edge_id": str, "from_node": str,
                                                        "to_node": str})
    trucks_df = pd.read_csv(DATA / "trucks.csv", dtype={"truck_id": str})
    loaders_df = pd.read_csv(DATA / "loaders.csv", dtype={"loader_id": str, "node_id": str})
    dump_df = pd.read_csv(DATA / "dump_points.csv", dtype={"dump_id": str, "node_id": str})
    scn = load_scenarios(DATA / "scenarios", ["baseline", "ramp_closed"])
    return nodes_df, edges_df, trucks_df, loaders_df, dump_df, scn


def test_same_seed_same_total_tonnes():
    nodes_df, edges_df, trucks_df, loaders_df, dump_df, scn = _setup()
    a_row, a_evs = run_replication(scn["baseline"], nodes_df, edges_df, trucks_df, loaders_df,
                                     dump_df, base_seed=12345, scenario_idx=0, replication_idx=0)
    b_row, b_evs = run_replication(scn["baseline"], nodes_df, edges_df, trucks_df, loaders_df,
                                     dump_df, base_seed=12345, scenario_idx=0, replication_idx=0)
    assert a_row["total_tonnes_delivered"] == b_row["total_tonnes_delivered"]
    assert a_row["random_seed"] == b_row["random_seed"]
    assert len(a_evs) == len(b_evs)


def test_different_seed_different_outcomes():
    nodes_df, edges_df, trucks_df, loaders_df, dump_df, scn = _setup()
    rows = []
    for r in range(3):
        row, _ = run_replication(scn["baseline"], nodes_df, edges_df, trucks_df, loaders_df,
                                  dump_df, base_seed=12345, scenario_idx=0, replication_idx=r)
        rows.append(row["total_tonnes_delivered"])
    # very unlikely all 3 identical with stochastic load/dump/travel
    assert len(set(rows)) > 1
