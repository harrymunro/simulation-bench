import os
import json
import numpy as np
import pandas as pd
import scipy.stats as st
from sim_core import run_replication, load_data

scenarios = ['baseline', 'trucks_4', 'trucks_12', 'ramp_upgrade', 'crusher_slowdown', 'ramp_closed']
replications = 30
base_seed = 12345

all_results = []
all_events = []
summary = {
    "benchmark_id": "001_synthetic_mine_throughput",
    "scenarios": {},
    "key_assumptions": [
        "Trucks always dispatch to the loader with the lowest expected wait and travel time.",
        "Shortest path routing uses distance instead of pure time for simplicity, but speeds are similar.",
        "Trucks queue before entering single-capacity edges (ramp, crusher approach)."
    ],
    "model_limitations": [
        "No breakdowns or maintenance stops are simulated.",
        "Traffic congestion on unconstrained roads is not explicitly modeled."
    ],
    "additional_scenarios_proposed": []
}

def mean_ci(data):
    if len(data) < 2:
        return np.mean(data), np.mean(data), np.mean(data)
    mean = np.mean(data)
    se = st.sem(data)
    ci = se * st.t.ppf((1 + 0.95) / 2., len(data)-1)
    return mean, mean-ci, mean+ci

for sc in scenarios:
    print(f"Running {sc}...")
    sc_results = []
    
    # Load scenario config to check replications if overridden
    _, _, _, _, _, cfg = load_data(sc)
    reps = cfg.get('simulation', {}).get('replications', replications)
    shift_len = cfg.get('simulation', {}).get('shift_length_hours', 8)
    
    for i in range(reps):
        seed = base_seed + i
        res = run_replication(sc, i+1, seed, all_events)
        sc_results.append(res)
        all_results.append(res)
        
    df_res = pd.DataFrame(sc_results)
    
    total_tonnes_m, total_tonnes_l, total_tonnes_h = mean_ci(df_res['total_tonnes_delivered'])
    tph_m, tph_l, tph_h = mean_ci(df_res['tonnes_per_hour'])
    
    summary['scenarios'][sc] = {
        "replications": reps,
        "shift_length_hours": shift_len,
        "total_tonnes_mean": float(total_tonnes_m),
        "total_tonnes_ci95_low": float(total_tonnes_l),
        "total_tonnes_ci95_high": float(total_tonnes_h),
        "tonnes_per_hour_mean": float(tph_m),
        "tonnes_per_hour_ci95_low": float(tph_l),
        "tonnes_per_hour_ci95_high": float(tph_h),
        "average_cycle_time_min": float(df_res['average_truck_cycle_time_min'].mean()),
        "truck_utilisation_mean": float(df_res['average_truck_utilisation'].mean()),
        "loader_utilisation": {},
        "crusher_utilisation": float(df_res['crusher_utilisation'].mean()),
        "average_loader_queue_time_min": float(df_res['average_loader_queue_time_min'].mean()),
        "average_crusher_queue_time_min": float(df_res['average_crusher_queue_time_min'].mean()),
        "top_bottlenecks": []
    }
    
    # Determine bottleneck (e.g. queue times or high utilization)
    if df_res['average_crusher_queue_time_min'].mean() > df_res['average_loader_queue_time_min'].mean() * 2:
        summary['scenarios'][sc]['top_bottlenecks'].append("crusher")
    else:
        summary['scenarios'][sc]['top_bottlenecks'].append("loaders")
        
pd.DataFrame(all_results).to_csv('results.csv', index=False)
pd.DataFrame(all_events).to_csv('event_log.csv', index=False)
with open('summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print("Done.")
