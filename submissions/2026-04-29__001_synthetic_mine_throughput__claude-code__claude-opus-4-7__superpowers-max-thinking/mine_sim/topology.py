"""CSV loaders, graph construction, scenario overrides, shortest paths."""
from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

import networkx as nx


# ---------------------------------------------------------------------------
# Edge -> road-lock mapping. Hybrid policy:
#   - Paired bidirectional locks for narrow physical bottlenecks (ramp, pit access)
#   - Per-direction locks for the crusher approach (queueing lane, not physical lane)
# ---------------------------------------------------------------------------
EDGE_TO_LOCK: dict[str, str] = {
    "E03_UP":           "RAMP",
    "E03_DOWN":         "RAMP",
    "E07_TO_LOAD_N":    "PIT_N",
    "E07_FROM_LOAD_N":  "PIT_N",
    "E09_TO_LOAD_S":    "PIT_S",
    "E09_FROM_LOAD_S":  "PIT_S",
    "E05_TO_CRUSH":     "E05_TO",
    "E05_FROM_CRUSH":   "E05_FROM",
}


@dataclass
class Node:
    node_id: str
    node_name: str
    node_type: str
    x_m: float
    y_m: float
    z_m: float
    capacity: Optional[int] = None
    service_time_mean_min: Optional[float] = None
    service_time_sd_min: Optional[float] = None
    metadata: str = ""


@dataclass
class Edge:
    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    max_speed_kph: float
    road_type: str
    capacity: int
    closed: bool = False
    metadata: str = ""


@dataclass
class Truck:
    truck_id: str
    payload_tonnes: float
    empty_speed_factor: float
    loaded_speed_factor: float
    availability: float
    start_node: str


@dataclass
class Loader:
    loader_id: str
    node_id: str
    capacity: int
    bucket_capacity_tonnes: float
    mean_load_time_min: float
    sd_load_time_min: float
    availability: float


@dataclass
class DumpPoint:
    dump_id: str
    node_id: str
    type: str
    capacity: int
    mean_dump_time_min: float
    sd_dump_time_min: float


def _parse_optional_float(value: str) -> Optional[float]:
    if value is None or value.strip() == "":
        return None
    return float(value)


def _parse_optional_int(value: str) -> Optional[int]:
    if value is None or value.strip() == "":
        return None
    return int(value)


def _parse_bool(value: str) -> bool:
    return str(value).strip().lower() == "true"


def load_nodes(path: Path) -> dict[str, Node]:
    nodes: dict[str, Node] = {}
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("node_id"):
                continue
            nodes[row["node_id"]] = Node(
                node_id=row["node_id"],
                node_name=row["node_name"],
                node_type=row["node_type"],
                x_m=float(row["x_m"]),
                y_m=float(row["y_m"]),
                z_m=float(row["z_m"]),
                capacity=_parse_optional_int(row.get("capacity", "")),
                service_time_mean_min=_parse_optional_float(row.get("service_time_mean_min", "")),
                service_time_sd_min=_parse_optional_float(row.get("service_time_sd_min", "")),
                metadata=row.get("metadata", ""),
            )
    return nodes


def load_edges(path: Path) -> dict[str, Edge]:
    edges: dict[str, Edge] = {}
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("edge_id"):
                continue
            edges[row["edge_id"]] = Edge(
                edge_id=row["edge_id"],
                from_node=row["from_node"],
                to_node=row["to_node"],
                distance_m=float(row["distance_m"]),
                max_speed_kph=float(row["max_speed_kph"]),
                road_type=row["road_type"],
                capacity=int(row["capacity"]),
                closed=_parse_bool(row.get("closed", "false")),
                metadata=row.get("metadata", ""),
            )
    return edges


def load_trucks(path: Path) -> dict[str, Truck]:
    trucks: dict[str, Truck] = {}
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("truck_id"):
                continue
            trucks[row["truck_id"]] = Truck(
                truck_id=row["truck_id"],
                payload_tonnes=float(row["payload_tonnes"]),
                empty_speed_factor=float(row["empty_speed_factor"]),
                loaded_speed_factor=float(row["loaded_speed_factor"]),
                availability=float(row["availability"]),
                start_node=row["start_node"],
            )
    return trucks


def load_loaders(path: Path) -> dict[str, Loader]:
    loaders: dict[str, Loader] = {}
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("loader_id"):
                continue
            loaders[row["loader_id"]] = Loader(
                loader_id=row["loader_id"],
                node_id=row["node_id"],
                capacity=int(row["capacity"]),
                bucket_capacity_tonnes=float(row["bucket_capacity_tonnes"]),
                mean_load_time_min=float(row["mean_load_time_min"]),
                sd_load_time_min=float(row["sd_load_time_min"]),
                availability=float(row["availability"]),
            )
    return loaders


def load_dump_points(path: Path) -> dict[str, DumpPoint]:
    dumps: dict[str, DumpPoint] = {}
    with Path(path).open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get("dump_id"):
                continue
            dumps[row["dump_id"]] = DumpPoint(
                dump_id=row["dump_id"],
                node_id=row["node_id"],
                type=row["type"],
                capacity=int(row["capacity"]),
                mean_dump_time_min=float(row["mean_dump_time_min"]),
                sd_dump_time_min=float(row["sd_dump_time_min"]),
            )
    return dumps


def apply_overrides(
    *,
    edges_dict: dict[str, Edge],
    nodes_dict: dict[str, Node],
    dumps_dict: dict[str, DumpPoint],
    config: dict[str, Any],
) -> None:
    """Mutate the supplied dicts in place per scenario overrides."""
    for edge_id, patch in config.get("edge_overrides", {}).items():
        if edge_id not in edges_dict:
            raise KeyError(f"edge_overrides references unknown edge {edge_id!r}")
        edge = edges_dict[edge_id]
        for k, v in patch.items():
            if not hasattr(edge, k):
                raise KeyError(f"Edge has no attribute {k!r}")
            setattr(edge, k, v)
    for node_id, patch in config.get("node_overrides", {}).items():
        if node_id not in nodes_dict:
            raise KeyError(f"node_overrides references unknown node {node_id!r}")
        node = nodes_dict[node_id]
        for k, v in patch.items():
            if not hasattr(node, k):
                raise KeyError(f"Node has no attribute {k!r}")
            setattr(node, k, v)
    for dump_id, patch in config.get("dump_point_overrides", {}).items():
        if dump_id not in dumps_dict:
            raise KeyError(f"dump_point_overrides references unknown dump {dump_id!r}")
        dump = dumps_dict[dump_id]
        for k, v in patch.items():
            if not hasattr(dump, k):
                raise KeyError(f"DumpPoint has no attribute {k!r}")
            setattr(dump, k, v)


def edge_travel_time_min(edge: Edge) -> float:
    """Nominal travel time (no truck-specific or noise factors)."""
    return (edge.distance_m / 1000.0) / edge.max_speed_kph * 60.0


def build_graph(nodes: dict[str, Node], edges: dict[str, Edge]) -> nx.DiGraph:
    """Construct a NetworkX DiGraph; closed edges are excluded."""
    g = nx.DiGraph()
    for node_id, node in nodes.items():
        g.add_node(node_id, node_type=node.node_type, name=node.node_name)
    for edge_id, edge in edges.items():
        if edge.closed:
            continue
        g.add_edge(
            edge.from_node,
            edge.to_node,
            edge_id=edge.edge_id,
            distance_m=edge.distance_m,
            max_speed_kph=edge.max_speed_kph,
            travel_time_min=edge_travel_time_min(edge),
            capacity=edge.capacity,
            road_type=edge.road_type,
        )
    return g


class TopologyError(Exception):
    """Raised when required routes are not realisable on the graph."""


def compute_shortest_paths(
    g: nx.DiGraph,
    required_pairs: Optional[Iterable[tuple[str, str]]] = None,
) -> dict[str, dict[str, list[str]]]:
    """Compute shortest paths weighted by ``travel_time_min``.

    If ``required_pairs`` is supplied, ensure each is reachable; raise
    ``TopologyError`` otherwise.
    """
    paths: dict[str, dict[str, list[str]]] = {}
    for src in g.nodes:
        try:
            sp = nx.single_source_dijkstra_path(g, src, weight="travel_time_min")
            paths[src] = sp
        except nx.NetworkXNoPath:
            paths[src] = {}
    if required_pairs is not None:
        for src, dst in required_pairs:
            if dst not in paths.get(src, {}):
                raise TopologyError(f"No path from {src!r} to {dst!r}")
    return paths


def path_travel_time_min(path: list[str], g: nx.DiGraph) -> float:
    """Sum of nominal travel times along a path of node ids."""
    total = 0.0
    for u, v in zip(path, path[1:]):
        total += g[u][v]["travel_time_min"]
    return total


def path_edge_ids(path: list[str], g: nx.DiGraph) -> list[str]:
    """Return the list of edge_ids traversed by following node-id path."""
    return [g[u][v]["edge_id"] for u, v in zip(path, path[1:])]


def plot_topology(nodes: dict[str, Node], edges: dict[str, Edge], path: Path,
                   *, highlight_capacity_1: bool = True) -> None:
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 9))
    color_by_type = {
        "parking": "#4C72B0", "junction": "#888888", "load_ore": "#55A868",
        "crusher": "#C44E52", "waste_dump": "#CCB974",
        "maintenance": "#8172B2",
    }
    for node_id, node in nodes.items():
        ax.scatter(node.x_m, node.y_m, s=200,
                   color=color_by_type.get(node.node_type, "#cccccc"),
                   edgecolors="black", zorder=3)
        ax.annotate(node_id, (node.x_m, node.y_m), xytext=(7, 7),
                    textcoords="offset points", fontsize=9, fontweight="bold")
    for edge in edges.values():
        if edge.closed:
            continue
        x0, y0 = nodes[edge.from_node].x_m, nodes[edge.from_node].y_m
        x1, y1 = nodes[edge.to_node].x_m, nodes[edge.to_node].y_m
        is_constrained = edge.capacity == 1
        color = "#C44E52" if (highlight_capacity_1 and is_constrained) else "#aaaaaa"
        lw = 2.2 if is_constrained else 0.8
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="->", color=color, lw=lw, alpha=0.7))
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Mine topology — red = capacity-constrained edges (single-truck)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)
