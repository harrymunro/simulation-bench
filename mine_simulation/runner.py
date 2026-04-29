import pandas as pd
import numpy as np
import json
from pathlib import Path
from .topology import MineTopology
from .config import ScenarioConfig
from .simulation import MineSimulation
from .truck import Truck
from .metrics import calculate_advanced_metrics

def run_replication(config: ScenarioConfig, topology: MineTopology, loaders_df, dump_points_df, trucks_df, seed):
    sim = MineSimulation(config, topology, loaders_df, dump_points_df, seed)
    
    # Initialize trucks based on fleet size
    for i in range(config.truck_count):
        # Default payload if not fully specified, though we have trucks_df
        payload = trucks_df.iloc[i]['payload_tonnes'] if i < len(trucks_df) else 100
        Truck(sim, f"T{i+1:02d}", payload)
        
    sim.env.run(until=config.shift_length_hours * 60)
    
    return sim.metrics, sim.event_log

def run_scenarios(data_dir: Path, output_dir: Path):
    topology = MineTopology(data_dir / "nodes.csv", data_dir / "edges.csv")
    loaders_df = pd.read_csv(data_dir / "loaders.csv")
    dump_points_df = pd.read_csv(data_dir / "dump_points.csv")
    trucks_df = pd.read_csv(data_dir / "trucks.csv")
    
    all_results = []
    all_events = []
    summary_data = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": ["Constant truck payload", "Instantaneous dispatch routing"],
        "model_limitations": ["No shift change/breaks modelled"],
        "additional_scenarios_proposed": []
    }
    
    scenarios_dir = data_dir / "scenarios"
    for yaml_file in scenarios_dir.glob("*.yaml"):
        config = ScenarioConfig.from_yaml(yaml_file)
        
        scenario_tonnes = []
        
        for rep in range(config.replications):
            seed = config.base_random_seed + rep
            metrics, events = run_replication(config, topology, loaders_df, dump_points_df, trucks_df, seed)
            
            total_tonnes = metrics["total_tonnes_delivered"]
            scenario_tonnes.append(total_tonnes)
            
            all_results.append({
                "scenario_id": config.scenario_id,
                "replication": rep,
                "random_seed": seed,
                "total_tonnes_delivered": total_tonnes,
                "tonnes_per_hour": total_tonnes / config.shift_length_hours
            })
            
            # add rep details to events
            for e in events:
                e["scenario_id"] = config.scenario_id
                e["replication"] = rep
            all_events.extend(events)
            
        # Calc 95% CI
        mean_t = np.mean(scenario_tonnes)
        std_t = np.std(scenario_tonnes, ddof=1)
        ci = 1.96 * (std_t / np.sqrt(config.replications))
        
        events_df = pd.DataFrame(all_events)
        scenario_events = events_df[events_df['scenario_id'] == config.scenario_id]
        adv_metrics = calculate_advanced_metrics(scenario_events, config.shift_length_hours, config.replications)
        
        summary_data["scenarios"][config.scenario_id] = {
            "replications": config.replications,
            "shift_length_hours": config.shift_length_hours,
            "total_tonnes_mean": float(mean_t),
            "total_tonnes_ci95_low": float(mean_t - ci),
            "total_tonnes_ci95_high": float(mean_t + ci),
            "tonnes_per_hour_mean": float(mean_t / config.shift_length_hours),
            "tonnes_per_hour_ci95_low": float((mean_t - ci) / config.shift_length_hours),
            "tonnes_per_hour_ci95_high": float((mean_t + ci) / config.shift_length_hours),
        }
        summary_data["scenarios"][config.scenario_id].update(adv_metrics)
        
    # NOTE: The advanced metrics calculation is modified in Task 5
    # For now, just dump the initial results
    
    pd.DataFrame(all_results).to_csv(output_dir / "results.csv", index=False)
    pd.DataFrame(all_events).to_csv(output_dir / "event_log.csv", index=False)
    
    with open(output_dir / "summary.json", 'w') as f:
        json.dump(summary_data, f, indent=2)

if __name__ == "__main__":
    run_scenarios(Path("../../data"), Path("."))