"""Scenario YAML loader with deep-merge inheritance."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


def _deep_merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = deepcopy(parent)
    for key, child_val in child.items():
        if (
            key in merged
            and isinstance(merged[key], dict)
            and isinstance(child_val, dict)
        ):
            merged[key] = _deep_merge(merged[key], child_val)
        else:
            merged[key] = deepcopy(child_val)
    return merged


def load_scenario(scenarios_dir: Path, scenario_id: str) -> dict[str, Any]:
    scenarios_dir = Path(scenarios_dir)
    path = scenarios_dir / f"{scenario_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Scenario file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario file {path} must contain a mapping at top level")

    inherits = raw.get("inherits")
    if inherits:
        parent = load_scenario(scenarios_dir, inherits)
        child = {k: v for k, v in raw.items() if k != "inherits"}
        merged = _deep_merge(parent, child)
        merged["scenario_id"] = raw.get("scenario_id", scenario_id)
        return merged

    return {k: v for k, v in raw.items() if k != "inherits"}


def list_scenarios(scenarios_dir: Path) -> list[str]:
    scenarios_dir = Path(scenarios_dir)
    return sorted(p.stem for p in scenarios_dir.glob("*.yaml"))
