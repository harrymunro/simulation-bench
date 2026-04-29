import yaml
import pandas as pd
from pathlib import Path
from dataclasses import dataclass

@dataclass
class Config:
    scenario_id: str
    shift_length_hours: int
    replications: int
    base_random_seed: int
    truck_count: int

def load_scenario(yaml_path: Path) -> Config:
    with open(yaml_path, 'r') as f:
        data = yaml.safe_load(f)
    return Config(
        scenario_id=data['scenario_id'],
        shift_length_hours=data['simulation']['shift_length_hours'],
        replications=data['simulation']['replications'],
        base_random_seed=data['simulation'].get('base_random_seed', 12345),
        truck_count=data['fleet']['truck_count']
    )

def load_csv_data(csv_path: Path) -> pd.DataFrame:
    return pd.read_csv(csv_path)
