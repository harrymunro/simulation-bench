"""Tests for scenario YAML loading and inherits: merging."""
from mine_sim.scenario import deep_merge, load_scenario


def test_deep_merge_replaces_scalars():
    parent = {"fleet": {"truck_count": 8}, "shift": 480}
    child = {"fleet": {"truck_count": 4}}
    merged = deep_merge(parent, child)
    assert merged["fleet"]["truck_count"] == 4
    assert merged["shift"] == 480


def test_deep_merge_nested_dicts():
    parent = {"a": {"b": 1, "c": 2}}
    child = {"a": {"b": 10}}
    assert deep_merge(parent, child) == {"a": {"b": 10, "c": 2}}


def test_deep_merge_does_not_mutate_inputs():
    parent = {"a": {"b": 1}}
    child = {"a": {"b": 2}}
    deep_merge(parent, child)
    assert parent == {"a": {"b": 1}}
    assert child == {"a": {"b": 2}}


def test_load_baseline(scenarios_dir):
    cfg = load_scenario("baseline", scenarios_dir)
    assert cfg["scenario_id"] == "baseline"
    assert cfg["fleet"]["truck_count"] == 8
    assert cfg["simulation"]["replications"] == 30
    assert "inherits" not in cfg


def test_load_inherited_trucks_4(scenarios_dir):
    cfg = load_scenario("trucks_4", scenarios_dir)
    assert cfg["scenario_id"] == "trucks_4"          # child wins on scenario_id
    assert cfg["fleet"]["truck_count"] == 4          # child override
    assert cfg["simulation"]["replications"] == 30   # inherited from baseline
    assert "inherits" not in cfg


def test_load_ramp_upgrade_carries_overrides(scenarios_dir):
    cfg = load_scenario("ramp_upgrade", scenarios_dir)
    assert cfg["edge_overrides"]["E03_UP"]["capacity"] == 999
    assert cfg["edge_overrides"]["E03_UP"]["max_speed_kph"] == 28
    assert cfg["fleet"]["truck_count"] == 8          # inherited


def test_load_ramp_closed_marks_edges_closed(scenarios_dir):
    cfg = load_scenario("ramp_closed", scenarios_dir)
    assert cfg["edge_overrides"]["E03_UP"]["closed"] is True
    assert cfg["edge_overrides"]["E03_DOWN"]["closed"] is True
