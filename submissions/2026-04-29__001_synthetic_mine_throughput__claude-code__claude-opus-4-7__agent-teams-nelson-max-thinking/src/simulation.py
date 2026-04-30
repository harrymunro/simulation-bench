"""SimPy discrete-event simulation of the synthetic mine.

Trucks are SimPy processes that drive empty to a chosen loader, queue and
load, drive loaded to the crusher, queue and dump, then repeat. Loaders,
the crusher, and capacity-constrained road edges are SimPy resources that
serialise truck access. Service and travel times are stochastic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np
import simpy

from .topology import Topology, edge_lookup, shortest_time_path, travel_time_min


_LOAD_NODE_TO_LOADER: dict[str, str] = {}  # populated per-run
_DEFAULT_EMPTY_SPEED_FACTOR = 1.0
_DEFAULT_LOADED_SPEED_FACTOR = 0.85
_DEFAULT_PAYLOAD_TONNES = 100.0
_DEFAULT_TRAVEL_NOISE_CV = 0.10
_TRAVEL_NOISE_FLOOR = 0.1
_SERVICE_TIME_TRUNC_LOWER_FRAC = 0.5
_SERVICE_TIME_TRUNC_UPPER_FRAC = 2.0
_SERVICE_TIME_FLOOR_MIN = 0.5
_GRACE_MINUTES = 60.0  # let in-flight cycles complete (but only count by start time)


@dataclass
class SimResult:
    events: list[dict]
    cycles: list[dict]
    shift_minutes: float
    scenario_id: str
    replication: int
    seed: int
    fleet: dict[str, Any]
    loader_busy_min: dict[str, float]
    crusher_busy_min: float
    edge_busy_min: dict[str, float]
    warmup_minutes: float = 0.0
    # Each queue-wait list holds (request_time_min, wait_min) tuples so
    # downstream metrics can filter to the post-warmup window.
    loader_queue_waits: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    crusher_queue_waits: list[tuple[float, float]] = field(default_factory=list)
    edge_queue_waits: dict[str, list[tuple[float, float]]] = field(default_factory=dict)
    truck_busy_min: dict[str, float] = field(default_factory=dict)
    truck_queue_wait_min: dict[str, float] = field(default_factory=dict)
    truck_queue_wait_min_post_warmup: dict[str, float] = field(default_factory=dict)


class _ResourceTracker:
    """Wraps a SimPy resource and accumulates busy minutes within ``[warmup_end, shift_end]``.

    Busy minutes are accumulated as ``in_use / capacity * elapsed``. Time before
    ``warmup_end`` is excluded from utilisation, and time after ``shift_end`` is
    excluded so post-shift activity (during the grace window) does not inflate
    utilisation calculations.
    """

    def __init__(
        self,
        env: simpy.Environment,
        resource: simpy.Resource,
        capacity: int,
        shift_end: float,
        warmup_end: float = 0.0,
    ):
        self.env = env
        self.resource = resource
        self.capacity = capacity
        self.shift_end = shift_end
        self.warmup_end = warmup_end
        self._busy_minutes = 0.0
        self._last_change_time = 0.0
        self._in_use = 0

    def _accumulate_to(self, now: float) -> None:
        capped_now = min(now, self.shift_end)
        window_start = max(self._last_change_time, self.warmup_end)
        elapsed = capped_now - window_start
        if elapsed > 0 and self._in_use > 0:
            self._busy_minutes += elapsed * (self._in_use / self.capacity)
        self._last_change_time = capped_now

    def acquire_event(self) -> None:
        self._accumulate_to(self.env.now)
        self._in_use += 1

    def release_event(self) -> None:
        self._accumulate_to(self.env.now)
        self._in_use = max(0, self._in_use - 1)

    def busy_minutes(self, until: float) -> float:
        self._accumulate_to(until)
        return self._busy_minutes

    def queue_length(self) -> int:
        return len(self.resource.queue)


def _truncated_normal_min(
    rng: np.random.Generator, mean: float, sd: float
) -> float:
    """Sample a service time from a truncated normal, bounded above floor."""
    lower = max(_SERVICE_TIME_FLOOR_MIN, _SERVICE_TIME_TRUNC_LOWER_FRAC * mean)
    upper = _SERVICE_TIME_TRUNC_UPPER_FRAC * mean
    for _ in range(20):
        x = rng.normal(mean, sd)
        if lower <= x <= upper:
            return float(x)
    # Fall back to a clipped sample if rejection sampling fails repeatedly.
    return float(np.clip(rng.normal(mean, sd), lower, upper))


def _wait_within_window(
    request_time: float, wait: float, window_start: float, window_end: float
) -> float:
    """Return the portion of ``[request_time, request_time+wait]`` that falls
    inside ``[window_start, window_end]``.

    Used to attribute queue-wait time to the post-warmup, in-shift window for
    per-truck utilisation accounting.
    """
    end = request_time + wait
    overlap_start = max(request_time, window_start)
    overlap_end = min(end, window_end)
    return max(0.0, overlap_end - overlap_start)


def _noisy_travel_minutes(
    rng: np.random.Generator, base_min: float, cv: float
) -> float:
    """Multiply base travel time by a noise factor (truncated lognormal-ish).

    Uses 1 + cv * standard normal, floored at 0.1 to avoid negative or zero
    travel times.
    """
    if cv <= 0:
        return base_min
    factor = 1.0 + cv * float(rng.standard_normal())
    factor = max(_TRAVEL_NOISE_FLOOR, factor)
    return base_min * factor


def _select_loader(
    topology: Topology,
    loader_ids: list[str],
    loader_node: dict[str, str],
    loader_resources: dict[str, _ResourceTracker],
    loader_mean_load_min: dict[str, float],
    loaded_paths: dict[str, list[str]],
    pending_at_loader: dict[str, int],
    truck_node: str,
    empty_speed_factor: float,
    loaded_speed_factor: float,
) -> str:
    """Score loaders by expected cycle time and pick the best (lowest score).

    Uses ``pending_at_loader`` (trucks dispatched to but not yet released by
    the loader) plus current SimPy queue/users as the queue depth estimate.
    This balances the initial dispatch when multiple trucks decide simultaneously.
    """
    scores: list[tuple[float, float, str]] = []
    for lid in loader_ids:
        ln = loader_node[lid]
        empty_path = shortest_time_path(
            topology, truck_node, ln, loaded=False, exclude_closed=True
        )
        empty_min = _path_base_minutes(topology, empty_path, empty_speed_factor)
        loaded_path = loaded_paths[lid]
        loaded_min = _path_base_minutes(topology, loaded_path, loaded_speed_factor)
        tracker = loader_resources[lid]
        live_queue = tracker.queue_length() + len(tracker.resource.users)
        pending = pending_at_loader.get(lid, 0)
        # pending already includes any truck whose request is in the queue/users,
        # so use the max of the two views to avoid double-counting while also
        # not under-counting trucks still en route.
        queue_len = max(live_queue, pending)
        wait_estimate = queue_len * loader_mean_load_min[lid]
        cycle_score = empty_min + wait_estimate + loaded_min
        scores.append((cycle_score, empty_min, lid))
    scores.sort()
    return scores[0][2]


def _path_base_minutes(
    topology: Topology, path: list[str], speed_factor: float
) -> float:
    if len(path) < 2:
        return 0.0
    total = 0.0
    for u, v in zip(path[:-1], path[1:]):
        e = edge_lookup(topology, u, v)
        total += travel_time_min(e["distance_m"], e["max_speed_kph"], speed_factor)
    return total


def _resolve_dump_params(scenario: dict[str, Any], topology: Topology) -> tuple[float, float]:
    """Return (mean_dump_time_min, sd_dump_time_min) for D_CRUSH after overrides."""
    df = topology.dump_points_df
    row = df[df["dump_id"] == "D_CRUSH"]
    if row.empty:
        raise ValueError("D_CRUSH dump point not found in topology")
    mean_min = float(row.iloc[0]["mean_dump_time_min"])
    sd_min = float(row.iloc[0]["sd_dump_time_min"])
    return mean_min, sd_min


def run_simulation(
    topology: Topology,
    scenario: dict[str, Any],
    replication: int,
    seed: int,
) -> SimResult:
    """Run a single replication of the mine simulation and return raw event/state data."""
    sim_cfg = scenario.get("simulation", {})
    shift_minutes = float(sim_cfg.get("shift_length_hours", 8)) * 60.0
    warmup_minutes = float(sim_cfg.get("warmup_minutes", 0) or 0)
    if warmup_minutes < 0:
        raise ValueError(f"warmup_minutes must be >= 0, got {warmup_minutes}")
    if warmup_minutes >= shift_minutes:
        raise ValueError(
            f"warmup_minutes ({warmup_minutes}) must be less than shift "
            f"({shift_minutes})"
        )

    stoch_cfg = scenario.get("stochasticity", {})
    travel_cv = float(stoch_cfg.get("travel_time_noise_cv", _DEFAULT_TRAVEL_NOISE_CV))

    fleet_cfg = scenario.get("fleet", {})
    truck_count = int(fleet_cfg.get("truck_count", len(topology.trucks_df)))

    trucks_df = topology.trucks_df.head(truck_count)
    if trucks_df.empty:
        raise ValueError("Scenario specifies zero trucks; nothing to simulate")

    loaders_df = topology.loaders_df
    loader_ids = loaders_df["loader_id"].tolist()
    loader_node = dict(zip(loaders_df["loader_id"], loaders_df["node_id"]))
    loader_capacity = dict(zip(loaders_df["loader_id"], loaders_df["capacity"].astype(int)))
    loader_mean_load_min = dict(
        zip(loaders_df["loader_id"], loaders_df["mean_load_time_min"].astype(float))
    )
    loader_sd_load_min = dict(
        zip(loaders_df["loader_id"], loaders_df["sd_load_time_min"].astype(float))
    )

    crusher_node_id = "CRUSH"
    dump_mean, dump_sd = _resolve_dump_params(scenario, topology)

    # Pre-compute loaded paths from each loader to the crusher (route doesn't change).
    loaded_paths: dict[str, list[str]] = {
        lid: shortest_time_path(topology, loader_node[lid], crusher_node_id, loaded=True)
        for lid in loader_ids
    }

    env = simpy.Environment()

    # Build resources
    loader_resources: dict[str, _ResourceTracker] = {}
    for lid in loader_ids:
        cap = max(1, int(loader_capacity[lid]))
        loader_resources[lid] = _ResourceTracker(
            env,
            simpy.PriorityResource(env, capacity=cap),
            cap,
            shift_minutes,
            warmup_minutes,
        )

    crusher_resource = _ResourceTracker(
        env, simpy.Resource(env, capacity=1), 1, shift_minutes, warmup_minutes
    )

    edge_resources: dict[str, _ResourceTracker] = {}
    for _, edge_row in topology.edges_df.iterrows():
        if not bool(edge_row["is_capacity_constrained"]):
            continue
        if bool(edge_row["closed"]):
            continue
        eid = str(edge_row["edge_id"])
        cap = max(1, int(edge_row["capacity"]))
        edge_resources[eid] = _ResourceTracker(
            env,
            simpy.Resource(env, capacity=cap),
            cap,
            shift_minutes,
            warmup_minutes,
        )

    # RNG: master seed -> per-truck child seed sequences for independence.
    seed_seq = np.random.SeedSequence(seed)
    truck_seed_seqs = seed_seq.spawn(len(trucks_df) + 1)
    dispatcher_rng = np.random.default_rng(truck_seed_seqs[0])

    events: list[dict] = []
    cycles: list[dict] = []
    loader_queue_waits: dict[str, list[tuple[float, float]]] = {
        lid: [] for lid in loader_ids
    }
    crusher_queue_waits: list[tuple[float, float]] = []
    edge_queue_waits: dict[str, list[tuple[float, float]]] = {
        eid: [] for eid in edge_resources
    }
    truck_busy_min: dict[str, float] = {}
    truck_queue_wait_min: dict[str, float] = {}
    truck_queue_wait_min_post_warmup: dict[str, float] = {}
    pending_at_loader: dict[str, int] = {lid: 0 for lid in loader_ids}

    scenario_id = str(scenario.get("scenario_id", "unknown"))

    def _record_event(
        time_min: float,
        truck_id: str,
        event_type: str,
        from_node: str | None = None,
        to_node: str | None = None,
        location: str | None = None,
        loaded: bool = False,
        payload_tonnes: float = 0.0,
        resource_id: str | None = None,
        queue_length: int = 0,
    ) -> None:
        events.append(
            {
                "time_min": round(time_min, 4),
                "replication": replication,
                "scenario_id": scenario_id,
                "truck_id": truck_id,
                "event_type": event_type,
                "from_node": from_node,
                "to_node": to_node,
                "location": location,
                "loaded": loaded,
                "payload_tonnes": payload_tonnes,
                "resource_id": resource_id,
                "queue_length": queue_length,
            }
        )

    def _traverse_edge(
        truck_id: str,
        from_node: str,
        to_node: str,
        speed_factor: float,
        loaded: bool,
        rng: np.random.Generator,
    ):
        e = edge_lookup(topology, from_node, to_node)
        eid = str(e["edge_id"])
        base_min = travel_time_min(e["distance_m"], e["max_speed_kph"], speed_factor)
        actual_min = _noisy_travel_minutes(rng, base_min, travel_cv)
        is_constrained = bool(e["is_capacity_constrained"])

        if is_constrained and eid in edge_resources:
            tracker = edge_resources[eid]
            req_time = env.now
            _record_event(
                env.now,
                truck_id,
                "edge_request",
                from_node=from_node,
                to_node=to_node,
                location=from_node,
                loaded=loaded,
                resource_id=eid,
                queue_length=tracker.queue_length(),
            )
            req = tracker.resource.request()
            yield req
            wait = env.now - req_time
            edge_queue_waits[eid].append((req_time, wait))
            truck_queue_wait_min[truck_id] = (
                truck_queue_wait_min.get(truck_id, 0.0) + wait
            )
            truck_queue_wait_min_post_warmup[truck_id] = (
                truck_queue_wait_min_post_warmup.get(truck_id, 0.0)
                + _wait_within_window(req_time, wait, warmup_minutes, shift_minutes)
            )
            tracker.acquire_event()
            _record_event(
                env.now,
                truck_id,
                "edge_enter",
                from_node=from_node,
                to_node=to_node,
                location=from_node,
                loaded=loaded,
                resource_id=eid,
                queue_length=tracker.queue_length(),
            )
            yield env.timeout(actual_min)
            tracker.release_event()
            tracker.resource.release(req)
            _record_event(
                env.now,
                truck_id,
                "edge_exit",
                from_node=from_node,
                to_node=to_node,
                location=to_node,
                loaded=loaded,
                resource_id=eid,
            )
        else:
            _record_event(
                env.now,
                truck_id,
                "edge_enter",
                from_node=from_node,
                to_node=to_node,
                location=from_node,
                loaded=loaded,
                resource_id=eid,
            )
            yield env.timeout(actual_min)
            _record_event(
                env.now,
                truck_id,
                "edge_exit",
                from_node=from_node,
                to_node=to_node,
                location=to_node,
                loaded=loaded,
                resource_id=eid,
            )

    def _drive_path(
        truck_id: str,
        path: list[str],
        speed_factor: float,
        loaded: bool,
        rng: np.random.Generator,
    ):
        for u, v in zip(path[:-1], path[1:]):
            yield from _traverse_edge(truck_id, u, v, speed_factor, loaded, rng)

    def _truck_process(truck_id: str, start_node: str, payload_tonnes: float, rng: np.random.Generator):
        current_node = start_node
        empty_factor = _DEFAULT_EMPTY_SPEED_FACTOR
        loaded_factor = _DEFAULT_LOADED_SPEED_FACTOR
        truck_busy_start = env.now
        truck_queue_wait_min[truck_id] = 0.0
        truck_queue_wait_min_post_warmup[truck_id] = 0.0

        try:
            while env.now < shift_minutes:
                cycle_start = env.now
                # 1. Dispatch decision
                chosen_loader = _select_loader(
                    topology,
                    loader_ids,
                    loader_node,
                    loader_resources,
                    loader_mean_load_min,
                    loaded_paths,
                    pending_at_loader,
                    current_node,
                    empty_factor,
                    loaded_factor,
                )
                pending_at_loader[chosen_loader] += 1
                ln = loader_node[chosen_loader]
                _record_event(
                    env.now,
                    truck_id,
                    "dispatch",
                    from_node=current_node,
                    to_node=ln,
                    location=current_node,
                    loaded=False,
                    resource_id=chosen_loader,
                )
                dispatch_time = env.now

                # 2. Drive empty to loader
                empty_path = shortest_time_path(
                    topology, current_node, ln, loaded=False, exclude_closed=True
                )
                yield from _drive_path(truck_id, empty_path, empty_factor, False, rng)
                current_node = ln

                # 3. Queue and acquire loader
                loader_tracker = loader_resources[chosen_loader]
                _record_event(
                    env.now,
                    truck_id,
                    "arrive_loader",
                    location=ln,
                    loaded=False,
                    resource_id=chosen_loader,
                    queue_length=loader_tracker.queue_length(),
                )
                req_time = env.now
                req = loader_tracker.resource.request(priority=0)
                yield req
                wait = env.now - req_time
                loader_queue_waits[chosen_loader].append((req_time, wait))
                truck_queue_wait_min[truck_id] = (
                    truck_queue_wait_min.get(truck_id, 0.0) + wait
                )
                truck_queue_wait_min_post_warmup[truck_id] = (
                    truck_queue_wait_min_post_warmup.get(truck_id, 0.0)
                    + _wait_within_window(
                        req_time, wait, warmup_minutes, shift_minutes
                    )
                )
                loader_tracker.acquire_event()

                # 4. Load
                load_time = _truncated_normal_min(
                    rng,
                    loader_mean_load_min[chosen_loader],
                    loader_sd_load_min[chosen_loader],
                )
                _record_event(
                    env.now,
                    truck_id,
                    "load_start",
                    location=ln,
                    loaded=False,
                    resource_id=chosen_loader,
                )
                yield env.timeout(load_time)
                _record_event(
                    env.now,
                    truck_id,
                    "load_end",
                    location=ln,
                    loaded=True,
                    payload_tonnes=payload_tonnes,
                    resource_id=chosen_loader,
                )

                # 5. Release loader, depart loaded
                loader_tracker.release_event()
                loader_tracker.resource.release(req)
                pending_at_loader[chosen_loader] = max(
                    0, pending_at_loader[chosen_loader] - 1
                )
                _record_event(
                    env.now,
                    truck_id,
                    "depart_loader",
                    from_node=ln,
                    to_node=crusher_node_id,
                    location=ln,
                    loaded=True,
                    payload_tonnes=payload_tonnes,
                    resource_id=chosen_loader,
                )

                # 6. Drive loaded to crusher
                loaded_path = loaded_paths[chosen_loader]
                yield from _drive_path(truck_id, loaded_path, loaded_factor, True, rng)
                current_node = crusher_node_id

                # 7. Queue and acquire crusher
                _record_event(
                    env.now,
                    truck_id,
                    "arrive_crusher",
                    location=crusher_node_id,
                    loaded=True,
                    payload_tonnes=payload_tonnes,
                    resource_id="D_CRUSH",
                    queue_length=crusher_resource.queue_length(),
                )
                cr_req_time = env.now
                cr_req = crusher_resource.resource.request()
                yield cr_req
                cr_wait = env.now - cr_req_time
                crusher_queue_waits.append((cr_req_time, cr_wait))
                truck_queue_wait_min[truck_id] = (
                    truck_queue_wait_min.get(truck_id, 0.0) + cr_wait
                )
                truck_queue_wait_min_post_warmup[truck_id] = (
                    truck_queue_wait_min_post_warmup.get(truck_id, 0.0)
                    + _wait_within_window(
                        cr_req_time, cr_wait, warmup_minutes, shift_minutes
                    )
                )
                crusher_resource.acquire_event()
                dump_start_time = env.now

                # 8. Dump
                dump_time = _truncated_normal_min(rng, dump_mean, dump_sd)
                _record_event(
                    env.now,
                    truck_id,
                    "dump_start",
                    location=crusher_node_id,
                    loaded=True,
                    payload_tonnes=payload_tonnes,
                    resource_id="D_CRUSH",
                )
                yield env.timeout(dump_time)
                dump_end_time = env.now
                _record_event(
                    dump_end_time,
                    truck_id,
                    "dump_end",
                    location=crusher_node_id,
                    loaded=False,
                    payload_tonnes=payload_tonnes,
                    resource_id="D_CRUSH",
                )

                cycles.append(
                    {
                        "truck_id": truck_id,
                        "loader_id": chosen_loader,
                        "dispatch_time": dispatch_time,
                        "load_start": dump_start_time - dump_time,
                        "dump_start": dump_start_time,
                        "dump_end": dump_end_time,
                        "payload_tonnes": payload_tonnes,
                        "cycle_time_min": dump_end_time - dispatch_time,
                    }
                )

                # 9. Release crusher
                crusher_resource.release_event()
                crusher_resource.resource.release(cr_req)
                _record_event(
                    env.now,
                    truck_id,
                    "depart_crusher",
                    location=crusher_node_id,
                    loaded=False,
                    resource_id="D_CRUSH",
                )

                # If shift over and we are mid-cycle returning, stop scheduling.
                if env.now >= shift_minutes:
                    break
        finally:
            # Active time within the post-warmup, in-shift window.
            window_start = max(truck_busy_start, warmup_minutes)
            window_end = min(env.now, shift_minutes)
            shift_active_min = max(0.0, window_end - window_start)
            queue_within_shift = min(
                truck_queue_wait_min_post_warmup.get(truck_id, 0.0),
                shift_active_min,
            )
            truck_busy_min[truck_id] = max(0.0, shift_active_min - queue_within_shift)

    # Spawn truck processes
    for i, (_, row) in enumerate(trucks_df.iterrows()):
        truck_id = str(row["truck_id"])
        payload = float(row.get("payload_tonnes", _DEFAULT_PAYLOAD_TONNES))
        start_node = str(row["start_node"])
        truck_rng = np.random.default_rng(truck_seed_seqs[i + 1])
        env.process(_truck_process(truck_id, start_node, payload, truck_rng))

    # Run with grace period so trucks mid-dump can finish; metrics will respect strict shift.
    env.run(until=shift_minutes + _GRACE_MINUTES)

    # Finalise busy minutes (cap at shift end).
    final_t = min(env.now, shift_minutes)
    loader_busy_min = {
        lid: tracker.busy_minutes(final_t) for lid, tracker in loader_resources.items()
    }
    crusher_busy_min = crusher_resource.busy_minutes(final_t)
    edge_busy_min = {
        eid: tracker.busy_minutes(final_t) for eid, tracker in edge_resources.items()
    }

    return SimResult(
        events=events,
        cycles=cycles,
        shift_minutes=shift_minutes,
        scenario_id=scenario_id,
        replication=replication,
        seed=seed,
        fleet={"truck_count": int(truck_count)},
        loader_busy_min=loader_busy_min,
        crusher_busy_min=crusher_busy_min,
        edge_busy_min=edge_busy_min,
        warmup_minutes=warmup_minutes,
        loader_queue_waits=loader_queue_waits,
        crusher_queue_waits=crusher_queue_waits,
        edge_queue_waits=edge_queue_waits,
        truck_busy_min=truck_busy_min,
        truck_queue_wait_min=truck_queue_wait_min,
        truck_queue_wait_min_post_warmup=truck_queue_wait_min_post_warmup,
    )
