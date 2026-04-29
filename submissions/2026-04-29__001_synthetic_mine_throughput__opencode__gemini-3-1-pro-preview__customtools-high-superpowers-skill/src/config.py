import yaml
import pandas as pd
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any
import copy

@dataclass
class Config:
    scenario_id: str
    shift_length_hours: int
    replications: int
    base_random_seed: int
    truck_count: int
    stochasticity_cv: float = 0.10
    edge_overrides: Dict[str, Any] = field(default_factory=dict)
    node_overrides: Dict[str, Any] = field(default_factory=dict)

def deep_update(d, u):
    for k, v in u.items():
        if isinstance(v, dict):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def load_scenario(yaml_path: Path) -> Config:
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
        
    if 'inherits' in data:
        base_path = yaml_path.parent / f"{data['inherits']}.yaml"
        with open(base_path, 'r') as f:
            base_data = yaml.safe_load(f)
        data = deep_update(base_data, data)
        
    return Config(
        scenario_id=data['scenario_id'],
        shift_length_hours=data['simulation']['shift_length_hours'],
        replications=data['simulation']['replications'],
        base_random_seed=data['simulation'].get('base_random_seed', 12345),
        truck_count=data['fleet']['truck_count'],
        stochasticity_cv=data.get('simulation', {}).get('stochasticity_cv', 0.10),
        edge_overrides=data.get('edge_overrides', {}),
        node_overrides=data.get('node_overrides', {})
    )

def load_csv_data(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)
