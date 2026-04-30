"""Static shortest-time routing and reachability self-check.

The Seed contract specifies:

    Routing - static shortest-time per (origin, destination, scenario) via
    Dijkstra on free-flow edge times (distance / max_speed_kph), recomputed
    when scenario closes edges.

We compute one all-pairs shortest-path table per scenario at simulation
construction time and freeze it. The simulation reads precomputed routes
during dispatch and travel; it never re-runs Dijkstra at runtime, so the
hot path stays cheap.

We also enforce the Seed reachability rule:

    Reachability self-check at scenario load - fail loudly if any required
    OD pair (PARK<->LOAD_N, PARK<->LOAD_S, LOAD_N<->CRUSH, LOAD_S<->CRUSH)
    is unreachable.

Closures (``edge.closed = True``) are honoured by giving those edges weight
``+inf`` so Dijkstra never selects them — equivalent to removing them from
the graph but more transparent for debugging.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping

import networkx as nx

from mine_sim.topology import EdgeView, Topology

# ---------------------------------------------------------------------------
# Required OD pairs the Seed says must always be reachable. Listed here so
# it's a single source of truth referenced by both the simulation and tests.
# ---------------------------------------------------------------------------
REQUIRED_OD_PAIRS: tuple[tuple[str, str], ...] = (
    ("PARK", "LOAD_N"),
    ("LOAD_N", "PARK"),
    ("PARK", "LOAD_S"),
    ("LOAD_S", "PARK"),
    ("LOAD_N", "CRUSH"),
    ("CRUSH", "LOAD_N"),
    ("LOAD_S", "CRUSH"),
    ("CRUSH", "LOAD_S"),
)


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class Route:
    """Pre-computed shortest-time path between an (origin, destination) pair.

    ``edge_ids`` lists the directed edges to traverse in order; the simulation
    walks this sequence when moving a truck. ``free_flow_time_min`` is the
    cumulative deterministic time (used by the dispatch heuristic).
    """

    origin: str
    destination: str
    edge_ids: tuple[str, ...]
    free_flow_time_min: float

    @property
    def is_trivial(self) -> bool:
        """True when origin == destination (an empty route)."""
        return self.origin == self.destination


@dataclass(frozen=True)
class RoutingTable:
    """All precomputed routes for one scenario.

    Keyed by ``(origin, destination)``; missing keys mean unreachable.
    """

    routes: Mapping[tuple[str, str], Route]

    def get(self, origin: str, destination: str) -> Route | None:
        return self.routes.get((origin, destination))

    def require(self, origin: str, destination: str) -> Route:
        route = self.get(origin, destination)
        if route is None:
            raise KeyError(
                f"No precomputed route from {origin} to {destination}. "
                f"Was the reachability self-check run?"
            )
        return route


class ReachabilityError(RuntimeError):
    """Raised loudly when a required OD pair is unreachable in a scenario."""


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------
def _build_directed_graph(topology: Topology) -> nx.DiGraph:
    """Build a NetworkX DiGraph weighted by free-flow time (minutes).

    Closed edges are skipped entirely so Dijkstra cannot consider them.
    When two edges share the same (from, to) (none in our data, but defensive)
    we keep the cheapest.
    """
    graph: nx.DiGraph = nx.DiGraph()
    for node_id in topology.nodes:
        graph.add_node(node_id)
    for edge in topology.edges.values():
        if edge.closed:
            continue
        weight = edge.free_flow_time_min
        if weight == float("inf"):
            continue
        existing = graph.get_edge_data(edge.from_node, edge.to_node)
        if existing is not None and existing["weight"] <= weight:
            continue
        graph.add_edge(
            edge.from_node,
            edge.to_node,
            weight=weight,
            edge_id=edge.edge_id,
        )
    return graph


def _path_to_edge_ids(
    graph: nx.DiGraph,
    path: list[str],
) -> tuple[str, ...]:
    edge_ids: list[str] = []
    for u, v in zip(path[:-1], path[1:]):
        edge_ids.append(graph[u][v]["edge_id"])
    return tuple(edge_ids)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def compute_routes(
    topology: Topology,
    sources: tuple[str, ...] | None = None,
    targets: tuple[str, ...] | None = None,
) -> RoutingTable:
    """Compute shortest-time routes for the cycle-relevant OD pairs.

    By default we compute routes between the four cycle anchors
    (``PARK``, ``LOAD_N``, ``LOAD_S``, ``CRUSH``) in both directions, which
    is everything the simulation actually uses. ``sources`` and ``targets``
    can be passed for tests or future use cases.
    """
    cycle_nodes = ("PARK", "LOAD_N", "LOAD_S", "CRUSH")
    src = sources if sources is not None else cycle_nodes
    dst = targets if targets is not None else cycle_nodes

    graph = _build_directed_graph(topology)
    routes: dict[tuple[str, str], Route] = {}

    for origin in src:
        if origin not in graph:
            continue
        try:
            lengths, paths = nx.single_source_dijkstra(
                graph, origin, weight="weight"
            )
        except nx.NetworkXNoPath:
            # Should not occur with single_source_dijkstra; defensive.
            continue
        for destination in dst:
            if destination not in paths:
                continue
            path = paths[destination]
            routes[(origin, destination)] = Route(
                origin=origin,
                destination=destination,
                edge_ids=_path_to_edge_ids(graph, path),
                free_flow_time_min=float(lengths[destination]),
            )

    return RoutingTable(routes=MappingProxyType(routes))


def assert_reachable(
    table: RoutingTable,
    required: tuple[tuple[str, str], ...] = REQUIRED_OD_PAIRS,
    scenario_id: str | None = None,
) -> None:
    """Raise :class:`ReachabilityError` if any required OD pair is missing.

    The error lists *every* missing pair so a user diagnosing a closure can
    see all the impacts at once rather than fixing them one at a time.
    """
    missing = [pair for pair in required if pair not in table.routes]
    if not missing:
        return
    pretty = ", ".join(f"{a} -> {b}" for a, b in missing)
    prefix = f"Scenario '{scenario_id}': " if scenario_id else ""
    raise ReachabilityError(
        f"{prefix}required OD pairs unreachable in current topology: {pretty}"
    )


def free_flow_edge_time_min(edge: EdgeView) -> float:
    """Convenience re-export of :attr:`EdgeView.free_flow_time_min`."""
    return edge.free_flow_time_min


__all__ = [
    "ReachabilityError",
    "REQUIRED_OD_PAIRS",
    "Route",
    "RoutingTable",
    "assert_reachable",
    "compute_routes",
    "free_flow_edge_time_min",
]
