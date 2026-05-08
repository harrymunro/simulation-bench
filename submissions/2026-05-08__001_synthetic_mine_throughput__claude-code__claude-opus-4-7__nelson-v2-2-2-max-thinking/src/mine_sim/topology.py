"""Topology graph builder with closure / override application and reachability checks."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx

from .data import Edge, Node, StaticData
from .scenarios import ScenarioConfig


@dataclass
class ScenarioTopology:
    """Per-scenario, override-applied view of the static topology."""
    nodes: Dict[str, Node]
    edges: Dict[str, Edge]
    graph: nx.DiGraph
    capacity_one_edge_ids: List[str]
    loaders_effective: Dict[str, Dict]   # loader_id -> overridden attrs
    dump_points_effective: Dict[str, Dict]
    nodes_effective: Dict[str, Dict]


def _apply_edge_overrides(
    edges: Dict[str, Edge], overrides: Dict[str, Dict]
) -> Dict[str, Edge]:
    out: Dict[str, Edge] = {}
    for eid, e in edges.items():
        if eid in overrides:
            patch = overrides[eid]
            out[eid] = Edge(
                edge_id=e.edge_id,
                from_node=e.from_node,
                to_node=e.to_node,
                distance_m=float(patch.get("distance_m", e.distance_m)),
                max_speed_kph=float(patch.get("max_speed_kph", e.max_speed_kph)),
                road_type=str(patch.get("road_type", e.road_type)),
                capacity=int(patch.get("capacity", e.capacity)),
                closed=bool(patch.get("closed", e.closed)),
                metadata=str(patch.get("metadata", e.metadata)),
            )
        else:
            out[eid] = e
    return out


def _materialise_loader_attrs(static: StaticData, scenario: ScenarioConfig) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for lid, l in static.loaders.items():
        attrs = {
            "loader_id": l.loader_id,
            "node_id": l.node_id,
            "capacity": l.capacity,
            "bucket_capacity_tonnes": l.bucket_capacity_tonnes,
            "mean_load_time_min": l.mean_load_time_min,
            "sd_load_time_min": l.sd_load_time_min,
            "availability": l.availability,
        }
        if lid in scenario.loader_overrides:
            attrs.update(scenario.loader_overrides[lid])
        out[lid] = attrs
    return out


def _materialise_dump_attrs(static: StaticData, scenario: ScenarioConfig) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for did, d in static.dump_points.items():
        attrs = {
            "dump_id": d.dump_id,
            "node_id": d.node_id,
            "type": d.type,
            "capacity": d.capacity,
            "mean_dump_time_min": d.mean_dump_time_min,
            "sd_dump_time_min": d.sd_dump_time_min,
        }
        if did in scenario.dump_point_overrides:
            attrs.update(scenario.dump_point_overrides[did])
        out[did] = attrs
    return out


def _materialise_node_attrs(static: StaticData, scenario: ScenarioConfig) -> Dict[str, Dict]:
    out: Dict[str, Dict] = {}
    for nid, n in static.nodes.items():
        attrs = {
            "node_id": n.node_id,
            "node_type": n.node_type,
            "x_m": n.x_m,
            "y_m": n.y_m,
            "z_m": n.z_m,
            "capacity": n.capacity,
            "service_time_mean_min": n.service_time_mean_min,
            "service_time_sd_min": n.service_time_sd_min,
        }
        if nid in scenario.node_overrides:
            attrs.update(scenario.node_overrides[nid])
        out[nid] = attrs
    return out


def free_flow_minutes(distance_m: float, max_speed_kph: float, speed_factor: float) -> float:
    """Edge traversal time at free-flow speed for the given speed factor."""
    if max_speed_kph <= 0 or speed_factor <= 0:
        raise ValueError("max_speed_kph and speed_factor must be positive")
    effective_kph = max_speed_kph * speed_factor
    return distance_m * 60.0 / (effective_kph * 1000.0)


def build_scenario_topology(
    static: StaticData, scenario: ScenarioConfig
) -> ScenarioTopology:
    """Apply scenario overrides, build the directed graph, validate reachability."""
    edges = _apply_edge_overrides(static.edges, scenario.edge_overrides)
    g = nx.DiGraph()
    for nid, n in static.nodes.items():
        g.add_node(nid, **_materialise_node_attrs(static, scenario)[nid])
    capacity_one_ids: List[str] = []
    for eid, e in edges.items():
        if e.closed:
            continue
        # We use the empty free-flow time as the *default* edge weight; routing
        # decides whether to use empty / loaded weights via separate weight maps.
        g.add_edge(
            e.from_node,
            e.to_node,
            edge_id=e.edge_id,
            distance_m=e.distance_m,
            max_speed_kph=e.max_speed_kph,
            road_type=e.road_type,
            capacity=e.capacity,
        )
        if e.capacity == 1:
            capacity_one_ids.append(eid)

    loaders_eff = _materialise_loader_attrs(static, scenario)
    dumps_eff = _materialise_dump_attrs(static, scenario)
    nodes_eff = _materialise_node_attrs(static, scenario)

    topo = ScenarioTopology(
        nodes={n: static.nodes[n] for n in static.nodes},
        edges=edges,
        graph=g,
        capacity_one_edge_ids=capacity_one_ids,
        loaders_effective=loaders_eff,
        dump_points_effective=dumps_eff,
        nodes_effective=nodes_eff,
    )
    _validate_reachability(topo, static, scenario)
    return topo


def _validate_reachability(
    topo: ScenarioTopology, static: StaticData, scenario: ScenarioConfig
) -> None:
    """Fail loudly if trucks cannot reach loaders, or loaders cannot reach the crusher."""
    g = topo.graph
    crusher_nodes = [
        d["node_id"] for d in topo.dump_points_effective.values() if d["type"] == "crusher"
    ]
    if not crusher_nodes:
        raise RuntimeError("No crusher dump point defined for scenario.")
    crusher_node = crusher_nodes[0]
    loader_nodes = [l["node_id"] for l in topo.loaders_effective.values()]

    # Truck start nodes used by the active fleet (subset of trucks).
    fleet_size = scenario.truck_count
    used_trucks = static.trucks[:fleet_size]
    truck_starts = sorted({t.start_node for t in used_trucks})

    problems: List[str] = []

    for ts in truck_starts:
        for ln in loader_nodes:
            if not nx.has_path(g, ts, ln):
                problems.append(f"truck start {ts} cannot reach loader node {ln}")
        if not nx.has_path(g, ts, crusher_node):
            problems.append(f"truck start {ts} cannot reach crusher {crusher_node}")

    for ln in loader_nodes:
        if not nx.has_path(g, ln, crusher_node):
            problems.append(f"loader node {ln} cannot reach crusher {crusher_node}")
        if not nx.has_path(g, crusher_node, ln):
            problems.append(f"crusher {crusher_node} cannot return to loader node {ln}")

    if problems:
        details = "\n  - ".join(problems)
        raise RuntimeError(
            f"Reachability self-check FAILED for scenario '{scenario.scenario_id}':\n  - {details}"
        )
