"""Scenario YAML loader with `inherits:` merging."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import yaml


def deep_merge(parent: dict[str, Any], child: dict[str, Any]) -> dict[str, Any]:
    """Recursive merge: child wins on scalars/lists; child dicts merge into parent dicts.

    Returns a new dict; does not mutate inputs.
    """
    out = copy.deepcopy(parent)
    for key, child_val in child.items():
        parent_val = out.get(key)
        if isinstance(parent_val, dict) and isinstance(child_val, dict):
            out[key] = deep_merge(parent_val, child_val)
        else:
            out[key] = copy.deepcopy(child_val)
    return out


def load_scenario(scenario_id: str, scenarios_dir: Path) -> dict[str, Any]:
    """Load a scenario YAML, recursively resolving any `inherits:` parent."""
    path = Path(scenarios_dir) / f"{scenario_id}.yaml"
    with path.open() as fh:
        raw = yaml.safe_load(fh)
    if "inherits" in raw:
        parent = load_scenario(raw["inherits"], scenarios_dir)
        merged = deep_merge(parent, raw)
    else:
        merged = raw
    merged.pop("inherits", None)
    return merged
