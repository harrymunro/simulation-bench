"""Truck SimPy process — represents a single haul truck running an 8-hour shift."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
import simpy

from .topology import Topology, edge_time_min
from .resources import ResourcePool


def truncated_normal(mean: float, sd: float, rng: np.random.Generator,
                     low_factor: float = 0.5, high_factor: float = 2.0) -> float:
    """Draw from normal then clamp to [low_factor*mean, high_factor*mean]. Always >=0."""
    if sd <= 0:
        return float(mean)
    x = rng.normal(mean, sd)
    lo, hi = low_factor * mean, high_factor * mean
    return float(max(lo, min(hi, max(0.0, x))))


@dataclass
class TruckMetrics:
    truck_id: str
    cycles_completed: int = 0
    tonnes_delivered: float = 0.0
    cycle_times_min: List[float] = field(default_factory=list)
    busy_time_min: float = 0.0          # not idle (travelling or being served)
    loader_queue_time_min: float = 0.0
    crusher_queue_time_min: float = 0.0


def _expected_loader_wait(loader_res: simpy.Resource, mean_load_min: float) -> float:
    in_use = len(loader_res.users)
    queued = len(loader_res.queue)
    return (in_use + queued) * mean_load_min


def pick_loader(current_node: str,
                 topology: Topology,
                 g_with_attrs,
                 loader_paths: Dict[str, List[str]],
                 res: ResourcePool,
                 loaded_speed_factor: float,
                 rng: np.random.Generator) -> Tuple[str, str, List[str]]:
    """Pick loader minimising expected (path_time + queue_wait).
    Tie-break: shortest expected total cycle time (path + load + return path + dump).
    Returns (loader_id, loader_node, path_from_current).
    """
    best = None
    best_metric = (float("inf"), float("inf"))
    for lid, lcfg in res.loader_cfg.items():
        path = loader_paths.get((current_node, lcfg.node_id))
        if path is None:
            continue
        # estimate path time empty
        path_t = 0.0
        for u, v in zip(path[:-1], path[1:]):
            attrs = g_with_attrs[u][v]
            path_t += edge_time_min(attrs["distance_m"], attrs["max_speed_kph"],
                                     loaded=False, loaded_speed_factor=loaded_speed_factor,
                                     rng=rng, noise_cv=0.0)
        wait = _expected_loader_wait(res.loaders[lid], lcfg.mean_load_min)
        primary = path_t + wait
        if primary < best_metric[0] - 1e-9:
            best_metric = (primary, path_t)
            best = (lid, lcfg.node_id, path)
        elif abs(primary - best_metric[0]) < 1e-9 and path_t < best_metric[1]:
            best_metric = (primary, path_t)
            best = (lid, lcfg.node_id, path)
    return best  # type: ignore[return-value]


def truck_process(env: simpy.Environment,
                  truck_id: str,
                  payload_t: float,
                  empty_speed_factor: float,
                  loaded_speed_factor: float,
                  start_node: str,
                  topology: Topology,
                  g_with_attrs,
                  loader_paths: Dict[Tuple[str, str], Optional[List[str]]],
                  crusher_paths: Dict[Tuple[str, str], Optional[List[str]]],
                  res: ResourcePool,
                  scenario_cfg: dict,
                  shift_end_min: float,
                  recorder,
                  rng: np.random.Generator,
                  metrics: TruckMetrics):
    """Generator-based SimPy truck process."""
    current_node = start_node
    noise_cv = float(scenario_cfg.get("stochasticity", {}).get("travel_time_noise_cv", 0.10))
    loaded = False

    recorder.log(env.now, truck_id, "shift_start", location=current_node, loaded=False,
                  resource_id="")

    while env.now < shift_end_min:
        # 1. Pick loader (nearest available)
        pick = pick_loader(current_node, topology, g_with_attrs, loader_paths, res,
                            loaded_speed_factor, rng)
        if pick is None:
            recorder.log(env.now, truck_id, "no_route_to_loader", location=current_node,
                          loaded=False)
            break
        loader_id, loader_node, path_to_loader = pick
        loader_cfg = res.loader_cfg[loader_id]

        recorder.log(env.now, truck_id, "dispatched_to_loader",
                      location=current_node, loaded=False, resource_id=loader_id,
                      queue_length=len(res.loaders[loader_id].queue))

        # 2. Travel empty to loader (consume edges along path)
        cycle_start = env.now
        for u, v in zip(path_to_loader[:-1], path_to_loader[1:]):
            if env.now >= shift_end_min:
                break
            attrs = g_with_attrs[u][v]
            eid = attrs["edge_id"]
            t_edge = edge_time_min(attrs["distance_m"], attrs["max_speed_kph"],
                                    loaded=False, loaded_speed_factor=loaded_speed_factor,
                                    rng=rng, noise_cv=noise_cv)
            edge_res = res.edges.get(eid)
            if edge_res is not None:
                with edge_res.request() as req:
                    yield req
                    t0 = env.now
                    yield env.timeout(t_edge)
                    res.edge_busy_time[eid] += (env.now - t0)
            else:
                yield env.timeout(t_edge)
            metrics.busy_time_min += t_edge
            current_node = v
            recorder.log(env.now, truck_id, "edge_traversed", from_node=u, to_node=v,
                          location=v, loaded=False, resource_id=eid)

        if env.now >= shift_end_min:
            break

        recorder.log(env.now, truck_id, "arrive_loader", location=current_node,
                      loaded=False, resource_id=loader_id,
                      queue_length=len(res.loaders[loader_id].queue))

        # 3. Load
        t_q_start = env.now
        with res.loaders[loader_id].request() as req:
            yield req
            q_wait = env.now - t_q_start
            metrics.loader_queue_time_min += q_wait
            recorder.log(env.now, truck_id, "load_start", location=current_node,
                          loaded=False, resource_id=loader_id)
            t_load = truncated_normal(loader_cfg.mean_load_min, loader_cfg.sd_load_min, rng)
            t0 = env.now
            yield env.timeout(t_load)
            res.loader_busy_time[loader_id] += (env.now - t0)
            metrics.busy_time_min += t_load
            loaded = True
            recorder.log(env.now, truck_id, "load_end", location=current_node, loaded=True,
                          payload_tonnes=payload_t, resource_id=loader_id)

        if env.now >= shift_end_min:
            # truck loaded but shift may end during travel — let it try
            pass

        # 4. Travel loaded to crusher
        path_to_crusher = crusher_paths.get((current_node, "CRUSH"))
        if path_to_crusher is None:
            recorder.log(env.now, truck_id, "no_route_to_crusher", location=current_node,
                          loaded=True)
            break
        for u, v in zip(path_to_crusher[:-1], path_to_crusher[1:]):
            if env.now >= shift_end_min + 30:  # hard stop 30 min past shift end
                break
            attrs = g_with_attrs[u][v]
            eid = attrs["edge_id"]
            t_edge = edge_time_min(attrs["distance_m"], attrs["max_speed_kph"],
                                    loaded=True, loaded_speed_factor=loaded_speed_factor,
                                    rng=rng, noise_cv=noise_cv)
            edge_res = res.edges.get(eid)
            if edge_res is not None:
                with edge_res.request() as req:
                    yield req
                    t0 = env.now
                    yield env.timeout(t_edge)
                    res.edge_busy_time[eid] += (env.now - t0)
            else:
                yield env.timeout(t_edge)
            metrics.busy_time_min += t_edge
            current_node = v
            recorder.log(env.now, truck_id, "edge_traversed", from_node=u, to_node=v,
                          location=v, loaded=True, payload_tonnes=payload_t, resource_id=eid)

        recorder.log(env.now, truck_id, "arrive_crusher", location=current_node,
                      loaded=True, payload_tonnes=payload_t, resource_id="CRUSH",
                      queue_length=len(res.crusher.queue))

        # 5. Dump
        t_q_start = env.now
        with res.crusher.request() as req:
            yield req
            q_wait = env.now - t_q_start
            metrics.crusher_queue_time_min += q_wait
            recorder.log(env.now, truck_id, "dump_start", location=current_node, loaded=True,
                          payload_tonnes=payload_t, resource_id="CRUSH")
            t_dump = truncated_normal(res.crusher_cfg.mean_dump_min,
                                       res.crusher_cfg.sd_dump_min, rng)
            t0 = env.now
            yield env.timeout(t_dump)
            res.crusher_busy_time += (env.now - t0)
            metrics.busy_time_min += t_dump
            # Credit tonnes ONLY at dump_end — this is the throughput-of-record event
            metrics.tonnes_delivered += payload_t
            metrics.cycles_completed += 1
            metrics.cycle_times_min.append(env.now - cycle_start)
            recorder.log(env.now, truck_id, "dump_end", location=current_node, loaded=False,
                          payload_tonnes=payload_t, resource_id="CRUSH")
            loaded = False

    recorder.log(env.now, truck_id, "shift_end", location=current_node, loaded=loaded)
