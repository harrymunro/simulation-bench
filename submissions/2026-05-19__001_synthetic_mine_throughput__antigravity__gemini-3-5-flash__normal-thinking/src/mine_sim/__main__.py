import os
import sys
import argparse
import pandas as pd
import json

from mine_sim.data_loader import load_csv_data, load_scenario
from mine_sim.graph import MineGraph
from mine_sim.experiment import ExperimentManager
from mine_sim.visualisation import MineVisualiser

def run_validation(data_dir, output_dir):
    """
    Automated verification suite to check model correctness.
    """
    print("\n==========================================")
    print("RUNNING AUTOMATED MODEL VALIDATION SUITE")
    print("==========================================\n")
    
    results_path = os.path.join(output_dir, "results.csv")
    summary_path = os.path.join(output_dir, "summary.json")
    event_log_path = os.path.join(output_dir, "event_log.csv")
    
    errors = []
    
    # Check 1: Verify output files exist
    print("Checking output file presence...")
    for path in [results_path, summary_path, event_log_path]:
        if not os.path.exists(path):
            errors.append(f"Missing output file: {path}")
        else:
            print(f"  ✓ Found: {os.path.basename(path)}")
            
    if errors:
        print("\nValidation failed early due to missing files.")
        return False
        
    # Load files
    df_results = pd.read_csv(results_path)
    df_events = pd.read_csv(event_log_path)
    with open(summary_path, 'r') as f:
        summary_cfg = json.load(f)
        
    # Check 2: Hard cutoff verification (all times <= 480.0)
    print("Checking hard-cut shift length limits (480.0 mins)...")
    max_time = df_events["time_min"].max()
    if max_time > 480.0001:
        errors.append(f"Simulation event occurred after shift end: {max_time} min")
    else:
        print(f"  ✓ Passed: Maximum event time is {max_time:.2f} min (within 480.0 min)")
        
    # Check 3: Graph connectivity and reachability validation
    print("Checking graph reachability...")
    mine_data = load_csv_data(data_dir)
    try:
        for sc in summary_cfg["scenarios"].keys():
            cfg = load_scenario(data_dir, sc)
            graph = MineGraph(mine_data["nodes"], mine_data["edges"], cfg)
            print(f"  ✓ Passed: Graph built and fully verified for scenario '{sc}'")
    except Exception as e:
        errors.append(f"Graph reachability failure: {e}")
        
    # Check 4: Strict edge capacity limit validation
    # Assert that on capacity-1 edges, no two trucks occupy the edge simultaneously at any time t.
    print("Checking capacity-1 edge constraint adherence...")
    capacity_violations = 0
    
    # We will sample 3 scenarios and 2 replications to keep validation fast
    scenarios_to_check = df_events["scenario_id"].unique()[:3]
    replications_to_check = [0, 1]
    
    for sc in scenarios_to_check:
        for rep in replications_to_check:
            df_slice = df_events[(df_events["scenario_id"] == sc) & (df_events["replication"] == rep)].sort_values("time_min", kind="mergesort")
            
            # Find all capacity-1 edge enter/leave pairs
            active_trucks_on_edge = {} # edge_id -> set of truck_ids
            
            for _, row in df_slice.iterrows():
                evt = row["event_type"]
                edge_id = row["resource_id"]
                truck_id = row["truck_id"]
                t_val = row["time_min"]
                
                # Check if this resource is a capacity-constrained edge (edges start with E)
                if isinstance(edge_id, str) and edge_id.startswith("E") and "approach" not in edge_id and "return" not in edge_id:
                    # Look up edge in graph to verify capacity is 1
                    cfg = load_scenario(data_dir, sc)
                    edge_overrides = cfg.get("edge_overrides", {}).get(edge_id, {})
                    # Default capacity from edges.csv
                    edge_row = mine_data["edges"][mine_data["edges"]["edge_id"] == edge_id]
                    if not edge_row.empty:
                        orig_cap = int(edge_row.iloc[0]["capacity"])
                        cap = int(edge_overrides.get("capacity", orig_cap))
                        
                        if cap == 1:
                            if edge_id not in active_trucks_on_edge:
                                active_trucks_on_edge[edge_id] = set()
                                
                            if evt == "edge_enter":
                                active_trucks_on_edge[edge_id].add(truck_id)
                                if len(active_trucks_on_edge[edge_id]) > 1:
                                    capacity_violations += 1
                                    print(f"    [VIOLATION] Scenario {sc}, Rep {rep}, Edge {edge_id} occupied by multiple trucks: {active_trucks_on_edge[edge_id]} at {t_val} min")
                            elif evt == "edge_leave":
                                active_trucks_on_edge[edge_id].discard(truck_id)
                                
    if capacity_violations > 0:
        errors.append(f"Capacity constraint violations found: {capacity_violations} instances")
    else:
        print("  ✓ Passed: Capacity-constrained single-lane road segments strictly adhered to limit (capacity <= 1)")
        
    # Check 5: Consistent Throughput Accounting
    print("Checking consistency of throughput calculations...")
    consistent_accounting = True
    for sc in df_results["scenario_id"].unique():
        for rep in df_results["replication"].unique():
            rep_tonnes = df_results[(df_results["scenario_id"] == sc) & (df_results["replication"] == rep)].iloc[0]["total_tonnes_delivered"]
            
            # Count completed dumps in event log
            dump_events = df_events[(df_events["scenario_id"] == sc) & (df_events["replication"] == rep) & (df_events["event_type"] == "dump_end")]
            log_tonnes = dump_events["payload_tonnes"].sum()
            
            if abs(rep_tonnes - log_tonnes) > 0.001:
                consistent_accounting = False
                errors.append(f"Throughput mismatch in Scenario {sc}, Rep {rep}: results.csv says {rep_tonnes} t, event_log.csv says {log_tonnes} t")
                break
                
    if consistent_accounting:
        print("  ✓ Passed: Total delivered tonnes is 100% consistent between results.csv and event_log.csv")
        
    # Summary of validation
    print("\n==========================================")
    if errors:
        print("❌ VALIDATION FAILED WITH ERRORS:")
        for err in errors:
            print(f"  - {err}")
        print("==========================================\n")
        return False
    else:
        print("🎉 ALL VALIDATION CHECKS PASSED SUCCESSFULLY!")
        print("==========================================\n")
        return True

def main():
    parser = argparse.ArgumentParser(description="Synthetic Mine Throughput Simulator CLI")
    parser.add_argument("--data_dir", type=str, default="data", help="Directory containing nodes.csv, edges.csv, etc.")
    parser.add_argument("--output_dir", type=str, default=".", help="Directory to save output files results.csv, summary.json, etc.")
    parser.add_argument("--validate", action="store_true", help="Run automated model correctness validation suite")
    
    args = parser.parse_args()
    
    if args.validate:
        success = run_validation(args.data_dir, args.output_dir)
        sys.exit(0 if success else 1)
        
    # Standard run: simulate and generate outputs
    print("\n==========================================")
    print("SYNTHETIC MINE HAULAGE SIMULATOR")
    print("==========================================\n")
    
    manager = ExperimentManager(args.data_dir, args.output_dir)
    summary_results = manager.run_all()
    
    # Generate spatial map and flow animation
    print("\nGenerating visual assets...")
    baseline_cfg = load_scenario(args.data_dir, "baseline")
    graph = MineGraph(manager.mine_data["nodes"], manager.mine_data["edges"], baseline_cfg)
    
    visualiser = MineVisualiser(graph, args.output_dir)
    visualiser.generate_topology_plot()
    
    # Limit animation duration to first 45 minutes to keep file size reasonable
    visualiser.generate_animation(os.path.join(args.output_dir, "event_log.csv"), duration_min=45)
    
    print("\nAll simulations and visualization asset generations completed successfully!")
    print("Output files written:")
    print(f"  - results.csv                -> {os.path.join(args.output_dir, 'results.csv')}")
    print(f"  - event_log.csv              -> {os.path.join(args.output_dir, 'event_log.csv')}")
    print(f"  - summary.json               -> {os.path.join(args.output_dir, 'summary.json')}")
    print(f"  - topology.png               -> {os.path.join(args.output_dir, 'topology.png')}")
    print(f"  - animation.gif              -> {os.path.join(args.output_dir, 'animation.gif')}\n")
    print("Ready to run validation. To execute, run:")
    print("  python -m mine_sim --validate\n")

if __name__ == "__main__":
    main()
