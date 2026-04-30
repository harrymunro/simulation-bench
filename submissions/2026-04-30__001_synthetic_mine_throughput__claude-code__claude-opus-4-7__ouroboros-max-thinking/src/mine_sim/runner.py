"""Single-replication entry point for the mine throughput simulation.

This module exposes :func:`run_replication`, the smallest public unit of
work the rest of the system orchestrates. Given a scenario config, the
simulation data directory, and a replication index, it:

1. Loads the scenario-resolved :class:`mine_sim.topology.Topology` from
   the input CSVs.
2. Computes the static shortest-time :class:`mine_sim.routing.RoutingTable`
   and runs the reachability self-check (fails loudly on missing OD pairs).
3. Builds an independent :class:`mine_sim.rng.ReplicationRNG` whose seed
   is ``base_random_seed + replication_index``.
4. Constructs a :class:`mine_sim.model.MineSimulation`, runs the SimPy
   environment until the shift cut, and finalises the metrics.
5. Returns a :class:`ReplicationResult` carrying the immutable
   :class:`mine_sim.metrics.ReplicationMetrics` plus the captured event
   log.

The function is deterministic for a given ``(scenario, replication_index)``
pair: identical inputs always produce identical metric and event outputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from mine_sim.events import EventRecord
from mine_sim.metrics import MetricsRecorder, ReplicationMetrics
from mine_sim.model import MineSimulation
from mine_sim.rng import make_replication_rng
from mine_sim.routing import RoutingTable, assert_reachable, compute_routes
from mine_sim.scenarios import ScenarioConfig
from mine_sim.topology import Topology, build_topology

# ---------------------------------------------------------------------------
# Result dataclass returned to callers (aggregator, CLI, tests).
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReplicationResult:
    """Output of one simulation replication.

    The ``metrics`` field carries the per-rep KPIs (frozen), and ``events``
    is the captured event log as an immutable tuple. Both can be serialised
    to ``results.csv`` / ``event_log.csv`` by upstream tooling.
    """

    metrics: ReplicationMetrics
    events: tuple[EventRecord, ...]
    topology: Topology
    routing: RoutingTable


# ---------------------------------------------------------------------------
# Default payload fallback — only used if trucks.csv is empty (which would
# itself be a bug). Kept here so the value never silently leaks into a
# scenario.
# ---------------------------------------------------------------------------
_DEFAULT_PAYLOAD_TONNES = 100.0


def _resolve_payload_tonnes(topology: Topology) -> float:
    """All trucks share the same payload by spec; assert and return it."""
    if not topology.trucks:
        return _DEFAULT_PAYLOAD_TONNES
    payloads = {truck.payload_tonnes for truck in topology.trucks}
    if len(payloads) != 1:
        raise ValueError(
            "Heterogeneous payloads detected; the current model assumes a "
            f"single payload value but got {sorted(payloads)}"
        )
    return float(next(iter(payloads)))


def _capacity_edge_ids(topology: Topology) -> tuple[str, ...]:
    """Stable, sorted tuple of capacity-1 edge IDs (deterministic order)."""
    return tuple(sorted(topology.capacity_constrained_edges()))


def _crusher_dump_id(topology: Topology) -> str:
    for dump in topology.dump_points.values():
        if dump.type == "crusher":
            return dump.dump_id
    raise RuntimeError("No crusher dump point found in topology")


def _truck_ids(topology: Topology) -> tuple[str, ...]:
    return tuple(truck.truck_id for truck in topology.trucks)


def _loader_ids(topology: Topology) -> tuple[str, ...]:
    return tuple(sorted(topology.loaders))


def run_replication(
    scenario: ScenarioConfig,
    data_dir: str | Path,
    replication_index: int,
    *,
    topology: Topology | None = None,
    routing: RoutingTable | None = None,
) -> ReplicationResult:
    """Execute one simulation replication and return KPIs + event log.

    Parameters
    ----------
    scenario:
        Scenario configuration loaded from YAML (already resolved).
    data_dir:
        Directory containing the input CSVs (``nodes.csv``, ``edges.csv``,
        ``trucks.csv``, ``loaders.csv``, ``dump_points.csv``).
    replication_index:
        Zero-based replication number. Per-rep seed is ``base_seed + idx``.
    topology, routing:
        Optional precomputed objects. Passing them skips re-loading the
        CSVs / re-running Dijkstra. The aggregator uses this hot path so a
        scenario only pays the topology cost once across 30 replications.

    Returns
    -------
    ReplicationResult:
        Frozen result bundle containing per-rep metrics and the event log.
    """
    if replication_index < 0:
        raise ValueError(
            f"replication_index must be >= 0, got {replication_index}"
        )

    if topology is None:
        topology = build_topology(data_dir, scenario)
    if routing is None:
        routing = compute_routes(topology)
        assert_reachable(routing, scenario_id=scenario.scenario_id)

    rng = make_replication_rng(
        base_seed=scenario.simulation.base_random_seed,
        replication_index=replication_index,
    )

    recorder = MetricsRecorder(
        scenario_id=scenario.scenario_id,
        replication_index=replication_index,
        random_seed=rng.seed,
        shift_length_min=scenario.simulation.shift_length_minutes,
        payload_tonnes=_resolve_payload_tonnes(topology),
        truck_ids=_truck_ids(topology),
        loader_ids=_loader_ids(topology),
        crusher_id=_crusher_dump_id(topology),
        capacity_edge_ids=_capacity_edge_ids(topology),
    )

    sim = MineSimulation(
        scenario=scenario,
        topology=topology,
        routes=routing,
        rng=rng,
        recorder=recorder,
    )
    sim.run()

    metrics = recorder.finalise()
    return ReplicationResult(
        metrics=metrics,
        events=tuple(sim.events),
        topology=topology,
        routing=routing,
    )


def run_replications(
    scenario: ScenarioConfig,
    data_dir: str | Path,
    replication_indices: Iterable[int] | None = None,
) -> list[ReplicationResult]:
    """Run a sequence of replications for the same scenario.

    Topology and routing are computed *once* and shared across reps for
    efficiency. The reachability self-check therefore runs exactly once
    per scenario, which is the desired Seed contract behaviour.
    """
    topology = build_topology(data_dir, scenario)
    routing = compute_routes(topology)
    assert_reachable(routing, scenario_id=scenario.scenario_id)

    indices = (
        list(replication_indices)
        if replication_indices is not None
        else list(range(scenario.simulation.replications))
    )
    return [
        run_replication(
            scenario=scenario,
            data_dir=data_dir,
            replication_index=idx,
            topology=topology,
            routing=routing,
        )
        for idx in indices
    ]


__all__ = [
    "ReplicationResult",
    "run_replication",
    "run_replications",
]
