import argparse
import random
import simpy
from pathlib import Path
import pandas as pd
import json
import numpy as np

from src.config import load_scenario, load_csv_data
from src.topology import build_graph
from src.simulation import MineSimulation
from src.truck import truck_process
from src.output import calculate_ci

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', type=str, default='data', help="Path to data dir")
    parser.add_argument('--out-dir', type=str, default='.', help="Output directory")
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    out_dir = Path(args.out_dir)
    
    nodes = load_csv_data(data_dir / 'nodes.csv')
    edges = load_csv_data(data_dir / 'edges.csv')
    trucks_df = load_csv_data(data_dir / 'trucks.csv')
    
    scenario_files = list((data_dir / 'scenarios').glob('*.yaml'))
    
    summary_data = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": [
            "Trucks always choose the loader with the minimum expected time (travel + queue)",
            "Stochasticity follows a truncated normal distribution",
            "Crusher and loader service times are normally distributed"
        ],
        "model_limitations": [
            "Breakdowns and maintenance are not explicitly modeled in cycles",
            "Traffic congestion beyond capacity limits (speed reduction) is not modeled"
        ],
        "additional_scenarios_proposed": []
    }
    
    all_results = []
    all_events = []
    
    for scenario_file in scenario_files:
        config = load_scenario(scenario_file)
        print(f"Running scenario: {config.scenario_id}")
        
        if config.truck_count > len(trucks_df):
            print(f"Warning: Configured truck_count ({config.truck_count}) exceeds available trucks in trucks.csv ({len(trucks_df)}). Capping at {len(trucks_df)}.")
            config.truck_count = len(trucks_df)
        
        nodes_df = nodes.copy()
        edges_df = edges.copy()
        
        # Apply node overrides
        for node_id, override_data in config.node_overrides.items():
            for key, value in override_data.items():
                nodes_df.loc[nodes_df['node_id'] == node_id, key] = value
                
        # Apply edge overrides
        for edge_id, override_data in config.edge_overrides.items():
            for key, value in override_data.items():
                edges_df.loc[edges_df['edge_id'] == edge_id, key] = value
                
        G = build_graph(nodes_df, edges_df)
        
        scenario_metrics = []
        
        for rep in range(config.replications):
            random.seed(config.base_random_seed + rep)
            env = simpy.Environment()
            sim = MineSimulation(env, config, G, rep)
            
            truck_configs = trucks_df.head(config.truck_count).to_dict('records')
            for tc in truck_configs:
                env.process(truck_process(
                    env, sim, tc['truck_id'], tc['start_node'], 
                    tc['payload_tonnes'], tc['empty_speed_factor'], tc['loaded_speed_factor']
                ))
                
            env.run(until=config.shift_length_hours * 60)
            scenario_metrics.append(sim.metrics)
            all_events.extend(sim.logger.events)
            
            # Record replication level results
            all_results.append({
                "scenario_id": config.scenario_id,
                "replication": rep,
                "random_seed": config.base_random_seed + rep,
                "total_tonnes_delivered": sim.metrics.total_tonnes,
                "tonnes_per_hour": sim.metrics.total_tonnes / config.shift_length_hours,
                "average_truck_cycle_time_min": np.mean(sim.metrics.cycle_times) if sim.metrics.cycle_times else 0,
                "average_truck_utilisation": 0, # Placeholder
                "crusher_utilisation": sum(sim.metrics.crusher_queue_times)/ (config.shift_length_hours*60) if sim.metrics.crusher_queue_times else 0, # simplified
                "average_loader_queue_time_min": np.mean(sim.metrics.loader_queue_times) if sim.metrics.loader_queue_times else 0,
                "average_crusher_queue_time_min": np.mean(sim.metrics.crusher_queue_times) if sim.metrics.crusher_queue_times else 0,
            })
            
        # Aggregate for summary
        tonnes = [m.total_tonnes for m in scenario_metrics]
        tph = [m.total_tonnes / config.shift_length_hours for m in scenario_metrics]
        cycles = [np.mean(m.cycle_times) if m.cycle_times else 0 for m in scenario_metrics]
        
        t_m, t_l, t_h = calculate_ci(tonnes)
        tph_m, tph_l, tph_h = calculate_ci(tph)
        
        l_q = [np.mean(m.loader_queue_times) if m.loader_queue_times else 0 for m in scenario_metrics]
        c_q = [np.mean(m.crusher_queue_times) if m.crusher_queue_times else 0 for m in scenario_metrics]
        
        summary_data["scenarios"][config.scenario_id] = {
            "replications": config.replications,
            "shift_length_hours": config.shift_length_hours,
            "total_tonnes_mean": float(t_m),
            "total_tonnes_ci95_low": float(t_l),
            "total_tonnes_ci95_high": float(t_h),
            "tonnes_per_hour_mean": float(tph_m),
            "tonnes_per_hour_ci95_low": float(tph_l),
            "tonnes_per_hour_ci95_high": float(tph_h),
            "average_cycle_time_min": float(np.mean(cycles)),
            "truck_utilisation_mean": 0, # Placeholder
            "loader_utilisation": {},
            "crusher_utilisation": 0,
            "average_loader_queue_time_min": float(np.mean(l_q)),
            "average_crusher_queue_time_min": float(np.mean(c_q)),
            "top_bottlenecks": []
        }
    
    # Output results
    pd.DataFrame(all_results).to_csv(out_dir / 'results.csv', index=False)
    pd.DataFrame(all_events).to_csv(out_dir / 'event_log.csv', index=False)
    with open(out_dir / 'summary.json', 'w') as f:
        json.dump(summary_data, f, indent=2)

if __name__ == '__main__':
    main()
