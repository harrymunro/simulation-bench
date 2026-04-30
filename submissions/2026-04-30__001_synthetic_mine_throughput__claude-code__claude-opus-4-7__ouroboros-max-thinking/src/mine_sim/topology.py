"""Topology loading and scenario-aware graph construction.

The mine topology is described by four flat CSV files in :mod:`data/`:

* ``nodes.csv`` — node geometry, type, and (for service nodes) service-time
  metadata.
* ``edges.csv`` — directed edges with distance, max speed, road type,
  capacity, and a closed flag.
* ``loaders.csv`` — loader resources with mean/sd service times.
* ``dump_points.csv`` — dump resources (the primary crusher and the
  out-of-scope waste dump).

This module turns those CSVs plus a :class:`mine_sim.scenarios.ScenarioConfig`
into a single immutable :class:`Topology` object that the simulation reads
from. Scenario overrides (closed edges, ramp upgrades, crusher slowdowns)
are applied here so downstream code does not have to re-implement override
logic.

All public dataclasses are ``frozen=True`` and the embedded mappings are
wrapped in ``MappingProxyType`` to enforce the project-wide immutability
rule; the simulation must never mutate the topology view it was handed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import pandas as pd

from mine_sim.scenarios import ScenarioConfig

# ---------------------------------------------------------------------------
# Constants — names of input files. Kept here so the simulation does not have
# string-typed paths sprinkled around the codebase.
# ---------------------------------------------------------------------------
NODES_CSV = "nodes.csv"
EDGES_CSV = "edges.csv"
TRUCKS_CSV = "trucks.csv"
LOADERS_CSV = "loaders.csv"
DUMP_POINTS_CSV = "dump_points.csv"

#: A capacity strictly greater than 1 means the edge is high-throughput and
#: does not need a SimPy ``Resource``. We treat any ``capacity > 1`` as
#: effectively unconstrained — the CSV uses 999 as a sentinel.
UNCONSTRAINED_CAPACITY_THRESHOLD = 1


# ---------------------------------------------------------------------------
# Immutable view dataclasses
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class NodeView:
    """Single node in the post-override topology."""

    node_id: str
    node_type: str
    x_m: float
    y_m: float
    z_m: float
    service_time_mean_min: float | None
    service_time_sd_min: float | None


@dataclass(frozen=True)
class EdgeView:
    """Single directed edge in the post-override topology.

    ``free_flow_time_min`` is the deterministic per-direction traversal time
    (``distance_m / (max_speed_kph * 1000 / 60)``) and is the weight used by
    Dijkstra. Closed edges carry an infinite weight so they cannot appear in
    any shortest path.

    ``is_capacity_constrained`` is the single source of truth for whether
    this edge needs a SimPy ``Resource``; the simulation must consult this
    flag rather than re-deriving it from raw capacity.
    """

    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    max_speed_kph: float
    road_type: str
    capacity: int
    closed: bool

    @property
    def is_capacity_constrained(self) -> bool:
        return (
            not self.closed
            and self.capacity <= UNCONSTRAINED_CAPACITY_THRESHOLD
        )

    @property
    def free_flow_time_min(self) -> float:
        """Free-flow traversal time (minutes) at full ``max_speed_kph``.

        Returns positive infinity for closed edges so Dijkstra ignores them.
        """
        if self.closed or self.max_speed_kph <= 0:
            return float("inf")
        # km/h to m/min: max_speed_kph * 1000 / 60
        return self.distance_m / (self.max_speed_kph * 1000.0 / 60.0)


@dataclass(frozen=True)
class LoaderSpec:
    """Static spec of a loader (LOAD_N or LOAD_S) after node-level overrides."""

    loader_id: str
    node_id: str
    capacity: int
    bucket_capacity_tonnes: float
    mean_load_time_min: float
    sd_load_time_min: float
    availability: float


@dataclass(frozen=True)
class DumpSpec:
    """Static spec of a dump point (CRUSH or WASTE) after overrides."""

    dump_id: str
    node_id: str
    type: str
    capacity: int
    mean_dump_time_min: float
    sd_dump_time_min: float


@dataclass(frozen=True)
class TruckSpec:
    """Static spec of a truck. The simulation always starts trucks at PARK."""

    truck_id: str
    payload_tonnes: float
    empty_speed_factor: float
    loaded_speed_factor: float
    availability: float
    start_node: str


@dataclass(frozen=True)
class Topology:
    """Whole-graph immutable view used by the simulation.

    All maps are wrapped in ``MappingProxyType`` so the simulation cannot
    accidentally edit them mid-run.
    """

    nodes: Mapping[str, NodeView]
    edges: Mapping[str, EdgeView]
    loaders: Mapping[str, LoaderSpec]
    dump_points: Mapping[str, DumpSpec]
    trucks: tuple[TruckSpec, ...]

    # Convenience views ------------------------------------------------------
    def capacity_constrained_edges(self) -> tuple[str, ...]:
        """Edge IDs that the simulation should wrap in a SimPy ``Resource``."""
        return tuple(
            edge_id
            for edge_id, edge in self.edges.items()
            if edge.is_capacity_constrained
        )

    def open_edges(self) -> tuple[EdgeView, ...]:
        """All edges that are not currently closed."""
        return tuple(edge for edge in self.edges.values() if not edge.closed)

    def loaders_at(self, node_id: str) -> tuple[LoaderSpec, ...]:
        return tuple(loader for loader in self.loaders.values() if loader.node_id == node_id)


# ---------------------------------------------------------------------------
# CSV loaders — keep them tiny and pure. Pandas does the heavy lifting.
# ---------------------------------------------------------------------------
def _load_nodes(data_dir: Path) -> dict[str, NodeView]:
    df = pd.read_csv(data_dir / NODES_CSV).dropna(subset=["node_id"])
    out: dict[str, NodeView] = {}
    for row in df.itertuples():
        out[str(row.node_id)] = NodeView(
            node_id=str(row.node_id),
            node_type=str(row.node_type),
            x_m=float(row.x_m),
            y_m=float(row.y_m),
            z_m=float(row.z_m),
            service_time_mean_min=(
                float(row.service_time_mean_min)
                if pd.notna(row.service_time_mean_min)
                else None
            ),
            service_time_sd_min=(
                float(row.service_time_sd_min)
                if pd.notna(row.service_time_sd_min)
                else None
            ),
        )
    return out


def _load_edges(data_dir: Path) -> dict[str, EdgeView]:
    df = pd.read_csv(data_dir / EDGES_CSV).dropna(subset=["edge_id"])
    out: dict[str, EdgeView] = {}
    for row in df.itertuples():
        closed_raw = str(row.closed).strip().lower()
        out[str(row.edge_id)] = EdgeView(
            edge_id=str(row.edge_id),
            from_node=str(row.from_node),
            to_node=str(row.to_node),
            distance_m=float(row.distance_m),
            max_speed_kph=float(row.max_speed_kph),
            road_type=str(row.road_type),
            capacity=int(row.capacity),
            closed=closed_raw in ("true", "1", "yes"),
        )
    return out


def _load_loaders(data_dir: Path) -> dict[str, LoaderSpec]:
    df = pd.read_csv(data_dir / LOADERS_CSV).dropna(subset=["loader_id"])
    return {
        str(row.loader_id): LoaderSpec(
            loader_id=str(row.loader_id),
            node_id=str(row.node_id),
            capacity=int(row.capacity),
            bucket_capacity_tonnes=float(row.bucket_capacity_tonnes),
            mean_load_time_min=float(row.mean_load_time_min),
            sd_load_time_min=float(row.sd_load_time_min),
            availability=float(row.availability),
        )
        for row in df.itertuples()
    }


def _load_dump_points(data_dir: Path) -> dict[str, DumpSpec]:
    df = pd.read_csv(data_dir / DUMP_POINTS_CSV).dropna(subset=["dump_id"])
    return {
        str(row.dump_id): DumpSpec(
            dump_id=str(row.dump_id),
            node_id=str(row.node_id),
            type=str(row.type),
            capacity=int(row.capacity),
            mean_dump_time_min=float(row.mean_dump_time_min),
            sd_dump_time_min=float(row.sd_dump_time_min),
        )
        for row in df.itertuples()
    }


def _load_trucks(data_dir: Path) -> tuple[TruckSpec, ...]:
    df = pd.read_csv(data_dir / TRUCKS_CSV).dropna(subset=["truck_id"])
    return tuple(
        TruckSpec(
            truck_id=str(row.truck_id),
            payload_tonnes=float(row.payload_tonnes),
            empty_speed_factor=float(row.empty_speed_factor),
            loaded_speed_factor=float(row.loaded_speed_factor),
            availability=float(row.availability),
            start_node=str(row.start_node),
        )
        for row in df.itertuples()
    )


# ---------------------------------------------------------------------------
# Override application (returns NEW dataclass instances; never mutates inputs)
# ---------------------------------------------------------------------------
def _apply_edge_overrides(
    edges: dict[str, EdgeView],
    scenario: ScenarioConfig,
) -> dict[str, EdgeView]:
    out: dict[str, EdgeView] = {}
    for edge_id, edge in edges.items():
        override = scenario.edge_overrides.get(edge_id)
        if override is None:
            out[edge_id] = edge
            continue
        out[edge_id] = EdgeView(
            edge_id=edge.edge_id,
            from_node=edge.from_node,
            to_node=edge.to_node,
            distance_m=edge.distance_m,
            max_speed_kph=(
                override.max_speed_kph
                if override.max_speed_kph is not None
                else edge.max_speed_kph
            ),
            road_type=edge.road_type,
            capacity=(
                int(override.capacity)
                if override.capacity is not None
                else edge.capacity
            ),
            closed=(
                bool(override.closed)
                if override.closed is not None
                else edge.closed
            ),
        )
    return out


def _apply_node_overrides(
    nodes: dict[str, NodeView],
    scenario: ScenarioConfig,
) -> dict[str, NodeView]:
    out: dict[str, NodeView] = {}
    for node_id, node in nodes.items():
        override = scenario.node_overrides.get(node_id)
        if override is None:
            out[node_id] = node
            continue
        out[node_id] = NodeView(
            node_id=node.node_id,
            node_type=node.node_type,
            x_m=node.x_m,
            y_m=node.y_m,
            z_m=node.z_m,
            service_time_mean_min=(
                override.service_time_mean_min
                if override.service_time_mean_min is not None
                else node.service_time_mean_min
            ),
            service_time_sd_min=(
                override.service_time_sd_min
                if override.service_time_sd_min is not None
                else node.service_time_sd_min
            ),
        )
    return out


def _apply_dump_overrides(
    dumps: dict[str, DumpSpec],
    scenario: ScenarioConfig,
) -> dict[str, DumpSpec]:
    out: dict[str, DumpSpec] = {}
    for dump_id, dump in dumps.items():
        override = scenario.dump_point_overrides.get(dump_id)
        if override is None:
            out[dump_id] = dump
            continue
        out[dump_id] = DumpSpec(
            dump_id=dump.dump_id,
            node_id=dump.node_id,
            type=dump.type,
            capacity=dump.capacity,
            mean_dump_time_min=(
                override.mean_dump_time_min
                if override.mean_dump_time_min is not None
                else dump.mean_dump_time_min
            ),
            sd_dump_time_min=(
                override.sd_dump_time_min
                if override.sd_dump_time_min is not None
                else dump.sd_dump_time_min
            ),
        )
    return out


def _truncate_fleet(
    trucks: tuple[TruckSpec, ...],
    truck_count: int,
) -> tuple[TruckSpec, ...]:
    """Return the first ``truck_count`` trucks in CSV order.

    The CSV defines T01..T12. Scenarios cap the fleet at 4, 8, or 12 trucks;
    we always pick the lowest-numbered trucks so trucks_4 is a *subset* of
    baseline (8) and baseline is a subset of trucks_12. This keeps cross-
    scenario comparisons interpretable.
    """
    if truck_count < 0:
        raise ValueError(f"truck_count must be >= 0, got {truck_count}")
    if truck_count > len(trucks):
        raise ValueError(
            f"Scenario asks for {truck_count} trucks but only "
            f"{len(trucks)} are defined in trucks.csv"
        )
    return trucks[:truck_count]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_topology(data_dir: str | Path, scenario: ScenarioConfig) -> Topology:
    """Load all CSVs and return a scenario-resolved :class:`Topology`."""
    directory = Path(data_dir)
    if not directory.is_dir():
        raise NotADirectoryError(f"Data directory not found: {directory}")

    nodes = _apply_node_overrides(_load_nodes(directory), scenario)
    edges = _apply_edge_overrides(_load_edges(directory), scenario)
    loaders = _load_loaders(directory)
    dump_points = _apply_dump_overrides(_load_dump_points(directory), scenario)
    trucks = _truncate_fleet(_load_trucks(directory), scenario.fleet.truck_count)

    return Topology(
        nodes=MappingProxyType(nodes),
        edges=MappingProxyType(edges),
        loaders=MappingProxyType(loaders),
        dump_points=MappingProxyType(dump_points),
        trucks=trucks,
    )


__all__ = [
    "DUMP_POINTS_CSV",
    "DumpSpec",
    "EDGES_CSV",
    "EdgeView",
    "LOADERS_CSV",
    "LoaderSpec",
    "NODES_CSV",
    "NodeView",
    "TRUCKS_CSV",
    "Topology",
    "TruckSpec",
    "UNCONSTRAINED_CAPACITY_THRESHOLD",
    "build_topology",
]
