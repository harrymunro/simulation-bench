"""Data loading, scenario inheritance, and topology graph construction.

This module is the single source of truth for the static model: it reads the
provided CSVs, merges YAML scenario configs (resolving ``inherits`` chains
and applying surgical overrides), and builds a routing graph.

Stochastic distribution helpers also live here so they can be unit-tested in
isolation from the SimPy simulation.
"""

from __future__ import annotations

import copy
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
import yaml


CONSTRAINED_CAPACITY_THRESHOLD = 100  # edges with capacity < 100 are real bottlenecks


class RoutingError(RuntimeError):
    """Raised when no path exists between two required nodes in a scenario."""


@dataclass(frozen=True)
class InputData:
    """Static inputs read once per benchmark."""
    nodes: pd.DataFrame
    edges: pd.DataFrame
    trucks: pd.DataFrame
    loaders: pd.DataFrame
    dump_points: pd.DataFrame


def load_inputs(data_dir: Path) -> InputData:
    """Load the five canonical CSV files."""
    data_dir = Path(data_dir)
    nodes = pd.read_csv(data_dir / "nodes.csv").dropna(how="all")
    edges = pd.read_csv(data_dir / "edges.csv").dropna(how="all")
    trucks = pd.read_csv(data_dir / "trucks.csv").dropna(how="all")
    loaders = pd.read_csv(data_dir / "loaders.csv").dropna(how="all")
    dump_points = pd.read_csv(data_dir / "dump_points.csv").dropna(how="all")

    # Coerce booleans (csv reads "false"/"true" as strings).
    if edges["closed"].dtype == object:
        edges = edges.copy()
        edges["closed"] = edges["closed"].astype(str).str.lower().map(
            {"true": True, "false": False}
        ).fillna(False)

    return InputData(nodes=nodes, edges=edges, trucks=trucks,
                     loaders=loaders, dump_points=dump_points)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge override into base, returning a new dict.

    Nested dicts are merged. Other values are replaced wholesale.
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if (
            key in result
            and isinstance(result[key], dict)
            and isinstance(val, dict)
        ):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def load_scenario(scenarios_dir: Path, scenario_id: str) -> dict[str, Any]:
    """Load a scenario YAML, recursively resolving ``inherits``.

    Returns a flat config dict where the child's overrides have been applied
    on top of the parent. Removes the ``inherits`` key from the result.
    """
    scenarios_dir = Path(scenarios_dir)
    path = scenarios_dir / f"{scenario_id}.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))

    parent_id = raw.pop("inherits", None)
    if parent_id is None:
        return raw

    parent = load_scenario(scenarios_dir, parent_id)
    return _deep_merge(parent, raw)


def apply_edge_overrides(edges: pd.DataFrame,
                         overrides: dict[str, dict[str, Any]] | None) -> pd.DataFrame:
    """Return a new edges dataframe with per-edge overrides applied."""
    if not overrides:
        return edges.copy()
    edges = edges.copy()
    for edge_id, fields in overrides.items():
        mask = edges["edge_id"] == edge_id
        if not mask.any():
            raise ValueError(f"edge_overrides references unknown edge_id: {edge_id}")
        for field, value in fields.items():
            edges.loc[mask, field] = value
    return edges


def apply_dump_point_overrides(dump_points: pd.DataFrame,
                               overrides: dict[str, dict[str, Any]] | None) -> pd.DataFrame:
    if not overrides:
        return dump_points.copy()
    dump_points = dump_points.copy()
    for dump_id, fields in overrides.items():
        mask = dump_points["dump_id"] == dump_id
        if not mask.any():
            raise ValueError(f"dump_point_overrides references unknown dump_id: {dump_id}")
        for field, value in fields.items():
            dump_points.loc[mask, field] = value
    return dump_points


def build_graph(edges: pd.DataFrame) -> nx.DiGraph:
    """Build a directed graph with travel-time weights (minutes).

    Closed edges are dropped entirely. Travel time uses ``max_speed_kph`` so
    an unloaded truck running at speed_factor=1.0 covers ``distance_m`` in
    ``distance_m / (max_speed_kph * 1000 / 60)`` minutes.
    """
    g = nx.DiGraph()
    for _, row in edges.iterrows():
        if bool(row["closed"]):
            continue
        speed_m_per_min = float(row["max_speed_kph"]) * 1000.0 / 60.0
        travel_min = float(row["distance_m"]) / speed_m_per_min
        g.add_edge(
            row["from_node"], row["to_node"],
            edge_id=row["edge_id"],
            distance_m=float(row["distance_m"]),
            max_speed_kph=float(row["max_speed_kph"]),
            capacity=int(row["capacity"]),
            road_type=row["road_type"],
            travel_min=travel_min,
        )
    return g


def compute_route(graph: nx.DiGraph, source: str, target: str) -> list[dict[str, Any]]:
    """Return the shortest-time path from ``source`` to ``target`` as edge dicts.

    Raises :class:`RoutingError` if either endpoint is missing or no path
    exists. The returned list contains one dict per edge traversed.
    """
    if source not in graph:
        raise RoutingError(f"Source node {source} not in graph")
    if target not in graph:
        raise RoutingError(f"Target node {target} not in graph")
    try:
        path_nodes = nx.dijkstra_path(graph, source, target, weight="travel_min")
    except nx.NetworkXNoPath as exc:
        raise RoutingError(f"No path from {source} to {target}") from exc

    edges: list[dict[str, Any]] = []
    for u, v in zip(path_nodes[:-1], path_nodes[1:]):
        data = graph.edges[u, v]
        edges.append({
            "edge_id": data["edge_id"],
            "from_node": u,
            "to_node": v,
            "distance_m": data["distance_m"],
            "max_speed_kph": data["max_speed_kph"],
            "capacity": data["capacity"],
            "travel_min": data["travel_min"],
        })
    return edges


def truncated_normal(rng: np.random.Generator, mean: float, sd: float,
                     low_factor: float = 0.1) -> float:
    """Sample from N(mean, sd) truncated below at ``low_factor * mean``.

    Resamples on rejection. With sd typically << mean this loops at most a
    handful of times; bounded explicitly to prevent pathological cases.
    """
    if sd <= 0 or mean <= 0:
        return max(mean, low_factor * mean)
    floor = low_factor * mean
    for _ in range(20):
        x = float(rng.normal(mean, sd))
        if x >= floor:
            return x
    return floor


def lognormal_unit_mean(rng: np.random.Generator, cv: float) -> float:
    """Sample from a lognormal distribution with mean 1 and coefficient ``cv``.

    Uses ``sigma^2 = ln(1 + cv^2)`` and ``mu = -sigma^2 / 2`` so that
    E[X] = exp(mu + sigma^2/2) = 1.0 exactly.
    """
    if cv <= 0:
        return 1.0
    sigma2 = math.log(1.0 + cv * cv)
    sigma = math.sqrt(sigma2)
    mu = -0.5 * sigma2
    return float(rng.lognormal(mu, sigma))
