import os
import math
import yaml
import numpy as np
import pandas as pd
from scipy import stats
from .simulation import MineSimulation

def deep_merge(dict1, dict2):
    """Recursively merges dict2 into dict1."""
    result = dict1.copy()
    for k, v in dict2.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = deep_merge(result[k], v)
        else:
            result[k] = v
    return result

def load_scenario(scenarios_dir, scenario_id):
    """Loads a scenario YAML, handling recursive inheritance."""
    yaml_path = os.path.join(scenarios_dir, f"{scenario_id}.yaml")
    if not os.path.exists(yaml_path):
        raise FileNotFoundError(f"Scenario file '{yaml_path}' not found.")
        
    with open(yaml_path, 'r') as f:
        config = yaml.safe_load(f)
        
    if 'inherits' in config:
        parent_id = config['inherits']
        parent_config = load_scenario(scenarios_dir, parent_id)
        merged = deep_merge(parent_config, config)
        merged['scenario_id'] = scenario_id  # Preserve child scenario_id
        return merged
    return config

def calculate_95ci(data):
    """Calculates 95% confidence interval using Student-t distribution."""
    n = len(data)
    if n <= 1:
        return np.mean(data), np.mean(data), np.mean(data)
    mean = np.mean(data)
    sem = stats.sem(data)
    # df = n - 1
    h = sem * stats.t.ppf((1 + 0.95) / 2.0, n - 1)
    return mean, max(0.0, mean - h), mean + h

class ExperimentRunner:
    def __init__(self, data_dir, output_dir):
        self.data_dir = data_dir
        self.scenarios_dir = os.path.join(data_dir, 'scenarios')
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        
        # Scenarios list
        self.scenario_ids = [
            'baseline',
            'trucks_4',
            'trucks_12',
            'ramp_upgrade',
            'crusher_slowdown',
            'ramp_closed'
        ]
        
    def run_all_scenarios(self):
        all_rep_results = []
        all_event_logs = []
        summary_scenarios = {}
        
        # We will also load and run our 7th scenario: trucks_12_ramp_upgrade
        # Let's create its config dynamically or by writing a YAML file.
        # It's cleaner to create its YAML in the scenarios directory so it can be parsed normally!
        self._write_combo_scenario_yaml()
        
        scenarios_to_run = self.scenario_ids + ['trucks_12_ramp_upgrade']
        
        print(f"Starting experiments. Running {len(scenarios_to_run)} scenarios with 30 replications each...")
        
        for sc_id in scenarios_to_run:
            print(f"Running scenario: {sc_id}...")
            scenario_config = load_scenario(self.scenarios_dir, sc_id)
            replications = scenario_config['simulation']['replications']
            
            sc_rep_results = []
            
            for rep_idx in range(replications):
                sim = MineSimulation(scenario_config, self.data_dir, rep_idx)
                rep_res = sim.run()
                sc_rep_results.append(rep_res)
                all_rep_results.append(rep_res)
                
                # Append event logs
                all_event_logs.extend(sim.event_log)
                
            # Aggregate stats across replications
            summary_scenarios[sc_id] = self._aggregate_scenario_results(sc_id, sc_rep_results)
            print(f"Scenario {sc_id} complete. Mean throughput: {summary_scenarios[sc_id]['total_tonnes_mean']:.1f} tonnes.")

        # Write results.csv
        self._write_results_csv(all_rep_results)
        
        # Write summary.json
        self._write_summary_json(summary_scenarios)
        
        # Write event_log.csv
        self._write_event_log_csv(all_event_logs)
        
        print("All experiment runs complete. Outputs generated.")

    def run_single_scenario(self, sc_id):
        if sc_id == 'trucks_12_ramp_upgrade':
            self._write_combo_scenario_yaml()
            
        print(f"Running single scenario: {sc_id}...")
        scenario_config = load_scenario(self.scenarios_dir, sc_id)
        replications = scenario_config['simulation']['replications']
        
        sc_rep_results = []
        all_event_logs = []
        
        for rep_idx in range(replications):
            sim = MineSimulation(scenario_config, self.data_dir, rep_idx)
            rep_res = sim.run()
            sc_rep_results.append(rep_res)
            all_event_logs.extend(sim.event_log)
            
        summary = self._aggregate_scenario_results(sc_id, sc_rep_results)
        print(f"Scenario {sc_id} complete. Mean throughput: {summary['total_tonnes_mean']:.1f} tonnes.")
        
        # Generate standalone results for this scenario
        self._write_results_csv(sc_rep_results, filename=f"results_{sc_id}.csv")
        self._write_event_log_csv(all_event_logs, filename=f"event_log_{sc_id}.csv")
        return summary

    def _write_combo_scenario_yaml(self):
        """Creates the trucks_12_ramp_upgrade.yaml file dynamically."""
        yaml_content = """scenario_id: trucks_12_ramp_upgrade
inherits: baseline
description: Proposed Combo - 12 Trucks and Upgraded Ramp

fleet:
  truck_count: 12

edge_overrides:
  E03_UP:
    capacity: 999
    max_speed_kph: 28
  E03_DOWN:
    capacity: 999
    max_speed_kph: 28
"""
        combo_path = os.path.join(self.scenarios_dir, "trucks_12_ramp_upgrade.yaml")
        if not os.path.exists(combo_path):
            with open(combo_path, 'w') as f:
                f.write(yaml_content)

    def _aggregate_scenario_results(self, scenario_id, rep_results):
        replications = len(rep_results)
        shift_length_hours = rep_results[0]['total_tonnes_delivered'] / rep_results[0]['tonnes_per_hour'] if rep_results[0]['tonnes_per_hour'] > 0 else 8.0
        
        # Extract series
        tonnes_list = [r['total_tonnes_delivered'] for r in rep_results]
        tph_list = [r['tonnes_per_hour'] for r in rep_results]
        cycle_list = [r['average_truck_cycle_time_min'] for r in rep_results]
        util_list = [r['average_truck_utilisation'] for r in rep_results]
        crush_util_list = [r['crusher_utilisation'] for r in rep_results]
        loader_q_list = [r['average_loader_queue_time_min'] for r in rep_results]
        crusher_q_list = [r['average_crusher_queue_time_min'] for r in rep_results]
        
        # CIs
        t_mean, t_low, t_high = calculate_95ci(tonnes_list)
        tph_mean, tph_low, tph_high = calculate_95ci(tph_list)
        
        # Loader utilities aggregate
        loader_utils_agg = {}
        for r in rep_results:
            for l_id, u in r['loader_utilisation'].items():
                loader_utils_agg.setdefault(l_id, []).append(u)
        loader_utilisation_mean = {l_id: float(np.mean(utils)) for l_id, utils in loader_utils_agg.items()}
        
        # Bottlenecks aggregate
        bottleneck_scores_agg = {}
        for r in rep_results:
            for res_id, score in r['bottleneck_scores'].items():
                bottleneck_scores_agg.setdefault(res_id, []).append(score)
        
        avg_bottlenecks = {res_id: float(np.mean(scores)) for res_id, scores in bottleneck_scores_agg.items()}
        sorted_bottlenecks = sorted(avg_bottlenecks.items(), key=lambda x: x[1], reverse=True)
        top_bottlenecks = [res_id for res_id, score in sorted_bottlenecks if score > 0.0]
        
        return {
            "replications": replications,
            "shift_length_hours": int(round(shift_length_hours)),
            "total_tonnes_mean": float(t_mean),
            "total_tonnes_ci95_low": float(t_low),
            "total_tonnes_ci95_high": float(t_high),
            "tonnes_per_hour_mean": float(tph_mean),
            "tonnes_per_hour_ci95_low": float(tph_low),
            "tonnes_per_hour_ci95_high": float(tph_high),
            "average_cycle_time_min": float(np.mean(cycle_list)),
            "truck_utilisation_mean": float(np.mean(util_list)),
            "loader_utilisation": loader_utilisation_mean,
            "crusher_utilisation": float(np.mean(crush_util_list)),
            "average_loader_queue_time_min": float(np.mean(loader_q_list)),
            "average_crusher_queue_time_min": float(np.mean(crusher_q_list)),
            "top_bottlenecks": top_bottlenecks
        }

    def _write_results_csv(self, rep_results, filename="results.csv"):
        rows = []
        for r in rep_results:
            rows.append({
                'scenario_id': r['scenario_id'],
                'replication': r['replication'],
                'random_seed': r['random_seed'],
                'total_tonnes_delivered': r['total_tonnes_delivered'],
                'tonnes_per_hour': r['tonnes_per_hour'],
                'average_truck_cycle_time_min': r['average_truck_cycle_time_min'],
                'average_truck_utilisation': r['average_truck_utilisation'],
                'crusher_utilisation': r['crusher_utilisation'],
                'average_loader_queue_time_min': r['average_loader_queue_time_min'],
                'average_crusher_queue_time_min': r['average_crusher_queue_time_min']
            })
        df = pd.DataFrame(rows)
        df.to_csv(os.path.join(self.output_dir, filename), index=False)

    def _write_summary_json(self, summary_scenarios):
        import json
        summary_data = {
            "benchmark_id": "001_synthetic_mine_throughput",
            "scenarios": summary_scenarios,
            "key_assumptions": [
                "Lognormal noise (10% CV) is applied to individual edge-traversal travel times to represent operational variances and prevent non-physical negative times.",
                "Stochastic loading and dumping service times are truncated normal distributions: max(0.1 min, normal(mean, sd)).",
                "Empty trucks are dynamically dispatched to loaders from PARK or CRUSH using a min expected completion score: travel_time + (queue_len + active) * loader_mean_load + loader_mean_load.",
                "All capacity-constrained edges of capacity 1 (such as ramps E03_UP/E03_DOWN, crusher approach, pit roads) are modeled as distinct queuing resources.",
                "Operations at the waste dump (WASTE) and maintenance bay (MAINT) are omitted since they are outside the primary crusher throughput objective boundary."
            ],
            "model_limitations": [
                "Ramp opposite-direction single-lane mutual exclusions are modeled as independent separate resources (E03_UP and E03_DOWN do not block each other).",
                "Trucks have perfect global information about queue lengths and active loadings at the exact moment of dispatch.",
                "No mechanical breakdowns, operator breaks, or weather delays are modeled."
            ],
            "additional_scenarios_proposed": [
                {
                    "scenario_id": "trucks_12_ramp_upgrade",
                    "description": "Proposed combination scenario of larger fleet size (12 trucks) and fully upgraded ramp capacity & speeds to analyze their combined synergetic effect.",
                    "throughput_gain_over_baseline_pct": float((summary_scenarios['trucks_12_ramp_upgrade']['total_tonnes_mean'] - summary_scenarios['baseline']['total_tonnes_mean']) / summary_scenarios['baseline']['total_tonnes_mean'] * 100.0)
                }
            ]
        }
        
        with open(os.path.join(self.output_dir, "summary.json"), "w") as f:
            json.dump(summary_data, f, indent=2)

    def _write_event_log_csv(self, event_log, filename="event_log.csv"):
        df = pd.DataFrame(event_log)
        df.to_csv(os.path.join(self.output_dir, filename), index=False)
