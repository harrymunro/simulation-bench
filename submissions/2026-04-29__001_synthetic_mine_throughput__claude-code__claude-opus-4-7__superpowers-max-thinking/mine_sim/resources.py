"""SimPy resource pool: loaders, crusher, paired-bidirectional road locks."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import simpy

from mine_sim.topology import EDGE_TO_LOCK, DumpPoint, Edge, Loader


@dataclass
class ResourcePool:
    loaders: dict[str, simpy.Resource]
    crusher: simpy.Resource
    road_locks: dict[str, simpy.Resource]
    loader_service: dict[tuple[str, str], float]
    loader_node: dict[str, str]
    crusher_service: dict[str, float]
    crusher_node: str
    bucket_capacity_tonnes: dict[str, float] = field(default_factory=dict)


def _apply_loader_overrides(
    loaders: dict[str, Loader],
    overrides: dict[str, dict[str, Any]] | None,
) -> None:
    """Mutating helper: patches Loader fields per scenario override."""
    if not overrides:
        return
    for lid, patch in overrides.items():
        if lid not in loaders:
            raise KeyError(f"loader_overrides references unknown loader {lid!r}")
        loader = loaders[lid]
        for k, v in patch.items():
            if not hasattr(loader, k):
                raise KeyError(f"Loader has no attribute {k!r}")
            setattr(loader, k, v)


def build_resources(
    env: simpy.Environment,
    config: dict[str, Any],
    *,
    edges: dict[str, Edge],
    loaders: dict[str, Loader],
    dumps: dict[str, DumpPoint],
) -> ResourcePool:
    """Build SimPy resources for one replication.

    Caller is expected to have already applied scenario overrides on edges/nodes/dumps
    via `mine_sim.topology.apply_overrides`. Loader overrides (rare; reserved for
    future scenarios) are applied here.
    """
    _apply_loader_overrides(loaders, config.get("loader_overrides"))

    # --- Loaders -------------------------------------------------------------
    loader_resources: dict[str, simpy.Resource] = {}
    loader_service: dict[tuple[str, str], float] = {}
    loader_node: dict[str, str] = {}
    bucket_capacity: dict[str, float] = {}
    for lid, loader in loaders.items():
        loader_resources[lid] = simpy.Resource(env, capacity=int(loader.capacity))
        loader_service[(lid, "mean")] = float(loader.mean_load_time_min)
        loader_service[(lid, "sd")] = float(loader.sd_load_time_min)
        loader_node[lid] = loader.node_id
        bucket_capacity[lid] = float(loader.bucket_capacity_tonnes)

    # --- Crusher (the dump point of type "crusher") --------------------------
    crusher_dump = next(d for d in dumps.values() if d.type == "crusher")
    crusher = simpy.Resource(env, capacity=int(crusher_dump.capacity))
    crusher_service = {
        "mean": float(crusher_dump.mean_dump_time_min),
        "sd": float(crusher_dump.sd_dump_time_min),
    }
    crusher_node = crusher_dump.node_id

    # --- Road locks ----------------------------------------------------------
    # Group edges by lock id; create a lock only if at least one member edge
    # (post-override) has effective capacity == 1 AND is not closed.
    lock_members: dict[str, list[Edge]] = {}
    for eid, edge in edges.items():
        lock_id = EDGE_TO_LOCK.get(eid)
        if lock_id is None:
            continue
        lock_members.setdefault(lock_id, []).append(edge)

    road_locks: dict[str, simpy.Resource] = {}
    for lock_id, members in lock_members.items():
        if any(m.capacity == 1 and not m.closed for m in members):
            road_locks[lock_id] = simpy.Resource(env, capacity=1)

    return ResourcePool(
        loaders=loader_resources,
        crusher=crusher,
        road_locks=road_locks,
        loader_service=loader_service,
        loader_node=loader_node,
        crusher_service=crusher_service,
        crusher_node=crusher_node,
        bucket_capacity_tonnes=bucket_capacity,
    )
