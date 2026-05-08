"""SimPy discrete-event mine throughput simulation.

One replication produces a typed ``ReplicationResult`` with throughput, per-truck
productive / queue time, and per-resource utilisation / queue stats. Event log
entries are emitted as plain dicts for downstream CSV writing.

Design (per interview-decisions memory):

* One ``simpy.Resource`` per directed capacity-1 edge (mirrors the CSV).
* Lognormal travel-time noise with cv=0.10 around free-flow mean.
* Normal-truncated load and dump samples; sample = ``max(0.1, N(mu, sigma))``.
* Dispatch rule: ``min(travel_empty + queue_len * mean_load + own_load)``.
* Simultaneous t=0 dispatch for all trucks.
* Hard cut at ``shift_length_min`` — ``env.run(until=shift_length_min)``;
  throughput counts only ``dump_end`` events with time <= shift_length_min.
* Per-rep RNG seed = ``base_random_seed + rep_idx``.
* Truck utilisation = productive time only (loading + dumping + traveling).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import simpy

from .data import StaticData, Truck
from .routing import RoutingTables, build_routing, choose_loader
from .scenarios import ScenarioConfig
from .topology import ScenarioTopology, free_flow_minutes


@dataclass
class TruckStats:
    truck_id: str
    productive_min: float = 0.0
    loader_queue_min: float = 0.0
    crusher_queue_min: float = 0.0
    edge_queue_min: float = 0.0
    cycles_completed: int = 0
    tonnes_delivered: float = 0.0
    cycle_times: List[float] = field(default_factory=list)


@dataclass
class ResourceStats:
    """Tracking object for a single SimPy resource (loader / crusher / edge).

    ``busy_intervals`` is a list of ``(start_min, end_min)`` pairs giving the
    time the resource was *in use*. ``queue_waits`` is a list of (wait_minutes)
    values, one per requesting truck.
    """
    resource_id: str
    kind: str   # "loader" | "crusher" | "edge"
    busy_intervals: List[Tuple[float, float]] = field(default_factory=list)
    queue_waits: List[float] = field(default_factory=list)


@dataclass
class ReplicationResult:
    scenario_id: str
    replication: int
    random_seed: int
    shift_length_min: float
    total_tonnes: float
    tonnes_per_hour: float
    truck_stats: Dict[str, TruckStats]
    resource_stats: Dict[str, ResourceStats]
    events: List[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Helpers


def _sample_lognormal(rng: np.random.Generator, mean: float, cv: float) -> float:
    """Lognormal sample with target arithmetic mean ``mean`` and coefficient of
    variation ``cv``. Falls back to ``mean`` for degenerate inputs.
    """
    if mean <= 0:
        return 0.0
    if cv <= 0:
        return mean
    sigma2 = math.log(1.0 + cv * cv)
    sigma = math.sqrt(sigma2)
    mu = math.log(mean) - 0.5 * sigma2
    return float(rng.lognormal(mean=mu, sigma=sigma))


def _sample_truncnorm(rng: np.random.Generator, mean: float, sd: float, floor: float = 0.1) -> float:
    """Sample N(mean, sd) and clamp to ``floor`` from below."""
    if sd <= 0:
        return float(max(floor, mean))
    s = float(rng.normal(loc=mean, scale=sd))
    return float(max(floor, s))


# ---------------------------------------------------------------------------
# Event log helper


class EventLog:
    """Lightweight, append-only event log."""

    def __init__(self) -> None:
        self.events: List[Dict[str, Any]] = []

    def add(
        self,
        env: simpy.Environment,
        *,
        replication: int,
        scenario_id: str,
        truck_id: str,
        event_type: str,
        from_node: str = "",
        to_node: str = "",
        location: str = "",
        loaded: Optional[bool] = None,
        payload_tonnes: float = 0.0,
        resource_id: str = "",
        queue_length: int = 0,
    ) -> None:
        self.events.append({
            "time_min": round(env.now, 4),
            "replication": replication,
            "scenario_id": scenario_id,
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": "" if loaded is None else int(bool(loaded)),
            "payload_tonnes": payload_tonnes,
            "resource_id": resource_id,
            "queue_length": queue_length,
        })


# ---------------------------------------------------------------------------
# Truck process factory


def _truck_process(
    env: simpy.Environment,
    *,
    rng: np.random.Generator,
    truck: Truck,
    scenario: ScenarioConfig,
    topology: ScenarioTopology,
    routing: RoutingTables,
    loader_resources: Dict[str, simpy.Resource],
    crusher_resource: simpy.Resource,
    crusher_id: str,
    crusher_node: str,
    edge_resources: Dict[str, simpy.Resource],
    edge_stats: Dict[str, ResourceStats],
    loader_stats: Dict[str, ResourceStats],
    crusher_stats: ResourceStats,
    truck_stats: TruckStats,
    log: EventLog,
    travel_cv: float,
):
    """Generator: loops dispatch -> load -> haul -> dump -> return until shift cut."""
    shift_min = scenario.shift_length_minutes
    candidate_loader_ids = list(loader_resources.keys())
    crusher_dump_mean = float(topology.dump_points_effective[crusher_id]["mean_dump_time_min"])
    crusher_dump_sd = float(topology.dump_points_effective[crusher_id]["sd_dump_time_min"])

    current_node = truck.start_node

    while env.now < shift_min:
        # --- Dispatch ---------------------------------------------------------
        queue_lengths = {
            lid: len(loader_resources[lid].queue) + (1 if loader_resources[lid].count > 0 else 0)
            for lid in candidate_loader_ids
        }
        loader_id = choose_loader(
            current_node=current_node,
            candidate_loader_ids=candidate_loader_ids,
            loaders_effective=topology.loaders_effective,
            routing=routing,
            queue_lengths=queue_lengths,
        )
        loader_attrs = topology.loaders_effective[loader_id]
        loader_node = loader_attrs["node_id"]

        cycle_start = env.now
        log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                event_type="dispatched", from_node=current_node, to_node=loader_node,
                location=current_node, loaded=False, resource_id=loader_id)

        # --- Travel empty to loader ------------------------------------------
        yield from _traverse(
            env, truck.truck_id, scenario.scenario_id,
            current_node, loader_node, loaded=False,
            routing=routing, edge_resources=edge_resources, edge_stats=edge_stats,
            truck_stats=truck_stats, log=log, rng=rng, travel_cv=travel_cv,
            payload_tonnes=0.0,
        )
        current_node = loader_node
        log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                event_type="arrive_loader", location=loader_node, loaded=False, resource_id=loader_id,
                queue_length=len(loader_resources[loader_id].queue))

        # --- Load -------------------------------------------------------------
        wait_start = env.now
        with loader_resources[loader_id].request() as req:
            yield req
            wait_end = env.now
            wait = wait_end - wait_start
            truck_stats.loader_queue_min += wait
            loader_stats[loader_id].queue_waits.append(wait)
            log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                    event_type="load_start", location=loader_node, loaded=False, resource_id=loader_id)
            mean_load = float(loader_attrs["mean_load_time_min"])
            sd_load = float(loader_attrs["sd_load_time_min"])
            load_t = _sample_truncnorm(rng, mean_load, sd_load)
            busy_start = env.now
            yield env.timeout(load_t)
            busy_end = env.now
            loader_stats[loader_id].busy_intervals.append((busy_start, busy_end))
            truck_stats.productive_min += (busy_end - busy_start)
            payload = truck.payload_tonnes
            log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                    event_type="load_end", location=loader_node, loaded=True,
                    payload_tonnes=payload, resource_id=loader_id)

        # --- Travel loaded to crusher ----------------------------------------
        yield from _traverse(
            env, truck.truck_id, scenario.scenario_id,
            loader_node, crusher_node, loaded=True,
            routing=routing, edge_resources=edge_resources, edge_stats=edge_stats,
            truck_stats=truck_stats, log=log, rng=rng, travel_cv=travel_cv,
            payload_tonnes=truck.payload_tonnes,
        )
        current_node = crusher_node
        log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                event_type="arrive_crusher", location=crusher_node, loaded=True,
                payload_tonnes=truck.payload_tonnes, resource_id=crusher_id,
                queue_length=len(crusher_resource.queue))

        # --- Dump -------------------------------------------------------------
        wait_start = env.now
        with crusher_resource.request() as req:
            yield req
            wait_end = env.now
            wait = wait_end - wait_start
            truck_stats.crusher_queue_min += wait
            crusher_stats.queue_waits.append(wait)
            log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                    event_type="dump_start", location=crusher_node, loaded=True,
                    payload_tonnes=truck.payload_tonnes, resource_id=crusher_id)
            dump_t = _sample_truncnorm(rng, crusher_dump_mean, crusher_dump_sd)
            busy_start = env.now
            yield env.timeout(dump_t)
            busy_end = env.now
            crusher_stats.busy_intervals.append((busy_start, busy_end))
            truck_stats.productive_min += (busy_end - busy_start)
            cycle_end = env.now
            cycle_time = cycle_end - cycle_start
            # Throughput counts only dumps completed within the shift window.
            if busy_end <= shift_min:
                truck_stats.tonnes_delivered += truck.payload_tonnes
                truck_stats.cycles_completed += 1
                truck_stats.cycle_times.append(cycle_time)
            log.add(env, replication=-1, scenario_id=scenario.scenario_id, truck_id=truck.truck_id,
                    event_type="dump_end", location=crusher_node, loaded=False,
                    payload_tonnes=truck.payload_tonnes, resource_id=crusher_id)

    # Truck terminates by simply returning when env.run hits the cut. (We don't
    # need explicit teardown; cancelled yields are dropped automatically.)


def _traverse(
    env: simpy.Environment,
    truck_id: str,
    scenario_id: str,
    src: str,
    dst: str,
    *,
    loaded: bool,
    routing: RoutingTables,
    edge_resources: Dict[str, simpy.Resource],
    edge_stats: Dict[str, ResourceStats],
    truck_stats: TruckStats,
    log: EventLog,
    rng: np.random.Generator,
    travel_cv: float,
    payload_tonnes: float,
):
    """Walk an ordered edge path, requesting capacity-1 edge resources as needed."""
    if src == dst:
        return
    edge_path = routing.edge_ids[(src, dst)]
    node_path = routing.paths[(src, dst)]
    free_flow_map = routing.edge_time_loaded if loaded else routing.edge_time_empty
    for idx, eid in enumerate(edge_path):
        u_node = node_path[idx]
        v_node = node_path[idx + 1]
        nominal = free_flow_map[eid]
        actual = _sample_lognormal(rng, mean=nominal, cv=travel_cv)
        if eid in edge_resources:
            wait_start = env.now
            with edge_resources[eid].request() as ereq:
                yield ereq
                wait_end = env.now
                wait = wait_end - wait_start
                truck_stats.edge_queue_min += wait
                edge_stats[eid].queue_waits.append(wait)
                log.add(env, replication=-1, scenario_id=scenario_id, truck_id=truck_id,
                        event_type="enter_edge", from_node=u_node, to_node=v_node,
                        location=u_node, loaded=loaded, payload_tonnes=payload_tonnes,
                        resource_id=eid, queue_length=len(edge_resources[eid].queue))
                busy_start = env.now
                yield env.timeout(actual)
                busy_end = env.now
                edge_stats[eid].busy_intervals.append((busy_start, busy_end))
                truck_stats.productive_min += (busy_end - busy_start)
                log.add(env, replication=-1, scenario_id=scenario_id, truck_id=truck_id,
                        event_type="leave_edge", from_node=u_node, to_node=v_node,
                        location=v_node, loaded=loaded, payload_tonnes=payload_tonnes,
                        resource_id=eid)
        else:
            yield env.timeout(actual)
            truck_stats.productive_min += actual


# ---------------------------------------------------------------------------
# Replication entry point


def run_replication(
    *,
    static: StaticData,
    scenario: ScenarioConfig,
    topology: ScenarioTopology,
    rep_idx: int,
) -> ReplicationResult:
    """Run a single replication and return the typed result."""
    seed = scenario.base_random_seed + rep_idx
    rng = np.random.default_rng(seed)

    env = simpy.Environment()

    # Identify the crusher dump_id (production target).
    crusher_id: Optional[str] = None
    crusher_node: Optional[str] = None
    target_node = scenario.production.get("dump_destination", "CRUSH")
    for did, attrs in topology.dump_points_effective.items():
        if attrs["node_id"] == target_node:
            crusher_id = did
            crusher_node = attrs["node_id"]
            break
    if crusher_id is None or crusher_node is None:
        raise RuntimeError(f"Could not locate crusher dump for node '{target_node}'")

    # Loader resources.
    loader_resources: Dict[str, simpy.Resource] = {}
    loader_stats: Dict[str, ResourceStats] = {}
    for lid, attrs in topology.loaders_effective.items():
        capacity = max(1, int(attrs["capacity"]))
        loader_resources[lid] = simpy.Resource(env, capacity=capacity)
        loader_stats[lid] = ResourceStats(resource_id=lid, kind="loader")

    # Crusher resource.
    crusher_capacity = max(1, int(topology.dump_points_effective[crusher_id]["capacity"]))
    crusher_resource = simpy.Resource(env, capacity=crusher_capacity)
    crusher_stats = ResourceStats(resource_id=crusher_id, kind="crusher")

    # Capacity-1 edge resources.
    edge_resources: Dict[str, simpy.Resource] = {}
    edge_stats: Dict[str, ResourceStats] = {}
    for eid in topology.capacity_one_edge_ids:
        edge_resources[eid] = simpy.Resource(env, capacity=1)
        edge_stats[eid] = ResourceStats(resource_id=eid, kind="edge")

    # Routing — based on the *first* truck's speed factors. Per memory the routing
    # is static per scenario; all trucks share identical factors in our data.
    sample_truck = static.trucks[0]
    routing = build_routing(
        topology,
        empty_speed_factor=sample_truck.empty_speed_factor,
        loaded_speed_factor=sample_truck.loaded_speed_factor,
    )

    # Build truck stats and processes.
    fleet = static.trucks[: scenario.truck_count]
    truck_stats: Dict[str, TruckStats] = {t.truck_id: TruckStats(truck_id=t.truck_id) for t in fleet}
    log = EventLog()

    travel_cv = float(scenario.stochasticity.get("travel_time_noise_cv", 0.10))

    for t in fleet:
        env.process(_truck_process(
            env,
            rng=rng,
            truck=t,
            scenario=scenario,
            topology=topology,
            routing=routing,
            loader_resources=loader_resources,
            crusher_resource=crusher_resource,
            crusher_id=crusher_id,
            crusher_node=crusher_node,
            edge_resources=edge_resources,
            edge_stats=edge_stats,
            loader_stats=loader_stats,
            crusher_stats=crusher_stats,
            truck_stats=truck_stats[t.truck_id],
            log=log,
            travel_cv=travel_cv,
        ))

    env.run(until=scenario.shift_length_minutes)

    # Stamp the rep idx onto every event (we used -1 as a placeholder).
    for ev in log.events:
        ev["replication"] = rep_idx

    total_tonnes = sum(ts.tonnes_delivered for ts in truck_stats.values())
    tonnes_per_hour = total_tonnes / scenario.shift_length_hours

    resource_stats: Dict[str, ResourceStats] = {}
    for lid, rs in loader_stats.items():
        resource_stats[f"loader::{lid}"] = rs
    resource_stats[f"crusher::{crusher_id}"] = crusher_stats
    for eid, rs in edge_stats.items():
        resource_stats[f"edge::{eid}"] = rs

    return ReplicationResult(
        scenario_id=scenario.scenario_id,
        replication=rep_idx,
        random_seed=seed,
        shift_length_min=scenario.shift_length_minutes,
        total_tonnes=total_tonnes,
        tonnes_per_hour=tonnes_per_hour,
        truck_stats=truck_stats,
        resource_stats=resource_stats,
        events=log.events,
    )
