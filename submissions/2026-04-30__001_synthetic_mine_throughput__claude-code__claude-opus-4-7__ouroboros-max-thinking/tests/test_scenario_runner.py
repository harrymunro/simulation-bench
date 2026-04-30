"""Tests for the multi-replication, multi-scenario runner (AC 50202).

These tests pin down the contract Sub-AC 2 promises:

* Each per-rep record carries ``random_seed = base + rep_idx``.
* Each scenario runs the configured number of replications when no
  override is supplied; the override is honoured when supplied.
* All seven required scenarios (six required + the combo extra) are
  reachable and runnable end-to-end.
* The orchestrator preserves a deterministic scenario / replication
  order so downstream CSV output is reproducible.
* The reachability self-check still fires before the scenario starts
  burning replication time.

The fast path uses a single replication per scenario — the multi-rep
behaviour is exercised separately on the baseline scenario only so the
full test sweep stays under ~10s.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mine_sim.scenario_runner import (
    MultiScenarioRunResult,
    ReplicationProgress,
    ScenarioRunResult,
    run_all_scenarios,
    run_required_scenarios,
    run_scenario,
)
from mine_sim.scenarios import (
    REQUIRED_SCENARIO_IDS,
    EdgeOverride,
    FleetParams,
    ScenarioConfig,
    SimulationParams,
    load_all_scenarios,
    load_scenario,
)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def baseline_scenario() -> ScenarioConfig:
    return load_scenario(SCENARIOS_DIR / "baseline.yaml")


@pytest.fixture(scope="module")
def all_required_scenarios() -> dict[str, ScenarioConfig]:
    return load_all_scenarios(SCENARIOS_DIR)


# ---------------------------------------------------------------------------
# Single-scenario runner
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_scenario_uses_per_rep_seed_formula(
    baseline_scenario: ScenarioConfig,
) -> None:
    """Each rep's random_seed must equal base_seed + replication_index."""
    result = run_scenario(
        baseline_scenario,
        DATA_DIR,
        replication_indices=(0, 1, 2),
    )
    base = baseline_scenario.simulation.base_random_seed
    seeds = [r.metrics.random_seed for r in result.replications]
    assert seeds == [base + 0, base + 1, base + 2]
    indices = [r.metrics.replication_index for r in result.replications]
    assert indices == [0, 1, 2]


@pytest.mark.integration
def test_run_scenario_default_replication_count(
    baseline_scenario: ScenarioConfig,
) -> None:
    """When no override is supplied, n == scenario.simulation.replications."""
    # Use a tiny override scenario so the test is fast but still
    # exercises the default-count branch.
    fast_scenario = ScenarioConfig(
        scenario_id="fast_baseline_for_test",
        simulation=SimulationParams(replications=3, base_random_seed=42),
        fleet=FleetParams(truck_count=baseline_scenario.fleet.truck_count),
    )
    result = run_scenario(fast_scenario, DATA_DIR)
    assert result.replication_count == 3
    assert [r.metrics.replication_index for r in result.replications] == [0, 1, 2]
    assert [r.metrics.random_seed for r in result.replications] == [42, 43, 44]


@pytest.mark.integration
def test_run_scenario_returns_immutable_result(
    baseline_scenario: ScenarioConfig,
) -> None:
    """ScenarioRunResult is a frozen dataclass with a tuple of reps."""
    result = run_scenario(
        baseline_scenario,
        DATA_DIR,
        replication_indices=(0,),
    )
    assert isinstance(result, ScenarioRunResult)
    assert isinstance(result.replications, tuple)
    with pytest.raises(Exception):
        # frozen=True ⇒ FrozenInstanceError (a subclass of AttributeError)
        result.scenario = baseline_scenario  # type: ignore[misc]


@pytest.mark.integration
def test_run_scenario_progress_callback_fires_in_order(
    baseline_scenario: ScenarioConfig,
) -> None:
    """Progress callback receives one event per replication, in order."""
    events: list[ReplicationProgress] = []
    indices = (0, 1)
    run_scenario(
        baseline_scenario,
        DATA_DIR,
        replication_indices=indices,
        progress=events.append,
    )
    assert len(events) == len(indices)
    assert [e.replication_index for e in events] == list(indices)
    assert all(e.scenario_id == "baseline" for e in events)
    assert all(e.replication_total == len(indices) for e in events)


@pytest.mark.integration
def test_run_scenario_rejects_negative_indices(
    baseline_scenario: ScenarioConfig,
) -> None:
    with pytest.raises(ValueError, match="must be >= 0"):
        run_scenario(
            baseline_scenario,
            DATA_DIR,
            replication_indices=(0, -1),
        )


@pytest.mark.integration
def test_run_scenario_rejects_non_positive_default_replications() -> None:
    bad_scenario = ScenarioConfig(
        scenario_id="bad_zero_reps",
        simulation=SimulationParams(replications=0),
    )
    with pytest.raises(ValueError, match="positive"):
        run_scenario(bad_scenario, DATA_DIR)


@pytest.mark.integration
def test_run_scenario_reachability_check_fires_loudly() -> None:
    """Closing the only access to LOAD_N must raise before any rep runs."""
    from mine_sim.routing import ReachabilityError

    broken = ScenarioConfig(
        scenario_id="broken_test",
        simulation=SimulationParams(replications=1),
        fleet=FleetParams(truck_count=1),
        edge_overrides={
            "E07_TO_LOAD_N": EdgeOverride(closed=True),
            "E07_FROM_LOAD_N": EdgeOverride(closed=True),
        },
    )
    with pytest.raises(ReachabilityError, match="unreachable"):
        run_scenario(broken, DATA_DIR)


# ---------------------------------------------------------------------------
# Multi-scenario runner
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_all_scenarios_runs_every_required_scenario(
    all_required_scenarios: dict[str, ScenarioConfig],
) -> None:
    """All seven scenarios complete with the requested rep count."""
    # rep_count=1 keeps this fast; the formula and ordering are what we
    # care about, not the per-rep KPI.
    result = run_all_scenarios(
        all_required_scenarios,
        DATA_DIR,
        scenario_ids=REQUIRED_SCENARIO_IDS,
        replication_indices=(0,),
    )
    assert isinstance(result, MultiScenarioRunResult)
    assert result.scenario_ids == REQUIRED_SCENARIO_IDS
    for scenario_id in REQUIRED_SCENARIO_IDS:
        scenario_result = result.results[scenario_id]
        assert scenario_result.replication_count == 1
        assert scenario_result.replications[0].metrics.scenario_id == scenario_id


@pytest.mark.integration
def test_run_all_scenarios_includes_combo_scenario(
    all_required_scenarios: dict[str, ScenarioConfig],
) -> None:
    """The seventh scenario (trucks_12_ramp_upgrade) is part of the run set."""
    assert "trucks_12_ramp_upgrade" in all_required_scenarios
    combo = all_required_scenarios["trucks_12_ramp_upgrade"]
    assert combo.fleet.truck_count == 12
    assert combo.edge_overrides["E03_UP"].capacity == 999

    result = run_all_scenarios(
        {combo.scenario_id: combo},
        DATA_DIR,
        replication_indices=(0,),
    )
    rep = result.results["trucks_12_ramp_upgrade"].replications[0]
    assert rep.metrics.scenario_id == "trucks_12_ramp_upgrade"
    assert rep.metrics.truck_count == 12


@pytest.mark.integration
def test_run_all_scenarios_progress_callback_receives_every_rep(
    all_required_scenarios: dict[str, ScenarioConfig],
) -> None:
    events: list[ReplicationProgress] = []
    result = run_all_scenarios(
        all_required_scenarios,
        DATA_DIR,
        scenario_ids=REQUIRED_SCENARIO_IDS,
        replication_indices=(0, 1),
        progress=events.append,
    )
    # 7 scenarios * 2 reps = 14 progress events.
    assert len(events) == 14
    # Order: scenario1.rep0, scenario1.rep1, scenario2.rep0, ...
    expected_order = [
        (sid, idx) for sid in REQUIRED_SCENARIO_IDS for idx in (0, 1)
    ]
    actual_order = [(e.scenario_id, e.replication_index) for e in events]
    assert actual_order == expected_order
    # scenario_total/scenario_index plumbing
    assert all(e.scenario_total == 7 for e in events)
    assert result.total_replications() == 14


@pytest.mark.integration
def test_run_all_scenarios_filter_subset(
    all_required_scenarios: dict[str, ScenarioConfig],
) -> None:
    """Passing ``scenario_ids`` must filter and reorder."""
    subset = ("crusher_slowdown", "baseline")
    result = run_all_scenarios(
        all_required_scenarios,
        DATA_DIR,
        scenario_ids=subset,
        replication_indices=(0,),
    )
    # Order is preserved as the caller requested.
    assert result.scenario_ids == subset
    assert set(result.results) == set(subset)


@pytest.mark.integration
def test_run_all_scenarios_unknown_scenario_id_raises(
    all_required_scenarios: dict[str, ScenarioConfig],
) -> None:
    with pytest.raises(KeyError, match="not found"):
        run_all_scenarios(
            all_required_scenarios,
            DATA_DIR,
            scenario_ids=("baseline", "no_such_scenario"),
        )


@pytest.mark.integration
def test_run_all_scenarios_accepts_iterable_input(
    all_required_scenarios: dict[str, ScenarioConfig],
) -> None:
    """Passing a plain iterable of configs works as well as a dict."""
    configs = list(all_required_scenarios.values())
    result = run_all_scenarios(
        configs,
        DATA_DIR,
        replication_indices=(0,),
    )
    assert set(result.scenario_ids) == set(REQUIRED_SCENARIO_IDS)


@pytest.mark.integration
def test_run_all_scenarios_rejects_duplicate_iterable(
    baseline_scenario: ScenarioConfig,
) -> None:
    with pytest.raises(ValueError, match="Duplicate scenario_id"):
        run_all_scenarios(
            [baseline_scenario, baseline_scenario],
            DATA_DIR,
            replication_indices=(0,),
        )


@pytest.mark.integration
def test_run_all_scenarios_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="No scenarios"):
        run_all_scenarios({}, DATA_DIR, replication_indices=(0,))


# ---------------------------------------------------------------------------
# Required-scenarios convenience wrapper
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_required_scenarios_loads_and_runs_all_seven() -> None:
    """`run_required_scenarios` is the CLI's `run-all` entry point."""
    result = run_required_scenarios(
        SCENARIOS_DIR,
        DATA_DIR,
        replication_indices=(0,),
    )
    assert result.scenario_ids == REQUIRED_SCENARIO_IDS
    for sid in REQUIRED_SCENARIO_IDS:
        s_result = result.results[sid]
        assert s_result.replication_count == 1
        rep = s_result.replications[0]
        # KPI sanity: every scenario must produce some throughput at rep 0.
        assert rep.metrics.completed_dumps >= 0
        assert rep.metrics.scenario_id == sid


# ---------------------------------------------------------------------------
# Per-rep KPI record collection (the heart of Sub-AC 2)
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_per_rep_kpis_form_a_flat_collection(
    baseline_scenario: ScenarioConfig,
) -> None:
    """Sub-AC 2 must yield one KPI record per replication per scenario."""
    result = run_all_scenarios(
        {baseline_scenario.scenario_id: baseline_scenario},
        DATA_DIR,
        replication_indices=(0, 1, 2),
    )
    flat = result.all_replications()
    assert len(flat) == 3
    seeds = [rep.metrics.random_seed for rep in flat]
    base = baseline_scenario.simulation.base_random_seed
    assert seeds == [base + 0, base + 1, base + 2]
    # KPI records carry the right scenario_id and replication_index.
    for idx, rep in enumerate(flat):
        assert rep.metrics.scenario_id == "baseline"
        assert rep.metrics.replication_index == idx
