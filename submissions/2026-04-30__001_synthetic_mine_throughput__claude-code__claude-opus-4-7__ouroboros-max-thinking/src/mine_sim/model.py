"""SimPy discrete-event model of the synthetic mine ore haulage system.

This module is the *active* simulation. It:

1. Spawns one SimPy process per truck.
2. Implements the ore cycle: PARK -> chosen LOAD -> CRUSH -> next LOAD ...
3. Acquires SimPy ``Resource`` slots for loaders, the crusher, and every
   capacity-1 edge — the rest of the graph is modelled as a plain ``timeout``.
4. Pushes events into a list of :class:`mine_sim.events.EventRecord` and
   per-replication counters into a :class:`mine_sim.metrics.MetricsRecorder`.

Design contracts (Seed-derived):

* All trucks are released simultaneously at ``t = 0``.
* Dispatch policy: ``argmin(travel_to_loader + queue_len * mean_load_time
  + own_load_time)``. ``queue_len`` includes the truck currently in service.
* Travel time on an edge is ``free_flow_time / speed_factor *
  lognormal(cv=0.10)``; ``empty_speed_factor`` for empty trucks,
  ``loaded_speed_factor`` for loaded trucks.
* Loading and dumping draws come from ``truncated_normal(mean, sd, 0.1)``.
* ``end_dump`` events that occur strictly before ``shift_length_min`` are
  the only ones that count toward throughput (hard cut).
* Per-replication seed = ``base_seed + replication_index`` (handled in
  :mod:`mine_sim.rng`).

The module deliberately keeps "shapes" small: ``MineSimulation`` is a thin
SimPy host; the real logic lives in functional helpers and the
:class:`MetricsRecorder` so it can be unit-tested without spinning up
SimPy.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import numpy as np
import simpy

from mine_sim.events import (
    EVENT_ARRIVE_CRUSHER,
    EVENT_ARRIVE_LOADER,
    EVENT_DEPART_CRUSHER,
    EVENT_DEPART_LOADER,
    EVENT_DISPATCH,
    EVENT_EDGE_ENTER,
    EVENT_EDGE_LEAVE,
    EVENT_END_DUMP,
    EVENT_END_LOAD,
    EVENT_START_DUMP,
    EVENT_START_LOAD,
    EventRecord,
)
from mine_sim.metrics import MetricsRecorder
from mine_sim.rng import (
    ReplicationRNG,
    lognormal_noise_multiplier,
    truncated_normal,
)
from mine_sim.routing import RoutingTable
from mine_sim.scenarios import ScenarioConfig
from mine_sim.topology import EdgeView, LoaderSpec, Topology, TruckSpec

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
@dataclass
class _LoaderHandle:
    """Bundle a loader's SimPy ``Resource`` with its static spec."""

    spec: LoaderSpec
    resource: simpy.Resource


@dataclass
class _EdgeHandle:
    """SimPy ``Resource`` for a capacity-1 edge."""

    edge: EdgeView
    resource: simpy.Resource


@dataclass
class _CrusherHandle:
    dump_id: str
    mean_dump_time_min: float
    sd_dump_time_min: float
    resource: simpy.Resource


def _stochastic_edge_time_min(
    edge: EdgeView,
    speed_factor: float,
    travel_noise_cv: float,
    rng: np.random.Generator,
) -> float:
    """Sampled traversal time for a single edge.

    ``free_flow_time`` is multiplied by ``1 / speed_factor`` (truck class)
    and by an independent lognormal noise multiplier with mean 1.

    Closed edges should not appear in any precomputed route, but as a
    safety we still raise so a routing bug surfaces immediately.
    """
    if edge.closed:
        raise RuntimeError(f"Cannot traverse closed edge {edge.edge_id}")
    base = edge.free_flow_time_min
    if base == float("inf"):
        raise RuntimeError(f"Edge {edge.edge_id} has infinite free-flow time")
    if speed_factor <= 0:
        raise ValueError(f"speed_factor must be > 0, got {speed_factor}")
    multiplier = lognormal_noise_multiplier(rng, cv=travel_noise_cv)
    return (base / speed_factor) * multiplier


# ---------------------------------------------------------------------------
# Main simulation host
# ---------------------------------------------------------------------------
@dataclass
class MineSimulation:
    """Wires SimPy together for one replication.

    The class is *not* itself a SimPy process; it owns the environment,
    resources, RNG bundle, recorder, and event list, and exposes one
    truck-process method ``run_truck`` that the constructor schedules.

    Use :func:`run_replication` (in :mod:`mine_sim.runner`) as the public
    entry point — it instantiates this class, runs the env, and finalises
    metrics.
    """

    scenario: ScenarioConfig
    topology: Topology
    routes: RoutingTable
    rng: ReplicationRNG
    recorder: MetricsRecorder
    events: list[EventRecord] = field(default_factory=list)

    # Filled in by ``_build_resources``
    env: simpy.Environment = field(init=False)
    loaders: dict[str, _LoaderHandle] = field(default_factory=dict, init=False)
    edge_resources: dict[str, _EdgeHandle] = field(default_factory=dict, init=False)
    crusher: _CrusherHandle = field(init=False)

    def __post_init__(self) -> None:
        self.env = simpy.Environment()
        self._build_resources()
        self._schedule_trucks()

    # ------------------------------------------------------------------
    # Wiring
    # ------------------------------------------------------------------
    def _build_resources(self) -> None:
        # Loaders
        for loader in self.topology.loaders.values():
            # Skip loaders that aren't ore loaders (defensive, matches CSV).
            self.loaders[loader.loader_id] = _LoaderHandle(
                spec=loader,
                resource=simpy.Resource(self.env, capacity=loader.capacity),
            )

        # Crusher (D_CRUSH only — WASTE is out-of-scope)
        crusher_spec = next(
            (
                d
                for d in self.topology.dump_points.values()
                if d.type == "crusher"
            ),
            None,
        )
        if crusher_spec is None:
            raise RuntimeError("Topology has no dump_point of type 'crusher'")
        self.crusher = _CrusherHandle(
            dump_id=crusher_spec.dump_id,
            mean_dump_time_min=crusher_spec.mean_dump_time_min,
            sd_dump_time_min=crusher_spec.sd_dump_time_min,
            resource=simpy.Resource(self.env, capacity=crusher_spec.capacity),
        )

        # Capacity-1 edge resources
        for edge_id in self.topology.capacity_constrained_edges():
            edge = self.topology.edges[edge_id]
            self.edge_resources[edge_id] = _EdgeHandle(
                edge=edge,
                resource=simpy.Resource(self.env, capacity=max(1, edge.capacity)),
            )

    def _schedule_trucks(self) -> None:
        for truck in self.topology.trucks:
            self.env.process(self._truck_process(truck))

    # ------------------------------------------------------------------
    # Event helpers
    # ------------------------------------------------------------------
    def _emit(
        self,
        truck_id: str,
        event_type: str,
        *,
        from_node: str | None = None,
        to_node: str | None = None,
        location: str | None = None,
        loaded: bool | None = None,
        payload_tonnes: float | None = None,
        resource_id: str | None = None,
        queue_length: int | None = None,
    ) -> None:
        self.events.append(
            EventRecord(
                time_min=float(self.env.now),
                replication=self.recorder.replication_index,
                scenario_id=self.scenario.scenario_id,
                truck_id=truck_id,
                event_type=event_type,
                from_node=from_node,
                to_node=to_node,
                location=location,
                loaded=loaded,
                payload_tonnes=payload_tonnes,
                resource_id=resource_id,
                queue_length=queue_length,
            )
        )

    # ------------------------------------------------------------------
    # Dispatch helper
    # ------------------------------------------------------------------
    def _choose_loader(
        self,
        origin: str,
        speed_factor: float,
    ) -> _LoaderHandle:
        """Apply the dispatch policy: argmin over loaders.

        Cost = travel_to_loader + queue_len * mean_load_time + own_load_time.

        ``travel_to_loader`` uses the precomputed free-flow route time
        scaled by the truck's empty ``speed_factor``. ``queue_len`` is the
        live SimPy resource count + queue length (i.e. includes the truck
        currently being served). Ties are broken by lower loader id.
        """
        best: _LoaderHandle | None = None
        best_cost = float("inf")
        # Sort to make ties deterministic.
        for loader_id in sorted(self.loaders):
            handle = self.loaders[loader_id]
            route = self.routes.get(origin, handle.spec.node_id)
            if route is None:
                continue
            travel_min = route.free_flow_time_min / max(speed_factor, 1e-9)
            queue_len = handle.resource.count + len(handle.resource.queue)
            cost = (
                travel_min
                + queue_len * handle.spec.mean_load_time_min
                + handle.spec.mean_load_time_min
            )
            if cost < best_cost:
                best = handle
                best_cost = cost
        if best is None:
            raise RuntimeError(
                f"No reachable loader from {origin} — reachability check broken?"
            )
        return best

    # ------------------------------------------------------------------
    # Travel along a route (sequence of edges)
    # ------------------------------------------------------------------
    def _travel(
        self,
        truck_id: str,
        edge_ids: Iterable[str],
        speed_factor: float,
        loaded: bool,
        payload_tonnes: float,
    ):
        """Generator: walk a route, holding capacity-1 edge resources.

        Capacity-1 edges are wrapped with request/release; queue waits and
        traversal times are recorded. Free-flow edges are plain timeouts.
        Productive busy time is accumulated for every wall-clock minute of
        wait + traversal.
        """
        edge_noise_rng = self.rng["edge_noise"]
        for edge_id in edge_ids:
            edge = self.topology.edges[edge_id]
            travel_time = _stochastic_edge_time_min(
                edge=edge,
                speed_factor=speed_factor,
                travel_noise_cv=self.scenario.stochasticity.travel_time_noise_cv,
                rng=edge_noise_rng,
            )
            if edge.is_capacity_constrained:
                handle = self.edge_resources[edge_id]
                # Per conceptual model: edge_enter / edge_leave bracket the
                # *holding* of the Resource. Truck arrives at from_node and
                # silently joins the queue; once granted (request boundary)
                # we fire edge_enter, traverse, then fire edge_leave at the
                # release boundary just before exiting the ``with`` block.
                wait_start = self.env.now
                with handle.resource.request() as req:
                    yield req
                    # --- Request boundary: resource just acquired ---
                    wait_time = self.env.now - wait_start
                    self._emit(
                        truck_id,
                        EVENT_EDGE_ENTER,
                        from_node=edge.from_node,
                        to_node=edge.to_node,
                        location=edge.from_node,
                        loaded=loaded,
                        payload_tonnes=payload_tonnes,
                        resource_id=edge_id,
                        queue_length=(
                            handle.resource.count + len(handle.resource.queue)
                        ),
                    )
                    yield self.env.timeout(travel_time)
                    self.recorder.record_edge_traversal(
                        edge_id=edge_id,
                        wait_time_min=wait_time,
                        traversal_time_min=travel_time,
                    )
                    self.recorder.add_productive_time(
                        truck_id, wait_time + travel_time
                    )
                    # --- Release boundary: about to exit ``with`` block ---
                    self._emit(
                        truck_id,
                        EVENT_EDGE_LEAVE,
                        from_node=edge.from_node,
                        to_node=edge.to_node,
                        location=edge.to_node,
                        loaded=loaded,
                        payload_tonnes=payload_tonnes,
                        resource_id=edge_id,
                        queue_length=(
                            handle.resource.count + len(handle.resource.queue)
                        ),
                    )
            else:
                yield self.env.timeout(travel_time)
                self.recorder.add_productive_time(truck_id, travel_time)

    # ------------------------------------------------------------------
    # Loading / dumping
    # ------------------------------------------------------------------
    def _load(
        self,
        truck: TruckSpec,
        loader: _LoaderHandle,
    ):
        """Generator: queue + service at a loader, emit events."""
        loading_rng = self.rng["loading"]
        queue_len = loader.resource.count + len(loader.resource.queue)
        self._emit(
            truck.truck_id,
            EVENT_ARRIVE_LOADER,
            location=loader.spec.node_id,
            loaded=False,
            payload_tonnes=0.0,
            resource_id=loader.spec.loader_id,
            queue_length=queue_len,
        )
        wait_start = self.env.now
        with loader.resource.request() as req:
            yield req
            wait_time = self.env.now - wait_start
            self._emit(
                truck.truck_id,
                EVENT_START_LOAD,
                location=loader.spec.node_id,
                loaded=False,
                payload_tonnes=0.0,
                resource_id=loader.spec.loader_id,
                queue_length=loader.resource.count + len(loader.resource.queue),
            )
            duration = truncated_normal(
                loading_rng,
                mean=loader.spec.mean_load_time_min,
                sd=loader.spec.sd_load_time_min,
            )
            yield self.env.timeout(duration)
            self.recorder.record_loader_service(
                loader_id=loader.spec.loader_id,
                wait_time_min=wait_time,
                service_time_min=duration,
            )
            self.recorder.add_productive_time(
                truck.truck_id, wait_time + duration
            )
            self._emit(
                truck.truck_id,
                EVENT_END_LOAD,
                location=loader.spec.node_id,
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
                resource_id=loader.spec.loader_id,
                queue_length=loader.resource.count + len(loader.resource.queue),
            )
        self._emit(
            truck.truck_id,
            EVENT_DEPART_LOADER,
            location=loader.spec.node_id,
            loaded=True,
            payload_tonnes=truck.payload_tonnes,
            resource_id=loader.spec.loader_id,
            queue_length=loader.resource.count + len(loader.resource.queue),
        )

    def _dump(
        self,
        truck: TruckSpec,
    ):
        """Generator: queue + service at the crusher; credit tonnes if before cut."""
        dumping_rng = self.rng["dumping"]
        queue_len = self.crusher.resource.count + len(self.crusher.resource.queue)
        self._emit(
            truck.truck_id,
            EVENT_ARRIVE_CRUSHER,
            location="CRUSH",
            loaded=True,
            payload_tonnes=truck.payload_tonnes,
            resource_id=self.crusher.dump_id,
            queue_length=queue_len,
        )
        wait_start = self.env.now
        with self.crusher.resource.request() as req:
            yield req
            wait_time = self.env.now - wait_start
            self._emit(
                truck.truck_id,
                EVENT_START_DUMP,
                location="CRUSH",
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
                resource_id=self.crusher.dump_id,
                queue_length=self.crusher.resource.count
                + len(self.crusher.resource.queue),
            )
            duration = truncated_normal(
                dumping_rng,
                mean=self.crusher.mean_dump_time_min,
                sd=self.crusher.sd_dump_time_min,
            )
            yield self.env.timeout(duration)
            self.recorder.record_crusher_service(
                wait_time_min=wait_time,
                service_time_min=duration,
            )
            self.recorder.add_productive_time(
                truck.truck_id, wait_time + duration
            )
            now = self.env.now
            # Hard cut: only credit completed dumps strictly before shift end.
            if now < self.recorder.shift_length_min:
                self.recorder.record_completed_dump(now, truck.truck_id)
                self.recorder.record_cycle_end(truck.truck_id, now)
            self._emit(
                truck.truck_id,
                EVENT_END_DUMP,
                location="CRUSH",
                loaded=False,
                payload_tonnes=truck.payload_tonnes,
                resource_id=self.crusher.dump_id,
                queue_length=self.crusher.resource.count
                + len(self.crusher.resource.queue),
            )
        self._emit(
            truck.truck_id,
            EVENT_DEPART_CRUSHER,
            location="CRUSH",
            loaded=False,
            payload_tonnes=0.0,
            resource_id=self.crusher.dump_id,
            queue_length=self.crusher.resource.count
            + len(self.crusher.resource.queue),
        )

    # ------------------------------------------------------------------
    # Main truck loop
    # ------------------------------------------------------------------
    def _truck_process(self, truck: TruckSpec):
        """SimPy process generator implementing the ore haulage loop."""
        # Initial dispatch event (all trucks released at t=0)
        self.recorder.record_dispatch(truck.truck_id, time_min=self.env.now)
        self._emit(
            truck.truck_id,
            EVENT_DISPATCH,
            location=truck.start_node,
            loaded=False,
            payload_tonnes=0.0,
            queue_length=0,
        )
        current_node = truck.start_node
        shift_min = self.recorder.shift_length_min

        while self.env.now < shift_min:
            # ---- Choose a loader given current state -------------------
            chosen = self._choose_loader(
                origin=current_node,
                speed_factor=truck.empty_speed_factor,
            )
            route_to_loader = self.routes.require(
                current_node, chosen.spec.node_id
            )
            # Travel empty to the loader
            yield from self._travel(
                truck_id=truck.truck_id,
                edge_ids=route_to_loader.edge_ids,
                speed_factor=truck.empty_speed_factor,
                loaded=False,
                payload_tonnes=0.0,
            )
            current_node = chosen.spec.node_id
            if self.env.now >= shift_min:
                break

            # ---- Load -----------------------------------------------------
            yield from self._load(truck, chosen)
            if self.env.now >= shift_min:
                break

            # ---- Travel loaded to crusher ---------------------------------
            route_to_crusher = self.routes.require(current_node, "CRUSH")
            yield from self._travel(
                truck_id=truck.truck_id,
                edge_ids=route_to_crusher.edge_ids,
                speed_factor=truck.loaded_speed_factor,
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
            )
            current_node = "CRUSH"
            if self.env.now >= shift_min:
                break

            # ---- Dump -----------------------------------------------------
            yield from self._dump(truck)
            # The dump generator is responsible for crediting tonnes &
            # cycle end if before the shift cut.
            # Loop continues; truck will pick a new loader next iteration.

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------
    def run(self, until_min: float | None = None) -> None:
        """Run the simulation until the shift cut (or a custom horizon)."""
        horizon = (
            until_min if until_min is not None else self.recorder.shift_length_min
        )
        self.env.run(until=horizon)


__all__ = [
    "MineSimulation",
]
