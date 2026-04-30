"""Per-replication metric accumulator and result dataclasses.

The simulation calls into :class:`MetricsRecorder` while it runs, then
asks for an immutable :class:`ReplicationMetrics` snapshot at the hard
shift cut. Aggregating across replications happens elsewhere; this
module is intentionally side-effect-free between calls.

Performance measures we track per replication, lifted directly from the
Seed contract and ``conceptual_model.md`` section 5:

* ``total_tonnes_delivered`` — payload * count(end_dump events at CRUSH
  with time_min < shift_length).
* ``tonnes_per_hour`` — total_tonnes_delivered / shift_length_hours.
* ``average_truck_cycle_time_min`` — mean of completed cycle durations.
  The first cycle uses ``dispatch -> end_dump``; subsequent cycles use
  ``end_dump -> end_dump``.
* ``average_truck_utilisation`` — mean across trucks of
  ``productive_busy_time / shift_length_min``.
* ``crusher_utilisation`` — D_CRUSH busy_time / shift_length_min.
* ``loader_utilisation`` per loader — busy_time / shift_length_min.
* ``average_loader_queue_time_min`` / ``average_crusher_queue_time_min``
  — mean wait per service event.
* ``edge_metrics`` — for every capacity-1 edge: utilisation, mean
  wait, mean traversal time, count, total wait time.

We deliberately do *not* compute confidence intervals here. CI math is a
cross-replication concern handled by ``aggregate.py`` (a later sub-AC).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping


# ---------------------------------------------------------------------------
# Per-truck running counters used during the simulation. Mutable internally
# but converted to a frozen snapshot when the rep ends.
# ---------------------------------------------------------------------------
class _TruckCounter:
    """Mutable per-truck accumulator (internal helper)."""

    __slots__ = (
        "truck_id",
        "productive_busy_time",
        "completed_cycle_count",
        "completed_cycle_total_min",
        "last_cycle_anchor",
    )

    def __init__(self, truck_id: str) -> None:
        self.truck_id: str = truck_id
        self.productive_busy_time: float = 0.0
        self.completed_cycle_count: int = 0
        self.completed_cycle_total_min: float = 0.0
        # Time of the last "cycle anchor" — initially the dispatch time
        # (set by the recorder), then updated to each end_dump.
        self.last_cycle_anchor: float | None = None


# ---------------------------------------------------------------------------
# Per-resource running counters.
# ---------------------------------------------------------------------------
class _ResourceCounter:
    """Mutable per-resource accumulator (internal helper)."""

    __slots__ = (
        "resource_id",
        "busy_time",
        "wait_time_total",
        "service_count",
        "traversal_count",
    )

    def __init__(self, resource_id: str) -> None:
        self.resource_id: str = resource_id
        self.busy_time: float = 0.0
        self.wait_time_total: float = 0.0
        self.service_count: int = 0
        self.traversal_count: int = 0


# ---------------------------------------------------------------------------
# Public, immutable result dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EdgeMetrics:
    """Per capacity-1 edge KPIs at end-of-shift."""

    edge_id: str
    utilisation: float
    mean_queue_wait_min: float
    mean_traversal_time_min: float
    traversal_count: int
    total_wait_time_min: float


@dataclass(frozen=True)
class LoaderMetrics:
    """Per loader KPIs at end-of-shift."""

    loader_id: str
    utilisation: float
    mean_queue_wait_min: float
    services_completed: int


@dataclass(frozen=True)
class CrusherMetrics:
    """Per crusher KPIs at end-of-shift."""

    dump_id: str
    utilisation: float
    mean_queue_wait_min: float
    services_completed: int


@dataclass(frozen=True)
class ReplicationMetrics:
    """Immutable snapshot of one rep's KPIs.

    The runner returns this object; aggregation across reps walks a list
    of these and computes Student-t CIs.
    """

    scenario_id: str
    replication_index: int
    random_seed: int
    shift_length_min: float
    truck_count: int

    total_tonnes_delivered: float
    tonnes_per_hour: float
    average_truck_cycle_time_min: float
    average_truck_utilisation: float

    crusher: CrusherMetrics
    loaders: Mapping[str, LoaderMetrics]
    edges: Mapping[str, EdgeMetrics]

    average_loader_queue_time_min: float
    average_crusher_queue_time_min: float

    completed_dumps: int


# ---------------------------------------------------------------------------
# Recorder — the live object the simulation writes into
# ---------------------------------------------------------------------------
@dataclass
class MetricsRecorder:
    """Mutable recorder used during a single replication.

    Construct via :func:`make_recorder`. The simulation calls the
    ``record_*`` methods; at end-of-shift the runner calls
    :meth:`finalise` to obtain a :class:`ReplicationMetrics` snapshot.

    Not thread-safe — but SimPy runs on a single greenlet-style scheduler,
    so that is fine.
    """

    scenario_id: str
    replication_index: int
    random_seed: int
    shift_length_min: float
    payload_tonnes: float

    truck_ids: tuple[str, ...]
    loader_ids: tuple[str, ...]
    crusher_id: str
    capacity_edge_ids: tuple[str, ...]

    # Internal state
    _trucks: dict[str, _TruckCounter] = field(default_factory=dict, init=False)
    _loaders: dict[str, _ResourceCounter] = field(default_factory=dict, init=False)
    _crusher: _ResourceCounter | None = field(default=None, init=False)
    _edges: dict[str, _ResourceCounter] = field(default_factory=dict, init=False)

    completed_dumps: int = field(default=0, init=False)
    edge_traversal_total_min: dict[str, float] = field(default_factory=dict, init=False)

    def __post_init__(self) -> None:
        for tid in self.truck_ids:
            self._trucks[tid] = _TruckCounter(tid)
        for lid in self.loader_ids:
            self._loaders[lid] = _ResourceCounter(lid)
        self._crusher = _ResourceCounter(self.crusher_id)
        for eid in self.capacity_edge_ids:
            self._edges[eid] = _ResourceCounter(eid)
            self.edge_traversal_total_min[eid] = 0.0

    # ------------------------------------------------------------------
    # Truck-level updates
    # ------------------------------------------------------------------
    def record_dispatch(self, truck_id: str, time_min: float) -> None:
        truck = self._trucks[truck_id]
        truck.last_cycle_anchor = time_min

    def add_productive_time(self, truck_id: str, duration_min: float) -> None:
        if duration_min <= 0:
            return
        self._trucks[truck_id].productive_busy_time += duration_min

    def record_cycle_end(self, truck_id: str, time_min: float) -> None:
        """Called at every ``end_dump`` event before the post-shift cut.

        The Seed defines the first cycle as ``dispatch -> end_dump`` and
        every subsequent cycle as ``end_dump -> end_dump``. We use
        ``last_cycle_anchor`` for the start of the current cycle and reset
        it to the current ``end_dump`` time afterwards.
        """
        truck = self._trucks[truck_id]
        anchor = truck.last_cycle_anchor
        if anchor is None:
            return
        duration = time_min - anchor
        if duration > 0:
            truck.completed_cycle_count += 1
            truck.completed_cycle_total_min += duration
        truck.last_cycle_anchor = time_min

    # ------------------------------------------------------------------
    # Resource-level updates
    # ------------------------------------------------------------------
    def record_loader_service(
        self,
        loader_id: str,
        wait_time_min: float,
        service_time_min: float,
    ) -> None:
        counter = self._loaders[loader_id]
        counter.service_count += 1
        counter.wait_time_total += max(0.0, wait_time_min)
        counter.busy_time += max(0.0, service_time_min)

    def record_crusher_service(
        self,
        wait_time_min: float,
        service_time_min: float,
    ) -> None:
        assert self._crusher is not None
        self._crusher.service_count += 1
        self._crusher.wait_time_total += max(0.0, wait_time_min)
        self._crusher.busy_time += max(0.0, service_time_min)

    def record_completed_dump(self, time_min: float, truck_id: str) -> None:
        """Credit one closed dump (only call when ``time_min < shift_length``)."""
        if time_min >= self.shift_length_min:
            return
        self.completed_dumps += 1

    def record_edge_traversal(
        self,
        edge_id: str,
        wait_time_min: float,
        traversal_time_min: float,
    ) -> None:
        counter = self._edges.get(edge_id)
        if counter is None:
            return
        counter.traversal_count += 1
        counter.wait_time_total += max(0.0, wait_time_min)
        counter.busy_time += max(0.0, traversal_time_min)
        self.edge_traversal_total_min[edge_id] += max(0.0, traversal_time_min)

    # ------------------------------------------------------------------
    # Snapshot
    # ------------------------------------------------------------------
    def finalise(self) -> ReplicationMetrics:
        shift_min = self.shift_length_min
        shift_hours = shift_min / 60.0 if shift_min > 0 else 1.0

        total_tonnes = self.completed_dumps * self.payload_tonnes
        tonnes_per_hour = total_tonnes / shift_hours

        # Truck cycle / utilisation -------------------------------------------
        cycle_totals: list[float] = []
        cycle_counts: list[int] = []
        utilisations: list[float] = []
        for truck in self._trucks.values():
            if truck.completed_cycle_count > 0:
                cycle_totals.append(truck.completed_cycle_total_min)
                cycle_counts.append(truck.completed_cycle_count)
            if shift_min > 0:
                utilisations.append(min(1.0, truck.productive_busy_time / shift_min))

        if sum(cycle_counts) > 0:
            avg_cycle_time = sum(cycle_totals) / sum(cycle_counts)
        else:
            avg_cycle_time = 0.0
        avg_utilisation = (
            sum(utilisations) / len(utilisations) if utilisations else 0.0
        )

        # Loader / crusher metrics --------------------------------------------
        loader_metrics: dict[str, LoaderMetrics] = {}
        loader_wait_totals: list[float] = []
        loader_service_counts: list[int] = []
        for loader_id, counter in self._loaders.items():
            mean_wait = (
                counter.wait_time_total / counter.service_count
                if counter.service_count
                else 0.0
            )
            utilisation = (
                min(1.0, counter.busy_time / shift_min) if shift_min > 0 else 0.0
            )
            loader_metrics[loader_id] = LoaderMetrics(
                loader_id=loader_id,
                utilisation=utilisation,
                mean_queue_wait_min=mean_wait,
                services_completed=counter.service_count,
            )
            loader_wait_totals.append(counter.wait_time_total)
            loader_service_counts.append(counter.service_count)

        total_loader_services = sum(loader_service_counts)
        avg_loader_queue = (
            sum(loader_wait_totals) / total_loader_services
            if total_loader_services
            else 0.0
        )

        assert self._crusher is not None
        crusher_mean_wait = (
            self._crusher.wait_time_total / self._crusher.service_count
            if self._crusher.service_count
            else 0.0
        )
        crusher_metrics = CrusherMetrics(
            dump_id=self.crusher_id,
            utilisation=(
                min(1.0, self._crusher.busy_time / shift_min)
                if shift_min > 0
                else 0.0
            ),
            mean_queue_wait_min=crusher_mean_wait,
            services_completed=self._crusher.service_count,
        )

        # Edge metrics --------------------------------------------------------
        edge_metrics: dict[str, EdgeMetrics] = {}
        for edge_id, counter in self._edges.items():
            mean_wait = (
                counter.wait_time_total / counter.traversal_count
                if counter.traversal_count
                else 0.0
            )
            mean_traversal = (
                self.edge_traversal_total_min[edge_id] / counter.traversal_count
                if counter.traversal_count
                else 0.0
            )
            utilisation = (
                min(1.0, counter.busy_time / shift_min) if shift_min > 0 else 0.0
            )
            edge_metrics[edge_id] = EdgeMetrics(
                edge_id=edge_id,
                utilisation=utilisation,
                mean_queue_wait_min=mean_wait,
                mean_traversal_time_min=mean_traversal,
                traversal_count=counter.traversal_count,
                total_wait_time_min=counter.wait_time_total,
            )

        return ReplicationMetrics(
            scenario_id=self.scenario_id,
            replication_index=self.replication_index,
            random_seed=self.random_seed,
            shift_length_min=shift_min,
            truck_count=len(self.truck_ids),
            total_tonnes_delivered=total_tonnes,
            tonnes_per_hour=tonnes_per_hour,
            average_truck_cycle_time_min=avg_cycle_time,
            average_truck_utilisation=avg_utilisation,
            crusher=crusher_metrics,
            loaders=MappingProxyType(loader_metrics),
            edges=MappingProxyType(edge_metrics),
            average_loader_queue_time_min=avg_loader_queue,
            average_crusher_queue_time_min=crusher_mean_wait,
            completed_dumps=self.completed_dumps,
        )


__all__ = [
    "CrusherMetrics",
    "EdgeMetrics",
    "LoaderMetrics",
    "MetricsRecorder",
    "ReplicationMetrics",
]
