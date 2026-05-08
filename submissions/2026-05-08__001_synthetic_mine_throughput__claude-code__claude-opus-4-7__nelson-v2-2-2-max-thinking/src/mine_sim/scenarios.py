"""Scenario YAML loader with `inherits:` resolution and override merging."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml


@dataclass
class ScenarioConfig:
    scenario_id: str
    description: str
    shift_length_hours: float
    replications: int
    base_random_seed: int
    warmup_minutes: float
    routing: Dict[str, Any]
    production: Dict[str, Any]
    dispatching: Dict[str, Any]
    stochasticity: Dict[str, Any]
    truck_count: int
    edge_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    node_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    loader_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    dump_point_overrides: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def shift_length_minutes(self) -> float:
        return self.shift_length_hours * 60.0


def _read_yaml(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive dict merge — override wins; lists are replaced, not concatenated."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if (
            k in out
            and isinstance(out[k], dict)
            and isinstance(v, dict)
        ):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def _resolve_inheritance(scenarios_dir: Path, raw: Dict[str, Any]) -> Dict[str, Any]:
    """Walk the `inherits:` chain (one level deep is enough for our scenarios)."""
    if "inherits" not in raw:
        return raw
    parent_id = raw["inherits"]
    parent_path = scenarios_dir / f"{parent_id}.yaml"
    parent_raw = _read_yaml(parent_path)
    parent_resolved = _resolve_inheritance(scenarios_dir, parent_raw)
    merged = _deep_merge(parent_resolved, raw)
    merged.pop("inherits", None)
    return merged


def _build_synthetic_scenario(
    raw_resolved: Dict[str, Any],
    scenario_id: str,
    description: str,
    extra_edge_overrides: Optional[Dict[str, Dict[str, Any]]] = None,
    extra_truck_count: Optional[int] = None,
) -> Dict[str, Any]:
    """Compose the trucks_12_ramp_upgrade synthetic scenario at load time."""
    out = copy.deepcopy(raw_resolved)
    out["scenario_id"] = scenario_id
    out["description"] = description
    if extra_edge_overrides:
        eo = out.get("edge_overrides", {}) or {}
        out["edge_overrides"] = _deep_merge(eo, extra_edge_overrides)
    if extra_truck_count is not None:
        out.setdefault("fleet", {})["truck_count"] = extra_truck_count
    return out


def load_scenario(scenarios_dir: Path, scenario_id: str) -> ScenarioConfig:
    """Load a scenario YAML by id, resolving inheritance and overrides."""
    scenarios_dir = Path(scenarios_dir)
    if scenario_id == "trucks_12_ramp_upgrade":
        # Synthetic combo scenario: inherit baseline + apply ramp upgrade and 12 trucks.
        baseline = _resolve_inheritance(scenarios_dir, _read_yaml(scenarios_dir / "baseline.yaml"))
        ramp_overrides = (
            _read_yaml(scenarios_dir / "ramp_upgrade.yaml").get("edge_overrides", {}) or {}
        )
        merged = _build_synthetic_scenario(
            baseline,
            scenario_id="trucks_12_ramp_upgrade",
            description="Combined: 12 trucks AND main ramp upgraded (capacity + speed)",
            extra_edge_overrides=ramp_overrides,
            extra_truck_count=12,
        )
        return _to_config(merged)
    path = scenarios_dir / f"{scenario_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    raw = _read_yaml(path)
    resolved = _resolve_inheritance(scenarios_dir, raw)
    return _to_config(resolved)


def _to_config(resolved: Dict[str, Any]) -> ScenarioConfig:
    sim = resolved.get("simulation", {}) or {}
    fleet = resolved.get("fleet", {}) or {}
    return ScenarioConfig(
        scenario_id=resolved["scenario_id"],
        description=resolved.get("description", ""),
        shift_length_hours=float(sim.get("shift_length_hours", 8)),
        replications=int(sim.get("replications", 30)),
        base_random_seed=int(sim.get("base_random_seed", 12345)),
        warmup_minutes=float(sim.get("warmup_minutes", 0)),
        routing=resolved.get("routing", {}) or {},
        production=resolved.get("production", {}) or {},
        dispatching=resolved.get("dispatching", {}) or {},
        stochasticity=resolved.get("stochasticity", {}) or {},
        truck_count=int(fleet.get("truck_count", 8)),
        edge_overrides=resolved.get("edge_overrides", {}) or {},
        node_overrides=resolved.get("node_overrides", {}) or {},
        loader_overrides=resolved.get("loader_overrides", {}) or {},
        dump_point_overrides=resolved.get("dump_point_overrides", {}) or {},
        extra={k: v for k, v in resolved.items() if k not in {
            "scenario_id", "description", "simulation", "routing", "production",
            "dispatching", "stochasticity", "fleet",
            "edge_overrides", "node_overrides", "loader_overrides", "dump_point_overrides",
        }},
    )


def list_required_scenarios() -> List[str]:
    """The seven scenarios this submission produces (six required + combo)."""
    return [
        "baseline",
        "trucks_4",
        "trucks_12",
        "ramp_upgrade",
        "crusher_slowdown",
        "ramp_closed",
        "trucks_12_ramp_upgrade",
    ]
