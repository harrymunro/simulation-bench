"""Unit tests for :mod:`mine_sim.io_writers`.

Each writer is a pure function over already-built dataclasses, so the
tests construct minimal synthetic records and assert the on-disk shape
matches the Seed-pinned schema.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from types import MappingProxyType

import pytest

from mine_sim.aggregate import (
    BottleneckEntry,
    CrusherSummary,
    EdgeSummary,
    LoaderSummary,
    RunSummary,
    ScenarioSummary,
    StatSummary,
)
from mine_sim.events import EVENT_CSV_COLUMNS, EVENT_DISPATCH, EventRecord
from mine_sim.io_writers import (
    DEFAULT_ADDITIONAL_SCENARIOS_PROPOSED,
    DEFAULT_BENCHMARK_ID,
    DEFAULT_KEY_ASSUMPTIONS,
    DEFAULT_MODEL_LIMITATIONS,
    RESULTS_CSV_COLUMNS,
    RUN_SUMMARY_REQUIRED_KEYS,
    SCENARIO_SUMMARY_REQUIRED_KEYS,
    STAT_SUMMARY_REQUIRED_KEYS,
    SchemaValidationError,
    bottleneck_to_dict,
    collect_events,
    crusher_summary_to_dict,
    edge_summary_to_dict,
    loader_summary_to_dict,
    replication_to_results_row,
    run_summary_to_dict,
    scenario_summary_to_dict,
    stat_to_dict,
    validate_run_summary_payload,
    validate_scenario_summary_payload,
    validate_stat_summary_dict,
    write_event_log_csv,
    write_results_csv,
    write_run_summary_json,
    write_scenario_summary_json,
)
from mine_sim.metrics import (
    CrusherMetrics,
    EdgeMetrics,
    LoaderMetrics,
    ReplicationMetrics,
)
from mine_sim.runner import ReplicationResult


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_replication(
    scenario_id: str = "baseline",
    rep_idx: int = 0,
) -> ReplicationResult:
    crusher = CrusherMetrics(
        dump_id="D_CRUSH",
        utilisation=0.85,
        mean_queue_wait_min=2.5,
        services_completed=120,
    )
    metrics = ReplicationMetrics(
        scenario_id=scenario_id,
        replication_index=rep_idx,
        random_seed=12345 + rep_idx,
        shift_length_min=480.0,
        truck_count=8,
        total_tonnes_delivered=12000.0 + rep_idx,
        tonnes_per_hour=1500.0 + rep_idx,
        average_truck_cycle_time_min=30.0,
        average_truck_utilisation=0.95,
        crusher=crusher,
        loaders=MappingProxyType({}),
        edges=MappingProxyType({}),
        average_loader_queue_time_min=2.1,
        average_crusher_queue_time_min=2.5,
        completed_dumps=120,
    )
    event = EventRecord(
        time_min=0.0,
        replication=rep_idx,
        scenario_id=scenario_id,
        truck_id="T01",
        event_type=EVENT_DISPATCH,
        from_node=None,
        to_node="LOAD_N",
        location="PARK",
        loaded=False,
        payload_tonnes=None,
        resource_id=None,
        queue_length=None,
    )
    return ReplicationResult(
        metrics=metrics,
        events=(event,),
        topology=None,  # type: ignore[arg-type]
        routing=None,  # type: ignore[arg-type]
    )


def _make_scenario_summary(scenario_id: str = "baseline") -> ScenarioSummary:
    stat = StatSummary(mean=1.0, ci95_low=0.9, ci95_high=1.1, std=0.05, n=2)
    crusher = CrusherSummary(
        dump_id="D_CRUSH",
        utilisation=stat,
        mean_queue_wait_min=stat,
        services_completed=stat,
    )
    loader = LoaderSummary(
        loader_id="L_N",
        utilisation=stat,
        mean_queue_wait_min=stat,
        services_completed=stat,
    )
    edge = EdgeSummary(
        edge_id="E03_UP",
        utilisation=stat,
        mean_queue_wait_min=stat,
        mean_traversal_time_min=stat,
        traversal_count=stat,
    )
    bottleneck = BottleneckEntry(
        resource_id="L_N",
        resource_kind="loader",
        utilisation_mean=0.9,
        mean_queue_wait_min=2.0,
        composite_score=1.8,
    )
    return ScenarioSummary(
        scenario_id=scenario_id,
        replications=2,
        shift_length_hours=8.0,
        total_tonnes_delivered=stat,
        tonnes_per_hour=stat,
        average_truck_cycle_time_min=stat,
        average_truck_utilisation=stat,
        crusher_utilisation=stat,
        average_loader_queue_time_min=stat,
        average_crusher_queue_time_min=stat,
        loaders=MappingProxyType({"L_N": loader}),
        crusher=crusher,
        edges=MappingProxyType({"E03_UP": edge}),
        top_bottlenecks=(bottleneck,),
    )


# ---------------------------------------------------------------------------
# results.csv
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_results_csv_columns_match_seed_schema() -> None:
    expected = (
        "scenario_id",
        "replication",
        "random_seed",
        "total_tonnes_delivered",
        "tonnes_per_hour",
        "average_truck_cycle_time_min",
        "average_truck_utilisation",
        "crusher_utilisation",
        "average_loader_queue_time_min",
        "average_crusher_queue_time_min",
    )
    assert RESULTS_CSV_COLUMNS == expected


@pytest.mark.unit
def test_replication_to_results_row_round_trips_metrics() -> None:
    rep = _make_replication(rep_idx=2)
    row = replication_to_results_row(rep)
    assert row["scenario_id"] == "baseline"
    assert row["replication"] == 2
    assert row["random_seed"] == 12347
    assert row["total_tonnes_delivered"] == 12002.0
    assert row["crusher_utilisation"] == 0.85


@pytest.mark.unit
def test_write_results_csv_sorts_and_emits_header(tmp_path: Path) -> None:
    reps = [_make_replication(rep_idx=2), _make_replication(rep_idx=0)]
    out = tmp_path / "results.csv"
    write_results_csv(reps, out)
    with out.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # Sorted by replication index ascending within the same scenario.
    assert [int(r["replication"]) for r in rows] == [0, 2]
    assert tuple(rows[0].keys()) == RESULTS_CSV_COLUMNS


# ---------------------------------------------------------------------------
# event_log.csv
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_write_event_log_csv_uses_event_csv_columns(tmp_path: Path) -> None:
    rep = _make_replication()
    out = tmp_path / "events.csv"
    write_event_log_csv(rep.events, out)
    with out.open("r", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 1
    assert tuple(rows[0].keys()) == EVENT_CSV_COLUMNS
    assert rows[0]["event_type"] == EVENT_DISPATCH


@pytest.mark.unit
def test_collect_events_concatenates_in_order() -> None:
    reps = [_make_replication(rep_idx=0), _make_replication(rep_idx=1)]
    events = collect_events(reps)
    assert len(events) == 2
    assert [e.replication for e in events] == [0, 1]


# ---------------------------------------------------------------------------
# summary.json
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_stat_to_dict_round_trips_to_floats() -> None:
    stat = StatSummary(mean=1.5, ci95_low=1.0, ci95_high=2.0, std=0.25, n=10)
    d = stat_to_dict(stat)
    assert d["mean"] == 1.5
    assert d["ci95_low"] == 1.0
    assert d["ci95_high"] == 2.0
    assert d["std"] == 0.25
    assert d["n"] == 10


@pytest.mark.unit
def test_scenario_summary_to_dict_includes_seed_required_fields() -> None:
    summary = _make_scenario_summary()
    d = scenario_summary_to_dict(summary)
    for required in (
        "scenario_id",
        "replications",
        "shift_length_hours",
        "total_tonnes_delivered",
        "tonnes_per_hour",
        "average_truck_cycle_time_min",
        "average_truck_utilisation",
        "crusher_utilisation",
        "average_loader_queue_time_min",
        "average_crusher_queue_time_min",
        "loaders",
        "crusher",
        "edges",
        "top_bottlenecks",
        "key_assumptions",
        "model_limitations",
        "additional_scenarios_proposed",
    ):
        assert required in d
    # Defaults populate the narrative fields.
    assert d["key_assumptions"] == list(DEFAULT_KEY_ASSUMPTIONS)


@pytest.mark.unit
def test_write_scenario_summary_json_creates_file(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "summary.json"
    summary = _make_scenario_summary("trucks_12")
    write_scenario_summary_json(summary, out)
    assert out.exists()
    with out.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert loaded["scenario_id"] == "trucks_12"


@pytest.mark.unit
def test_run_summary_to_dict_keys_by_scenario_id() -> None:
    summaries = MappingProxyType(
        {
            "baseline": _make_scenario_summary("baseline"),
            "trucks_4": _make_scenario_summary("trucks_4"),
        }
    )
    run_summary = RunSummary(scenarios=summaries)
    d = run_summary_to_dict(run_summary)
    assert set(d["scenarios"].keys()) == {"baseline", "trucks_4"}


@pytest.mark.unit
def test_run_summary_to_dict_includes_top_level_narrative() -> None:
    """``run_summary_to_dict`` must lift the narrative + benchmark_id to the top level.

    The recommended schema in :doc:`prompt.md` places ``benchmark_id``,
    ``key_assumptions``, ``model_limitations``, and
    ``additional_scenarios_proposed`` at the top of ``summary.json`` so
    an external grader can read the qualitative sections without
    descending into a per-scenario block. This test pins the contract.
    """
    summaries = MappingProxyType(
        {"baseline": _make_scenario_summary("baseline")}
    )
    run_summary = RunSummary(scenarios=summaries)
    d = run_summary_to_dict(run_summary)
    for required in RUN_SUMMARY_REQUIRED_KEYS:
        assert required in d, f"top-level key '{required}' missing from run_summary_to_dict output"
    assert d["benchmark_id"] == DEFAULT_BENCHMARK_ID
    assert d["key_assumptions"] == list(DEFAULT_KEY_ASSUMPTIONS)
    assert d["model_limitations"] == list(DEFAULT_MODEL_LIMITATIONS)
    assert d["additional_scenarios_proposed"] == list(
        DEFAULT_ADDITIONAL_SCENARIOS_PROPOSED
    )


@pytest.mark.unit
def test_run_summary_to_dict_accepts_overridden_narrative() -> None:
    """Narrative content is configurable per call (used by the README author)."""
    summaries = MappingProxyType(
        {"baseline": _make_scenario_summary("baseline")}
    )
    custom_assumptions = ("custom assumption A", "custom assumption B")
    custom_limitations = ("custom limitation",)
    custom_extras = ("custom proposed scenario",)
    d = run_summary_to_dict(
        RunSummary(scenarios=summaries),
        benchmark_id="custom_benchmark",
        key_assumptions=custom_assumptions,
        model_limitations=custom_limitations,
        additional_scenarios_proposed=custom_extras,
    )
    assert d["benchmark_id"] == "custom_benchmark"
    assert d["key_assumptions"] == list(custom_assumptions)
    # Per-scenario narrative is duplicated for self-contained per-scenario files.
    assert d["scenarios"]["baseline"]["key_assumptions"] == list(custom_assumptions)


@pytest.mark.unit
def test_default_narrative_constants_are_non_empty_strings() -> None:
    """Catch regressions that would emit empty narrative content."""
    for label, lst in (
        ("DEFAULT_KEY_ASSUMPTIONS", DEFAULT_KEY_ASSUMPTIONS),
        ("DEFAULT_MODEL_LIMITATIONS", DEFAULT_MODEL_LIMITATIONS),
        ("DEFAULT_ADDITIONAL_SCENARIOS_PROPOSED", DEFAULT_ADDITIONAL_SCENARIOS_PROPOSED),
    ):
        assert len(lst) >= 3, f"{label} should carry multiple entries"
        for idx, entry in enumerate(lst):
            assert isinstance(entry, str), f"{label}[{idx}] must be a string"
            assert entry.strip(), f"{label}[{idx}] must be non-empty"
    assert DEFAULT_BENCHMARK_ID == "001_synthetic_mine_throughput"


@pytest.mark.unit
def test_write_run_summary_json_writes_full_payload(tmp_path: Path) -> None:
    run_summary = RunSummary(
        scenarios=MappingProxyType(
            {"baseline": _make_scenario_summary("baseline")}
        )
    )
    out = tmp_path / "summary.json"
    write_run_summary_json(run_summary, out)
    with out.open("r", encoding="utf-8") as f:
        loaded = json.load(f)
    assert "scenarios" in loaded
    assert "baseline" in loaded["scenarios"]


# ---------------------------------------------------------------------------
# Bottleneck / edge / loader serialisation
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_bottleneck_to_dict_emits_composite_score() -> None:
    entry = BottleneckEntry(
        resource_id="E03_UP",
        resource_kind="edge",
        utilisation_mean=0.7,
        mean_queue_wait_min=1.5,
        composite_score=1.05,
    )
    d = bottleneck_to_dict(entry)
    assert d["resource_id"] == "E03_UP"
    assert d["resource_kind"] == "edge"
    assert d["composite_score"] == 1.05


@pytest.mark.unit
def test_loader_and_edge_dicts_are_well_formed() -> None:
    summary = _make_scenario_summary()
    loader_d = loader_summary_to_dict(summary.loaders["L_N"])
    edge_d = edge_summary_to_dict(summary.edges["E03_UP"])
    crusher_d = crusher_summary_to_dict(summary.crusher)

    for k in ("loader_id", "utilisation", "mean_queue_wait_min", "services_completed"):
        assert k in loader_d
    for k in (
        "edge_id",
        "utilisation",
        "mean_queue_wait_min",
        "mean_traversal_time_min",
        "traversal_count",
    ):
        assert k in edge_d
    for k in ("dump_id", "utilisation", "mean_queue_wait_min", "services_completed"):
        assert k in crusher_d


# ---------------------------------------------------------------------------
# Schema validation (Sub-AC 3)
# ---------------------------------------------------------------------------
def _build_valid_run_payload(
    *,
    scenario_ids: tuple[str, ...] = ("baseline", "trucks_4"),
    replications: int = 30,
    shift_length_hours: float = 8.0,
) -> dict:
    """Render a valid multi-scenario payload for validation tests."""
    summaries = MappingProxyType(
        {sid: _make_scenario_summary(sid) for sid in scenario_ids}
    )
    payload = run_summary_to_dict(RunSummary(scenarios=summaries))
    # Patch each scenario's replications / shift_length_hours so the
    # canonical-shape assertion succeeds without altering the helper.
    for sid in scenario_ids:
        payload["scenarios"][sid]["replications"] = replications
        payload["scenarios"][sid]["shift_length_hours"] = shift_length_hours
    return payload


@pytest.mark.unit
def test_validate_stat_summary_dict_accepts_valid_payload() -> None:
    payload = stat_to_dict(StatSummary(mean=1.0, ci95_low=0.9, ci95_high=1.1, std=0.05, n=30))
    # Returns ``None`` on success; no exception raised.
    assert validate_stat_summary_dict(payload, path="stat") is None


@pytest.mark.unit
def test_validate_stat_summary_dict_flags_missing_keys() -> None:
    payload = {"mean": 1.0, "ci95_low": 0.9, "ci95_high": 1.1}
    with pytest.raises(SchemaValidationError) as exc:
        validate_stat_summary_dict(payload, path="stat")
    assert "missing required key" in str(exc.value)
    assert exc.value.path == "stat"


@pytest.mark.unit
def test_validate_stat_summary_dict_rejects_nan_or_inf() -> None:
    payload = {"mean": float("nan"), "ci95_low": 0.0, "ci95_high": 0.0, "std": 0.0, "n": 1}
    with pytest.raises(SchemaValidationError) as exc:
        validate_stat_summary_dict(payload, path="stat")
    assert exc.value.path == "stat.mean"


@pytest.mark.unit
def test_validate_stat_summary_dict_rejects_negative_n() -> None:
    payload = {"mean": 1.0, "ci95_low": 1.0, "ci95_high": 1.0, "std": 0.0, "n": -1}
    with pytest.raises(SchemaValidationError) as exc:
        validate_stat_summary_dict(payload, path="stat")
    assert exc.value.path == "stat.n"


@pytest.mark.unit
def test_validate_scenario_summary_payload_accepts_default_render() -> None:
    summary = _make_scenario_summary()
    payload = scenario_summary_to_dict(summary)
    assert validate_scenario_summary_payload(payload, path="s") is None


@pytest.mark.unit
def test_validate_scenario_summary_payload_enforces_required_keys() -> None:
    summary = _make_scenario_summary()
    payload = scenario_summary_to_dict(summary)
    payload.pop("loaders")
    with pytest.raises(SchemaValidationError) as exc:
        validate_scenario_summary_payload(payload, path="s")
    assert "loaders" in str(exc.value)


@pytest.mark.unit
def test_validate_scenario_summary_payload_enforces_replications_match() -> None:
    summary = _make_scenario_summary()
    payload = scenario_summary_to_dict(summary)
    # _make_scenario_summary uses replications=2 — assert our 30-rep
    # contract is detected as a mismatch.
    with pytest.raises(SchemaValidationError) as exc:
        validate_scenario_summary_payload(
            payload, path="s", expected_replications=30
        )
    assert "expected 30" in str(exc.value)


@pytest.mark.unit
def test_validate_scenario_summary_payload_enforces_shift_length() -> None:
    summary = _make_scenario_summary()
    payload = scenario_summary_to_dict(summary)
    payload["shift_length_hours"] = 4.0
    with pytest.raises(SchemaValidationError) as exc:
        validate_scenario_summary_payload(
            payload, path="s", expected_shift_length_hours=8.0
        )
    assert "expected 8.0" in str(exc.value)


@pytest.mark.unit
def test_validate_scenario_summary_payload_requires_bottlenecks_by_default() -> None:
    summary = _make_scenario_summary()
    payload = scenario_summary_to_dict(summary)
    payload["top_bottlenecks"] = []
    with pytest.raises(SchemaValidationError) as exc:
        validate_scenario_summary_payload(payload, path="s")
    assert "top_bottlenecks" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_accepts_seven_scenarios() -> None:
    payload = _build_valid_run_payload(
        scenario_ids=(
            "baseline",
            "trucks_4",
            "trucks_12",
            "ramp_upgrade",
            "crusher_slowdown",
            "ramp_closed",
            "trucks_12_ramp_upgrade",
        ),
    )
    assert (
        validate_run_summary_payload(
            payload,
            expected_scenario_ids=(
                "baseline",
                "trucks_4",
                "trucks_12",
                "ramp_upgrade",
                "crusher_slowdown",
                "ramp_closed",
            ),
            expected_replications=30,
            expected_shift_length_hours=8.0,
        )
        is None
    )


@pytest.mark.unit
def test_validate_run_summary_payload_flags_missing_required_scenario() -> None:
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    with pytest.raises(SchemaValidationError) as exc:
        validate_run_summary_payload(
            payload,
            expected_scenario_ids=("baseline", "trucks_4"),
            expected_replications=30,
            expected_shift_length_hours=8.0,
        )
    assert "trucks_4" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_flags_keying_mismatch() -> None:
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    payload["scenarios"]["baseline"]["scenario_id"] = "wrong_id"
    with pytest.raises(SchemaValidationError) as exc:
        validate_run_summary_payload(
            payload, expected_replications=30, expected_shift_length_hours=8.0
        )
    assert "wrong_id" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_requires_top_level_narrative() -> None:
    """Top-level narrative + benchmark_id are mandatory by default."""
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    payload.pop("benchmark_id")
    with pytest.raises(SchemaValidationError) as exc:
        validate_run_summary_payload(
            payload,
            expected_replications=30,
            expected_shift_length_hours=8.0,
        )
    assert "benchmark_id" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_rejects_empty_narrative_lists() -> None:
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    payload["key_assumptions"] = []
    with pytest.raises(SchemaValidationError) as exc:
        validate_run_summary_payload(
            payload,
            expected_replications=30,
            expected_shift_length_hours=8.0,
        )
    assert "key_assumptions" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_rejects_blank_narrative_entries() -> None:
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    payload["model_limitations"] = ["valid limitation", "   "]
    with pytest.raises(SchemaValidationError) as exc:
        validate_run_summary_payload(
            payload,
            expected_replications=30,
            expected_shift_length_hours=8.0,
        )
    assert "model_limitations[1]" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_enforces_benchmark_id_match() -> None:
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    with pytest.raises(SchemaValidationError) as exc:
        validate_run_summary_payload(
            payload,
            expected_benchmark_id="some_other_benchmark",
            expected_replications=30,
            expected_shift_length_hours=8.0,
        )
    assert "benchmark_id" in str(exc.value)


@pytest.mark.unit
def test_validate_run_summary_payload_legacy_mode_accepts_pre_narrative_shape() -> None:
    """``require_top_level_narrative=False`` preserves backwards compatibility.

    A few internal call sites and tests still build payloads without the
    top-level narrative (e.g. older fixtures). Setting the flag allows
    them to keep validating without modification.
    """
    payload = _build_valid_run_payload(scenario_ids=("baseline",))
    for key in ("benchmark_id", "key_assumptions", "model_limitations", "additional_scenarios_proposed"):
        payload.pop(key, None)
    # Should not raise.
    assert (
        validate_run_summary_payload(
            payload,
            expected_replications=30,
            expected_shift_length_hours=8.0,
            require_top_level_narrative=False,
        )
        is None
    )


@pytest.mark.unit
def test_write_run_summary_json_validates_before_write_failure(
    tmp_path: Path,
) -> None:
    """If validation fails the file should NOT be created."""
    summary = RunSummary(
        scenarios=MappingProxyType({"baseline": _make_scenario_summary("baseline")})
    )
    out = tmp_path / "summary.json"
    with pytest.raises(SchemaValidationError):
        write_run_summary_json(
            summary,
            out,
            expected_replications=30,  # _make_scenario_summary uses 2
        )
    assert not out.exists(), (
        "Validation must run before file open so failed writes do not "
        "leave a half-formed artefact behind."
    )


@pytest.mark.unit
def test_write_scenario_summary_json_skips_validation_when_disabled(
    tmp_path: Path,
) -> None:
    summary = _make_scenario_summary("baseline")
    out = tmp_path / "summary.json"
    write_scenario_summary_json(
        summary,
        out,
        expected_replications=30,  # 2 != 30 — would normally raise
        validate=False,
    )
    assert out.exists()


@pytest.mark.unit
def test_required_keys_constants_match_seed_schema() -> None:
    # Catches accidental drift between the public constants and the
    # actually-rendered payload — a refactor that adds a new field
    # must update both this constant and any consumers.
    summary = _make_scenario_summary()
    payload = scenario_summary_to_dict(summary)
    assert set(SCENARIO_SUMMARY_REQUIRED_KEYS).issubset(payload.keys())
    stat_payload = stat_to_dict(
        StatSummary(mean=1.0, ci95_low=0.9, ci95_high=1.1, std=0.05, n=2)
    )
    assert set(STAT_SUMMARY_REQUIRED_KEYS) == set(stat_payload.keys())
