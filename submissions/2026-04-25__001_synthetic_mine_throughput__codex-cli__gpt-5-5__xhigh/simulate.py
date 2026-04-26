#!/usr/bin/env python3
"""Discrete-event mine haulage simulation for the synthetic throughput benchmark."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd
import simpy
import yaml
from scipy import stats


REQUIRED_SCENARIOS = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]


BENCHMARK_ID = "001_synthetic_mine_throughput"
HIGH_CAPACITY = 999


@dataclass
class TrackedResource:
    resource_id: str
    resource_type: str
    capacity: int
    env: simpy.Environment
    resource: simpy.Resource = field(init=False)
    busy_time_min: float = 0.0
    queue_waits_min: list[float] = field(default_factory=list)
    queue_entries: int = 0

    def __post_init__(self) -> None:
        self.resource = simpy.Resource(self.env, capacity=self.capacity)

    def add_busy_time(self, start_min: float, duration_min: float, shift_end_min: float) -> None:
        clipped = max(0.0, min(start_min + duration_min, shift_end_min) - start_min)
        self.busy_time_min += clipped

    def utilisation(self, shift_end_min: float) -> float:
        if shift_end_min <= 0 or self.capacity <= 0:
            return 0.0
        return self.busy_time_min / (self.capacity * shift_end_min)

    def average_queue_wait(self) -> float:
        if not self.queue_waits_min:
            return 0.0
        return float(np.mean(self.queue_waits_min))


@dataclass
class TruckState:
    truck_id: str
    payload_tonnes: float
    empty_speed_factor: float
    loaded_speed_factor: float
    start_node: str
    productive_time_min: float = 0.0
    cycle_times_min: list[float] = field(default_factory=list)


class MineSimulation:
    def __init__(
        self,
        data: dict[str, pd.DataFrame],
        scenario: dict[str, Any],
        replication: int,
        random_seed: int,
        output_events: list[dict[str, Any]],
    ) -> None:
        self.data = data
        self.scenario = scenario
        self.replication = replication
        self.random_seed = random_seed
        self.rng = np.random.default_rng(random_seed)
        self.env = simpy.Environment()
        self.shift_end_min = float(scenario["simulation"]["shift_length_hours"]) * 60.0
        self.output_events = output_events

        self.nodes = self._records_by_id(data["nodes"], "node_id")
        self.edges = self._records_by_id(data["edges"], "edge_id")
        self.loaders_df = data["loaders"]
        self.dumps_df = data["dump_points"]
        self.trucks_df = data["trucks"]

        self.ore_sources = list(scenario["production"]["ore_sources"])
        self.dump_node = scenario["production"]["dump_destination"]
        self.travel_cv = float(scenario.get("stochasticity", {}).get("travel_time_noise_cv", 0.0))
        self.road_capacity_enabled = bool(
            scenario.get("routing", {}).get("road_capacity_enabled", True)
        )

        self.graph = self._build_graph()
        self.loader_by_node = self._build_loader_lookup()
        self.dump = self._build_dump_lookup()
        self.loaders = self._build_loader_resources()
        self.crusher = self._build_crusher_resource()
        self.road_resource_for_edge, self.roads = self._build_road_resources()
        self.trucks = self._build_trucks()

        self.total_tonnes_delivered = 0.0
        self.completed_cycles = 0

        self._validate_routes()

    @staticmethod
    def _records_by_id(df: pd.DataFrame, id_column: str) -> dict[str, dict[str, Any]]:
        records: dict[str, dict[str, Any]] = {}
        for record in df.to_dict(orient="records"):
            records[str(record[id_column])] = record
        return records

    def _build_graph(self) -> nx.DiGraph:
        graph = nx.DiGraph()
        for node_id in self.nodes:
            graph.add_node(node_id)

        for edge in self.edges.values():
            if parse_bool(edge.get("closed", False)):
                continue
            speed = float(edge["max_speed_kph"])
            if speed <= 0:
                continue
            distance = float(edge["distance_m"])
            base_time_min = distance / 1000.0 / speed * 60.0
            graph.add_edge(
                edge["from_node"],
                edge["to_node"],
                weight=base_time_min,
                edge_id=edge["edge_id"],
            )
        return graph

    def _build_loader_lookup(self) -> dict[str, dict[str, Any]]:
        return {
            row["node_id"]: row
            for row in self.loaders_df.to_dict(orient="records")
            if float(row.get("availability", 1.0)) > 0.0
        }

    def _build_dump_lookup(self) -> dict[str, Any]:
        matches = self.dumps_df[self.dumps_df["node_id"] == self.dump_node]
        if matches.empty:
            raise ValueError(f"No dump point is configured at destination {self.dump_node}")
        return matches.iloc[0].to_dict()

    def _build_loader_resources(self) -> dict[str, TrackedResource]:
        resources: dict[str, TrackedResource] = {}
        for node_id in self.ore_sources:
            if node_id not in self.loader_by_node:
                raise ValueError(f"Ore source {node_id} has no loader definition")
            loader = self.loader_by_node[node_id]
            resources[loader["loader_id"]] = TrackedResource(
                str(loader["loader_id"]),
                "loader",
                int(loader["capacity"]),
                self.env,
            )
        return resources

    def _build_crusher_resource(self) -> TrackedResource:
        return TrackedResource(
            str(self.dump["dump_id"]),
            "crusher",
            int(self.dump["capacity"]),
            self.env,
        )

    def _build_road_resources(self) -> tuple[dict[str, str], dict[str, TrackedResource]]:
        if not self.road_capacity_enabled:
            return {}, {}

        grouped_caps: dict[str, list[int]] = {}
        edge_to_group: dict[str, str] = {}
        for edge in self.edges.values():
            if parse_bool(edge.get("closed", False)):
                continue
            capacity = int(edge["capacity"])
            if capacity >= HIGH_CAPACITY:
                continue
            group_id = physical_road_id(edge["from_node"], edge["to_node"])
            grouped_caps.setdefault(group_id, []).append(capacity)
            edge_to_group[edge["edge_id"]] = group_id

        resources = {
            group_id: TrackedResource(
                group_id,
                "road",
                max(1, min(capacities)),
                self.env,
            )
            for group_id, capacities in grouped_caps.items()
        }
        return edge_to_group, resources

    def _build_trucks(self) -> list[TruckState]:
        count = int(self.scenario["fleet"]["truck_count"])
        available = self.trucks_df[self.trucks_df["availability"].astype(float) > 0.0].copy()
        available = available.sort_values("truck_id").head(count)
        if len(available) < count:
            raise ValueError(f"Scenario requested {count} trucks, but only {len(available)} are available")

        trucks = []
        for row in available.to_dict(orient="records"):
            trucks.append(
                TruckState(
                    truck_id=str(row["truck_id"]),
                    payload_tonnes=float(row["payload_tonnes"]),
                    empty_speed_factor=float(row["empty_speed_factor"]),
                    loaded_speed_factor=float(row["loaded_speed_factor"]),
                    start_node=str(row["start_node"]),
                )
            )
        return trucks

    def _validate_routes(self) -> None:
        origins = {truck.start_node for truck in self.trucks} | {self.dump_node}
        for origin in origins:
            for loader_node in self.ore_sources:
                self.shortest_path(origin, loader_node)
        for loader_node in self.ore_sources:
            self.shortest_path(loader_node, self.dump_node)

    def log_event(
        self,
        truck: TruckState,
        event_type: str,
        *,
        from_node: str = "",
        to_node: str = "",
        location: str = "",
        loaded: bool = False,
        payload_tonnes: float = 0.0,
        resource_id: str = "",
        queue_length: int | str = "",
    ) -> None:
        self.output_events.append(
            {
                "time_min": round(float(self.env.now), 4),
                "replication": self.replication,
                "scenario_id": self.scenario["scenario_id"],
                "truck_id": truck.truck_id,
                "event_type": event_type,
                "from_node": from_node,
                "to_node": to_node,
                "location": location,
                "loaded": bool(loaded),
                "payload_tonnes": round(float(payload_tonnes), 4),
                "resource_id": resource_id,
                "queue_length": queue_length,
            }
        )

    def shortest_path(self, source: str, target: str) -> list[str]:
        try:
            return nx.shortest_path(self.graph, source=source, target=target, weight="weight")
        except (nx.NetworkXNoPath, nx.NodeNotFound) as exc:
            scenario_id = self.scenario["scenario_id"]
            raise RuntimeError(
                f"No route from {source} to {target} in scenario {scenario_id}"
            ) from exc

    def expected_route_time(self, path: list[str], truck: TruckState, loaded: bool) -> float:
        total = 0.0
        factor = truck.loaded_speed_factor if loaded else truck.empty_speed_factor
        for from_node, to_node in zip(path[:-1], path[1:]):
            edge_id = self.graph[from_node][to_node]["edge_id"]
            edge = self.edges[edge_id]
            speed = float(edge["max_speed_kph"]) * factor
            total += float(edge["distance_m"]) / 1000.0 / speed * 60.0
        return total

    def choose_loader(self, current_node: str, truck: TruckState) -> tuple[str, str]:
        candidates = []
        for loader_node in self.ore_sources:
            loader = self.loader_by_node[loader_node]
            loader_id = str(loader["loader_id"])
            resource = self.loaders[loader_id]
            empty_path = self.shortest_path(current_node, loader_node)
            loaded_path = self.shortest_path(loader_node, self.dump_node)

            empty_time = self.expected_route_time(empty_path, truck, loaded=False)
            loaded_time = self.expected_route_time(loaded_path, truck, loaded=True)
            mean_load = float(loader["mean_load_time_min"])
            queued_work = resource.resource.count + len(resource.resource.queue)
            estimated_wait = queued_work / resource.capacity * mean_load
            score = empty_time + estimated_wait + mean_load + loaded_time
            candidates.append((score, loaded_time + mean_load, loader_id, loader_node))

        candidates.sort()
        _, _, loader_id, loader_node = candidates[0]
        return loader_id, loader_node

    def sample_service_time(self, mean: float, sd: float) -> float:
        if sd <= 0:
            return max(0.1, mean)
        for _ in range(100):
            sample = float(self.rng.normal(mean, sd))
            if sample > 0:
                return sample
        return max(0.1, mean)

    def sample_travel_time(self, edge: dict[str, Any], truck: TruckState, loaded: bool) -> float:
        speed_factor = truck.loaded_speed_factor if loaded else truck.empty_speed_factor
        speed_kph = float(edge["max_speed_kph"]) * speed_factor
        mean_min = float(edge["distance_m"]) / 1000.0 / speed_kph * 60.0
        if self.travel_cv <= 0:
            return mean_min
        sigma = math.sqrt(math.log(self.travel_cv * self.travel_cv + 1.0))
        mu = -0.5 * sigma * sigma
        return mean_min * float(self.rng.lognormal(mu, sigma))

    def add_truck_productive_time(self, truck: TruckState, start: float, duration: float) -> None:
        truck.productive_time_min += max(0.0, min(start + duration, self.shift_end_min) - start)

    def traverse_route(
        self,
        truck: TruckState,
        path: list[str],
        *,
        loaded: bool,
        payload_tonnes: float,
    ) -> Any:
        for from_node, to_node in zip(path[:-1], path[1:]):
            edge_id = self.graph[from_node][to_node]["edge_id"]
            edge = self.edges[edge_id]
            road_id = self.road_resource_for_edge.get(edge_id, "")
            duration = self.sample_travel_time(edge, truck, loaded)

            if road_id:
                road = self.roads[road_id]
                road.queue_entries += 1
                self.log_event(
                    truck,
                    "road_queue",
                    from_node=from_node,
                    to_node=to_node,
                    location=from_node,
                    loaded=loaded,
                    payload_tonnes=payload_tonnes,
                    resource_id=road_id,
                    queue_length=len(road.resource.queue),
                )
                request_time = float(self.env.now)
                with road.resource.request() as request:
                    yield request
                    wait = float(self.env.now) - request_time
                    road.queue_waits_min.append(wait)
                    self.log_event(
                        truck,
                        "road_enter",
                        from_node=from_node,
                        to_node=to_node,
                        location=from_node,
                        loaded=loaded,
                        payload_tonnes=payload_tonnes,
                        resource_id=road_id,
                        queue_length=len(road.resource.queue),
                    )
                    start = float(self.env.now)
                    road.add_busy_time(start, duration, self.shift_end_min)
                    self.add_truck_productive_time(truck, start, duration)
                    yield self.env.timeout(duration)
            else:
                self.log_event(
                    truck,
                    "road_enter",
                    from_node=from_node,
                    to_node=to_node,
                    location=from_node,
                    loaded=loaded,
                    payload_tonnes=payload_tonnes,
                    resource_id=edge_id,
                    queue_length=0,
                )
                start = float(self.env.now)
                self.add_truck_productive_time(truck, start, duration)
                yield self.env.timeout(duration)

    def load_truck(self, truck: TruckState, loader_id: str, loader_node: str) -> Any:
        loader_row = self.loader_by_node[loader_node]
        loader = self.loaders[loader_id]
        loader.queue_entries += 1
        self.log_event(
            truck,
            "loader_queue",
            location=loader_node,
            loaded=False,
            payload_tonnes=0.0,
            resource_id=loader_id,
            queue_length=len(loader.resource.queue),
        )
        request_time = float(self.env.now)
        with loader.resource.request() as request:
            yield request
            wait = float(self.env.now) - request_time
            loader.queue_waits_min.append(wait)
            self.log_event(
                truck,
                "loading_start",
                location=loader_node,
                loaded=False,
                payload_tonnes=0.0,
                resource_id=loader_id,
                queue_length=len(loader.resource.queue),
            )
            duration = self.sample_service_time(
                float(loader_row["mean_load_time_min"]),
                float(loader_row["sd_load_time_min"]),
            )
            start = float(self.env.now)
            loader.add_busy_time(start, duration, self.shift_end_min)
            self.add_truck_productive_time(truck, start, duration)
            yield self.env.timeout(duration)
            self.log_event(
                truck,
                "loading_end",
                location=loader_node,
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
                resource_id=loader_id,
                queue_length=len(loader.resource.queue),
            )

    def dump_truck(self, truck: TruckState) -> Any:
        crusher = self.crusher
        crusher.queue_entries += 1
        self.log_event(
            truck,
            "crusher_queue",
            location=self.dump_node,
            loaded=True,
            payload_tonnes=truck.payload_tonnes,
            resource_id=crusher.resource_id,
            queue_length=len(crusher.resource.queue),
        )
        request_time = float(self.env.now)
        with crusher.resource.request() as request:
            yield request
            wait = float(self.env.now) - request_time
            crusher.queue_waits_min.append(wait)
            self.log_event(
                truck,
                "dumping_start",
                location=self.dump_node,
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
                resource_id=crusher.resource_id,
                queue_length=len(crusher.resource.queue),
            )
            duration = self.sample_service_time(
                float(self.dump["mean_dump_time_min"]),
                float(self.dump["sd_dump_time_min"]),
            )
            start = float(self.env.now)
            crusher.add_busy_time(start, duration, self.shift_end_min)
            self.add_truck_productive_time(truck, start, duration)
            yield self.env.timeout(duration)
            if self.env.now <= self.shift_end_min:
                self.total_tonnes_delivered += truck.payload_tonnes
                self.completed_cycles += 1
                self.log_event(
                    truck,
                    "dumping_end",
                    location=self.dump_node,
                    loaded=False,
                    payload_tonnes=truck.payload_tonnes,
                    resource_id=crusher.resource_id,
                    queue_length=len(crusher.resource.queue),
                )

    def truck_process(self, truck: TruckState) -> Any:
        current_node = truck.start_node
        self.log_event(truck, "truck_dispatched", location=current_node)

        while self.env.now < self.shift_end_min:
            cycle_start = float(self.env.now)
            loader_id, loader_node = self.choose_loader(current_node, truck)
            self.log_event(
                truck,
                "dispatch_to_loader",
                from_node=current_node,
                to_node=loader_node,
                location=current_node,
                resource_id=loader_id,
            )

            empty_path = self.shortest_path(current_node, loader_node)
            yield from self.traverse_route(
                truck,
                empty_path,
                loaded=False,
                payload_tonnes=0.0,
            )
            current_node = loader_node
            if self.env.now >= self.shift_end_min:
                break

            yield from self.load_truck(truck, loader_id, loader_node)
            if self.env.now >= self.shift_end_min:
                break

            loaded_path = self.shortest_path(loader_node, self.dump_node)
            yield from self.traverse_route(
                truck,
                loaded_path,
                loaded=True,
                payload_tonnes=truck.payload_tonnes,
            )
            current_node = self.dump_node
            if self.env.now >= self.shift_end_min:
                break

            before_completed = self.completed_cycles
            yield from self.dump_truck(truck)
            if self.completed_cycles > before_completed:
                truck.cycle_times_min.append(float(self.env.now) - cycle_start)

    def run(self) -> dict[str, Any]:
        for truck in self.trucks:
            self.env.process(self.truck_process(truck))
        self.env.run(until=self.shift_end_min + 1e-9)

        loader_waits = [
            wait
            for loader in self.loaders.values()
            for wait in loader.queue_waits_min
        ]
        cycle_times = [cycle for truck in self.trucks for cycle in truck.cycle_times_min]
        productive_utils = [
            truck.productive_time_min / self.shift_end_min
            for truck in self.trucks
        ]
        road_waits = [
            wait
            for road in self.roads.values()
            for wait in road.queue_waits_min
        ]

        result: dict[str, Any] = {
            "scenario_id": self.scenario["scenario_id"],
            "replication": self.replication,
            "random_seed": self.random_seed,
            "truck_count": len(self.trucks),
            "total_tonnes_delivered": self.total_tonnes_delivered,
            "tonnes_per_hour": self.total_tonnes_delivered / (self.shift_end_min / 60.0),
            "average_truck_cycle_time_min": safe_mean(cycle_times),
            "average_truck_utilisation": safe_mean(productive_utils),
            "crusher_utilisation": self.crusher.utilisation(self.shift_end_min),
            "average_loader_queue_time_min": safe_mean(loader_waits),
            "average_crusher_queue_time_min": self.crusher.average_queue_wait(),
            "average_road_queue_time_min": safe_mean(road_waits),
            "completed_cycles": self.completed_cycles,
        }

        for loader_id, loader in sorted(self.loaders.items()):
            result[f"loader_utilisation_{loader_id}"] = loader.utilisation(self.shift_end_min)
            result[f"loader_queue_time_{loader_id}_min"] = loader.average_queue_wait()
        for road_id, road in sorted(self.roads.items()):
            safe_id = encode_resource_id(road_id)
            result[f"road_utilisation_{safe_id}"] = road.utilisation(self.shift_end_min)
            result[f"road_queue_time_{safe_id}_min"] = road.average_queue_wait()
        return result


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return False
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def physical_road_id(from_node: str, to_node: str) -> str:
    a, b = sorted([str(from_node), str(to_node)])
    return f"road:{a}-{b}"


def encode_resource_id(resource_id: str) -> str:
    return resource_id.replace("_", "__underscore__").replace(":", "__colon__").replace("-", "__dash__")


def decode_resource_id(encoded: str) -> str:
    return (
        encoded.replace("__dash__", "-")
        .replace("__colon__", ":")
        .replace("__underscore__", "_")
    )


def safe_mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(np.mean(values))


def ci95(values: pd.Series) -> tuple[float, float, float]:
    clean = values.astype(float).dropna()
    mean = float(clean.mean()) if len(clean) else 0.0
    if len(clean) <= 1:
        return mean, mean, mean
    sem = float(clean.sem())
    half_width = float(stats.t.ppf(0.975, len(clean) - 1) * sem)
    return mean, mean - half_width, mean + half_width


def deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in overlay.items():
        if key == "inherits":
            continue
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = copy.deepcopy(value)
    return merged


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def load_scenario(scenarios_dir: Path, scenario_id: str) -> dict[str, Any]:
    raw = load_yaml(scenarios_dir / f"{scenario_id}.yaml")
    parent_id = raw.get("inherits")
    if parent_id:
        parent = load_scenario(scenarios_dir, parent_id)
        return deep_merge(parent, raw)
    return raw


def apply_overrides(data: dict[str, pd.DataFrame], scenario: dict[str, Any]) -> dict[str, pd.DataFrame]:
    copied = {name: df.copy(deep=True) for name, df in data.items()}

    for edge_id, overrides in scenario.get("edge_overrides", {}).items():
        apply_dataframe_overrides(copied["edges"], "edge_id", edge_id, overrides)
    for node_id, overrides in scenario.get("node_overrides", {}).items():
        apply_dataframe_overrides(copied["nodes"], "node_id", node_id, overrides)
    for dump_id, overrides in scenario.get("dump_point_overrides", {}).items():
        apply_dataframe_overrides(copied["dump_points"], "dump_id", dump_id, overrides)
    for loader_id, overrides in scenario.get("loader_overrides", {}).items():
        apply_dataframe_overrides(copied["loaders"], "loader_id", loader_id, overrides)
    for truck_id, overrides in scenario.get("truck_overrides", {}).items():
        apply_dataframe_overrides(copied["trucks"], "truck_id", truck_id, overrides)

    copied["edges"]["closed"] = copied["edges"]["closed"].map(parse_bool)
    return copied


def apply_dataframe_overrides(
    df: pd.DataFrame,
    id_column: str,
    record_id: str,
    overrides: dict[str, Any],
) -> None:
    mask = df[id_column] == record_id
    if not mask.any():
        raise ValueError(f"Cannot apply override for missing {id_column}={record_id}")
    for column, value in overrides.items():
        if column not in df.columns:
            raise ValueError(f"Cannot apply override to missing column {column}")
        df.loc[mask, column] = value


def load_input_data(data_dir: Path) -> dict[str, pd.DataFrame]:
    return {
        "nodes": pd.read_csv(data_dir / "nodes.csv"),
        "edges": pd.read_csv(data_dir / "edges.csv"),
        "trucks": pd.read_csv(data_dir / "trucks.csv"),
        "loaders": pd.read_csv(data_dir / "loaders.csv"),
        "dump_points": pd.read_csv(data_dir / "dump_points.csv"),
    }


def run_experiments(data_dir: Path, scenario_ids: list[str]) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    base_data = load_input_data(data_dir)
    scenarios_dir = data_dir / "scenarios"
    all_results: list[dict[str, Any]] = []
    all_events: list[dict[str, Any]] = []
    summary_scenarios: dict[str, Any] = {}

    for scenario_id in scenario_ids:
        scenario = load_scenario(scenarios_dir, scenario_id)
        replications = int(scenario["simulation"]["replications"])
        base_seed = int(scenario["simulation"]["base_random_seed"])
        scenario_results = []

        for replication in range(1, replications + 1):
            random_seed = base_seed + replication - 1
            scenario_data = apply_overrides(base_data, scenario)
            simulation = MineSimulation(
                scenario_data,
                scenario,
                replication,
                random_seed,
                all_events,
            )
            result = simulation.run()
            all_results.append(result)
            scenario_results.append(result)

        scenario_df = pd.DataFrame(scenario_results)
        summary_scenarios[scenario_id] = summarize_scenario(scenario, scenario_df)

    results_df = pd.DataFrame(all_results)
    events_df = pd.DataFrame(all_events)
    summary = {
        "benchmark_id": BENCHMARK_ID,
        "scenarios": summary_scenarios,
        "key_assumptions": [
            "Trucks are continuously dispatched while the 8-hour shift is active; throughput is counted only when dumping completes before the shift cutoff.",
            "Scenario fleet size selects the first available truck records from trucks.csv; truck availability is treated as deterministic inclusion when greater than zero.",
            "Roads with capacity below 999 are modelled as SimPy resources, paired by their two endpoint nodes so opposite directions share a physical constrained segment.",
            "Routing uses shortest expected travel time over open directed edges; stochastic travel time is applied after route selection.",
            "Loading and dumping times are positive truncated normal samples using the means and standard deviations in the input data.",
        ],
        "model_limitations": [
            "No truck breakdowns, refuelling, operator shift changes, blasting delays, or maintenance events are modelled.",
            "Dispatch uses current queue lengths and mean service times, not a global optimiser or look-ahead controller.",
            "Road resource occupancy is first-come, first-served and does not model passing bays, priority rules, or detailed traffic interactions.",
            "Crusher feed is represented only by dump service time and a single dumping resource; downstream plant constraints are outside the system boundary.",
        ],
        "additional_scenarios_proposed": [
            {
                "scenario_id": "loader_upgrade_south",
                "description": "Test whether a second or faster south-pit loader would unlock more value than adding trucks once the crusher and ramp are near saturation.",
            }
        ],
    }
    return results_df, events_df, summary


def summarize_scenario(scenario: dict[str, Any], scenario_df: pd.DataFrame) -> dict[str, Any]:
    total_mean, total_low, total_high = ci95(scenario_df["total_tonnes_delivered"])
    tph_mean, tph_low, tph_high = ci95(scenario_df["tonnes_per_hour"])

    loader_utilisation = {}
    for column in sorted(c for c in scenario_df.columns if c.startswith("loader_utilisation_")):
        loader_id = column.replace("loader_utilisation_", "")
        loader_utilisation[loader_id] = float(scenario_df[column].mean())

    bottlenecks = identify_bottlenecks(scenario_df)

    return {
        "replications": int(len(scenario_df)),
        "shift_length_hours": float(scenario["simulation"]["shift_length_hours"]),
        "truck_count": int(scenario["fleet"]["truck_count"]),
        "total_tonnes_mean": total_mean,
        "total_tonnes_ci95_low": total_low,
        "total_tonnes_ci95_high": total_high,
        "tonnes_per_hour_mean": tph_mean,
        "tonnes_per_hour_ci95_low": tph_low,
        "tonnes_per_hour_ci95_high": tph_high,
        "average_cycle_time_min": float(scenario_df["average_truck_cycle_time_min"].mean()),
        "truck_utilisation_mean": float(scenario_df["average_truck_utilisation"].mean()),
        "loader_utilisation": loader_utilisation,
        "crusher_utilisation": float(scenario_df["crusher_utilisation"].mean()),
        "average_loader_queue_time_min": float(scenario_df["average_loader_queue_time_min"].mean()),
        "average_crusher_queue_time_min": float(scenario_df["average_crusher_queue_time_min"].mean()),
        "top_bottlenecks": bottlenecks,
    }


def identify_bottlenecks(scenario_df: pd.DataFrame) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = [
        {
            "resource_id": "D_CRUSH",
            "resource_type": "crusher",
            "utilisation_mean": float(scenario_df["crusher_utilisation"].mean()),
            "average_queue_wait_min": float(scenario_df["average_crusher_queue_time_min"].mean()),
        }
    ]

    for column in sorted(c for c in scenario_df.columns if c.startswith("loader_utilisation_")):
        loader_id = column.replace("loader_utilisation_", "")
        queue_column = f"loader_queue_time_{loader_id}_min"
        candidates.append(
            {
                "resource_id": loader_id,
                "resource_type": "loader",
                "utilisation_mean": float(scenario_df[column].mean()),
                "average_queue_wait_min": float(scenario_df.get(queue_column, pd.Series([0.0])).mean()),
            }
        )

    for column in sorted(c for c in scenario_df.columns if c.startswith("road_utilisation_")):
        safe_id = column.replace("road_utilisation_", "")
        road_id = decode_resource_id(safe_id)
        queue_column = f"road_queue_time_{safe_id}_min"
        candidates.append(
            {
                "resource_id": road_id,
                "resource_type": "road",
                "utilisation_mean": float(scenario_df[column].mean()),
                "average_queue_wait_min": float(scenario_df.get(queue_column, pd.Series([0.0])).mean()),
            }
        )

    candidates.sort(
        key=lambda item: (
            item["utilisation_mean"],
            item["average_queue_wait_min"],
        ),
        reverse=True,
    )
    return candidates[:5]


def write_outputs(
    output_dir: Path,
    results_df: pd.DataFrame,
    events_df: pd.DataFrame,
    summary: dict[str, Any],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    results_df.to_csv(output_dir / "results.csv", index=False)
    events_df.to_csv(output_dir / "event_log.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    with (output_dir / "summary.json").open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2)
        handle.write("\n")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--output-dir", type=Path, default=Path("."))
    parser.add_argument(
        "--scenarios",
        nargs="+",
        default=REQUIRED_SCENARIOS,
        help="Scenario ids to run, without .yaml extension.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results_df, events_df, summary = run_experiments(args.data_dir, args.scenarios)
    write_outputs(args.output_dir, results_df, events_df, summary)

    print(f"Wrote {args.output_dir / 'results.csv'} ({len(results_df)} rows)")
    print(f"Wrote {args.output_dir / 'event_log.csv'} ({len(events_df)} rows)")
    print(f"Wrote {args.output_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
