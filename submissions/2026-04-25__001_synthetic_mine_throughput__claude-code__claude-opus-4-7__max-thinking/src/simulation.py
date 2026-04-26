"""SimPy discrete-event simulation of mine haulage."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
import pandas as pd
import simpy

from .topology import (
    EdgeRecord,
    NodeRecord,
    Router,
    apply_edge_overrides,
    apply_node_overrides,
    build_graph,
    lane_id_of,
    load_edges,
    load_nodes,
)


# ---------- Stochastic helpers --------------------------------------------------


def truncated_normal(rng: np.random.Generator, mean: float, sd: float,
                     min_val: Optional[float] = None) -> float:
    """Normal sample clipped at lower bound. Default lower bound = max(0.05, mean-3*sd)."""
    if sd <= 0:
        return float(mean)
    lower = min_val if min_val is not None else max(0.05, mean - 3.0 * sd)
    val = rng.normal(loc=mean, scale=sd)
    if val < lower:
        val = lower
    return float(val)


def lognormal_noise(rng: np.random.Generator, cv: float) -> float:
    """Multiplicative lognormal noise factor with given coefficient of variation."""
    if cv <= 0:
        return 1.0
    sigma = math.sqrt(math.log(1.0 + cv * cv))
    mu = -0.5 * sigma * sigma
    return float(rng.lognormal(mean=mu, sigma=sigma))


# ---------- Stats containers ----------------------------------------------------


@dataclass
class TruckStats:
    truck_id: str
    cycles_completed: int = 0
    tonnes_delivered: float = 0.0
    busy_time_min: float = 0.0  # any active activity (loading, dumping, travelling)
    queue_loader_time_min: float = 0.0
    queue_crusher_time_min: float = 0.0
    queue_lane_time_min: float = 0.0
    cycle_times_min: List[float] = field(default_factory=list)
    last_cycle_start: float = 0.0


@dataclass
class ResourceStats:
    name: str
    capacity: int
    busy_time_min: float = 0.0
    queue_time_min: float = 0.0
    requests: int = 0
    last_state_change: float = 0.0
    in_use: int = 0
    queue_len: int = 0
    queue_wait_samples: List[float] = field(default_factory=list)


# ---------- Simulation state ----------------------------------------------------


@dataclass
class SimConfig:
    scenario_id: str
    replication: int
    random_seed: int
    shift_minutes: float
    truck_count: int
    travel_cv: float
    routing_objective: str
    dispatch_policy: str
    dispatch_tiebreak: str
    allow_bypass: bool
    road_capacity_enabled: bool


class SimState:
    def __init__(
        self,
        env: simpy.Environment,
        cfg: SimConfig,
        nodes: Dict[str, NodeRecord],
        edges: List[EdgeRecord],
        graph: nx.DiGraph,
        router: Router,
        loader_specs: List[Dict[str, Any]],
        crusher_spec: Dict[str, Any],
        loaded_factor: float,
        empty_factor: float,
        rng: np.random.Generator,
        event_log: List[Dict[str, Any]],
    ):
        self.env = env
        self.cfg = cfg
        self.nodes = nodes
        self.edges = edges
        self.graph = graph
        self.router = router
        self.rng = rng
        self.loaded_factor = loaded_factor
        self.empty_factor = empty_factor
        self.event_log = event_log

        # Loaders: one Resource per loader, with metadata.
        self.loaders: Dict[str, simpy.Resource] = {}
        self.loader_specs: Dict[str, Dict[str, Any]] = {}
        self.loader_stats: Dict[str, ResourceStats] = {}
        for spec in loader_specs:
            lid = spec["loader_id"]
            cap = int(spec.get("capacity", 1))
            self.loaders[lid] = simpy.Resource(env, capacity=cap)
            self.loader_specs[lid] = spec
            self.loader_stats[lid] = ResourceStats(name=lid, capacity=cap)

        # Crusher
        self.crusher: simpy.Resource = simpy.Resource(
            env, capacity=int(crusher_spec.get("capacity", 1))
        )
        self.crusher_spec = crusher_spec
        self.crusher_stats = ResourceStats(name="crusher", capacity=int(crusher_spec.get("capacity", 1)))

        # Lane resources for capacity-constrained edges.
        self.lane_resources: Dict[str, simpy.Resource] = {}
        self.lane_capacity: Dict[str, int] = {}
        self.lane_stats: Dict[str, ResourceStats] = {}
        if cfg.road_capacity_enabled:
            lane_min_capacity: Dict[str, int] = {}
            for e in edges:
                if e.closed:
                    continue
                if e.capacity >= 999:
                    continue
                lid = lane_id_of(e.edge_id)
                if lid not in lane_min_capacity or e.capacity < lane_min_capacity[lid]:
                    lane_min_capacity[lid] = e.capacity
            for lid, cap in lane_min_capacity.items():
                self.lane_resources[lid] = simpy.Resource(env, capacity=int(cap))
                self.lane_capacity[lid] = int(cap)
                self.lane_stats[lid] = ResourceStats(name=f"lane_{lid}", capacity=int(cap))

        self.truck_stats: Dict[str, TruckStats] = {}

    # Resource utilisation accounting -------------------------------------------------

    def _record_resource_busy(self, stats: ResourceStats, busy: bool) -> None:
        now = self.env.now
        # If transitioning, accumulate prior period
        if stats.in_use > 0:
            stats.busy_time_min += (now - stats.last_state_change) * stats.in_use / max(stats.capacity, 1)
        # Record updated state - actually we'll just track raw busy fraction.
        stats.last_state_change = now
        if busy:
            stats.in_use = min(stats.in_use + 1, stats.capacity)
        else:
            stats.in_use = max(stats.in_use - 1, 0)

    def request_loader(self, loader_id: str):
        return self.loaders[loader_id].request()

    def request_crusher(self):
        return self.crusher.request()

    def request_lane(self, lane_id: str):
        if lane_id in self.lane_resources:
            return self.lane_resources[lane_id].request()
        return None


# ---------- Truck process -------------------------------------------------------


def _expected_cycle_time(state: SimState, current_node: str, loader_id: str,
                         load_node: str, dump_node: str) -> float:
    """Estimate one full cycle time from current_node through the loader/dump."""
    spec = state.loader_specs[loader_id]
    load_time = float(spec["mean_load_time_min"])
    dump_time = float(state.crusher_spec.get("mean_dump_time_min", 3.5))
    t_to_load = state.router.path_time_min(current_node, load_node)
    t_to_dump = state.router.path_time_min(load_node, dump_node)
    queue_pen = (
        state.loaders[loader_id].count * float(spec["mean_load_time_min"])
        + len(state.loaders[loader_id].queue) * float(spec["mean_load_time_min"])
    )
    return t_to_load + load_time + t_to_dump + dump_time + queue_pen


def _select_loader(state: SimState, current_node: str, dump_node: str) -> str:
    policy = state.cfg.dispatch_policy
    tiebreak = state.cfg.dispatch_tiebreak
    candidates: List[Tuple[str, str, float, float]] = []
    for lid, spec in state.loader_specs.items():
        node = spec["node_id"]
        try:
            t_to = state.router.path_time_min(current_node, node)
        except RuntimeError:
            continue  # unreachable
        cycle = _expected_cycle_time(state, current_node, lid, node, dump_node)
        candidates.append((lid, node, t_to, cycle))

    if not candidates:
        raise RuntimeError("No loader reachable from current location")

    if policy == "nearest_available_loader":
        # Prefer idle loader; among tied, shortest expected cycle time.
        idle = [c for c in candidates if state.loaders[c[0]].count == 0
                and len(state.loaders[c[0]].queue) == 0]
        pool = idle if idle else candidates
        if tiebreak == "shortest_expected_cycle_time":
            pool.sort(key=lambda c: (c[3], c[2]))
        else:
            pool.sort(key=lambda c: (c[2], c[3]))
        return pool[0][0]
    # default: shortest cycle time
    candidates.sort(key=lambda c: (c[3], c[2]))
    return candidates[0][0]


def _emit(state: SimState, *, truck_id: str, event_type: str,
          from_node: str = "", to_node: str = "", location: str = "",
          loaded: Optional[bool] = None, payload_tonnes: float = 0.0,
          resource_id: str = "", queue_length: int = 0) -> None:
    state.event_log.append({
        "time_min": round(float(state.env.now), 4),
        "replication": state.cfg.replication,
        "scenario_id": state.cfg.scenario_id,
        "truck_id": truck_id,
        "event_type": event_type,
        "from_node": from_node,
        "to_node": to_node,
        "location": location,
        "loaded": "" if loaded is None else int(bool(loaded)),
        "payload_tonnes": round(float(payload_tonnes), 4),
        "resource_id": resource_id,
        "queue_length": int(queue_length),
    })


def _travel(state: SimState, truck_id: str, source: str, target: str, *, loaded: bool,
            payload: float):
    """Generator: traverse shortest path from source to target.

    Holds capacity-constrained lane resources for the duration of each segment.
    """
    if source == target:
        return
    path = state.router.shortest_path(source, target)
    truck = state.truck_stats[truck_id]
    speed_factor = state.loaded_factor if loaded else state.empty_factor

    for u, v in zip(path[:-1], path[1:]):
        edge_data = state.graph[u][v]
        if edge_data.get("closed"):
            raise RuntimeError(
                f"Attempt to traverse closed edge {edge_data.get('edge_id')}"
            )
        lane_id = edge_data["lane_id"]
        capacity = int(edge_data["capacity"])
        distance_m = float(edge_data["distance_m"])
        max_speed = float(edge_data["max_speed_kph"])
        # Nominal travel time at this speed.
        nominal_min = (distance_m / 1000.0) / max(max_speed * speed_factor, 1e-6) * 60.0
        noise = lognormal_noise(state.rng, state.cfg.travel_cv)
        actual_min = nominal_min * noise

        constrained = (
            state.cfg.road_capacity_enabled
            and capacity < 999
            and lane_id in state.lane_resources
        )
        if constrained:
            req = state.lane_resources[lane_id].request()
            t_request = state.env.now
            yield req
            wait = state.env.now - t_request
            truck.queue_lane_time_min += wait
            stats = state.lane_stats[lane_id]
            stats.requests += 1
            stats.queue_wait_samples.append(wait)
            t_start = state.env.now
            _emit(state, truck_id=truck_id, event_type="enter_edge",
                  from_node=u, to_node=v, location=u,
                  loaded=loaded, payload_tonnes=payload,
                  resource_id=edge_data["edge_id"],
                  queue_length=len(state.lane_resources[lane_id].queue))
            yield state.env.timeout(actual_min)
            stats.busy_time_min += state.env.now - t_start
            state.lane_resources[lane_id].release(req)
            _emit(state, truck_id=truck_id, event_type="exit_edge",
                  from_node=u, to_node=v, location=v,
                  loaded=loaded, payload_tonnes=payload,
                  resource_id=edge_data["edge_id"])
        else:
            _emit(state, truck_id=truck_id, event_type="enter_edge",
                  from_node=u, to_node=v, location=u,
                  loaded=loaded, payload_tonnes=payload,
                  resource_id=edge_data["edge_id"])
            yield state.env.timeout(actual_min)
            _emit(state, truck_id=truck_id, event_type="exit_edge",
                  from_node=u, to_node=v, location=v,
                  loaded=loaded, payload_tonnes=payload,
                  resource_id=edge_data["edge_id"])

        truck.busy_time_min += actual_min


def truck_process(state: SimState, truck_id: str, payload_tonnes: float):
    env = state.env
    truck = state.truck_stats[truck_id]
    truck.last_cycle_start = env.now
    current_node = "PARK"
    dump_node = "CRUSH"

    _emit(state, truck_id=truck_id, event_type="dispatched",
          location=current_node, loaded=False, payload_tonnes=0.0)

    while env.now < state.cfg.shift_minutes:
        cycle_start = env.now
        # Choose loader.
        loader_id = _select_loader(state, current_node, dump_node)
        load_node = state.loader_specs[loader_id]["node_id"]
        spec = state.loader_specs[loader_id]
        _emit(state, truck_id=truck_id, event_type="route_to_loader",
              from_node=current_node, to_node=load_node, location=current_node,
              loaded=False, resource_id=loader_id)

        # Travel empty to load node.
        yield from _travel(state, truck_id, current_node, load_node,
                           loaded=False, payload=0.0)
        current_node = load_node
        _emit(state, truck_id=truck_id, event_type="arrive_loader",
              location=load_node, loaded=False, resource_id=loader_id,
              queue_length=len(state.loaders[loader_id].queue))

        if env.now >= state.cfg.shift_minutes:
            break

        # Queue for loader.
        req = state.loaders[loader_id].request()
        t_q = env.now
        _emit(state, truck_id=truck_id, event_type="queue_loader",
              location=load_node, loaded=False, resource_id=loader_id,
              queue_length=len(state.loaders[loader_id].queue))
        yield req
        wait = env.now - t_q
        truck.queue_loader_time_min += wait
        loader_stats = state.loader_stats[loader_id]
        loader_stats.requests += 1
        loader_stats.queue_wait_samples.append(wait)

        # Loading.
        load_time = truncated_normal(
            state.rng,
            mean=float(spec["mean_load_time_min"]),
            sd=float(spec.get("sd_load_time_min", 0.0)),
        )
        _emit(state, truck_id=truck_id, event_type="load_start",
              location=load_node, loaded=False, resource_id=loader_id)
        t_start = env.now
        yield env.timeout(load_time)
        loader_stats.busy_time_min += env.now - t_start
        truck.busy_time_min += load_time
        state.loaders[loader_id].release(req)
        _emit(state, truck_id=truck_id, event_type="load_end",
              location=load_node, loaded=True, payload_tonnes=payload_tonnes,
              resource_id=loader_id)

        # Travel loaded to crusher.
        yield from _travel(state, truck_id, load_node, dump_node,
                           loaded=True, payload=payload_tonnes)
        current_node = dump_node
        _emit(state, truck_id=truck_id, event_type="arrive_crusher",
              location=dump_node, loaded=True, payload_tonnes=payload_tonnes,
              resource_id="crusher",
              queue_length=len(state.crusher.queue))

        # Queue for crusher.
        req_c = state.crusher.request()
        t_q = env.now
        _emit(state, truck_id=truck_id, event_type="queue_crusher",
              location=dump_node, loaded=True, payload_tonnes=payload_tonnes,
              resource_id="crusher",
              queue_length=len(state.crusher.queue))
        yield req_c
        wait_c = env.now - t_q
        truck.queue_crusher_time_min += wait_c
        state.crusher_stats.requests += 1
        state.crusher_stats.queue_wait_samples.append(wait_c)

        dump_time = truncated_normal(
            state.rng,
            mean=float(state.crusher_spec.get("mean_dump_time_min", 3.5)),
            sd=float(state.crusher_spec.get("sd_dump_time_min", 0.0)),
        )
        _emit(state, truck_id=truck_id, event_type="dump_start",
              location=dump_node, loaded=True, payload_tonnes=payload_tonnes,
              resource_id="crusher")
        t_start = env.now
        yield env.timeout(dump_time)
        state.crusher_stats.busy_time_min += env.now - t_start
        truck.busy_time_min += dump_time
        state.crusher.release(req_c)

        # Cycle complete: tonnes counted at dump-end (crusher delivery).
        truck.cycles_completed += 1
        truck.tonnes_delivered += payload_tonnes
        truck.cycle_times_min.append(env.now - cycle_start)
        _emit(state, truck_id=truck_id, event_type="dump_end",
              location=dump_node, loaded=False, payload_tonnes=payload_tonnes,
              resource_id="crusher")

    _emit(state, truck_id=truck_id, event_type="shift_end",
          location=current_node, loaded=False)


# ---------- Run a single replication --------------------------------------------


def run_replication(
    *,
    scenario: Dict[str, Any],
    nodes: Dict[str, NodeRecord],
    edges: List[EdgeRecord],
    truck_records: pd.DataFrame,
    loader_records: pd.DataFrame,
    dump_records: pd.DataFrame,
    replication_index: int,
    base_seed: int,
    capture_event_log: bool = True,
) -> Dict[str, Any]:
    seed = base_seed + replication_index
    rng = np.random.default_rng(seed)

    sim_cfg_raw = scenario.get("simulation", {})
    shift_minutes = float(sim_cfg_raw.get("shift_length_hours", 8)) * 60.0

    routing = scenario.get("routing", {})
    dispatching = scenario.get("dispatching", {})
    stochastic = scenario.get("stochasticity", {})
    fleet = scenario.get("fleet", {})

    cfg = SimConfig(
        scenario_id=str(scenario.get("scenario_id", "")),
        replication=replication_index,
        random_seed=seed,
        shift_minutes=shift_minutes,
        truck_count=int(fleet.get("truck_count", len(truck_records))),
        travel_cv=float(stochastic.get("travel_time_noise_cv", 0.0)),
        routing_objective=str(routing.get("objective", "shortest_time")),
        dispatch_policy=str(dispatching.get("policy", "nearest_available_loader")),
        dispatch_tiebreak=str(dispatching.get(
            "tie_breaker", "shortest_expected_cycle_time"
        )),
        allow_bypass=bool(routing.get("allow_bypass", True)),
        road_capacity_enabled=bool(routing.get("road_capacity_enabled", True)),
    )

    # Apply overrides.
    edges_eff = apply_edge_overrides(edges, scenario.get("edge_overrides", {}))
    nodes_eff = apply_node_overrides(nodes, scenario.get("node_overrides", {}))

    # Loaded/empty speed factors come from the truck records (homogeneous fleet here).
    if not truck_records.empty:
        empty_factor = float(truck_records.iloc[0]["empty_speed_factor"])
        loaded_factor = float(truck_records.iloc[0]["loaded_speed_factor"])
    else:
        empty_factor, loaded_factor = 1.0, 0.85

    graph = build_graph(
        nodes_eff, edges_eff,
        empty_speed_factor=empty_factor,
        loaded_speed_factor=loaded_factor,
        drop_closed=True,
    )
    router = Router(graph, weight_attr="weight")

    # Loader specs (with possible overrides).
    loader_specs: List[Dict[str, Any]] = []
    loader_overrides = scenario.get("loader_overrides", {})
    for _, row in loader_records.iterrows():
        spec = {
            "loader_id": str(row["loader_id"]),
            "node_id": str(row["node_id"]),
            "capacity": int(row["capacity"]),
            "bucket_capacity_tonnes": float(row["bucket_capacity_tonnes"]),
            "mean_load_time_min": float(row["mean_load_time_min"]),
            "sd_load_time_min": float(row["sd_load_time_min"]),
            "availability": float(row["availability"]),
        }
        if spec["loader_id"] in loader_overrides:
            spec.update(loader_overrides[spec["loader_id"]])
        loader_specs.append(spec)

    # Crusher (dump) spec.
    dump_overrides = scenario.get("dump_point_overrides", {})
    crusher_row = dump_records[dump_records["dump_id"] == "D_CRUSH"].iloc[0]
    crusher_spec = {
        "dump_id": str(crusher_row["dump_id"]),
        "node_id": str(crusher_row["node_id"]),
        "type": str(crusher_row["type"]),
        "capacity": int(crusher_row["capacity"]),
        "mean_dump_time_min": float(crusher_row["mean_dump_time_min"]),
        "sd_dump_time_min": float(crusher_row["sd_dump_time_min"]),
    }
    if "D_CRUSH" in dump_overrides:
        crusher_spec.update(dump_overrides["D_CRUSH"])

    # Build SimPy environment and state.
    env = simpy.Environment()
    event_log: List[Dict[str, Any]] = []
    state = SimState(
        env=env, cfg=cfg, nodes=nodes_eff, edges=edges_eff,
        graph=graph, router=router,
        loader_specs=loader_specs, crusher_spec=crusher_spec,
        loaded_factor=loaded_factor, empty_factor=empty_factor,
        rng=rng, event_log=event_log,
    )

    # Build trucks (subset by truck_count, in order from CSV).
    selected_trucks = truck_records.iloc[: cfg.truck_count]
    for _, t_row in selected_trucks.iterrows():
        tid = str(t_row["truck_id"])
        state.truck_stats[tid] = TruckStats(truck_id=tid)
        env.process(truck_process(state, tid, payload_tonnes=float(t_row["payload_tonnes"])))

    # Run.
    env.run(until=shift_minutes)

    # Aggregate metrics.
    total_tonnes = sum(t.tonnes_delivered for t in state.truck_stats.values())
    cycle_times = [c for t in state.truck_stats.values() for c in t.cycle_times_min]
    avg_cycle = float(np.mean(cycle_times)) if cycle_times else 0.0
    avg_truck_busy = float(np.mean([t.busy_time_min / shift_minutes
                                    for t in state.truck_stats.values()]))
    # Per-loader queue wait (mean wait per request at each loader)
    loader_queue_waits: Dict[str, float] = {}
    for lid, ls in state.loader_stats.items():
        loader_queue_waits[lid] = float(np.mean(ls.queue_wait_samples)) if ls.queue_wait_samples else 0.0
    crusher_queue_wait = (
        float(np.mean(state.crusher_stats.queue_wait_samples))
        if state.crusher_stats.queue_wait_samples else 0.0
    )

    # Resource utilisation.
    loader_util: Dict[str, float] = {}
    for lid, ls in state.loader_stats.items():
        loader_util[lid] = min(1.0, ls.busy_time_min / shift_minutes)
    crusher_util = min(1.0, state.crusher_stats.busy_time_min / shift_minutes)

    # Lane utilisation.
    lane_util: Dict[str, float] = {}
    lane_queue_wait: Dict[str, float] = {}
    for lid, ls in state.lane_stats.items():
        lane_util[lid] = min(1.0, ls.busy_time_min / (shift_minutes * max(ls.capacity, 1)))
        lane_queue_wait[lid] = float(np.mean(ls.queue_wait_samples)) if ls.queue_wait_samples else 0.0

    return {
        "scenario_id": cfg.scenario_id,
        "replication": replication_index,
        "random_seed": seed,
        "shift_minutes": shift_minutes,
        "truck_count": cfg.truck_count,
        "total_tonnes_delivered": total_tonnes,
        "tonnes_per_hour": total_tonnes / (shift_minutes / 60.0),
        "average_truck_cycle_time_min": avg_cycle,
        "average_truck_utilisation": avg_truck_busy,
        "crusher_utilisation": crusher_util,
        "loader_utilisation": loader_util,
        "average_loader_queue_time_min": float(np.mean(list(loader_queue_waits.values())))
            if loader_queue_waits else 0.0,
        "loader_queue_waits": loader_queue_waits,
        "average_crusher_queue_time_min": crusher_queue_wait,
        "lane_utilisation": lane_util,
        "lane_queue_wait_min": lane_queue_wait,
        "cycles_completed": int(sum(t.cycles_completed for t in state.truck_stats.values())),
        "event_log": event_log if capture_event_log else None,
    }


def load_input_dataframes(data_dir: Path) -> Tuple[Dict[str, NodeRecord], List[EdgeRecord],
                                                    pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    nodes = load_nodes(data_dir / "nodes.csv")
    edges = load_edges(data_dir / "edges.csv")
    trucks = pd.read_csv(data_dir / "trucks.csv")
    loaders = pd.read_csv(data_dir / "loaders.csv")
    dump_points = pd.read_csv(data_dir / "dump_points.csv")
    return nodes, edges, trucks, loaders, dump_points
