"""Scenario YAML loader with `inherits: baseline` resolution."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Dict, List

import yaml


def _deep_merge(base: dict, override: dict) -> dict:
    out = deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = deepcopy(v)
    return out


def load_scenarios(scenarios_dir: Path, names: List[str]) -> Dict[str, dict]:
    """Load named scenario files and resolve inheritance chain."""
    raw: Dict[str, dict] = {}
    for fp in scenarios_dir.glob("*.yaml"):
        with open(fp, "r", encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        raw[d["scenario_id"]] = d

    resolved: Dict[str, dict] = {}

    def _resolve(name: str, seen: set) -> dict:
        if name in resolved:
            return resolved[name]
        if name in seen:
            raise ValueError(f"Cycle in scenario inheritance: {name}")
        seen.add(name)
        d = raw[name]
        if "inherits" in d:
            base = _resolve(d["inherits"], seen)
            merged = _deep_merge(base, d)
        else:
            merged = deepcopy(d)
        resolved[name] = merged
        return merged

    out = {}
    for n in names:
        out[n] = _resolve(n, set())
    return out
