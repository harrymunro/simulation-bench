"""Topology loading, graph construction, and routing."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import networkx as nx
import pandas as pd


@dataclass(frozen=True)
class NodeRecord:
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
class EdgeRecord:
    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    max_speed_kph: float
    road_type: str
    capacity: int
    closed: bool
    metadata: str


def _to_bool(value) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _opt_float(value) -> Optional[float]:
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        return None
    return float(value)


def _opt_int(value) -> Optional[int]:
    f = _opt_float(value)
    return None if f is None else int(f)


def load_nodes(path: Path) -> Dict[str, NodeRecord]:
    df = pd.read_csv(path)
    nodes: Dict[str, NodeRecord] = {}
    for _, row in df.iterrows():
        rec = NodeRecord(
            node_id=str(row["node_id"]),
            node_name=str(row["node_name"]),
            node_type=str(row["node_type"]),
            x_m=float(row["x_m"]),
            y_m=float(row["y_m"]),
            z_m=float(row["z_m"]),
            capacity=_opt_int(row.get("capacity")),
            service_time_mean_min=_opt_float(row.get("service_time_mean_min")),
            service_time_sd_min=_opt_float(row.get("service_time_sd_min")),
            metadata=str(row.get("metadata", "")),
        )
        nodes[rec.node_id] = rec
    return nodes


def load_edges(path: Path) -> List[EdgeRecord]:
    df = pd.read_csv(path)
    edges: List[EdgeRecord] = []
    for _, row in df.iterrows():
        edges.append(
            EdgeRecord(
                edge_id=str(row["edge_id"]),
                from_node=str(row["from_node"]),
                to_node=str(row["to_node"]),
                distance_m=float(row["distance_m"]),
                max_speed_kph=float(row["max_speed_kph"]),
                road_type=str(row["road_type"]),
                capacity=int(row["capacity"]),
                closed=_to_bool(row["closed"]),
                metadata=str(row.get("metadata", "")),
            )
        )
    return edges


def lane_id_of(edge_id: str) -> str:
    """Lane identifier: prefix before first underscore.

    E03_UP and E03_DOWN -> E03 (same physical narrow ramp).
    E05_TO_CRUSH and E05_FROM_CRUSH -> E05 (same crusher approach lane).
    """
    return edge_id.split("_", 1)[0]


def apply_edge_overrides(
    edges: List[EdgeRecord],
    overrides: Dict[str, Dict],
) -> List[EdgeRecord]:
    if not overrides:
        return list(edges)
    new_edges: List[EdgeRecord] = []
    for e in edges:
        if e.edge_id in overrides:
            o = overrides[e.edge_id]
            new_edges.append(
                EdgeRecord(
                    edge_id=e.edge_id,
                    from_node=e.from_node,
                    to_node=e.to_node,
                    distance_m=float(o.get("distance_m", e.distance_m)),
                    max_speed_kph=float(o.get("max_speed_kph", e.max_speed_kph)),
                    road_type=str(o.get("road_type", e.road_type)),
                    capacity=int(o.get("capacity", e.capacity)),
                    closed=_to_bool(o.get("closed", e.closed)),
                    metadata=str(o.get("metadata", e.metadata)),
                )
            )
        else:
            new_edges.append(e)
    return new_edges


def apply_node_overrides(
    nodes: Dict[str, NodeRecord],
    overrides: Dict[str, Dict],
) -> Dict[str, NodeRecord]:
    if not overrides:
        return dict(nodes)
    new_nodes: Dict[str, NodeRecord] = {}
    for nid, n in nodes.items():
        if nid in overrides:
            o = overrides[nid]
            new_nodes[nid] = NodeRecord(
                node_id=n.node_id,
                node_name=str(o.get("node_name", n.node_name)),
                node_type=str(o.get("node_type", n.node_type)),
                x_m=float(o.get("x_m", n.x_m)),
                y_m=float(o.get("y_m", n.y_m)),
                z_m=float(o.get("z_m", n.z_m)),
                capacity=_opt_int(o.get("capacity", n.capacity)),
                service_time_mean_min=_opt_float(
                    o.get("service_time_mean_min", n.service_time_mean_min)
                ),
                service_time_sd_min=_opt_float(
                    o.get("service_time_sd_min", n.service_time_sd_min)
                ),
                metadata=str(o.get("metadata", n.metadata)),
            )
        else:
            new_nodes[nid] = n
    return new_nodes


def build_graph(
    nodes: Dict[str, NodeRecord],
    edges: List[EdgeRecord],
    *,
    empty_speed_factor: float = 1.0,
    loaded_speed_factor: float = 0.85,
    drop_closed: bool = True,
) -> nx.DiGraph:
    """Return a directed graph with edge attributes including baseline travel times.

    Travel times are nominal (no stochasticity) and computed for both empty and
    loaded conditions so the routing layer can pick the appropriate weight.
    """
    g = nx.DiGraph()
    for nid, n in nodes.items():
        g.add_node(
            nid,
            name=n.node_name,
            node_type=n.node_type,
            x=n.x_m,
            y=n.y_m,
            z=n.z_m,
            capacity=n.capacity,
            service_time_mean_min=n.service_time_mean_min,
            service_time_sd_min=n.service_time_sd_min,
        )
    for e in edges:
        if drop_closed and e.closed:
            continue
        # nominal travel time in minutes at max speed
        # speed_factor reduces effective speed; factor < 1 means slower (longer time).
        empty_time_min = (e.distance_m / 1000.0) / max(
            e.max_speed_kph * empty_speed_factor, 1e-6
        ) * 60.0
        loaded_time_min = (e.distance_m / 1000.0) / max(
            e.max_speed_kph * loaded_speed_factor, 1e-6
        ) * 60.0
        g.add_edge(
            e.from_node,
            e.to_node,
            edge_id=e.edge_id,
            distance_m=e.distance_m,
            max_speed_kph=e.max_speed_kph,
            road_type=e.road_type,
            capacity=e.capacity,
            closed=e.closed,
            lane_id=lane_id_of(e.edge_id),
            empty_time_min=empty_time_min,
            loaded_time_min=loaded_time_min,
            # weight used for shortest_path: average of the two
            weight=(empty_time_min + loaded_time_min) / 2.0,
        )
    return g


class Router:
    """Shortest-time router with caching."""

    def __init__(self, graph: nx.DiGraph, weight_attr: str = "weight"):
        self.graph = graph
        self.weight_attr = weight_attr
        self._path_cache: Dict[Tuple[str, str], List[str]] = {}

    def shortest_path(self, source: str, target: str) -> List[str]:
        if source == target:
            return [source]
        key = (source, target)
        if key in self._path_cache:
            return self._path_cache[key]
        try:
            path = nx.shortest_path(
                self.graph, source=source, target=target, weight=self.weight_attr
            )
        except nx.NetworkXNoPath as exc:
            raise RuntimeError(
                f"No path from {source} to {target} in current topology"
            ) from exc
        except nx.NodeNotFound as exc:
            raise RuntimeError(f"Node not found while routing: {exc}") from exc
        self._path_cache[key] = path
        return path

    def path_time_min(self, source: str, target: str) -> float:
        path = self.shortest_path(source, target)
        total = 0.0
        for u, v in zip(path[:-1], path[1:]):
            total += float(self.graph[u][v][self.weight_attr])
        return total
