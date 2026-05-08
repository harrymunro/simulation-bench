"""Loaders for the static input data files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class Node:
    node_id: str
    node_name: str
    node_type: str
    x_m: float
    y_m: float
    z_m: float
    capacity: Optional[int]
    service_time_mean_min: Optional[float]
    service_time_sd_min: Optional[float]
    metadata: str


@dataclass(frozen=True)
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    max_speed_kph: float
    road_type: str
    capacity: int
    closed: bool
    metadata: str


@dataclass(frozen=True)
class Truck:
    truck_id: str
    payload_tonnes: float
    empty_speed_factor: float
    loaded_speed_factor: float
    availability: float
    start_node: str


@dataclass(frozen=True)
class Loader:
    loader_id: str
    node_id: str
    capacity: int
    bucket_capacity_tonnes: float
    mean_load_time_min: float
    sd_load_time_min: float
    availability: float


@dataclass(frozen=True)
class DumpPoint:
    dump_id: str
    node_id: str
    type: str
    capacity: int
    mean_dump_time_min: float
    sd_dump_time_min: float


@dataclass(frozen=True)
class StaticData:
    nodes: Dict[str, Node]
    edges: Dict[str, Edge]
    trucks: List[Truck]
    loaders: Dict[str, Loader]
    dump_points: Dict[str, DumpPoint]


def _coerce_optional_int(v) -> Optional[int]:
    if pd.isna(v):
        return None
    return int(v)


def _coerce_optional_float(v) -> Optional[float]:
    if pd.isna(v):
        return None
    return float(v)


def _coerce_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() in {"true", "1", "yes", "y"}
    return bool(v)


def load_static_data(data_dir: Path) -> StaticData:
    """Read the static CSV inputs into typed dataclasses."""
    data_dir = Path(data_dir)

    nodes_df = pd.read_csv(data_dir / "nodes.csv").dropna(how="all")
    edges_df = pd.read_csv(data_dir / "edges.csv").dropna(how="all")
    trucks_df = pd.read_csv(data_dir / "trucks.csv").dropna(how="all")
    loaders_df = pd.read_csv(data_dir / "loaders.csv").dropna(how="all")
    dumps_df = pd.read_csv(data_dir / "dump_points.csv").dropna(how="all")

    nodes: Dict[str, Node] = {}
    for _, r in nodes_df.iterrows():
        node = Node(
            node_id=str(r["node_id"]),
            node_name=str(r["node_name"]),
            node_type=str(r["node_type"]),
            x_m=float(r["x_m"]),
            y_m=float(r["y_m"]),
            z_m=float(r["z_m"]),
            capacity=_coerce_optional_int(r.get("capacity")),
            service_time_mean_min=_coerce_optional_float(r.get("service_time_mean_min")),
            service_time_sd_min=_coerce_optional_float(r.get("service_time_sd_min")),
            metadata=str(r.get("metadata", "")) if pd.notna(r.get("metadata")) else "",
        )
        nodes[node.node_id] = node

    edges: Dict[str, Edge] = {}
    for _, r in edges_df.iterrows():
        edge = Edge(
            edge_id=str(r["edge_id"]),
            from_node=str(r["from_node"]),
            to_node=str(r["to_node"]),
            distance_m=float(r["distance_m"]),
            max_speed_kph=float(r["max_speed_kph"]),
            road_type=str(r["road_type"]),
            capacity=int(r["capacity"]),
            closed=_coerce_bool(r["closed"]),
            metadata=str(r.get("metadata", "")) if pd.notna(r.get("metadata")) else "",
        )
        edges[edge.edge_id] = edge

    trucks: List[Truck] = []
    for _, r in trucks_df.iterrows():
        trucks.append(
            Truck(
                truck_id=str(r["truck_id"]),
                payload_tonnes=float(r["payload_tonnes"]),
                empty_speed_factor=float(r["empty_speed_factor"]),
                loaded_speed_factor=float(r["loaded_speed_factor"]),
                availability=float(r["availability"]),
                start_node=str(r["start_node"]),
            )
        )

    loaders: Dict[str, Loader] = {}
    for _, r in loaders_df.iterrows():
        loader = Loader(
            loader_id=str(r["loader_id"]),
            node_id=str(r["node_id"]),
            capacity=int(r["capacity"]),
            bucket_capacity_tonnes=float(r["bucket_capacity_tonnes"]),
            mean_load_time_min=float(r["mean_load_time_min"]),
            sd_load_time_min=float(r["sd_load_time_min"]),
            availability=float(r["availability"]),
        )
        loaders[loader.loader_id] = loader

    dump_points: Dict[str, DumpPoint] = {}
    for _, r in dumps_df.iterrows():
        dp = DumpPoint(
            dump_id=str(r["dump_id"]),
            node_id=str(r["node_id"]),
            type=str(r["type"]),
            capacity=int(r["capacity"]),
            mean_dump_time_min=float(r["mean_dump_time_min"]),
            sd_dump_time_min=float(r["sd_dump_time_min"]),
        )
        dump_points[dp.dump_id] = dp

    return StaticData(
        nodes=nodes,
        edges=edges,
        trucks=trucks,
        loaders=loaders,
        dump_points=dump_points,
    )
