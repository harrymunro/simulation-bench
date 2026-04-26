"""Scenario loading and merging (resolves `inherits` chains)."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict

import yaml


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """Recursive merge: override wins; nested dicts merged, scalars/lists replaced."""
    out = copy.deepcopy(base)
    for k, v in override.items():
        if k == "inherits":
            continue
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_scenario(scenario_dir: Path, scenario_id: str) -> Dict[str, Any]:
    """Load a scenario YAML, recursively resolving `inherits`."""
    path = scenario_dir / f"{scenario_id}.yaml"
    with path.open("r") as fh:
        raw = yaml.safe_load(fh) or {}
    parent_id = raw.get("inherits")
    if parent_id:
        parent = load_scenario(scenario_dir, parent_id)
        merged = _deep_merge(parent, raw)
        merged["scenario_id"] = raw.get("scenario_id", scenario_id)
        return merged
    raw.setdefault("scenario_id", scenario_id)
    return raw


def list_scenarios(scenario_dir: Path) -> list[str]:
    return sorted(p.stem for p in scenario_dir.glob("*.yaml"))
