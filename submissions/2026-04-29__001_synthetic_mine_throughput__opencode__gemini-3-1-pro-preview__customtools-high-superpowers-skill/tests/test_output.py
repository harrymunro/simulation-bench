import json
from pathlib import Path
import numpy as np
import pytest
from src.output import calculate_ci, generate_summary

def test_calculate_ci_empty():
    mean, ci_low, ci_high = calculate_ci([])
    assert mean == 0
    assert ci_low == 0
    assert ci_high == 0

def test_calculate_ci_single_value():
    mean, ci_low, ci_high = calculate_ci([5.0])
    assert mean == 5.0
    assert ci_low == 0
    assert ci_high == 0

def test_calculate_ci_multiple_values():
    data = [10, 12, 15, 14, 11]
    mean, ci_low, ci_high = calculate_ci(data)
    assert mean == np.mean(data)
    assert ci_low < mean
    assert ci_high > mean

class MockConfig:
    def __init__(self):
        self.scenario_id = "test_scenario"
        self.replications = 30
        self.shift_length_hours = 12.0

class MockMetrics:
    def __init__(self, total_tonnes, cycle_times):
        self.total_tonnes = total_tonnes
        self.cycle_times = cycle_times

def test_generate_summary(tmp_path):
    config = MockConfig()
    metrics_list = [
        MockMetrics(1000, [10, 12, 11]),
        MockMetrics(1200, [9, 10, 11]),
        MockMetrics(1100, [10, 11, 12])
    ]
    output_path = tmp_path / "summary.json"
    
    generate_summary(metrics_list, config, output_path)
    
    assert output_path.exists()
    with open(output_path) as f:
        data = json.load(f)
        
    assert data["benchmark_id"] == "001_synthetic_mine_throughput"
    assert "test_scenario" in data["scenarios"]
    scenario_data = data["scenarios"]["test_scenario"]
    assert scenario_data["replications"] == 30
    assert scenario_data["shift_length_hours"] == 12.0
    assert scenario_data["total_tonnes_mean"] == 1100.0
