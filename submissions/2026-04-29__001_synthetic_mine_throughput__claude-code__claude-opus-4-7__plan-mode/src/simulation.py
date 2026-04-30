"""SimPy simulation core: resources, truck process, dispatcher, event log.

Each replication instantiates a fresh :class:`MineSim`, registers SimPy
resources (loaders, crusher, capacity-constrained edges) and then runs one
truck process per truck in the fleet. Events that matter for traceability
or for utilisation/queue accounting are appended to ``event_log``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import simpy

from .model import (
    CONSTRAINED_CAPACITY_THRESHOLD,
    compute_route,
    lognormal_unit_mean,
    truncated_normal,
)


# --- Public dataclasses for stats ----------------------------------------------------


@dataclass
class ResourceStats:
    """Cumulative busy/queue stats for a single SimPy resource."""
    busy_time: float = 0.0
    queue_wait_total: float = 0.0
    queue_wait_count: int = 0
    queue_length_samples: list[tuple[float, int]] = field(default_factory=list)

    def mean_queue_wait(self) -> float:
        return self.queue_wait_total / self.queue_wait_count if self.queue_wait_count else 0.0


@dataclass
class TruckStats:
    """Per-truck metrics."""
    truck_id: str
    cycles_completed: int = 0
    total_loaded_tonnes: float = 0.0
    busy_time: float = 0.0          # time travelling, loading, dumping (NOT queueing)
    queue_time: float = 0.0
    cycle_starts: list[float] = field(default_factory=list)


# --- Main sim object -----------------------------------------------------------------


class MineSim:
    """One replication of the mine throughput simulation.

    Attributes set after :meth:`run` finishes:
        total_tonnes_delivered, dump_events, event_log,
        truck_stats, loader_stats, crusher_stats, edge_stats.
    """

    def __init__(self,
                 env: simpy.Environment,
                 scenario_cfg: dict[str, Any],
                 graph: nx.DiGraph,
                 trucks_df,
                 loaders_df,
                 dump_points_df,
                 edges_df,
                 rng: np.random.Generator,
                 scenario_id: str,
                 replication: int):
        self.env = env
        self.scenario_cfg = scenario_cfg
        self.graph = graph
        self.trucks_df = trucks_df
        self.loaders_df = loaders_df
        self.dump_points_df = dump_points_df
        self.edges_df = edges_df
        self.rng = rng
        self.scenario_id = scenario_id
        self.replication = replication

        self.shift_end_min: float = float(scenario_cfg["simulation"]["shift_length_hours"]) * 60.0
        self.travel_cv: float = float(scenario_cfg["stochasticity"].get("travel_time_noise_cv", 0.0))
        self.dump_node: str = scenario_cfg["production"]["dump_destination"]

        # Resources
        self.loaders: dict[str, simpy.Resource] = {}
        self.loader_meta: dict[str, dict[str, Any]] = {}
        for _, row in loaders_df.iterrows():
            self.loaders[row["loader_id"]] = simpy.Resource(env, capacity=int(row["capacity"]))
            self.loader_meta[row["loader_id"]] = {
                "node_id": row["node_id"],
                "mean_load_time_min": float(row["mean_load_time_min"]),
                "sd_load_time_min": float(row["sd_load_time_min"]),
                "bucket_capacity_tonnes": float(row["bucket_capacity_tonnes"]),
            }

        dump_row = dump_points_df.loc[dump_points_df["node_id"] == self.dump_node].iloc[0]
        self.crusher = simpy.Resource(env, capacity=int(dump_row["capacity"]))
        self.crusher_meta = {
            "dump_id": dump_row["dump_id"],
            "mean_dump_time_min": float(dump_row["mean_dump_time_min"]),
            "sd_dump_time_min": float(dump_row["sd_dump_time_min"]),
        }

        # Constrained edges only (capacity < threshold). Open edges only.
        self.edge_resources: dict[str, simpy.Resource] = {}
        self.edge_meta: dict[str, dict[str, Any]] = {}
        for _, row in edges_df.iterrows():
            if bool(row["closed"]):
                continue
            cap = int(row["capacity"])
            if cap >= CONSTRAINED_CAPACITY_THRESHOLD:
                continue
            self.edge_resources[row["edge_id"]] = simpy.Resource(env, capacity=cap)
            self.edge_meta[row["edge_id"]] = {
                "from_node": row["from_node"],
                "to_node": row["to_node"],
            }

        # Stats
        self.loader_stats: dict[str, ResourceStats] = {lid: ResourceStats() for lid in self.loaders}
        self.crusher_stats = ResourceStats()
        self.edge_stats: dict[str, ResourceStats] = {eid: ResourceStats() for eid in self.edge_resources}
        self.truck_stats: dict[str, TruckStats] = {}

        self.event_log: list[dict[str, Any]] = []
        self.total_tonnes_delivered: float = 0.0
        self.dump_events: int = 0

    # ---- logging helpers ----------------------------------------------------

    def _shift_clipped(self, start: float, duration: float) -> float:
        """Return the portion of ``[start, start+duration]`` inside the shift.

        Used so utilisation stats only credit work done during the 8-hour shift,
        not the tail period in which already-loaded trucks finish their dumps.
        """
        end = start + duration
        return max(0.0, min(end, self.shift_end_min) - max(start, 0.0))

    def log(self, truck_id: str, event_type: str,
            from_node: str | None = None, to_node: str | None = None,
            location: str | None = None, loaded: bool | None = None,
            payload_tonnes: float | None = None,
            resource_id: str | None = None,
            queue_length: int | None = None) -> None:
        self.event_log.append({
            "time_min": round(self.env.now, 4),
            "replication": self.replication,
            "scenario_id": self.scenario_id,
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": loaded,
            "payload_tonnes": payload_tonnes,
            "resource_id": resource_id,
            "queue_length": queue_length,
        })

    # ---- resource interactions ---------------------------------------------

    def _request_resource(self, resource: simpy.Resource, stats: ResourceStats):
        """Generator-friendly helper. Yields the queue-wait duration."""
        arrival = self.env.now
        stats.queue_length_samples.append((arrival, len(resource.queue)))
        return resource.request(), arrival

    def traverse_edge(self, edge: dict[str, Any], speed_factor: float, truck_id: str,
                      *, loaded: bool):
        """Generator: traverse a single edge, requesting its resource if constrained."""
        edge_id = edge["edge_id"]
        # Stochastic multiplier on travel time (mean 1).
        noise = lognormal_unit_mean(self.rng, self.travel_cv)
        # speed_factor < 1 for loaded trucks => longer travel.
        travel_min = (edge["travel_min"] / max(speed_factor, 1e-6)) * noise

        if edge_id in self.edge_resources:
            resource = self.edge_resources[edge_id]
            stats = self.edge_stats[edge_id]
            arrival = self.env.now
            stats.queue_length_samples.append((arrival, len(resource.queue)))
            self.log(truck_id, "edge_queue_join",
                     from_node=edge["from_node"], to_node=edge["to_node"],
                     loaded=loaded, resource_id=edge_id,
                     queue_length=len(resource.queue))
            with resource.request() as req:
                yield req
                wait = self.env.now - arrival
                stats.queue_wait_total += wait
                stats.queue_wait_count += 1
                self.log(truck_id, "edge_entered",
                         from_node=edge["from_node"], to_node=edge["to_node"],
                         loaded=loaded, resource_id=edge_id,
                         queue_length=len(resource.queue))
                start = self.env.now
                yield self.env.timeout(travel_min)
                stats.busy_time += self._shift_clipped(start, travel_min)
                self.log(truck_id, "edge_exited",
                         from_node=edge["from_node"], to_node=edge["to_node"],
                         loaded=loaded, resource_id=edge_id,
                         queue_length=len(resource.queue))
        else:
            self.log(truck_id, "edge_traversed_unconstrained",
                     from_node=edge["from_node"], to_node=edge["to_node"],
                     loaded=loaded, resource_id=edge_id)
            yield self.env.timeout(travel_min)

    # ---- dispatcher ---------------------------------------------------------

    def pick_loader(self, current_node: str) -> str:
        """Choose a loader by ``nearest_available_loader`` policy.

        Score = travel_time(current_node -> loader_node)
              + queue_size * mean_load_time_loader.
        Tie-breaker: shorter expected return cycle (loader -> crusher).
        """
        best_id = None
        best_score = float("inf")
        best_return = float("inf")
        for lid, meta in self.loader_meta.items():
            try:
                edges = compute_route(self.graph, current_node, meta["node_id"])
                travel = sum(e["travel_min"] for e in edges)
            except Exception:
                continue
            queue = len(self.loaders[lid].queue) + (1 if self.loaders[lid].count else 0)
            score = travel + queue * meta["mean_load_time_min"]
            if score < best_score - 1e-9:
                best_id, best_score = lid, score
                # Tie-breaker: pre-compute return-leg time.
                try:
                    ret_edges = compute_route(self.graph, meta["node_id"], self.dump_node)
                    best_return = sum(e["travel_min"] for e in ret_edges)
                except Exception:
                    best_return = float("inf")
            elif abs(score - best_score) < 1e-9:
                try:
                    ret_edges = compute_route(self.graph, meta["node_id"], self.dump_node)
                    ret_time = sum(e["travel_min"] for e in ret_edges)
                except Exception:
                    ret_time = float("inf")
                if ret_time < best_return:
                    best_id, best_return = lid, ret_time
        if best_id is None:
            raise RuntimeError(f"No reachable loader from {current_node}")
        return best_id

    # ---- truck process ------------------------------------------------------

    def truck_process(self, truck_row, initial_stagger: float):
        """SimPy process for a single truck."""
        env = self.env
        truck_id = truck_row["truck_id"]
        empty_factor = float(truck_row["empty_speed_factor"])
        loaded_factor = float(truck_row["loaded_speed_factor"])
        payload = float(truck_row["payload_tonnes"])

        ts = TruckStats(truck_id=truck_id)
        self.truck_stats[truck_id] = ts

        current_node = truck_row["start_node"]
        yield env.timeout(initial_stagger)
        self.log(truck_id, "truck_dispatched", location=current_node, loaded=False)

        while env.now < self.shift_end_min:
            # Choose a loader and route to it.
            loader_id = self.pick_loader(current_node)
            loader_meta = self.loader_meta[loader_id]
            target = loader_meta["node_id"]
            try:
                edges = compute_route(self.graph, current_node, target)
            except Exception as exc:
                self.log(truck_id, "routing_error", location=current_node)
                raise

            ts.cycle_starts.append(env.now)
            travel_start = env.now
            for e in edges:
                yield from self.traverse_edge(e, empty_factor, truck_id, loaded=False)
                current_node = e["to_node"]
            ts.busy_time += self._shift_clipped(travel_start, env.now - travel_start)
            self.log(truck_id, "arrived_at_loader",
                     location=target, resource_id=loader_id, loaded=False)

            # Request the loader.
            loader = self.loaders[loader_id]
            lstats = self.loader_stats[loader_id]
            arrival = env.now
            lstats.queue_length_samples.append((arrival, len(loader.queue)))
            with loader.request() as req:
                yield req
                wait = env.now - arrival
                lstats.queue_wait_total += wait
                lstats.queue_wait_count += 1
                ts.queue_time += wait
                self.log(truck_id, "load_start",
                         location=target, resource_id=loader_id, loaded=False,
                         queue_length=len(loader.queue))
                load_time = truncated_normal(self.rng,
                                             loader_meta["mean_load_time_min"],
                                             loader_meta["sd_load_time_min"])
                load_start = env.now
                yield env.timeout(load_time)
                in_shift = self._shift_clipped(load_start, load_time)
                lstats.busy_time += in_shift
                ts.busy_time += in_shift
                self.log(truck_id, "load_end",
                         location=target, resource_id=loader_id, loaded=True,
                         payload_tonnes=payload)

            # Route to dump and traverse loaded.
            try:
                edges_back = compute_route(self.graph, target, self.dump_node)
            except Exception:
                self.log(truck_id, "routing_error", location=target)
                raise
            travel_start = env.now
            for e in edges_back:
                yield from self.traverse_edge(e, loaded_factor, truck_id, loaded=True)
                current_node = e["to_node"]
            ts.busy_time += self._shift_clipped(travel_start, env.now - travel_start)
            self.log(truck_id, "arrived_at_crusher",
                     location=self.dump_node, resource_id=self.crusher_meta["dump_id"],
                     loaded=True, payload_tonnes=payload)

            # Dump.
            arrival = env.now
            self.crusher_stats.queue_length_samples.append((arrival, len(self.crusher.queue)))
            with self.crusher.request() as req:
                yield req
                wait = env.now - arrival
                self.crusher_stats.queue_wait_total += wait
                self.crusher_stats.queue_wait_count += 1
                ts.queue_time += wait
                self.log(truck_id, "dump_start",
                         location=self.dump_node, resource_id=self.crusher_meta["dump_id"],
                         loaded=True, payload_tonnes=payload,
                         queue_length=len(self.crusher.queue))
                dump_time = truncated_normal(self.rng,
                                             self.crusher_meta["mean_dump_time_min"],
                                             self.crusher_meta["sd_dump_time_min"])
                dump_start = env.now
                yield env.timeout(dump_time)
                in_shift = self._shift_clipped(dump_start, dump_time)
                self.crusher_stats.busy_time += in_shift
                ts.busy_time += in_shift
                self.log(truck_id, "dump_end",
                         location=self.dump_node, resource_id=self.crusher_meta["dump_id"],
                         loaded=False, payload_tonnes=payload)
                # Tonnes count only at completed dump events.
                self.total_tonnes_delivered += payload
                self.dump_events += 1
                ts.cycles_completed += 1
                ts.total_loaded_tonnes += payload

        self.log(truck_id, "shift_end_truncated", location=current_node, loaded=False)

    # ---- run ----------------------------------------------------------------

    def run(self) -> None:
        """Schedule all trucks and run the simulation until shift end (plus tail)."""
        # Random initial stagger over [0, 60] s = [0, 1] min, per truck.
        for _, truck_row in self.trucks_df.iterrows():
            stagger = float(self.rng.uniform(0.0, 1.0))
            self.env.process(self.truck_process(truck_row, stagger))
        # Run until well past shift_end so any in-flight loaded trucks finish.
        self.env.run(until=self.shift_end_min + 240.0)


def aggregate_truck_metrics(sim: MineSim) -> dict[str, float]:
    """Compute fleet-level metrics after a single run."""
    n_trucks = len(sim.truck_stats)
    shift_min = sim.shift_end_min
    if n_trucks == 0:
        return {}

    # Cycle time: mean inter-cycle-start gap (across all trucks).
    deltas: list[float] = []
    for ts in sim.truck_stats.values():
        starts = sorted(ts.cycle_starts)
        for a, b in zip(starts[:-1], starts[1:]):
            deltas.append(b - a)
    avg_cycle = float(np.mean(deltas)) if deltas else float("nan")

    truck_busy_total = sum(ts.busy_time for ts in sim.truck_stats.values())
    truck_util = truck_busy_total / (n_trucks * shift_min) if shift_min > 0 else 0.0

    loader_util = {
        lid: stats.busy_time / shift_min if shift_min > 0 else 0.0
        for lid, stats in sim.loader_stats.items()
    }
    crusher_util = sim.crusher_stats.busy_time / shift_min if shift_min > 0 else 0.0

    avg_loader_q = (
        sum(s.queue_wait_total for s in sim.loader_stats.values())
        / max(1, sum(s.queue_wait_count for s in sim.loader_stats.values()))
    )
    avg_crusher_q = sim.crusher_stats.mean_queue_wait()

    return {
        "total_tonnes_delivered": sim.total_tonnes_delivered,
        "tonnes_per_hour": sim.total_tonnes_delivered / (shift_min / 60.0),
        "average_truck_cycle_time_min": avg_cycle,
        "average_truck_utilisation": truck_util,
        "crusher_utilisation": crusher_util,
        "loader_utilisation": loader_util,
        "average_loader_queue_time_min": avg_loader_q,
        "average_crusher_queue_time_min": avg_crusher_q,
        "dump_events": sim.dump_events,
    }
