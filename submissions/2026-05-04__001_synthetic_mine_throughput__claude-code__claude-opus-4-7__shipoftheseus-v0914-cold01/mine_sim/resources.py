"""SimPy resource pool: loaders, crusher, capacity-bounded edges, dump points."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Optional

import pandas as pd
import simpy


@dataclass
class LoaderConfig:
    loader_id: str
    node_id: str
    bucket_capacity_t: float
    mean_load_min: float
    sd_load_min: float


@dataclass
class DumpConfig:
    dump_id: str
    node_id: str
    mean_dump_min: float
    sd_dump_min: float


@dataclass
class ResourcePool:
    env: simpy.Environment
    loaders: Dict[str, simpy.Resource]
    loader_cfg: Dict[str, LoaderConfig]
    edges: Dict[str, simpy.Resource]              # edge_id -> Resource (only for capacity <= 10)
    edge_capacity: Dict[str, int]                 # edge_id -> capacity (full)
    crusher: simpy.Resource
    crusher_cfg: DumpConfig
    waste_dump: Optional[simpy.Resource] = None
    waste_cfg: Optional[DumpConfig] = None
    # Telemetry
    loader_busy_time: Dict[str, float] = field(default_factory=dict)
    crusher_busy_time: float = 0.0
    edge_busy_time: Dict[str, float] = field(default_factory=dict)


def build_resource_pool(env: simpy.Environment,
                        loaders_df: pd.DataFrame,
                        dump_df: pd.DataFrame,
                        edges_df: pd.DataFrame,
                        scenario_cfg: dict) -> ResourcePool:
    overrides_dump = scenario_cfg.get("dump_point_overrides", {}) or {}

    # Loaders
    loaders: Dict[str, simpy.Resource] = {}
    loader_cfg: Dict[str, LoaderConfig] = {}
    for _, r in loaders_df.iterrows():
        cap = int(r.get("capacity", 1))
        loaders[r["loader_id"]] = simpy.Resource(env, capacity=cap)
        loader_cfg[r["loader_id"]] = LoaderConfig(
            loader_id=r["loader_id"],
            node_id=r["node_id"],
            bucket_capacity_t=float(r["bucket_capacity_tonnes"]),
            mean_load_min=float(r["mean_load_time_min"]),
            sd_load_min=float(r["sd_load_time_min"]),
        )

    # Edges (only those with capacity <= 10 get a Resource)
    edges: Dict[str, simpy.Resource] = {}
    edge_capacity: Dict[str, int] = {}
    for _, r in edges_df.iterrows():
        cap = int(r["capacity"])
        eid = r["edge_id"]
        edge_capacity[eid] = cap
        if cap <= 10:
            edges[eid] = simpy.Resource(env, capacity=cap)

    # Crusher
    crusher_row = dump_df[dump_df["type"] == "crusher"].iloc[0]
    crusher_cfg = DumpConfig(
        dump_id=crusher_row["dump_id"],
        node_id=crusher_row["node_id"],
        mean_dump_min=float(crusher_row["mean_dump_time_min"]),
        sd_dump_min=float(crusher_row["sd_dump_time_min"]),
    )
    if crusher_cfg.dump_id in overrides_dump:
        ov = overrides_dump[crusher_cfg.dump_id]
        if "mean_dump_time_min" in ov:
            crusher_cfg.mean_dump_min = float(ov["mean_dump_time_min"])
        if "sd_dump_time_min" in ov:
            crusher_cfg.sd_dump_min = float(ov["sd_dump_time_min"])
    crusher_res = simpy.Resource(env, capacity=int(crusher_row["capacity"]))

    # Waste dump (optional)
    waste_res: Optional[simpy.Resource] = None
    waste_cfg: Optional[DumpConfig] = None
    waste_rows = dump_df[dump_df["type"] == "waste_dump"]
    if len(waste_rows) > 0:
        wr = waste_rows.iloc[0]
        waste_res = simpy.Resource(env, capacity=int(wr["capacity"]))
        waste_cfg = DumpConfig(
            dump_id=wr["dump_id"],
            node_id=wr["node_id"],
            mean_dump_min=float(wr["mean_dump_time_min"]),
            sd_dump_min=float(wr["sd_dump_time_min"]),
        )

    return ResourcePool(
        env=env,
        loaders=loaders,
        loader_cfg=loader_cfg,
        edges=edges,
        edge_capacity=edge_capacity,
        crusher=crusher_res,
        crusher_cfg=crusher_cfg,
        waste_dump=waste_res,
        waste_cfg=waste_cfg,
        loader_busy_time={lid: 0.0 for lid in loaders},
        edge_busy_time={eid: 0.0 for eid in edges},
    )
