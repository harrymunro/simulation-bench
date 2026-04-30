"""Tests for the single-replication runner (AC 50201).

The runner is the smallest public unit of simulation work; these tests
pin down its determinism, KPI sanity, scenario sensitivity, and
reachability-fail-loudly contract. They double-up as integration tests
across :mod:`mine_sim.topology`, :mod:`mine_sim.routing`,
:mod:`mine_sim.metrics`, and :mod:`mine_sim.model`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mine_sim.routing import (
    ReachabilityError,
    assert_reachable,
    compute_routes,
)
from mine_sim.runner import ReplicationResult, run_replication
from mine_sim.scenarios import (
    EdgeOverride,
    FleetParams,
    ScenarioConfig,
    SimulationParams,
    load_scenario,
)
from mine_sim.topology import build_topology

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def baseline_scenario() -> ScenarioConfig:
    return load_scenario(SCENARIOS_DIR / "baseline.yaml")


@pytest.fixture(scope="module")
def baseline_rep0(baseline_scenario: ScenarioConfig) -> ReplicationResult:
    return run_replication(baseline_scenario, DATA_DIR, replication_index=0)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_run_replication_is_deterministic(baseline_scenario: ScenarioConfig) -> None:
    a = run_replication(baseline_scenario, DATA_DIR, replication_index=3)
    b = run_replication(baseline_scenario, DATA_DIR, replication_index=3)
    assert a.metrics.total_tonnes_delivered == b.metrics.total_tonnes_delivered
    assert a.metrics.tonnes_per_hour == b.metrics.tonnes_per_hour
    assert a.metrics.completed_dumps == b.metrics.completed_dumps
    assert len(a.events) == len(b.events)


@pytest.mark.integration
def test_different_replication_indices_produce_different_outputs(
    baseline_scenario: ScenarioConfig,
) -> None:
    rep0 = run_replication(baseline_scenario, DATA_DIR, replication_index=0)
    rep1 = run_replication(baseline_scenario, DATA_DIR, replication_index=1)
    # With cv=0.10 noise across many edge traversals we expect the per-rep
    # tonnes to differ. (If by accident they collided, this is a *strong*
    # signal something is wrong.)
    assert rep0.metrics.completed_dumps != rep1.metrics.completed_dumps or (
        rep0.metrics.average_truck_cycle_time_min
        != rep1.metrics.average_truck_cycle_time_min
    )


# ---------------------------------------------------------------------------
# KPI sanity
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_baseline_kpis_are_in_plausible_ranges(
    baseline_rep0: ReplicationResult,
) -> None:
    m = baseline_rep0.metrics
    # 100 t/dump * dumps; fleet of 8, 480-min shift ⇒ low thousands of tonnes.
    assert m.total_tonnes_delivered > 5_000
    assert m.total_tonnes_delivered < 25_000
    assert m.tonnes_per_hour == pytest.approx(m.total_tonnes_delivered / 8.0)
    assert m.completed_dumps > 0
    # All utilisations should be valid probabilities.
    assert 0.0 <= m.average_truck_utilisation <= 1.0
    assert 0.0 <= m.crusher.utilisation <= 1.0
    for loader in m.loaders.values():
        assert 0.0 <= loader.utilisation <= 1.0
    # Cycle time is positive.
    assert m.average_truck_cycle_time_min > 0


@pytest.mark.integration
def test_metrics_carry_replication_metadata(
    baseline_rep0: ReplicationResult, baseline_scenario: ScenarioConfig
) -> None:
    m = baseline_rep0.metrics
    assert m.scenario_id == "baseline"
    assert m.replication_index == 0
    assert m.random_seed == baseline_scenario.simulation.base_random_seed
    assert m.shift_length_min == 480
    assert m.truck_count == baseline_scenario.fleet.truck_count


@pytest.mark.integration
def test_capacity_edge_metrics_present(baseline_rep0: ReplicationResult) -> None:
    edges = baseline_rep0.metrics.edges
    # The Seed enumerates the cap-1 edges; all eight must show up.
    expected = {
        "E03_UP",
        "E03_DOWN",
        "E05_TO_CRUSH",
        "E05_FROM_CRUSH",
        "E07_TO_LOAD_N",
        "E07_FROM_LOAD_N",
        "E09_TO_LOAD_S",
        "E09_FROM_LOAD_S",
    }
    assert expected.issubset(set(edges))
    # Sanity-check shape on every cap-1 edge; not every edge is traversed in
    # a baseline cycle (e.g. E03_DOWN sits on the PARK return leg, which the
    # ore cycle never uses after the initial dispatch).
    for edge_id in expected:
        em = edges[edge_id]
        assert em.traversal_count >= 0
        assert 0.0 <= em.utilisation <= 1.0
    # The crusher approach (E05_TO_CRUSH) is on every loaded leg, so it must
    # see traffic.
    assert edges["E05_TO_CRUSH"].traversal_count > 0
    # The initial dispatch climbs the ramp once per truck.
    assert edges["E03_UP"].traversal_count > 0


# ---------------------------------------------------------------------------
# Hard-cut and event-log integrity
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_hard_cut_at_480_minutes(baseline_rep0: ReplicationResult) -> None:
    """No event with time_min > shift cut should be in the captured log."""
    shift_min = 480.0
    for ev in baseline_rep0.events:
        assert ev.time_min <= shift_min + 1e-6


@pytest.mark.integration
def test_dispatch_event_present_for_every_truck(
    baseline_rep0: ReplicationResult, baseline_scenario: ScenarioConfig
) -> None:
    dispatched = {
        ev.truck_id for ev in baseline_rep0.events if ev.event_type == "dispatch"
    }
    assert len(dispatched) == baseline_scenario.fleet.truck_count


# ---------------------------------------------------------------------------
# Edge enter/leave events fire at SimPy Resource request/release boundaries
# (Sub-AC 2 of AC 4)
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_edge_enter_and_leave_events_emitted(
    baseline_rep0: ReplicationResult,
    baseline_scenario: ScenarioConfig,
) -> None:
    """Capacity-1 edges must produce both enter and leave events."""
    enter = [e for e in baseline_rep0.events if e.event_type == "edge_enter"]
    leave = [e for e in baseline_rep0.events if e.event_type == "edge_leave"]
    assert len(enter) > 0
    assert len(leave) > 0
    # The shift cut can interrupt a truck mid-edge: it has fired enter but
    # was timed-out by env.run(until=480) before it could fire leave. The
    # resulting deficit is bounded above by the fleet size (one in-flight
    # truck per truck at most).
    deficit = len(enter) - len(leave)
    assert 0 <= deficit <= baseline_scenario.fleet.truck_count


@pytest.mark.integration
def test_edge_events_only_for_capacity_constrained_edges(
    baseline_rep0: ReplicationResult,
) -> None:
    """Only the eight capacity-1 edges may appear as resource_id."""
    capacity_constrained = {
        "E03_UP",
        "E03_DOWN",
        "E05_TO_CRUSH",
        "E05_FROM_CRUSH",
        "E07_TO_LOAD_N",
        "E07_FROM_LOAD_N",
        "E09_TO_LOAD_S",
        "E09_FROM_LOAD_S",
    }
    for ev in baseline_rep0.events:
        if ev.event_type in {"edge_enter", "edge_leave"}:
            assert ev.resource_id in capacity_constrained, (
                f"Unexpected edge event for non-cap-1 edge: {ev.resource_id}"
            )


@pytest.mark.integration
def test_edge_enter_leave_bracket_holding(
    baseline_rep0: ReplicationResult,
) -> None:
    """Per the conceptual model: edge_enter / edge_leave must bracket the
    *holding* of the resource. For a single edge that means each
    edge_enter for a given (truck, edge) is followed by exactly one
    edge_leave before the next edge_enter for the same pair, and the
    leave's location is the edge's to_node (truck has traversed)."""
    # Pick an edge that always sees traffic.
    edge_id = "E05_TO_CRUSH"
    per_truck: dict[str, list[tuple[str, float, str | None]]] = {}
    for ev in baseline_rep0.events:
        if ev.resource_id != edge_id:
            continue
        if ev.event_type not in {"edge_enter", "edge_leave"}:
            continue
        per_truck.setdefault(ev.truck_id, []).append(
            (ev.event_type, ev.time_min, ev.location)
        )

    assert per_truck, "Expected at least one truck to traverse E05_TO_CRUSH"

    for truck_id, sequence in per_truck.items():
        # Pair them up: enter, leave, enter, leave, ... A trailing
        # unpaired ``edge_enter`` is allowed iff it is the final entry
        # (truck was mid-traversal at the t=480 hard cut).
        if len(sequence) % 2 == 1:
            assert sequence[-1][0] == "edge_enter", (
                f"{truck_id} has odd edge_enter/edge_leave count and final "
                f"event is not edge_enter (cannot be a shift-cut interrupt)"
            )
            sequence = sequence[:-1]  # drop the dangling enter for pair check
        for i in range(0, len(sequence), 2):
            enter_type, enter_t, enter_loc = sequence[i]
            leave_type, leave_t, leave_loc = sequence[i + 1]
            assert enter_type == "edge_enter"
            assert leave_type == "edge_leave"
            # Leave must come strictly after enter (positive traversal time).
            assert leave_t > enter_t, (
                f"{truck_id}: edge_leave at {leave_t} must follow "
                f"edge_enter at {enter_t}"
            )
            # Enter is at from_node; leave is at to_node (truck has crossed).
            assert enter_loc != leave_loc, (
                f"{truck_id}: enter/leave locations must differ"
            )


@pytest.mark.integration
def test_edge_enter_emitted_after_acquisition(
    baseline_rep0: ReplicationResult,
) -> None:
    """Sub-AC 2 contract: edge_enter is emitted at the *request* boundary
    (just after the resource is granted), so its timestamp must equal or
    follow that of any concurrent edge_leave that releases the same
    resource. We probe this via the queue_length: at the acquisition
    boundary, count + queue includes the truck itself, so queue_length is
    always >= 1 for an edge_enter event."""
    enter_events = [
        ev for ev in baseline_rep0.events if ev.event_type == "edge_enter"
    ]
    assert enter_events, "No edge_enter events produced"
    for ev in enter_events:
        assert ev.queue_length is not None
        assert ev.queue_length >= 1, (
            f"edge_enter at t={ev.time_min} for {ev.resource_id} expected "
            f"queue_length >= 1 (resource held by emitting truck), got "
            f"{ev.queue_length}"
        )


# ---------------------------------------------------------------------------
# Scenario sensitivity (cheap regression tests)
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_trucks_4_yields_lower_throughput_than_baseline() -> None:
    baseline = load_scenario(SCENARIOS_DIR / "baseline.yaml")
    trucks_4 = load_scenario(SCENARIOS_DIR / "trucks_4.yaml")
    a = run_replication(baseline, DATA_DIR, replication_index=0)
    b = run_replication(trucks_4, DATA_DIR, replication_index=0)
    assert b.metrics.total_tonnes_delivered < a.metrics.total_tonnes_delivered


@pytest.mark.integration
def test_crusher_slowdown_yields_lower_throughput() -> None:
    baseline = load_scenario(SCENARIOS_DIR / "baseline.yaml")
    slowdown = load_scenario(SCENARIOS_DIR / "crusher_slowdown.yaml")
    a = run_replication(baseline, DATA_DIR, replication_index=0)
    b = run_replication(slowdown, DATA_DIR, replication_index=0)
    assert b.metrics.total_tonnes_delivered < a.metrics.total_tonnes_delivered


# ---------------------------------------------------------------------------
# Reachability fail-loudly contract
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_reachability_check_raises_when_loader_isolated() -> None:
    """Closing the only access to LOAD_N must trip the self-check."""
    scenario = ScenarioConfig(
        scenario_id="broken_test_loadn",
        simulation=SimulationParams(),
        fleet=FleetParams(truck_count=1),
        edge_overrides={
            "E07_TO_LOAD_N": EdgeOverride(closed=True),
            "E07_FROM_LOAD_N": EdgeOverride(closed=True),
        },
    )
    topology = build_topology(DATA_DIR, scenario)
    table = compute_routes(topology)
    with pytest.raises(ReachabilityError, match="unreachable"):
        assert_reachable(table, scenario_id=scenario.scenario_id)


@pytest.mark.unit
def test_reachability_check_passes_for_baseline() -> None:
    scenario = load_scenario(SCENARIOS_DIR / "baseline.yaml")
    topology = build_topology(DATA_DIR, scenario)
    table = compute_routes(topology)
    # Should not raise.
    assert_reachable(table, scenario_id=scenario.scenario_id)


@pytest.mark.unit
def test_reachability_check_passes_for_ramp_closed() -> None:
    """Bypass routing must keep all OD pairs reachable when the ramp is shut."""
    scenario = load_scenario(SCENARIOS_DIR / "ramp_closed.yaml")
    topology = build_topology(DATA_DIR, scenario)
    table = compute_routes(topology)
    assert_reachable(table, scenario_id=scenario.scenario_id)


# ---------------------------------------------------------------------------
# AC 10: reachability self-check passes for all required OD pairs across all
# seven scenarios (the six required + the trucks_12 + ramp_upgrade combo).
# ---------------------------------------------------------------------------
ALL_SCENARIO_IDS: tuple[str, ...] = (
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_closed",
    "ramp_upgrade",
    "crusher_slowdown",
    "trucks_12_ramp_upgrade",
)


@pytest.mark.unit
@pytest.mark.parametrize("scenario_id", ALL_SCENARIO_IDS)
def test_reachability_check_passes_for_all_seven_scenarios(
    scenario_id: str,
) -> None:
    """Every shipped scenario must satisfy the reachability self-check.

    Pins AC 10: the eight required OD pairs (PARK<->LOAD_N, PARK<->LOAD_S,
    LOAD_N<->CRUSH, LOAD_S<->CRUSH) must all resolve to a finite shortest
    path under each scenario's edge overrides.
    """
    from mine_sim.routing import REQUIRED_OD_PAIRS

    scenario = load_scenario(SCENARIOS_DIR / f"{scenario_id}.yaml")
    topology = build_topology(DATA_DIR, scenario)
    table = compute_routes(topology)
    # Should not raise — exhaustive check across every required OD pair.
    assert_reachable(table, scenario_id=scenario.scenario_id)
    for origin, destination in REQUIRED_OD_PAIRS:
        route = table.get(origin, destination)
        assert route is not None, (
            f"{scenario_id}: missing route {origin} -> {destination}"
        )
        assert route.free_flow_time_min > 0, (
            f"{scenario_id}: zero-length route {origin} -> {destination}"
        )
        assert route.free_flow_time_min != float("inf"), (
            f"{scenario_id}: infinite route {origin} -> {destination}"
        )


@pytest.mark.integration
def test_run_replication_rejects_negative_index(
    baseline_scenario: ScenarioConfig,
) -> None:
    with pytest.raises(ValueError, match="replication_index"):
        run_replication(baseline_scenario, DATA_DIR, replication_index=-1)
