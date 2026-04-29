import argparse
import random
import simpy
from pathlib import Path
from src.config import load_scenario, load_csv_data
from src.topology import build_graph
from src.simulation import MineSimulation
from src.truck import truck_process
from src.output import generate_summary

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--scenario', type=str, required=True, help="Path to scenario yaml")
    parser.add_argument('--data-dir', type=str, default='data', help="Path to data dir")
    parser.add_argument('--out-dir', type=str, default='.', help="Output directory")
    args = parser.parse_args()
    
    config = load_scenario(Path(args.scenario))
    config.stochasticity_cv = 0.10 # Hardcoded fallback if not in yaml
    
    nodes = load_csv_data(Path(args.data_dir) / 'nodes.csv')
    edges = load_csv_data(Path(args.data_dir) / 'edges.csv')
    trucks_df = load_csv_data(Path(args.data_dir) / 'trucks.csv')
    
    G = build_graph(nodes, edges)
    
    all_metrics = []
    
    for rep in range(config.replications):
        random.seed(config.base_random_seed + rep)
        env = simpy.Environment()
        sim = MineSimulation(env, config, G, rep)
        
        # Spawn trucks based on config (up to fleet limit in csv)
        truck_configs = trucks_df.head(config.truck_count).to_dict('records')
        for tc in truck_configs:
            env.process(truck_process(
                env, sim, tc['truck_id'], tc['start_node'], 
                tc['payload_tonnes'], tc['empty_speed_factor'], tc['loaded_speed_factor']
            ))
            
        env.run(until=config.shift_length_hours * 60)
        all_metrics.append(sim.metrics)
        print(f"Replication {rep+1}/{config.replications} finished. Tonnes: {sim.metrics.total_tonnes}")
        
    generate_summary(all_metrics, config, Path(args.out_dir) / 'summary.json')
    print("Done!")

if __name__ == '__main__':
    main()
