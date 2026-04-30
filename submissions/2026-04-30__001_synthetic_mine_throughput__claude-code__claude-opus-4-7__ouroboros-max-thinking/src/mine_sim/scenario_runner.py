"""Multi-replication, multi-scenario orchestration layer (AC 50202).

Where :mod:`mine_sim.runner` is the smallest public unit of work
(:func:`mine_sim.runner.run_replication` runs *one* shift), this module
sits one level up:

* :func:`run_scenario` runs all 30 replications for a single scenario,
  reusing the topology + routing computed once at the top of the loop.
* :func:`run_all_scenarios` walks a dict of ``ScenarioConfig`` objects
  and runs every scenario in turn, returning a flat collection of
  :class:`mine_sim.runner.ReplicationResult` records that downstream
  aggregation code (``results.csv``, ``summary.json``) consumes
  unchanged.

Design contracts (Seed-derived):

* Each replication uses ``random_seed = base_random_seed + replication_index``.
  The recipe lives in :mod:`mine_sim.rng`; this module just wires the
  index through.
* The seven required scenarios are exactly the IDs in
  :data:`mine_sim.scenarios.REQUIRED_SCENARIO_IDS`
  (``baseline``, ``trucks_4``, ``trucks_12``, ``ramp_upgrade``,
  ``crusher_slowdown``, ``ramp_closed``, ``trucks_12_ramp_upgrade``).
* Topology + routing are computed *once per scenario* and shared across
  reps. The reachability self-check therefore fires once per scenario
  (and fails loudly there).
* Replications run in deterministic order so the output sequence —
  written to ``results.csv`` and ``event_log.csv`` — is reproducible
  byte-for-byte across machines.

The orchestrator is intentionally pure-Python: no SimPy state crosses
scenario boundaries, no caches survive between calls, and the only
side-effects are an optional ``progress`` callback that the CLI uses
for stdout updates.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Callable, Iterable, Mapping, Sequence

from mine_sim.routing import RoutingTable, assert_reachable, compute_routes
from mine_sim.runner import ReplicationResult, run_replication
from mine_sim.scenarios import (
    REQUIRED_SCENARIO_IDS,
    ScenarioConfig,
    load_all_scenarios,
)
from mine_sim.topology import Topology, build_topology

# ---------------------------------------------------------------------------
# Progress callback signature
# ---------------------------------------------------------------------------
# Called once per (scenario, replication_index) immediately after the
# replication finishes. The CLI plugs in a stdout printer; tests can plug
# in a list-append to verify ordering.
ProgressCallback = Callable[["ReplicationProgress"], None]


@dataclass(frozen=True)
class ReplicationProgress:
    """Lightweight progress event emitted after each replication completes."""

    scenario_id: str
    scenario_index: int
    scenario_total: int
    replication_index: int
    replication_total: int
    result: ReplicationResult


# ---------------------------------------------------------------------------
# Per-scenario aggregate result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScenarioRunResult:
    """All replications for a single scenario, plus the shared topology.

    The topology and routing are exposed because aggregation code (e.g.
    bottleneck ranking) frequently needs the static graph — keeping a
    single shared reference avoids each consumer rebuilding it.
    """

    scenario: ScenarioConfig
    replications: tuple[ReplicationResult, ...]
    topology: Topology
    routing: RoutingTable

    @property
    def scenario_id(self) -> str:
        return self.scenario.scenario_id

    @property
    def replication_count(self) -> int:
        return len(self.replications)


# ---------------------------------------------------------------------------
# Multi-scenario aggregate result
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MultiScenarioRunResult:
    """Container returned by :func:`run_all_scenarios`.

    ``results`` preserves the iteration order requested by the caller so
    downstream CSV writers can rely on a deterministic row layout.
    """

    results: Mapping[str, ScenarioRunResult]

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(self.results.keys())

    def all_replications(self) -> tuple[ReplicationResult, ...]:
        """Flat tuple of every per-rep record across every scenario."""
        out: list[ReplicationResult] = []
        for scenario_result in self.results.values():
            out.extend(scenario_result.replications)
        return tuple(out)

    def total_replications(self) -> int:
        return sum(s.replication_count for s in self.results.values())


# ---------------------------------------------------------------------------
# Single-scenario orchestration
# ---------------------------------------------------------------------------
def _resolve_indices(
    scenario: ScenarioConfig,
    replication_indices: Sequence[int] | None,
) -> tuple[int, ...]:
    """Validate + freeze the replication index sequence."""
    if replication_indices is None:
        n = scenario.simulation.replications
        if n <= 0:
            raise ValueError(
                f"Scenario '{scenario.scenario_id}' requests {n} replications; "
                "must be a positive integer."
            )
        return tuple(range(n))
    indices = tuple(replication_indices)
    for idx in indices:
        if idx < 0:
            raise ValueError(
                f"Replication index must be >= 0, got {idx} for "
                f"scenario '{scenario.scenario_id}'."
            )
    return indices


def run_scenario(
    scenario: ScenarioConfig,
    data_dir: str | Path,
    *,
    replication_indices: Sequence[int] | None = None,
    progress: ProgressCallback | None = None,
    scenario_index: int = 0,
    scenario_total: int = 1,
) -> ScenarioRunResult:
    """Run every replication for a single scenario.

    Parameters
    ----------
    scenario:
        Resolved scenario configuration. Replication count and base seed
        come from ``scenario.simulation``.
    data_dir:
        Directory containing the input CSVs.
    replication_indices:
        Optional explicit sequence of replication indices to run. When
        ``None`` (the default), uses ``range(scenario.simulation.replications)``.
        Useful for resuming an interrupted run or for fast tests that
        only want a couple of replications.
    progress:
        Optional callback invoked after every replication. Receives a
        :class:`ReplicationProgress` record carrying the freshly produced
        :class:`ReplicationResult`.
    scenario_index, scenario_total:
        Positional metadata so progress callbacks can render
        ``scenario 3 of 7`` without the orchestrator owning the loop.

    Returns
    -------
    ScenarioRunResult:
        Frozen aggregate carrying every per-rep result for this scenario.
    """
    indices = _resolve_indices(scenario, replication_indices)

    # Topology + routing are computed exactly once per scenario; the
    # reachability self-check therefore raises before we start the
    # (potentially slow) 30-replication loop.
    topology = build_topology(data_dir, scenario)
    routing = compute_routes(topology)
    assert_reachable(routing, scenario_id=scenario.scenario_id)

    results: list[ReplicationResult] = []
    total = len(indices)
    for rep_idx in indices:
        result = run_replication(
            scenario=scenario,
            data_dir=data_dir,
            replication_index=rep_idx,
            topology=topology,
            routing=routing,
        )
        results.append(result)
        if progress is not None:
            progress(
                ReplicationProgress(
                    scenario_id=scenario.scenario_id,
                    scenario_index=scenario_index,
                    scenario_total=scenario_total,
                    replication_index=rep_idx,
                    replication_total=total,
                    result=result,
                )
            )

    return ScenarioRunResult(
        scenario=scenario,
        replications=tuple(results),
        topology=topology,
        routing=routing,
    )


# ---------------------------------------------------------------------------
# Multi-scenario orchestration
# ---------------------------------------------------------------------------
def _coerce_scenarios(
    scenarios: Mapping[str, ScenarioConfig] | Iterable[ScenarioConfig],
    scenario_ids: Sequence[str] | None,
) -> tuple[tuple[str, ScenarioConfig], ...]:
    """Resolve the input collection into a deterministic ordered list.

    Accepts both a ``dict[str, ScenarioConfig]`` (the natural output of
    :func:`load_all_scenarios`) and a plain iterable of configs. When
    ``scenario_ids`` is supplied it acts as both a filter and an
    ordering directive.
    """
    if isinstance(scenarios, Mapping):
        scenario_map = dict(scenarios)
    else:
        scenario_map = {}
        for cfg in scenarios:
            if cfg.scenario_id in scenario_map:
                raise ValueError(
                    f"Duplicate scenario_id '{cfg.scenario_id}' in input list"
                )
            scenario_map[cfg.scenario_id] = cfg

    if scenario_ids is not None:
        missing = [sid for sid in scenario_ids if sid not in scenario_map]
        if missing:
            raise KeyError(
                f"Requested scenario_ids not found in input: {missing}. "
                f"Available: {sorted(scenario_map)}"
            )
        ordered = [(sid, scenario_map[sid]) for sid in scenario_ids]
    else:
        ordered = list(scenario_map.items())

    if not ordered:
        raise ValueError("No scenarios provided to run.")
    return tuple(ordered)


def run_all_scenarios(
    scenarios: Mapping[str, ScenarioConfig] | Iterable[ScenarioConfig],
    data_dir: str | Path,
    *,
    scenario_ids: Sequence[str] | None = None,
    replication_indices: Sequence[int] | None = None,
    progress: ProgressCallback | None = None,
) -> MultiScenarioRunResult:
    """Run every replication for every scenario in deterministic order.

    Parameters
    ----------
    scenarios:
        Either a dict (``scenario_id -> ScenarioConfig``) or a plain
        iterable of :class:`ScenarioConfig` records. The natural source
        is :func:`mine_sim.scenarios.load_all_scenarios`.
    data_dir:
        Directory containing the input CSVs.
    scenario_ids:
        Optional ordered subset of scenario IDs to run. When ``None``,
        runs every scenario in the input collection in its natural
        order. When supplied, doubles as both a filter (only run these)
        and an ordering directive.
    replication_indices:
        Optional shared replication index sequence. Useful for "smoke
        tests run only rep 0 across every scenario" workflows. When
        ``None``, each scenario uses its own ``simulation.replications``.
    progress:
        Optional :class:`ReplicationProgress` callback (see
        :func:`run_scenario`).
    """
    ordered = _coerce_scenarios(scenarios, scenario_ids)

    out: dict[str, ScenarioRunResult] = {}
    total_scenarios = len(ordered)
    for scenario_index, (scenario_id, scenario) in enumerate(ordered):
        if scenario_id in out:
            # Defensive — _coerce_scenarios already deduplicates, but
            # belt-and-braces to catch future refactors.
            raise ValueError(
                f"Scenario '{scenario_id}' appeared twice during run_all_scenarios"
            )
        out[scenario_id] = run_scenario(
            scenario=scenario,
            data_dir=data_dir,
            replication_indices=replication_indices,
            progress=progress,
            scenario_index=scenario_index,
            scenario_total=total_scenarios,
        )

    return MultiScenarioRunResult(results=MappingProxyType(out))


def run_required_scenarios(
    scenarios_dir: str | Path,
    data_dir: str | Path,
    *,
    required: Sequence[str] = REQUIRED_SCENARIO_IDS,
    replication_indices: Sequence[int] | None = None,
    progress: ProgressCallback | None = None,
) -> MultiScenarioRunResult:
    """Convenience wrapper: load every required scenario YAML then run them.

    This is the entry point the CLI's ``run-all`` command uses. It:

    1. Loads every scenario YAML from ``scenarios_dir`` (failing loudly
       if any of the seven required IDs is missing).
    2. Filters / orders the resulting dict by the supplied ``required``
       sequence (default: the canonical seven).
    3. Delegates to :func:`run_all_scenarios`.
    """
    all_scenarios = load_all_scenarios(scenarios_dir, required=tuple(required))
    return run_all_scenarios(
        all_scenarios,
        data_dir=data_dir,
        scenario_ids=tuple(required),
        replication_indices=replication_indices,
        progress=progress,
    )


__all__ = [
    "MultiScenarioRunResult",
    "ProgressCallback",
    "ReplicationProgress",
    "ScenarioRunResult",
    "run_all_scenarios",
    "run_required_scenarios",
    "run_scenario",
]
