"""Topology loader, routing, and scenario application for the synthetic mine.

Topology is treated as immutable: ``apply_scenario`` returns a NEW Topology with
overrides applied. The underlying NetworkX graph and pandas DataFrames are
deep-copied (or rebuilt) so callers can safely keep references to the original.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import pandas as pd


_CAPACITY_THRESHOLD = 999
_DEFAULT_LOADED_SPEED_FACTOR = 0.85
_DEFAULT_EMPTY_SPEED_FACTOR = 1.0


@dataclass(frozen=True)
class Topology:
    G: nx.DiGraph
    nodes_df: pd.DataFrame
    edges_df: pd.DataFrame
    trucks_df: pd.DataFrame
    loaders_df: pd.DataFrame
    dump_points_df: pd.DataFrame


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    s = str(value).strip().lower()
    return s in {"true", "1", "yes", "y", "t"}


def _annotate_edges(edges_df: pd.DataFrame) -> pd.DataFrame:
    df = edges_df.copy()
    df["closed"] = df["closed"].apply(_coerce_bool)
    df["capacity"] = df["capacity"].astype(int)
    df["distance_m"] = df["distance_m"].astype(float)
    df["max_speed_kph"] = df["max_speed_kph"].astype(float)
    df["is_capacity_constrained"] = df["capacity"] < _CAPACITY_THRESHOLD
    return df


def _build_graph(nodes_df: pd.DataFrame, edges_df: pd.DataFrame) -> nx.DiGraph:
    G = nx.DiGraph()
    for _, row in nodes_df.iterrows():
        G.add_node(
            row["node_id"],
            node_name=row.get("node_name"),
            node_type=row.get("node_type"),
            x_m=float(row.get("x_m", 0.0)),
            y_m=float(row.get("y_m", 0.0)),
            z_m=float(row.get("z_m", 0.0)),
            capacity=row.get("capacity"),
            service_time_mean_min=row.get("service_time_mean_min"),
            service_time_sd_min=row.get("service_time_sd_min"),
            metadata=row.get("metadata"),
        )
    for _, row in edges_df.iterrows():
        G.add_edge(
            row["from_node"],
            row["to_node"],
            edge_id=row["edge_id"],
            distance_m=float(row["distance_m"]),
            max_speed_kph=float(row["max_speed_kph"]),
            road_type=row.get("road_type"),
            capacity=int(row["capacity"]),
            closed=_coerce_bool(row.get("closed", False)),
            is_capacity_constrained=bool(row["is_capacity_constrained"]),
            metadata=row.get("metadata"),
        )
    return G


def load_topology(data_dir: Path) -> Topology:
    data_dir = Path(data_dir)
    nodes_df = pd.read_csv(data_dir / "nodes.csv")
    edges_df = pd.read_csv(data_dir / "edges.csv")
    trucks_df = pd.read_csv(data_dir / "trucks.csv")
    loaders_df = pd.read_csv(data_dir / "loaders.csv")
    dump_points_df = pd.read_csv(data_dir / "dump_points.csv")

    edges_df = _annotate_edges(edges_df)
    G = _build_graph(nodes_df, edges_df)

    return Topology(
        G=G,
        nodes_df=nodes_df.reset_index(drop=True),
        edges_df=edges_df.reset_index(drop=True),
        trucks_df=trucks_df.reset_index(drop=True),
        loaders_df=loaders_df.reset_index(drop=True),
        dump_points_df=dump_points_df.reset_index(drop=True),
    )


def _apply_edge_overrides(
    edges_df: pd.DataFrame, overrides: dict[str, dict[str, Any]]
) -> pd.DataFrame:
    df = edges_df.copy()
    for edge_id, fields in overrides.items():
        mask = df["edge_id"] == edge_id
        if not mask.any():
            raise KeyError(f"Unknown edge_id in edge_overrides: {edge_id}")
        for field, value in fields.items():
            if field == "closed":
                df.loc[mask, field] = _coerce_bool(value)
            elif field == "capacity":
                df.loc[mask, field] = int(value)
            elif field == "max_speed_kph":
                df.loc[mask, field] = float(value)
            else:
                df.loc[mask, field] = value
    df["is_capacity_constrained"] = df["capacity"] < _CAPACITY_THRESHOLD
    return df


def _apply_node_overrides(
    nodes_df: pd.DataFrame, overrides: dict[str, dict[str, Any]]
) -> pd.DataFrame:
    df = nodes_df.copy()
    for node_id, fields in overrides.items():
        mask = df["node_id"] == node_id
        if not mask.any():
            raise KeyError(f"Unknown node_id in node_overrides: {node_id}")
        for field, value in fields.items():
            df.loc[mask, field] = value
    return df


def _apply_dump_overrides(
    dump_points_df: pd.DataFrame, overrides: dict[str, dict[str, Any]]
) -> pd.DataFrame:
    df = dump_points_df.copy()
    for dump_id, fields in overrides.items():
        mask = df["dump_id"] == dump_id
        if not mask.any():
            raise KeyError(f"Unknown dump_id in dump_point_overrides: {dump_id}")
        for field, value in fields.items():
            df.loc[mask, field] = value
    return df


def apply_scenario(topology: Topology, scenario: dict[str, Any]) -> Topology:
    edges_df = topology.edges_df
    nodes_df = topology.nodes_df
    dump_points_df = topology.dump_points_df

    edge_overrides = scenario.get("edge_overrides") or {}
    if edge_overrides:
        edges_df = _apply_edge_overrides(edges_df, edge_overrides)

    node_overrides = scenario.get("node_overrides") or {}
    if node_overrides:
        nodes_df = _apply_node_overrides(nodes_df, node_overrides)

    dump_overrides = scenario.get("dump_point_overrides") or {}
    if dump_overrides:
        dump_points_df = _apply_dump_overrides(dump_points_df, dump_overrides)

    G = _build_graph(nodes_df, edges_df)

    return Topology(
        G=G,
        nodes_df=nodes_df.reset_index(drop=True),
        edges_df=edges_df.reset_index(drop=True),
        trucks_df=topology.trucks_df.copy().reset_index(drop=True),
        loaders_df=topology.loaders_df.copy().reset_index(drop=True),
        dump_points_df=dump_points_df.reset_index(drop=True),
    )


def travel_time_min(
    distance_m: float, max_speed_kph: float, speed_factor: float
) -> float:
    if max_speed_kph <= 0 or speed_factor <= 0:
        raise ValueError(
            f"Non-positive speed: max_speed_kph={max_speed_kph}, speed_factor={speed_factor}"
        )
    return distance_m / 1000.0 / (max_speed_kph * speed_factor) * 60.0


def _routing_view(G: nx.DiGraph, exclude_closed: bool) -> nx.DiGraph:
    if not exclude_closed:
        return G
    H = nx.DiGraph()
    H.add_nodes_from(G.nodes(data=True))
    for u, v, data in G.edges(data=True):
        if not data.get("closed", False):
            H.add_edge(u, v, **data)
    return H


def shortest_time_path(
    topology: Topology,
    src: str,
    dst: str,
    loaded: bool,
    exclude_closed: bool = True,
) -> list[str]:
    if src not in topology.G:
        raise ValueError(f"Source node not in graph: {src}")
    if dst not in topology.G:
        raise ValueError(f"Destination node not in graph: {dst}")
    if src == dst:
        return [src]

    speed_factor = (
        _DEFAULT_LOADED_SPEED_FACTOR if loaded else _DEFAULT_EMPTY_SPEED_FACTOR
    )

    H = _routing_view(topology.G, exclude_closed)

    def weight(u: str, v: str, data: dict[str, Any]) -> float:
        return travel_time_min(data["distance_m"], data["max_speed_kph"], speed_factor)

    try:
        return nx.shortest_path(H, source=src, target=dst, weight=weight)
    except nx.NetworkXNoPath as exc:
        raise ValueError(
            f"No path from {src} to {dst} (loaded={loaded}, exclude_closed={exclude_closed})"
        ) from exc


def edge_lookup(topology: Topology, from_node: str, to_node: str) -> dict[str, Any]:
    if not topology.G.has_edge(from_node, to_node):
        raise KeyError(f"No edge {from_node}->{to_node}")
    return dict(topology.G.edges[from_node, to_node])
