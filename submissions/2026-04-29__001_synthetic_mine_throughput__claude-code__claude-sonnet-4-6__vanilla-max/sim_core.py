"""sim_core.py — Core SimPy discrete-event model for mine haulage throughput."""

from __future__ import annotations

import simpy
import numpy as np
import networkx as nx
import pandas as pd
from scipy import stats
from dataclasses import dataclass, field
from typing import Dict, List, Optional


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph(
    nodes_df: pd.DataFrame,
    edges_df: pd.DataFrame,
    edge_overrides: Optional[Dict] = None,
    node_overrides: Optional[Dict] = None,
) -> nx.DiGraph:
    G = nx.DiGraph()

    for _, row in nodes_df.iterrows():
        node_data = row.to_dict()
        if node_overrides and row["node_id"] in node_overrides:
            node_data.update(node_overrides[row["node_id"]])
        G.add_node(row["node_id"], **node_data)

    for _, row in edges_df.iterrows():
        edge_id = row["edge_id"]
        edge_data = row.to_dict()

        if edge_overrides and edge_id in edge_overrides:
            edge_data.update(edge_overrides[edge_id])

        closed = edge_data.get("closed", False)
        if isinstance(closed, str):
            closed = closed.strip().lower() == "true"
        if closed:
            continue

        speed_kph = float(edge_data["max_speed_kph"])
        distance_m = float(edge_data["distance_m"])
        travel_time_min = (distance_m / 1000.0) / speed_kph * 60.0
        capacity = int(float(edge_data["capacity"]))

        G.add_edge(
            edge_data["from_node"],
            edge_data["to_node"],
            edge_id=edge_id,
            distance_m=distance_m,
            max_speed_kph=speed_kph,
            road_type=edge_data["road_type"],
            capacity=capacity,
            travel_time_min=travel_time_min,
        )

    return G


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def find_route(G: nx.DiGraph, source: str, target: str) -> List[str]:
    try:
        return nx.shortest_path(G, source, target, weight="travel_time_min")
    except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
        raise ValueError(f"No path from {source!r} to {target!r}: {exc}") from exc


def route_travel_time(G: nx.DiGraph, path: List[str], speed_factor: float) -> float:
    return sum(
        G[path[i]][path[i + 1]]["travel_time_min"] / speed_factor
        for i in range(len(path) - 1)
    )


# ---------------------------------------------------------------------------
# Stochastic helpers
# ---------------------------------------------------------------------------

def trunc_normal(mean: float, sd: float, rng: np.random.Generator, low: float = 0.0) -> float:
    if sd <= 0.0:
        return max(mean, low)
    a = (low - mean) / sd
    return float(stats.truncnorm.rvs(a, np.inf, loc=mean, scale=sd, random_state=rng))


def lognormal_noise(cv: float, rng: np.random.Generator) -> float:
    """Return a lognormal multiplier with mean=1 and coefficient of variation=cv."""
    sigma2 = np.log(1.0 + cv ** 2)
    mu = -0.5 * sigma2
    return float(rng.lognormal(mu, np.sqrt(sigma2)))


# ---------------------------------------------------------------------------
# Dispatching
# ---------------------------------------------------------------------------

def select_loader(
    G: nx.DiGraph,
    current_node: str,
    loaders: List[Dict],
    loader_resources: Dict[str, simpy.Resource],
    empty_sf: float,
) -> Dict:
    """Pick loader with minimum (travel_time + queue_penalty)."""
    best: Optional[Dict] = None
    best_score = float("inf")

    for loader in loaders:
        try:
            path = find_route(G, current_node, loader["node_id"])
        except ValueError:
            continue
        travel_t = route_travel_time(G, path, empty_sf)
        res = loader_resources[loader["loader_id"]]
        queue_penalty = len(res.queue) * loader["mean_load_time_min"]
        score = travel_t + queue_penalty
        if score < best_score:
            best_score = score
            best = loader

    if best is None:
        raise ValueError(f"No reachable loader from {current_node!r}")
    return best


# ---------------------------------------------------------------------------
# Simulation state
# ---------------------------------------------------------------------------

@dataclass
class SimState:
    tonnes_delivered: float = 0.0
    dump_events: List[Dict] = field(default_factory=list)
    cycle_times: List[float] = field(default_factory=list)
    loader_queue_times: List[float] = field(default_factory=list)
    crusher_queue_times: List[float] = field(default_factory=list)
    crusher_service_times: List[float] = field(default_factory=list)
    loader_service_times: Dict[str, List[float]] = field(default_factory=dict)
    truck_active_time: Dict[str, float] = field(default_factory=dict)
    event_log: List[Dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Truck process
# ---------------------------------------------------------------------------

def truck_process(
    env: simpy.Environment,
    truck_id: str,
    truck_data: Dict,
    G: nx.DiGraph,
    loader_resources: Dict[str, simpy.Resource],
    crusher_resource: simpy.Resource,
    road_resources: Dict[str, simpy.Resource],
    loaders: List[Dict],
    dump_point: Dict,
    scenario_cfg: Dict,
    state: SimState,
    rng: np.random.Generator,
    log_events: bool,
    rep: int,
    scenario_id: str,
):
    empty_sf = float(truck_data["empty_speed_factor"])
    loaded_sf = float(truck_data["loaded_speed_factor"])
    payload = float(truck_data["payload_tonnes"])
    shift_end = scenario_cfg["shift_length_min"]
    noise_cv = scenario_cfg["noise_cv"]
    dump_node = scenario_cfg["dump_destination"]
    current_node = truck_data["start_node"]
    active_time = 0.0

    def log(event_type, *, from_node="", to_node="", location="", loaded=False,
            resource_id="", queue_length=0):
        if log_events:
            state.event_log.append({
                "time_min": round(env.now, 4),
                "replication": rep + 1,
                "scenario_id": scenario_id,
                "truck_id": truck_id,
                "event_type": event_type,
                "from_node": from_node,
                "to_node": to_node,
                "location": location or from_node,
                "loaded": loaded,
                "payload_tonnes": payload if loaded else 0.0,
                "resource_id": resource_id,
                "queue_length": queue_length,
            })

    while env.now < shift_end:
        cycle_start = env.now

        try:
            loader = select_loader(G, current_node, loaders, loader_resources, empty_sf)
        except ValueError:
            break

        loader_node = loader["node_id"]
        loader_id = loader["loader_id"]

        log("dispatch", location=current_node)

        # --- travel to loader (empty) ---
        try:
            route = find_route(G, current_node, loader_node)
        except ValueError:
            break

        for i in range(len(route) - 1):
            if env.now >= shift_end:
                return
            u, v = route[i], route[i + 1]
            edge = G[u][v]
            eid = edge["edge_id"]
            tt = (edge["travel_time_min"] / empty_sf) * lognormal_noise(noise_cv, rng)

            log("edge_depart", from_node=u, to_node=v, loaded=False)

            if edge["capacity"] < 10 and eid in road_resources:
                with road_resources[eid].request() as req:
                    yield req
                    yield env.timeout(tt)
            else:
                yield env.timeout(tt)

        current_node = loader_node
        if env.now >= shift_end:
            return

        # --- queue and load ---
        res = loader_resources[loader_id]
        log("loader_queue_join", location=loader_node, resource_id=loader_id,
            queue_length=len(res.queue))
        q_start = env.now

        with res.request() as req:
            yield req
            state.loader_queue_times.append(env.now - q_start)

            log("load_start", location=loader_node, resource_id=loader_id)
            load_t = trunc_normal(loader["mean_load_time_min"], loader["sd_load_time_min"], rng)
            yield env.timeout(load_t)
            state.loader_service_times.setdefault(loader_id, []).append(load_t)
            log("load_end", location=loader_node, loaded=True, resource_id=loader_id)

        if env.now >= shift_end:
            return

        # --- travel to crusher (loaded) ---
        try:
            route = find_route(G, loader_node, dump_node)
        except ValueError:
            break

        for i in range(len(route) - 1):
            if env.now >= shift_end:
                return
            u, v = route[i], route[i + 1]
            edge = G[u][v]
            eid = edge["edge_id"]
            tt = (edge["travel_time_min"] / loaded_sf) * lognormal_noise(noise_cv, rng)

            log("edge_depart", from_node=u, to_node=v, loaded=True)

            if edge["capacity"] < 10 and eid in road_resources:
                with road_resources[eid].request() as req:
                    yield req
                    yield env.timeout(tt)
            else:
                yield env.timeout(tt)

        current_node = dump_node
        if env.now >= shift_end:
            return

        # --- queue and dump ---
        log("crusher_queue_join", location=dump_node, resource_id="crusher",
            queue_length=len(crusher_resource.queue))
        q_start = env.now

        with crusher_resource.request() as req:
            yield req
            state.crusher_queue_times.append(env.now - q_start)

            log("dump_start", location=dump_node, loaded=True, resource_id="crusher")
            dump_t = trunc_normal(
                dump_point["mean_dump_time_min"], dump_point["sd_dump_time_min"], rng
            )
            yield env.timeout(dump_t)

            if env.now <= shift_end:
                state.tonnes_delivered += payload
                state.dump_events.append(
                    {"time": env.now, "tonnes": payload, "truck_id": truck_id}
                )
                state.crusher_service_times.append(dump_t)
                log("dump_end", location=dump_node, loaded=False, resource_id="crusher")

        cycle_time = env.now - cycle_start
        state.cycle_times.append(cycle_time)
        active_time += cycle_time

    state.truck_active_time[truck_id] = active_time


# ---------------------------------------------------------------------------
# Run one replication
# ---------------------------------------------------------------------------

def run_replication(
    scenario_cfg: Dict,
    G: nx.DiGraph,
    loaders: List[Dict],
    dump_point: Dict,
    trucks: pd.DataFrame,
    rng: np.random.Generator,
    rep: int,
    scenario_id: str,
    log_events: bool,
) -> SimState:
    env = simpy.Environment()

    loader_resources = {
        loader["loader_id"]: simpy.Resource(env, capacity=1) for loader in loaders
    }
    crusher_resource = simpy.Resource(env, capacity=1)

    road_resources: Dict[str, simpy.Resource] = {}
    for u, v, data in G.edges(data=True):
        if data["capacity"] < 10:
            eid = data["edge_id"]
            if eid not in road_resources:
                road_resources[eid] = simpy.Resource(env, capacity=data["capacity"])

    state = SimState()

    n_trucks = scenario_cfg.get("truck_count", len(trucks))
    active_trucks = trucks.head(n_trucks)

    for _, truck in active_trucks.iterrows():
        env.process(
            truck_process(
                env,
                truck["truck_id"],
                truck.to_dict(),
                G,
                loader_resources,
                crusher_resource,
                road_resources,
                loaders,
                dump_point,
                scenario_cfg,
                state,
                rng,
                log_events=log_events,
                rep=rep,
                scenario_id=scenario_id,
            )
        )

    env.run(until=scenario_cfg["shift_length_min"])
    return state


# ---------------------------------------------------------------------------
# Metrics extraction
# ---------------------------------------------------------------------------

def extract_metrics(state: SimState, scenario_cfg: Dict, trucks: pd.DataFrame) -> Dict:
    shift_min = scenario_cfg["shift_length_min"]
    n_trucks = scenario_cfg.get("truck_count", len(trucks))

    tph = state.tonnes_delivered / (shift_min / 60.0)
    avg_cycle = float(np.mean(state.cycle_times)) if state.cycle_times else 0.0

    active_truck_ids = list(trucks.head(n_trucks)["truck_id"])
    avg_util = float(
        np.mean([state.truck_active_time.get(t, 0.0) / shift_min for t in active_truck_ids])
    )

    crusher_util = (
        float(np.sum(state.crusher_service_times) / shift_min)
        if state.crusher_service_times
        else 0.0
    )

    loader_util = {}
    for loader_id, times in state.loader_service_times.items():
        loader_util[loader_id] = float(np.sum(times) / shift_min)

    avg_loader_q = float(np.mean(state.loader_queue_times)) if state.loader_queue_times else 0.0
    avg_crusher_q = float(np.mean(state.crusher_queue_times)) if state.crusher_queue_times else 0.0

    return {
        "total_tonnes": state.tonnes_delivered,
        "tph": tph,
        "avg_cycle_min": avg_cycle,
        "avg_truck_util": avg_util,
        "crusher_util": min(crusher_util, 1.0),
        "loader_util": loader_util,
        "avg_loader_q_min": avg_loader_q,
        "avg_crusher_q_min": avg_crusher_q,
        "n_dumps": len(state.dump_events),
    }
