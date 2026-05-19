import os
import argparse
from .experiment import ExperimentRunner

def main():
    parser = argparse.ArgumentParser(description="Synthetic Mine Throughput SimPy Discrete-Event Simulation")
    
    # Paths configuration
    current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    default_data_dir = os.path.join(current_dir, 'data')
    default_output_dir = current_dir
    
    parser.add_argument(
        '--data-dir', 
        type=str, 
        default=default_data_dir,
        help=f"Directory containing inputs like nodes.csv, edges.csv, etc. Default: {default_data_dir}"
    )
    parser.add_argument(
        '--output-dir', 
        type=str, 
        default=default_output_dir,
        help=f"Directory where outputs results.csv and summary.json will be saved. Default: {default_output_dir}"
    )
    
    # Run modes
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '--run-all', 
        action='store_true', 
        help="Run all scenarios (6 required + 7th combo scenario) with 30 replications each."
    )
    group.add_argument(
        '--scenario', 
        type=str, 
        help="Run a single specific scenario ID and print summary."
    )
    
    args = parser.parse_args()
    
    # Instantiate ExperimentRunner
    runner = ExperimentRunner(args.data_dir, args.output_dir)
    
    if args.run_all:
        runner.run_all_scenarios()
    elif args.scenario:
        summary = runner.run_single_scenario(args.scenario)
        print("\n" + "="*40)
        print(f"SUMMARY FOR SCENARIO: {args.scenario}")
        print("="*40)
        print(f"Replications:                    {summary['replications']}")
        print(f"Shift Length:                    {summary['shift_length_hours']} hours")
        print(f"Mean Throughput:                 {summary['total_tonnes_mean']:.2f} tonnes")
        print(f"Throughput 95% CI:               ({summary['total_tonnes_ci95_low']:.2f}, {summary['total_tonnes_ci95_high']:.2f}) tonnes")
        print(f"Mean Tonnes / Hour:              {summary['tonnes_per_hour_mean']:.2f} t/h")
        print(f"Tonnes / Hour 95% CI:            ({summary['tonnes_per_hour_ci95_low']:.2f}, {summary['tonnes_per_hour_ci95_high']:.2f}) t/h")
        print(f"Average Truck Cycle Time:        {summary['average_cycle_time_min']:.2f} minutes")
        print(f"Average Truck Utilisation:       {summary['truck_utilisation_mean']*100.0:.2f}%")
        print(f"Crusher Utilisation:             {summary['crusher_utilisation']*100.0:.2f}%")
        print(f"Average Loader Queue Wait:       {summary['average_loader_queue_time_min']:.2f} minutes")
        print(f"Average Crusher Queue Wait:      {summary['average_crusher_queue_time_min']:.2f} minutes")
        print("Loader Utilisations:")
        for l_id, u in summary['loader_utilisation'].items():
            print(f"  - {l_id}:                        {u*100.0:.2f}%")
        print(f"Top bottlenecks (by score):      {', '.join(summary['top_bottlenecks'][:5])}")
        print("="*40)

if __name__ == "__main__":
    main()
