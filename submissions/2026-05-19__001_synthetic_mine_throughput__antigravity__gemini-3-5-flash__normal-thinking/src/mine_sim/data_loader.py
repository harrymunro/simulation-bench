import os
import yaml
import pandas as pd

def deep_merge(dict1, dict2):
    """
    Recursively merges dict2 into dict1.
    """
    merged = dict1.copy()
    for k, v in dict2.items():
        if k in merged and isinstance(merged[k], dict) and isinstance(v, dict):
            merged[k] = deep_merge(merged[k], v)
        else:
            merged[k] = v
    return merged

def load_yaml(filepath):
    """
    Loads a YAML file.
    """
    with open(filepath, 'r') as f:
        return yaml.safe_load(f)

def load_scenario(data_dir, scenario_id):
    """
    Loads a scenario configuration, resolving inheritance if specified.
    """
    scenarios_dir = os.path.join(data_dir, "scenarios")
    
    # Check for combo scenario 7: trucks_12_ramp_upgrade
    if scenario_id == "trucks_12_ramp_upgrade":
        # Combines trucks_12 and ramp_upgrade
        cfg = load_scenario(data_dir, "ramp_upgrade")
        cfg["fleet"]["truck_count"] = 12
        cfg["scenario_id"] = "trucks_12_ramp_upgrade"
        cfg["description"] = "Combined 12 trucks and narrow ramp upgrade scenario"
        return cfg
        
    scenario_file = os.path.join(scenarios_dir, f"{scenario_id}.yaml")
    if not os.path.exists(scenario_file):
        raise FileNotFoundError(f"Scenario config {scenario_file} not found")
        
    cfg = load_yaml(scenario_file)
    
    if "inherits" in cfg:
        parent_id = cfg["inherits"]
        parent_cfg = load_scenario(data_dir, parent_id)
        cfg = deep_merge(parent_cfg, cfg)
        
    return cfg

def load_csv_data(data_dir):
    """
    Loads all CSV files in the data directory.
    """
    nodes = pd.read_csv(os.path.join(data_dir, "nodes.csv"))
    edges = pd.read_csv(os.path.join(data_dir, "edges.csv"))
    trucks = pd.read_csv(os.path.join(data_dir, "trucks.csv"))
    loaders = pd.read_csv(os.path.join(data_dir, "loaders.csv"))
    dump_points = pd.read_csv(os.path.join(data_dir, "dump_points.csv"))
    
    # Strip whitespace from column names and string values
    for df in [nodes, edges, trucks, loaders, dump_points]:
        df.columns = df.columns.str.strip()
        for col in df.select_dtypes(include='object').columns:
            df[col] = df[col].str.strip()
            
    return {
        "nodes": nodes,
        "edges": edges,
        "trucks": trucks,
        "loaders": loaders,
        "dump_points": dump_points
    }
