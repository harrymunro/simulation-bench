"""Static shortest-time routing and the dispatch rule.

Per design memory:
- Routes are computed once per scenario via Dijkstra over free-flow times.
- Closures are honoured by topology construction (closed edges are absent).
- Dispatch chooses the loader minimising:
      travel_to_loader_empty + queue_len * mean_load_time + own_load_time
  where ``own_load_time`` = mean_load_time of the chosen loader.
- WASTE / MAINT nodes are excluded from any haulage route.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import networkx as nx

from .data import Truck
from .topology import ScenarioTopology, free_flow_minutes


# Nodes excluded from haulage routing.
EXCLUDED_NODE_TYPES = {"waste_dump", "maintenance"}


@dataclass
class RoutingTables:
    """Pre-computed shortest-time paths and travel times.

    ``paths[(src, dst)]`` is a list of node ids beginning with ``src`` and ending
    with ``dst``. ``edge_ids[(src, dst)]`` is the corresponding ordered list of
    edge ids. Two travel-time maps are pre-computed: empty and loaded.
    """
    edge_time_empty: Dict[str, float]    # edge_id -> minutes (empty)
    edge_time_loaded: Dict[str, float]   # edge_id -> minutes (loaded)
    paths: Dict[Tuple[str, str], List[str]]
    edge_ids: Dict[Tuple[str, str], List[str]]
    travel_min_empty: Dict[Tuple[str, str], float]
    travel_min_loaded: Dict[Tuple[str, str], float]


def build_routing(
    topology: ScenarioTopology,
    empty_speed_factor: float,
    loaded_speed_factor: float,
) -> RoutingTables:
    """Compute Dijkstra shortest-time paths between all interesting node pairs.

    Excludes WASTE and MAINTENANCE nodes from valid intermediates by stripping
    them from the routing graph. Crusher (a dump_point but a routing endpoint)
    is retained.
    """
    g = topology.graph
    routing_graph = g.copy()
    for nid, attrs in topology.nodes_effective.items():
        if attrs.get("node_type") in EXCLUDED_NODE_TYPES:
            if nid in routing_graph:
                routing_graph.remove_node(nid)

    edge_time_empty: Dict[str, float] = {}
    edge_time_loaded: Dict[str, float] = {}
    weight_empty_attr = {}
    weight_loaded_attr = {}

    for u, v, data in routing_graph.edges(data=True):
        eid = data["edge_id"]
        t_empty = free_flow_minutes(data["distance_m"], data["max_speed_kph"], empty_speed_factor)
        t_loaded = free_flow_minutes(data["distance_m"], data["max_speed_kph"], loaded_speed_factor)
        edge_time_empty[eid] = t_empty
        edge_time_loaded[eid] = t_loaded
        weight_empty_attr[(u, v)] = t_empty
        weight_loaded_attr[(u, v)] = t_loaded

    nx.set_edge_attributes(routing_graph, weight_empty_attr, name="t_empty")
    nx.set_edge_attributes(routing_graph, weight_loaded_attr, name="t_loaded")

    interesting_sources = {
        nid for nid, attrs in topology.nodes_effective.items()
        if attrs.get("node_type") not in EXCLUDED_NODE_TYPES and nid in routing_graph
    }

    paths: Dict[Tuple[str, str], List[str]] = {}
    edge_ids: Dict[Tuple[str, str], List[str]] = {}
    travel_empty: Dict[Tuple[str, str], float] = {}
    travel_loaded: Dict[Tuple[str, str], float] = {}

    for src in interesting_sources:
        # Use empty-weight tree for pickup legs (truck arrives empty); loaded for delivery.
        # We compute both — the simulation picks the right map per leg.
        try:
            empty_lengths, empty_paths = nx.single_source_dijkstra(
                routing_graph, src, weight="t_empty"
            )
        except nx.NetworkXNoPath:
            continue
        try:
            loaded_lengths, loaded_paths = nx.single_source_dijkstra(
                routing_graph, src, weight="t_loaded"
            )
        except nx.NetworkXNoPath:
            continue
        for dst, length in empty_lengths.items():
            if dst == src:
                continue
            paths[(src, dst)] = empty_paths[dst]
            edge_ids[(src, dst)] = _node_path_to_edge_ids(empty_paths[dst], routing_graph)
            travel_empty[(src, dst)] = length
        for dst, length in loaded_lengths.items():
            if dst == src:
                continue
            travel_loaded[(src, dst)] = length

    return RoutingTables(
        edge_time_empty=edge_time_empty,
        edge_time_loaded=edge_time_loaded,
        paths=paths,
        edge_ids=edge_ids,
        travel_min_empty=travel_empty,
        travel_min_loaded=travel_loaded,
    )


def _node_path_to_edge_ids(node_path: List[str], graph: nx.DiGraph) -> List[str]:
    """Map a node-id path to the ordered list of edge ids it traverses."""
    out: List[str] = []
    for u, v in zip(node_path, node_path[1:]):
        out.append(graph[u][v]["edge_id"])
    return out


def choose_loader(
    *,
    current_node: str,
    candidate_loader_ids: List[str],
    loaders_effective: Dict[str, Dict],
    routing: RoutingTables,
    queue_lengths: Dict[str, int],
) -> str:
    """Apply the dispatch rule and return the loader id with the lowest expected cost.

    cost(L) = travel_empty(current_node -> loader_node)
              + queue_len(L) * mean_load(L)
              + own_load(L)
            = travel_empty + (queue_len + 1) * mean_load(L)
    """
    best_id: Optional[str] = None
    best_cost = float("inf")
    for lid in candidate_loader_ids:
        attrs = loaders_effective[lid]
        loader_node = attrs["node_id"]
        # If current_node IS the loader node (e.g., truck just dumped at crusher
        # then re-dispatched to same), travel = 0.
        if current_node == loader_node:
            travel = 0.0
        else:
            travel = routing.travel_min_empty.get((current_node, loader_node), float("inf"))
        if travel == float("inf"):
            continue
        mean_load = float(attrs["mean_load_time_min"])
        ql = int(queue_lengths.get(lid, 0))
        cost = travel + (ql + 1) * mean_load
        if cost < best_cost:
            best_cost = cost
            best_id = lid
    if best_id is None:
        raise RuntimeError(
            f"No reachable loader from {current_node} among candidates {candidate_loader_ids}"
        )
    return best_id
