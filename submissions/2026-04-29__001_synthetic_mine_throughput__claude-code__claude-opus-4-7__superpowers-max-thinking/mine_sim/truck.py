"""Truck SimPy process, Simulation container, and dispatcher."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx
import numpy as np
import simpy

from mine_sim.metrics import MetricsCollector
from mine_sim.resources import ResourcePool
from mine_sim.topology import (
    EDGE_TO_LOCK,
    Edge,
    Node,
    path_edge_ids,
    path_travel_time_min,
)


def draw_truncated_normal(rng: np.random.Generator, mean: float, sd: float) -> float:
    """Draw from Normal(mean, sd), truncated to [0.1, mean + 5*sd]."""
    if sd <= 0.0:
        return float(max(0.1, mean))
    val = rng.normal(mean, sd)
    upper = mean + 5.0 * sd
    return float(np.clip(val, 0.1, upper))


@dataclass
class Simulation:
    """Container bundling everything a TruckProcess needs."""

    env: simpy.Environment
    config: dict[str, Any]
    graph: nx.DiGraph
    edges: dict[str, Edge]
    nodes: dict[str, Node]
    pool: ResourcePool
    rng: np.random.Generator
    collector: MetricsCollector
    shortest_paths: dict[str, dict[str, list[str]]] = field(default_factory=dict)

    def node_path(self, src: str, dst: str) -> list[str]:
        return self.shortest_paths[src][dst]

    def edge_path(self, src: str, dst: str) -> list[Edge]:
        if src == dst:
            return []
        return [self.edges[eid] for eid in path_edge_ids(self.node_path(src, dst), self.graph)]

    def nominal_travel_time_min(self, src: str, dst: str) -> float:
        if src == dst:
            return 0.0
        return path_travel_time_min(self.node_path(src, dst), self.graph)


def choose_loader(current_node: str, sim: Simulation) -> str:
    """Return loader_id minimising expected cycle time. Deterministic tie-break by id."""
    crusher_node = sim.pool.crusher_node
    crusher_mean = sim.pool.crusher_service["mean"]
    candidates: list[tuple[float, str]] = []
    for loader_id, loader_node in sim.pool.loader_node.items():
        travel_to = sim.nominal_travel_time_min(current_node, loader_node)
        travel_loaded = sim.nominal_travel_time_min(loader_node, crusher_node)
        loader_res = sim.pool.loaders[loader_id]
        queue_count = len(loader_res.queue) + len(loader_res.users)
        load_mean = sim.pool.loader_service[(loader_id, "mean")]
        expected_cycle = (
            travel_to
            + queue_count * load_mean
            + load_mean
            + travel_loaded
            + crusher_mean
        )
        candidates.append((expected_cycle, loader_id))
    candidates.sort()
    return candidates[0][1]


@dataclass
class TruckProcess:
    sim: Simulation
    truck_id: str
    payload_tonnes: float
    empty_speed_factor: float
    loaded_speed_factor: float
    start_node: str
    _current_node: str = ""
    _loaded: bool = False
    _cycle_start_time: float = 0.0

    def start(self) -> None:
        self._current_node = self.start_node
        self.sim.env.process(self._run())

    def _run(self):
        env = self.sim.env
        shift_minutes = float(self.sim.config["simulation"]["shift_length_hours"]) * 60.0
        while env.now < shift_minutes:
            self._cycle_start_time = env.now

            # 1. Dispatch
            loader_id = choose_loader(self._current_node, self.sim)
            loader_node = self.sim.pool.loader_node[loader_id]
            self._log("truck_dispatched", from_node=self._current_node,
                      to_node=loader_node, location=self._current_node,
                      resource_id=f"loader_{loader_id}")

            # 2. Travel empty -> loader
            yield from self._travel_path(self._current_node, loader_node, loaded=False)
            if env.now >= shift_minutes:
                break

            # 3. Load
            yield from self._load(loader_id)
            if env.now >= shift_minutes:
                break

            # 4. Travel loaded -> crusher
            yield from self._travel_path(loader_node, self.sim.pool.crusher_node, loaded=True)
            if env.now >= shift_minutes:
                break

            # 5. Dump
            yield from self._dump()

            self.sim.collector.truck(self.truck_id).cycle_times_min.append(
                env.now - self._cycle_start_time
            )

    def _travel_path(self, src: str, dst: str, *, loaded: bool):
        if src == dst:
            return
        for edge in self.sim.edge_path(src, dst):
            yield from self._traverse(edge, loaded=loaded)

    def _traverse(self, edge: Edge, *, loaded: bool):
        env = self.sim.env
        speed_factor = self.loaded_speed_factor if loaded else self.empty_speed_factor
        base_speed = edge.max_speed_kph * speed_factor
        cv = self.sim.config.get("stochasticity", {}).get("travel_time_noise_cv", 0.10)
        noise = float(self.sim.rng.normal(1.0, cv))
        speed = max(0.1 * edge.max_speed_kph, base_speed * noise)
        travel_time_min = (edge.distance_m / 1000.0) / speed * 60.0

        lock_id = EDGE_TO_LOCK.get(edge.edge_id)
        lock = self.sim.pool.road_locks.get(lock_id) if lock_id else None

        self._log("traversal_started",
                  from_node=edge.from_node, to_node=edge.to_node,
                  location=edge.from_node, resource_id=lock_id,
                  queue_length=(len(lock.queue) if lock is not None else None),
                  loaded=loaded)

        if lock is not None:
            self._log("road_lock_requested",
                      from_node=edge.from_node, to_node=edge.to_node,
                      location=edge.from_node, resource_id=lock_id,
                      queue_length=len(lock.queue), loaded=loaded)
            t_request = env.now
            with lock.request() as req:
                yield req
                wait = env.now - t_request
                self.sim.collector.record_queue_wait(
                    f"road_{lock_id}",
                    queue_len_on_entry=len(lock.queue),
                    wait_minutes=wait,
                )
                self._log("road_lock_acquired",
                          from_node=edge.from_node, to_node=edge.to_node,
                          location=edge.from_node, resource_id=lock_id,
                          queue_length=len(lock.queue), loaded=loaded)
                t0 = env.now
                yield env.timeout(travel_time_min)
                self.sim.collector.record_resource_busy(f"road_{lock_id}", env.now - t0)
        else:
            yield env.timeout(travel_time_min)

        self.sim.collector.truck(self.truck_id).travelling_minutes += travel_time_min
        self._current_node = edge.to_node

        self._log("traversal_ended",
                  from_node=edge.from_node, to_node=edge.to_node,
                  location=edge.to_node, resource_id=lock_id, loaded=loaded)

    def _load(self, loader_id: str):
        env = self.sim.env
        loader_res = self.sim.pool.loaders[loader_id]
        node_id = self.sim.pool.loader_node[loader_id]
        resource_id = f"loader_{loader_id}"

        self._log("loader_requested", from_node=node_id, to_node=node_id,
                  location=node_id, resource_id=resource_id,
                  queue_length=len(loader_res.queue))
        t_req = env.now
        with loader_res.request() as req:
            yield req
            wait = env.now - t_req
            self.sim.collector.record_queue_wait(
                resource_id,
                queue_len_on_entry=len(loader_res.queue),
                wait_minutes=wait,
            )
            mean = self.sim.pool.loader_service[(loader_id, "mean")]
            sd = self.sim.pool.loader_service[(loader_id, "sd")]
            duration = draw_truncated_normal(self.sim.rng, mean, sd)
            self._log("loading_started", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(loader_res.queue))
            yield env.timeout(duration)
            self.sim.collector.record_resource_busy(resource_id, duration)
            self.sim.collector.truck(self.truck_id).loading_minutes += duration
            self._loaded = True
            self._log("loading_ended", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(loader_res.queue))

    def _dump(self):
        env = self.sim.env
        crusher_res = self.sim.pool.crusher
        node_id = self.sim.pool.crusher_node
        resource_id = "crusher"
        shift_minutes = float(self.sim.config["simulation"]["shift_length_hours"]) * 60.0

        self._log("crusher_requested", from_node=node_id, to_node=node_id,
                  location=node_id, resource_id=resource_id,
                  queue_length=len(crusher_res.queue))
        t_req = env.now
        with crusher_res.request() as req:
            yield req
            wait = env.now - t_req
            self.sim.collector.record_queue_wait(
                resource_id,
                queue_len_on_entry=len(crusher_res.queue),
                wait_minutes=wait,
            )
            mean = self.sim.pool.crusher_service["mean"]
            sd = self.sim.pool.crusher_service["sd"]
            duration = draw_truncated_normal(self.sim.rng, mean, sd)
            self._log("dumping_started", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(crusher_res.queue))
            yield env.timeout(duration)
            self.sim.collector.record_resource_busy(resource_id, duration)
            self.sim.collector.truck(self.truck_id).dumping_minutes += duration
            if env.now <= shift_minutes:
                self.sim.collector.record_dump(env.now, self.truck_id, self.payload_tonnes)
            self._loaded = False
            self._log("dumping_ended", from_node=node_id, to_node=node_id,
                      location=node_id, resource_id=resource_id,
                      queue_length=len(crusher_res.queue),
                      payload_tonnes=self.payload_tonnes)

    def _log(
        self,
        event_type: str,
        *,
        from_node: str | None = None,
        to_node: str | None = None,
        location: str | None = None,
        resource_id: str | None = None,
        queue_length: int | None = None,
        loaded: bool | None = None,
        payload_tonnes: float | None = None,
    ) -> None:
        self.sim.collector.log_event(
            time_min=self.sim.env.now,
            truck_id=self.truck_id,
            event_type=event_type,
            from_node=from_node,
            to_node=to_node,
            location=location,
            loaded=self._loaded if loaded is None else loaded,
            payload_tonnes=(self.payload_tonnes if self._loaded else 0.0)
                           if payload_tonnes is None else payload_tonnes,
            resource_id=resource_id,
            queue_length=queue_length,
        )
