import json
import pandas as pd
import numpy as np
import scipy.stats as st
from typing import List
from pathlib import Path

def calculate_ci(data: list, confidence=0.95):
    if not data or len(data) < 2:
        return np.mean(data) if data else 0, 0, 0
    a = 1.0 * np.array(data)
    m, se = np.mean(a), st.sem(a)
    h = se * st.t.ppf((1 + confidence) / 2., len(a)-1)
    return m, m-h, m+h

def generate_summary(metrics_list: List['SimulationMetrics'], config: 'Config', output_path: Path):
    tonnes = [m.total_tonnes for m in metrics_list]
    tph = [m.total_tonnes / config.shift_length_hours for m in metrics_list]
    cycles = [np.mean(m.cycle_times) if m.cycle_times else 0 for m in metrics_list]
    
    t_m, t_l, t_h = calculate_ci(tonnes)
    tph_m, tph_l, tph_h = calculate_ci(tph)
    
    summary = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {
            config.scenario_id: {
                "replications": config.replications,
                "shift_length_hours": config.shift_length_hours,
                "total_tonnes_mean": float(t_m),
                "total_tonnes_ci95_low": float(t_l),
                "total_tonnes_ci95_high": float(t_h),
                "tonnes_per_hour_mean": float(tph_m),
                "tonnes_per_hour_ci95_low": float(tph_l),
                "tonnes_per_hour_ci95_high": float(tph_h),
                "average_cycle_time_min": float(np.mean(cycles)),
            }
        }
    }
    
    with open(output_path, 'w') as f:
        json.dump(summary, f, indent=2)
