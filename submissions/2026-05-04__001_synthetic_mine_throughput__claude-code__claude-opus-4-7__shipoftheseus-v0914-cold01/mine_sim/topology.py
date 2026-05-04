"""Mine topology: graph build, scenario-aware overrides, route caching, edge time draws."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import networkx as nx
import numpy as np
import pandas as pd


def _to_bool(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.strip().lower() == "true"
    return bool(v)


@dataclass
class EdgeAttr:
    edge_id: str
    from_node: str
    to_node: str
    distance_m: float
    max_speed_kph: float
    road_type: str
    capacity: int
    closed: bool
    metadata: str = ""


@dataclass
class NodeAttr:
    node_id: str
    node_name: str
    node_type: str
    x_m: float
    y_m: float
    z_m: float
    capacity: Optional[float] = None
    service_time_mean_min: Optional[float] = None
    service_time_sd_min: Optional[float] = None
    metadata: str = ""


def edge_time_min(distance_m: float, max_speed_kph: float, loaded: bool,
                   loaded_speed_factor: float, rng: np.random.Generator,
                   noise_cv: float = 0.10) -> float:
    """Return travel time in minutes for an edge with multiplicative lognormal noise.

    Loaded trucks travel slower: effective speed = max_speed * loaded_speed_factor.
    Noise: t = base_t * exp(N(0, noise_cv)).
    """
    speed_kph = max_speed_kph * (loaded_speed_factor if loaded else 1.0)
    if speed_kph <= 0:
        return float("inf")
    base_t = (distance_m / 1000.0) / (speed_kph / 60.0)  # minutes
    if noise_cv > 0:
        z = rng.normal(0.0, noise_cv)
        # mean preserving lognormal: subtract sigma^2/2
        return float(base_t * math.exp(z - 0.5 * noise_cv * noise_cv))
    return float(base_t)


class Topology:
    """Mine topology with per-scenario graph derivation and shortest-path caching."""

    def __init__(self, nodes_df: pd.DataFrame, edges_df: pd.DataFrame):
        self.nodes_df = nodes_df.copy()
        self.edges_df = edges_df.copy()
        self.nodes: Dict[str, NodeAttr] = {}
        for _, r in nodes_df.iterrows():
            self.nodes[r["node_id"]] = NodeAttr(
                node_id=r["node_id"],
                node_name=r.get("node_name", ""),
                node_type=r.get("node_type", ""),
                x_m=float(r["x_m"]),
                y_m=float(r["y_m"]),
                z_m=float(r["z_m"]),
                capacity=(float(r["capacity"]) if pd.notna(r.get("capacity")) else None),
                service_time_mean_min=(float(r["service_time_mean_min"])
                                        if pd.notna(r.get("service_time_mean_min")) else None),
                service_time_sd_min=(float(r["service_time_sd_min"])
                                      if pd.notna(r.get("service_time_sd_min")) else None),
                metadata=str(r.get("metadata", "")),
            )

    def _apply_edge_overrides(self, base: pd.DataFrame, overrides: dict) -> pd.DataFrame:
        df = base.copy()
        if not overrides:
            return df
        for edge_id, mods in overrides.items():
            mask = df["edge_id"] == edge_id
            for k, v in mods.items():
                if k not in df.columns:
                    df[k] = None
                df.loc[mask, k] = v
        return df

    def graph_for_scenario(self, edge_overrides: Optional[dict] = None) -> Tuple[nx.DiGraph, pd.DataFrame]:
        df = self._apply_edge_overrides(self.edges_df, edge_overrides or {})
        df["closed"] = df["closed"].apply(_to_bool)
        df["capacity"] = df["capacity"].fillna(999).astype(int)
        df["max_speed_kph"] = df["max_speed_kph"].astype(float)
        df["distance_m"] = df["distance_m"].astype(float)

        g = nx.DiGraph()
        for nid in self.nodes:
            g.add_node(nid)
        for _, r in df.iterrows():
            if r["closed"]:
                continue
            t_min = (r["distance_m"] / 1000.0) / (r["max_speed_kph"] / 60.0)
            g.add_edge(r["from_node"], r["to_node"],
                       edge_id=r["edge_id"],
                       distance_m=r["distance_m"],
                       max_speed_kph=r["max_speed_kph"],
                       capacity=int(r["capacity"]),
                       road_type=r["road_type"],
                       weight=t_min)
        return g, df

    def shortest_path(self, g: nx.DiGraph, src: str, dst: str) -> Optional[List[str]]:
        try:
            return nx.shortest_path(g, src, dst, weight="weight")
        except nx.NetworkXNoPath:
            return None
        except nx.NodeNotFound:
            return None

    def precompute_paths(self, g: nx.DiGraph, pairs: List[Tuple[str, str]]) -> Dict[Tuple[str, str], Optional[List[str]]]:
        return {p: self.shortest_path(g, p[0], p[1]) for p in pairs}

    @staticmethod
    def edge_sequence(path: List[str]) -> List[Tuple[str, str]]:
        return list(zip(path[:-1], path[1:]))
