import yaml
from dataclasses import dataclass, field
from typing import List

@dataclass
class ScenarioConfig:
    scenario_id: str
    shift_length_hours: int
    replications: int
    base_random_seed: int
    truck_count: int
    ore_sources: List[str]
    dump_destination: str
    travel_time_noise_cv: float

    @classmethod
    def from_yaml(cls, filepath):
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
        return cls(
            scenario_id=data['scenario_id'],
            shift_length_hours=data['simulation']['shift_length_hours'],
            replications=data['simulation']['replications'],
            base_random_seed=data['simulation']['base_random_seed'],
            truck_count=data['fleet']['truck_count'],
            ore_sources=data['production']['ore_sources'],
            dump_destination=data['production']['dump_destination'],
            travel_time_noise_cv=data['stochasticity']['travel_time_noise_cv']
        )
