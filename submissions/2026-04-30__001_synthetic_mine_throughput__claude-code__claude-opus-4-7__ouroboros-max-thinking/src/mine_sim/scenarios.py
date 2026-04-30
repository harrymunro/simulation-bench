"""Scenario configuration data structures and YAML loading.

Scenarios are defined as YAML files with optional inheritance from a base
scenario (typically `baseline`). Override blocks let a scenario change:

* `fleet.truck_count`             - number of trucks released at t=0
* `edge_overrides.<edge_id>`      - capacity, max_speed_kph, closed flag
                                    (used to model ramp upgrades and closures)
* `dump_point_overrides.<dump>`   - crusher mean/sd dump time
* `node_overrides.<node_id>`      - service-time overrides for the dump node
* `simulation.*`                  - shift length, replications, seed, warmup
* `routing.*`, `dispatching.*`,
  `stochasticity.*`               - tunable policy / noise parameters

The resulting :class:`ScenarioConfig` is an immutable dataclass; mutation is
forbidden so simulation runs cannot accidentally drift from the spec on disk.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping

import yaml

# ---------------------------------------------------------------------------
# Defaults — used when a YAML file (or its ancestor chain) does not specify a
# value. Kept here, not in the YAML, so behaviour is explicit in code review.
# ---------------------------------------------------------------------------
DEFAULT_SHIFT_LENGTH_HOURS = 8
DEFAULT_REPLICATIONS = 30
DEFAULT_BASE_RANDOM_SEED = 12345
DEFAULT_WARMUP_MINUTES = 0
DEFAULT_TRAVEL_NOISE_CV = 0.10
DEFAULT_TRUCK_COUNT = 8


# ---------------------------------------------------------------------------
# Override dataclasses — each is a sparse patch applied on top of the CSV
# topology / fleet / dump-point data. Missing fields == "do not override".
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class EdgeOverride:
    """Patch applied to a single edge_id from edges.csv."""

    capacity: int | None = None
    max_speed_kph: float | None = None
    closed: bool | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "EdgeOverride":
        return cls(
            capacity=raw.get("capacity"),
            max_speed_kph=raw.get("max_speed_kph"),
            closed=raw.get("closed"),
        )


@dataclass(frozen=True)
class DumpPointOverride:
    """Patch applied to a single dump point row from dump_points.csv."""

    mean_dump_time_min: float | None = None
    sd_dump_time_min: float | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "DumpPointOverride":
        return cls(
            mean_dump_time_min=raw.get("mean_dump_time_min"),
            sd_dump_time_min=raw.get("sd_dump_time_min"),
        )


@dataclass(frozen=True)
class NodeOverride:
    """Patch applied to a single node row from nodes.csv."""

    service_time_mean_min: float | None = None
    service_time_sd_min: float | None = None
    capacity: int | None = None

    @classmethod
    def from_mapping(cls, raw: Mapping[str, Any]) -> "NodeOverride":
        return cls(
            service_time_mean_min=raw.get("service_time_mean_min"),
            service_time_sd_min=raw.get("service_time_sd_min"),
            capacity=raw.get("capacity"),
        )


# ---------------------------------------------------------------------------
# Policy / stochasticity blocks
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SimulationParams:
    shift_length_hours: int = DEFAULT_SHIFT_LENGTH_HOURS
    replications: int = DEFAULT_REPLICATIONS
    base_random_seed: int = DEFAULT_BASE_RANDOM_SEED
    warmup_minutes: float = DEFAULT_WARMUP_MINUTES

    @property
    def shift_length_minutes(self) -> float:
        return self.shift_length_hours * 60.0


@dataclass(frozen=True)
class RoutingParams:
    objective: str = "shortest_time"
    allow_bypass: bool = True
    road_capacity_enabled: bool = True


@dataclass(frozen=True)
class DispatchingParams:
    policy: str = "nearest_available_loader"
    tie_breaker: str = "shortest_expected_cycle_time"


@dataclass(frozen=True)
class StochasticityParams:
    loading_time_distribution: str = "normal_truncated"
    dumping_time_distribution: str = "normal_truncated"
    travel_time_noise_cv: float = DEFAULT_TRAVEL_NOISE_CV


@dataclass(frozen=True)
class FleetParams:
    truck_count: int = DEFAULT_TRUCK_COUNT


# ---------------------------------------------------------------------------
# Top-level scenario record
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScenarioConfig:
    """Resolved scenario after inheritance and override merging.

    `edge_overrides`, `dump_point_overrides`, and `node_overrides` are keyed
    by their CSV ids (e.g. ``E03_UP``, ``D_CRUSH``, ``CRUSH``).
    """

    scenario_id: str
    description: str = ""
    simulation: SimulationParams = field(default_factory=SimulationParams)
    routing: RoutingParams = field(default_factory=RoutingParams)
    dispatching: DispatchingParams = field(default_factory=DispatchingParams)
    stochasticity: StochasticityParams = field(default_factory=StochasticityParams)
    fleet: FleetParams = field(default_factory=FleetParams)
    edge_overrides: Mapping[str, EdgeOverride] = field(default_factory=dict)
    dump_point_overrides: Mapping[str, DumpPointOverride] = field(default_factory=dict)
    node_overrides: Mapping[str, NodeOverride] = field(default_factory=dict)
    inherits: str | None = None

    # Helpers ----------------------------------------------------------------
    def replication_seed(self, replication_index: int) -> int:
        """Per-replication seed = base_seed + replication_index."""
        return self.simulation.base_random_seed + replication_index

    def closed_edge_ids(self) -> tuple[str, ...]:
        """Edges marked closed by this scenario's overrides."""
        return tuple(
            edge_id
            for edge_id, override in self.edge_overrides.items()
            if override.closed is True
        )

    def with_overrides(self, **kwargs: Any) -> "ScenarioConfig":
        """Return a new config with the given top-level fields replaced."""
        return replace(self, **kwargs)


# ---------------------------------------------------------------------------
# YAML loading with single-step inheritance
# ---------------------------------------------------------------------------
def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle) or {}
    if not isinstance(loaded, dict):
        raise ValueError(f"Scenario YAML at {path} must be a mapping at the top level")
    return loaded


def _deep_merge(base: dict[str, Any], patch: Mapping[str, Any]) -> dict[str, Any]:
    """Recursively merge `patch` onto `base`, returning a new dict.

    Mappings merge key-by-key; scalars and lists in `patch` overwrite `base`.
    Neither input is mutated.
    """
    out = dict(base)
    for key, patch_value in patch.items():
        base_value = out.get(key)
        if isinstance(base_value, dict) and isinstance(patch_value, Mapping):
            out[key] = _deep_merge(base_value, patch_value)
        else:
            out[key] = patch_value
    return out


def _resolve_inherited(
    raw: Mapping[str, Any],
    scenarios_dir: Path,
    seen: tuple[str, ...] = (),
) -> dict[str, Any]:
    """Walk the `inherits` chain and merge child onto parent."""
    parent_id = raw.get("inherits")
    if parent_id is None:
        return dict(raw)
    if parent_id in seen:
        chain = " -> ".join((*seen, parent_id))
        raise ValueError(f"Cyclic scenario inheritance detected: {chain}")
    parent_path = scenarios_dir / f"{parent_id}.yaml"
    if not parent_path.exists():
        raise FileNotFoundError(
            f"Scenario '{raw.get('scenario_id', '<unknown>')}' inherits from "
            f"'{parent_id}', but {parent_path} does not exist."
        )
    parent_raw = _read_yaml(parent_path)
    parent_resolved = _resolve_inherited(
        parent_raw,
        scenarios_dir,
        seen=(*seen, raw.get("scenario_id", "<unknown>")),
    )
    # The child's `inherits` key is intentionally dropped after resolution so
    # the merged dict reflects a fully flattened scenario.
    child = {k: v for k, v in raw.items() if k != "inherits"}
    merged = _deep_merge(parent_resolved, child)
    merged["inherits"] = parent_id
    return merged


def _build_simulation(raw: Mapping[str, Any]) -> SimulationParams:
    return SimulationParams(
        shift_length_hours=int(raw.get("shift_length_hours", DEFAULT_SHIFT_LENGTH_HOURS)),
        replications=int(raw.get("replications", DEFAULT_REPLICATIONS)),
        base_random_seed=int(raw.get("base_random_seed", DEFAULT_BASE_RANDOM_SEED)),
        warmup_minutes=float(raw.get("warmup_minutes", DEFAULT_WARMUP_MINUTES)),
    )


def _build_routing(raw: Mapping[str, Any]) -> RoutingParams:
    return RoutingParams(
        objective=str(raw.get("objective", "shortest_time")),
        allow_bypass=bool(raw.get("allow_bypass", True)),
        road_capacity_enabled=bool(raw.get("road_capacity_enabled", True)),
    )


def _build_dispatching(raw: Mapping[str, Any]) -> DispatchingParams:
    return DispatchingParams(
        policy=str(raw.get("policy", "nearest_available_loader")),
        tie_breaker=str(raw.get("tie_breaker", "shortest_expected_cycle_time")),
    )


def _build_stochasticity(raw: Mapping[str, Any]) -> StochasticityParams:
    return StochasticityParams(
        loading_time_distribution=str(
            raw.get("loading_time_distribution", "normal_truncated")
        ),
        dumping_time_distribution=str(
            raw.get("dumping_time_distribution", "normal_truncated")
        ),
        travel_time_noise_cv=float(
            raw.get("travel_time_noise_cv", DEFAULT_TRAVEL_NOISE_CV)
        ),
    )


def _build_fleet(raw: Mapping[str, Any]) -> FleetParams:
    return FleetParams(truck_count=int(raw.get("truck_count", DEFAULT_TRUCK_COUNT)))


def _build_overrides(
    raw: Mapping[str, Any],
    factory,
):
    return {key: factory(value) for key, value in raw.items()}


def scenario_from_mapping(raw: Mapping[str, Any]) -> ScenarioConfig:
    """Convert a fully merged YAML mapping into a :class:`ScenarioConfig`."""
    scenario_id = raw.get("scenario_id")
    if not scenario_id:
        raise ValueError("Scenario YAML missing required 'scenario_id'")
    return ScenarioConfig(
        scenario_id=str(scenario_id),
        description=str(raw.get("description", "")),
        simulation=_build_simulation(raw.get("simulation", {})),
        routing=_build_routing(raw.get("routing", {})),
        dispatching=_build_dispatching(raw.get("dispatching", {})),
        stochasticity=_build_stochasticity(raw.get("stochasticity", {})),
        fleet=_build_fleet(raw.get("fleet", {})),
        edge_overrides=_build_overrides(
            raw.get("edge_overrides", {}) or {}, EdgeOverride.from_mapping
        ),
        dump_point_overrides=_build_overrides(
            raw.get("dump_point_overrides", {}) or {}, DumpPointOverride.from_mapping
        ),
        node_overrides=_build_overrides(
            raw.get("node_overrides", {}) or {}, NodeOverride.from_mapping
        ),
        inherits=raw.get("inherits"),
    )


def load_scenario(path: str | Path) -> ScenarioConfig:
    """Load a single scenario YAML file, applying inheritance."""
    yaml_path = Path(path)
    if not yaml_path.exists():
        raise FileNotFoundError(f"Scenario YAML not found: {yaml_path}")
    raw = _read_yaml(yaml_path)
    merged = _resolve_inherited(raw, scenarios_dir=yaml_path.parent)
    return scenario_from_mapping(merged)


REQUIRED_SCENARIO_IDS: tuple[str, ...] = (
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
    "trucks_12_ramp_upgrade",
)


def load_all_scenarios(
    scenarios_dir: str | Path,
    required: tuple[str, ...] = REQUIRED_SCENARIO_IDS,
) -> dict[str, ScenarioConfig]:
    """Load every scenario in a directory, keyed by scenario_id.

    Verifies each ``required`` scenario_id is present so that a typo in a
    filename fails loudly rather than silently dropping a run.
    """
    directory = Path(scenarios_dir)
    if not directory.is_dir():
        raise NotADirectoryError(f"Scenarios directory not found: {directory}")
    scenarios: dict[str, ScenarioConfig] = {}
    for yaml_path in sorted(directory.glob("*.yaml")):
        config = load_scenario(yaml_path)
        if config.scenario_id in scenarios:
            raise ValueError(
                f"Duplicate scenario_id '{config.scenario_id}' "
                f"detected in {yaml_path}"
            )
        scenarios[config.scenario_id] = config
    missing = tuple(s for s in required if s not in scenarios)
    if missing:
        raise ValueError(
            f"Missing required scenario YAML(s): {missing}. "
            f"Found: {tuple(scenarios)}"
        )
    return scenarios


__all__ = [
    "DEFAULT_BASE_RANDOM_SEED",
    "DEFAULT_REPLICATIONS",
    "DEFAULT_SHIFT_LENGTH_HOURS",
    "DEFAULT_TRAVEL_NOISE_CV",
    "DEFAULT_TRUCK_COUNT",
    "DEFAULT_WARMUP_MINUTES",
    "DispatchingParams",
    "DumpPointOverride",
    "EdgeOverride",
    "FleetParams",
    "NodeOverride",
    "REQUIRED_SCENARIO_IDS",
    "RoutingParams",
    "ScenarioConfig",
    "SimulationParams",
    "StochasticityParams",
    "load_all_scenarios",
    "load_scenario",
    "scenario_from_mapping",
]
