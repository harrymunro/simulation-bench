"""Tests for the cross-replication KPI aggregator (AC 50203).

The aggregator collapses ``ReplicationMetrics`` records into a single
``ScenarioSummary`` with Student-t n-1 95% CIs. These tests pin down:

* the CI math (matches the textbook formula and ``scipy.stats.t.ppf``),
* graceful handling of degenerate samples (n=0, n=1, zero variance),
* per-loader / crusher / edge aggregation,
* the composite bottleneck ranking,
* error paths (mixed scenarios, mismatched keys),
* end-to-end integration with a real run.
"""

from __future__ import annotations

import math
from pathlib import Path
from types import MappingProxyType

import pytest
from scipy import stats

from mine_sim.aggregate import (
    BottleneckEntry,
    CrusherSummary,
    EdgeSummary,
    LoaderSummary,
    RunSummary,
    ScenarioSummary,
    StatSummary,
    aggregate_run,
    aggregate_scenario,
    student_t_ci_95,
)
from mine_sim.metrics import (
    CrusherMetrics,
    EdgeMetrics,
    LoaderMetrics,
    ReplicationMetrics,
)
from mine_sim.scenario_runner import run_scenario
from mine_sim.scenarios import ScenarioConfig, load_scenario

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
SCENARIOS_DIR = DATA_DIR / "scenarios"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_metrics(
    *,
    scenario_id: str = "test",
    rep_idx: int = 0,
    seed: int = 1,
    shift_min: float = 480.0,
    truck_count: int = 8,
    total_tonnes: float = 100.0,
    cycle_time: float = 30.0,
    truck_util: float = 0.7,
    crusher_util: float = 0.5,
    crusher_wait: float = 1.0,
    crusher_services: int = 10,
    loader_util: float = 0.6,
    loader_wait: float = 0.5,
    loader_services: int = 10,
    edge_util: float = 0.4,
    edge_wait: float = 0.2,
    edge_traversal: float = 1.5,
    edge_count: int = 20,
) -> ReplicationMetrics:
    """Build a synthetic ReplicationMetrics object for unit tests."""
    crusher = CrusherMetrics(
        dump_id="D_CRUSH",
        utilisation=crusher_util,
        mean_queue_wait_min=crusher_wait,
        services_completed=crusher_services,
    )
    loaders = MappingProxyType(
        {
            "LOAD_N": LoaderMetrics(
                loader_id="LOAD_N",
                utilisation=loader_util,
                mean_queue_wait_min=loader_wait,
                services_completed=loader_services,
            ),
            "LOAD_S": LoaderMetrics(
                loader_id="LOAD_S",
                utilisation=loader_util * 0.8,
                mean_queue_wait_min=loader_wait * 0.5,
                services_completed=loader_services,
            ),
        }
    )
    edges = MappingProxyType(
        {
            "E03_UP": EdgeMetrics(
                edge_id="E03_UP",
                utilisation=edge_util,
                mean_queue_wait_min=edge_wait,
                mean_traversal_time_min=edge_traversal,
                traversal_count=edge_count,
                total_wait_time_min=edge_wait * edge_count,
            ),
            "E03_DOWN": EdgeMetrics(
                edge_id="E03_DOWN",
                utilisation=edge_util * 0.5,
                mean_queue_wait_min=edge_wait * 0.5,
                mean_traversal_time_min=edge_traversal,
                traversal_count=edge_count,
                total_wait_time_min=edge_wait * 0.5 * edge_count,
            ),
        }
    )
    return ReplicationMetrics(
        scenario_id=scenario_id,
        replication_index=rep_idx,
        random_seed=seed,
        shift_length_min=shift_min,
        truck_count=truck_count,
        total_tonnes_delivered=total_tonnes,
        tonnes_per_hour=total_tonnes / (shift_min / 60.0),
        average_truck_cycle_time_min=cycle_time,
        average_truck_utilisation=truck_util,
        crusher=crusher,
        loaders=loaders,
        edges=edges,
        average_loader_queue_time_min=loader_wait,
        average_crusher_queue_time_min=crusher_wait,
        completed_dumps=int(total_tonnes / 100.0) if total_tonnes > 0 else 0,
    )


# ---------------------------------------------------------------------------
# student_t_ci_95
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_student_t_ci_95_matches_textbook_formula() -> None:
    """The CI half-width must equal t_{n-1, 0.975} * s / sqrt(n)."""
    values = (10.0, 12.0, 11.0, 9.0, 13.0)
    summary = student_t_ci_95(values)

    n = len(values)
    mean = sum(values) / n
    sse = sum((v - mean) ** 2 for v in values)
    std = math.sqrt(sse / (n - 1))
    t_crit = float(stats.t.ppf(0.975, df=n - 1))
    expected_half = t_crit * std / math.sqrt(n)

    assert summary.n == n
    assert summary.mean == pytest.approx(mean)
    assert summary.std == pytest.approx(std)
    assert summary.ci95_low == pytest.approx(mean - expected_half)
    assert summary.ci95_high == pytest.approx(mean + expected_half)
    assert summary.half_width == pytest.approx(expected_half)


@pytest.mark.unit
def test_student_t_ci_95_handles_empty_sequence() -> None:
    """n=0 -> all-zero summary (no NaN in JSON)."""
    summary = student_t_ci_95(())
    assert summary == StatSummary(mean=0.0, ci95_low=0.0, ci95_high=0.0, std=0.0, n=0)


@pytest.mark.unit
def test_student_t_ci_95_handles_single_observation() -> None:
    """n=1 -> half-width 0 (mean == low == high)."""
    summary = student_t_ci_95((42.0,))
    assert summary.n == 1
    assert summary.mean == 42.0
    assert summary.ci95_low == 42.0
    assert summary.ci95_high == 42.0
    assert summary.std == 0.0


@pytest.mark.unit
def test_student_t_ci_95_handles_zero_variance() -> None:
    """Constant sample -> half-width 0 (no division by zero)."""
    summary = student_t_ci_95((5.0, 5.0, 5.0, 5.0))
    assert summary.mean == 5.0
    assert summary.ci95_low == 5.0
    assert summary.ci95_high == 5.0
    assert summary.std == 0.0


@pytest.mark.unit
def test_student_t_ci_95_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        student_t_ci_95((1.0, 2.0), confidence=0.0)
    with pytest.raises(ValueError, match="confidence"):
        student_t_ci_95((1.0, 2.0), confidence=1.0)


@pytest.mark.unit
def test_student_t_ci_95_two_observations_uses_df_one() -> None:
    """df = n - 1; for n=2 the t critical value is large (12.706)."""
    summary = student_t_ci_95((1.0, 3.0))
    # Mean = 2, std = sqrt(2), n=2, t_{1,0.975} ≈ 12.7062
    assert summary.mean == pytest.approx(2.0)
    expected_t = float(stats.t.ppf(0.975, df=1))
    expected_half = expected_t * math.sqrt(2.0) / math.sqrt(2.0)
    assert summary.half_width == pytest.approx(expected_half)


# ---------------------------------------------------------------------------
# aggregate_scenario — synthetic inputs
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_aggregate_scenario_constant_inputs_yields_zero_ci() -> None:
    reps = [_make_metrics(rep_idx=i) for i in range(5)]
    summary = aggregate_scenario(reps)
    assert isinstance(summary, ScenarioSummary)
    assert summary.scenario_id == "test"
    assert summary.replications == 5
    assert summary.shift_length_hours == 8.0
    # Every CI collapses to the mean because inputs are constant.
    assert summary.total_tonnes_delivered.ci95_low == summary.total_tonnes_delivered.mean
    assert summary.tonnes_per_hour.std == 0.0
    assert summary.average_truck_cycle_time_min.mean == pytest.approx(30.0)


@pytest.mark.unit
def test_aggregate_scenario_means_match_per_rep_inputs() -> None:
    """Means must be the arithmetic mean of the per-rep values."""
    reps = [
        _make_metrics(rep_idx=0, total_tonnes=900.0),
        _make_metrics(rep_idx=1, total_tonnes=1000.0),
        _make_metrics(rep_idx=2, total_tonnes=1100.0),
    ]
    summary = aggregate_scenario(reps)
    assert summary.total_tonnes_delivered.mean == pytest.approx(1000.0)
    assert summary.total_tonnes_delivered.ci95_low < 1000.0 < summary.total_tonnes_delivered.ci95_high


@pytest.mark.unit
def test_aggregate_scenario_per_loader_summaries_present() -> None:
    reps = [_make_metrics(rep_idx=i) for i in range(3)]
    summary = aggregate_scenario(reps)
    assert set(summary.loaders.keys()) == {"LOAD_N", "LOAD_S"}
    load_n = summary.loaders["LOAD_N"]
    assert isinstance(load_n, LoaderSummary)
    assert load_n.loader_id == "LOAD_N"
    assert load_n.utilisation.n == 3
    assert load_n.mean_queue_wait_min.mean == pytest.approx(0.5)


@pytest.mark.unit
def test_aggregate_scenario_crusher_summary_uses_crusher_stats() -> None:
    reps = [_make_metrics(rep_idx=i, crusher_util=0.5) for i in range(3)]
    summary = aggregate_scenario(reps)
    assert isinstance(summary.crusher, CrusherSummary)
    assert summary.crusher.dump_id == "D_CRUSH"
    assert summary.crusher.utilisation.mean == pytest.approx(0.5)
    assert summary.crusher_utilisation.mean == pytest.approx(0.5)


@pytest.mark.unit
def test_aggregate_scenario_per_edge_summaries_present() -> None:
    reps = [_make_metrics(rep_idx=i) for i in range(3)]
    summary = aggregate_scenario(reps)
    assert set(summary.edges.keys()) == {"E03_UP", "E03_DOWN"}
    e03_up = summary.edges["E03_UP"]
    assert isinstance(e03_up, EdgeSummary)
    assert e03_up.utilisation.mean == pytest.approx(0.4)
    assert e03_up.traversal_count.mean == pytest.approx(20.0)


@pytest.mark.unit
def test_aggregate_scenario_top_bottlenecks_ranked_by_composite() -> None:
    """Composite score = util * mean_queue_wait, sorted descending."""
    reps = [
        _make_metrics(
            rep_idx=i,
            loader_util=0.9,
            loader_wait=2.0,  # composite 1.8
            crusher_util=0.5,
            crusher_wait=0.1,  # composite 0.05
            edge_util=0.3,
            edge_wait=0.1,  # composite 0.03
        )
        for i in range(3)
    ]
    summary = aggregate_scenario(reps, top_bottleneck_count=10)
    assert len(summary.top_bottlenecks) >= 3
    # First entry should be the loader with largest composite.
    top = summary.top_bottlenecks[0]
    assert isinstance(top, BottleneckEntry)
    assert top.resource_id == "LOAD_N"
    assert top.resource_kind == "loader"
    assert top.composite_score == pytest.approx(0.9 * 2.0)
    # Scores are non-increasing
    scores = [b.composite_score for b in summary.top_bottlenecks]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.unit
def test_aggregate_scenario_top_bottleneck_count_zero_returns_empty() -> None:
    reps = [_make_metrics(rep_idx=i) for i in range(3)]
    summary = aggregate_scenario(reps, top_bottleneck_count=0)
    assert summary.top_bottlenecks == ()


@pytest.mark.unit
def test_aggregate_scenario_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="empty"):
        aggregate_scenario([])


@pytest.mark.unit
def test_aggregate_scenario_rejects_mixed_scenarios() -> None:
    reps = [
        _make_metrics(scenario_id="baseline", rep_idx=0),
        _make_metrics(scenario_id="trucks_4", rep_idx=0),
    ]
    with pytest.raises(ValueError, match="same scenario_id"):
        aggregate_scenario(reps)


@pytest.mark.unit
def test_aggregate_scenario_immutable_outputs() -> None:
    """Summary fields should be frozen + read-only mappings."""
    reps = [_make_metrics(rep_idx=i) for i in range(3)]
    summary = aggregate_scenario(reps)
    with pytest.raises(Exception):
        summary.scenario_id = "other"  # type: ignore[misc]
    # MappingProxyType raises TypeError on mutation.
    with pytest.raises(TypeError):
        summary.loaders["LOAD_N"] = None  # type: ignore[index]


# ---------------------------------------------------------------------------
# aggregate_run — multi-scenario
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_aggregate_run_keys_match_input() -> None:
    run = {
        "baseline": [_make_metrics(scenario_id="baseline", rep_idx=i) for i in range(3)],
        "trucks_4": [_make_metrics(scenario_id="trucks_4", rep_idx=i) for i in range(3)],
    }
    result = aggregate_run(run)
    assert isinstance(result, RunSummary)
    assert set(result.scenario_ids) == {"baseline", "trucks_4"}
    assert result.scenarios["baseline"].scenario_id == "baseline"


@pytest.mark.unit
def test_aggregate_run_rejects_key_mismatch() -> None:
    """Refuses to mis-key the summary if the input dict is wrong."""
    bad = {
        "baseline": [_make_metrics(scenario_id="something_else", rep_idx=0)],
    }
    with pytest.raises(ValueError, match="mismatch"):
        aggregate_run(bad)


# ---------------------------------------------------------------------------
# Integration with a real scenario run
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def baseline_scenario() -> ScenarioConfig:
    return load_scenario(SCENARIOS_DIR / "baseline.yaml")


@pytest.mark.integration
def test_aggregate_real_baseline_three_reps_yields_meaningful_summary(
    baseline_scenario: ScenarioConfig,
) -> None:
    """Run a tiny real simulation and aggregate it end-to-end."""
    result = run_scenario(
        baseline_scenario, DATA_DIR, replication_indices=(0, 1, 2)
    )
    summary = aggregate_scenario(result.replications)
    assert summary.scenario_id == "baseline"
    assert summary.replications == 3
    assert summary.total_tonnes_delivered.mean > 0
    assert summary.tonnes_per_hour.mean > 0
    assert summary.tonnes_per_hour.ci95_low <= summary.tonnes_per_hour.mean
    assert summary.tonnes_per_hour.ci95_high >= summary.tonnes_per_hour.mean
    assert summary.crusher_utilisation.mean >= 0
    assert summary.crusher_utilisation.mean <= 1.0
    # Loader IDs come from the topology (L_N / L_S in the CSV).
    assert len(summary.loaders) >= 2
    for loader in summary.loaders.values():
        assert loader.utilisation.mean >= 0
        assert loader.utilisation.mean <= 1.0
    # Bottleneck list is non-empty and ordered.
    assert len(summary.top_bottlenecks) > 0
    scores = [b.composite_score for b in summary.top_bottlenecks]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.integration
def test_aggregate_accepts_replication_results_directly(
    baseline_scenario: ScenarioConfig,
) -> None:
    """The aggregator unwraps ReplicationResult automatically."""
    result = run_scenario(
        baseline_scenario, DATA_DIR, replication_indices=(0, 1)
    )
    # Pass the ReplicationResult tuples (not .metrics) directly.
    summary = aggregate_scenario(result.replications)
    assert summary.replications == 2
