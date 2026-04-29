import yaml
from dataclasses import dataclass, field
from typing import List, Dict

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
    edge_overrides: Dict = field(default_factory=dict)
    node_overrides: Dict = field(default_factory=dict)
    dump_point_overrides: Dict = field(default_factory=dict)

    @classmethod
    def from_yaml(cls, filepath):
        with open(filepath, 'r') as f:
            data = yaml.safe_load(f)
            
        if 'inherits' in data:
            import os
            base_filepath = os.path.join(os.path.dirname(filepath), data['inherits'] + '.yaml')
            with open(base_filepath, 'r') as bf:
                base_data = yaml.safe_load(bf)
                
            def deep_update(d, u):
                for k, v in u.items():
                    if isinstance(v, dict) and k in d and isinstance(d[k], dict):
                        d[k] = deep_update(d[k], v)
                    else:
                        d[k] = v
                return d
                
            deep_update(base_data, data)
            data = base_data

        return cls(
            scenario_id=data['scenario_id'],
            shift_length_hours=data.get('simulation', {}).get('shift_length_hours', 8),
            replications=data.get('simulation', {}).get('replications', 1),
            base_random_seed=data.get('simulation', {}).get('base_random_seed', 42),
            truck_count=data.get('fleet', {}).get('truck_count', 8),
            ore_sources=data.get('production', {}).get('ore_sources', []),
            dump_destination=data.get('production', {}).get('dump_destination', ''),
            travel_time_noise_cv=data.get('stochasticity', {}).get('travel_time_noise_cv', 0.1),
            edge_overrides=data.get('edge_overrides', {}),
            node_overrides=data.get('node_overrides', {}),
            dump_point_overrides=data.get('dump_point_overrides', {})
        )
