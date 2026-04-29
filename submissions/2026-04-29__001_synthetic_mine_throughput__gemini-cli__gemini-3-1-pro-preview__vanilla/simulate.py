import os
import sys
import json
import yaml
import simpy
import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path

def load_scenario(scenario_id, scenarios_dir):
    with open(f"{scenarios_dir}/{scenario_id}.yaml", "r") as f:
        config = yaml.safe_load(f)
    if "inherits" in config:
        base_config = load_scenario(config["inherits"], scenarios_dir)
        def deep_update(d, u):
            for k, v in u.items():
                if isinstance(v, dict):
                    d[k] = deep_update(d.get(k, {}), v)
                else:
                    d[k] = v
            return d
        config = deep_update(base_config, config)
    return config

class MineSimulation:
    def __init__(self, env, scenario_id, config, replication, seed, nodes_df, edges_df, trucks_df, loaders_df, dump_points_df):
        self.env = env
        self.scenario_id = scenario_id
        self.config = config
        self.replication = replication
        self.rng = np.random.default_rng(seed)
        
        # Apply overrides
        self.edges = edges_df.copy()
        if "edge_overrides" in config:
            for eid, overrides in config["edge_overrides"].items():
                for k, v in overrides.items():
                    if eid in self.edges.index:
                        self.edges.at[eid, k] = v
        
        self.dump_points = dump_points_df.copy()
        if "dump_point_overrides" in config:
            for did, overrides in config["dump_point_overrides"].items():
                for k, v in overrides.items():
                    if did in self.dump_points.index:
                        self.dump_points.at[did, k] = v

        self.trucks = trucks_df.copy()
        if "fleet" in config and "truck_count" in config["fleet"]:
            self.trucks = self.trucks.head(config["fleet"]["truck_count"])

        self.loaders = loaders_df.copy()
        
        # Build Graph
        self.G = nx.DiGraph()
        for idx, row in self.edges.iterrows():
            if not row.get("closed", False):
                self.G.add_edge(row["from_node"], row["to_node"], id=idx, **row.to_dict())
                
        # Create Resources
        self.edge_resources = {}
        for idx, row in self.edges.iterrows():
            if not row.get("closed", False) and row["capacity"] < 100:
                self.edge_resources[idx] = simpy.Resource(env, capacity=int(row["capacity"]))
                
        self.loader_resources = {}
        for idx, row in self.loaders.iterrows():
            self.loader_resources[idx] = simpy.Resource(env, capacity=int(row["capacity"]))
            
        self.crusher_resource = simpy.Resource(env, capacity=int(self.dump_points.loc["D_CRUSH", "capacity"]))
        
        # Stats
        self.total_tonnes = 0
        self.event_log = []
        self.truck_cycle_times = []
        
        # Start processes
        for _, truck_row in self.trucks.iterrows():
            env.process(self.truck_process(truck_row))

    def log(self, truck_id, event_type, from_node, to_node, location, loaded, payload, resource_id, queue_length):
        self.event_log.append({
            "time_min": self.env.now,
            "replication": self.replication,
            "scenario_id": self.scenario_id,
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": loaded,
            "payload_tonnes": payload,
            "resource_id": resource_id,
            "queue_length": queue_length
        })

    def get_shortest_path(self, source, target, speed_factor):
        def weight(u, v, d):
            dist = d["distance_m"] / 1000
            speed = d["max_speed_kph"] * speed_factor
            return (dist / speed) * 60 # minutes
            
        try:
            path_nodes = nx.shortest_path(self.G, source=source, target=target, weight=weight)
            return path_nodes
        except nx.NetworkXNoPath:
            return None

    def truck_process(self, truck):
        tid = truck["truck_id"]
        payload_cap = truck["payload_tonnes"]
        empty_speed = truck["empty_speed_factor"]
        loaded_speed = truck["loaded_speed_factor"]
        
        current_node = truck["start_node"]
        
        while True:
            # 1. Decide which loader to go to
            best_loader = None
            best_time = float("inf")
            best_path = None
            
            for l_id, l_row in self.loaders.iterrows():
                l_node = l_row["node_id"]
                path = self.get_shortest_path(current_node, l_node, empty_speed)
                if path:
                    # Calculate expected time
                    travel_t = sum((self.G[path[i]][path[i+1]]["distance_m"]/1000)/(self.G[path[i]][path[i+1]]["max_speed_kph"]*empty_speed)*60 for i in range(len(path)-1))
                    queue_len = len(self.loader_resources[l_id].queue)
                    wait_t = queue_len * l_row["mean_load_time_min"]
                    total_t = travel_t + wait_t + l_row["mean_load_time_min"]
                    if total_t < best_time:
                        best_time = total_t
                        best_loader = l_id
                        best_path = path
                        
            if not best_loader:
                # print(f"Truck {tid} cannot find path to any loader from {current_node}")
                break
                
            cycle_start = self.env.now
            self.log(tid, "dispatch", current_node, best_path[-1], current_node, False, 0, "", 0)
            
            # Travel to loader
            for i in range(len(best_path)-1):
                u = best_path[i]
                v = best_path[i+1]
                edge_data = self.G[u][v]
                eid = edge_data["id"]
                t_travel = (edge_data["distance_m"]/1000) / (edge_data["max_speed_kph"]*empty_speed) * 60
                
                if eid in self.edge_resources:
                    self.log(tid, "join_road_queue", u, v, u, False, 0, eid, len(self.edge_resources[eid].queue))
                    with self.edge_resources[eid].request() as req:
                        yield req
                        self.log(tid, "enter_road", u, v, u, False, 0, eid, len(self.edge_resources[eid].queue))
                        yield self.env.timeout(t_travel)
                        self.log(tid, "leave_road", u, v, v, False, 0, eid, 0)
                else:
                    self.log(tid, "enter_road", u, v, u, False, 0, eid, 0)
                    yield self.env.timeout(t_travel)
                    self.log(tid, "leave_road", u, v, v, False, 0, eid, 0)
                    
            current_node = best_path[-1]
            
            # Load
            l_id = best_loader
            self.log(tid, "join_loader_queue", "", "", current_node, False, 0, l_id, len(self.loader_resources[l_id].queue))
            with self.loader_resources[l_id].request() as req:
                yield req
                self.log(tid, "loading_start", "", "", current_node, False, 0, l_id, 0)
                l_time = max(0, self.rng.normal(self.loaders.loc[l_id, "mean_load_time_min"], self.loaders.loc[l_id, "sd_load_time_min"]))
                yield self.env.timeout(l_time)
                self.log(tid, "loading_end", "", "", current_node, True, payload_cap, l_id, 0)
                
            # Travel to Crusher
            crush_node = self.dump_points.loc["D_CRUSH", "node_id"]
            path = self.get_shortest_path(current_node, crush_node, loaded_speed)
            if not path:
                # print(f"Truck {tid} cannot find path to crusher from {current_node}")
                break
                
            for i in range(len(path)-1):
                u = path[i]
                v = path[i+1]
                edge_data = self.G[u][v]
                eid = edge_data["id"]
                t_travel = (edge_data["distance_m"]/1000) / (edge_data["max_speed_kph"]*loaded_speed) * 60
                
                if eid in self.edge_resources:
                    self.log(tid, "join_road_queue", u, v, u, True, payload_cap, eid, len(self.edge_resources[eid].queue))
                    with self.edge_resources[eid].request() as req:
                        yield req
                        self.log(tid, "enter_road", u, v, u, True, payload_cap, eid, len(self.edge_resources[eid].queue))
                        yield self.env.timeout(t_travel)
                        self.log(tid, "leave_road", u, v, v, True, payload_cap, eid, 0)
                else:
                    self.log(tid, "enter_road", u, v, u, True, payload_cap, eid, 0)
                    yield self.env.timeout(t_travel)
                    self.log(tid, "leave_road", u, v, v, True, payload_cap, eid, 0)
                    
            current_node = path[-1]
            
            # Dump
            self.log(tid, "join_crusher_queue", "", "", current_node, True, payload_cap, "D_CRUSH", len(self.crusher_resource.queue))
            with self.crusher_resource.request() as req:
                yield req
                self.log(tid, "dumping_start", "", "", current_node, True, payload_cap, "D_CRUSH", 0)
                d_time = max(0, self.rng.normal(self.dump_points.loc["D_CRUSH", "mean_dump_time_min"], self.dump_points.loc["D_CRUSH", "sd_dump_time_min"]))
                yield self.env.timeout(d_time)
                self.total_tonnes += payload_cap
                self.truck_cycle_times.append(self.env.now - cycle_start)
                self.log(tid, "dumping_end", "", "", current_node, False, 0, "D_CRUSH", 0)

def main():
    nodes_df = pd.read_csv("data/nodes.csv").set_index("node_id")
    edges_df = pd.read_csv("data/edges.csv").set_index("edge_id")
    trucks_df = pd.read_csv("data/trucks.csv")
    loaders_df = pd.read_csv("data/loaders.csv").set_index("loader_id")
    dump_points_df = pd.read_csv("data/dump_points.csv").set_index("dump_id")

    scenarios = ["baseline", "trucks_4", "trucks_12", "ramp_upgrade", "crusher_slowdown", "ramp_closed"]
    
    all_event_logs = []
    all_results = []
    summary = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": [
            "Shortest-time dynamic routing using distance and speed limits.",
            "Dynamic loader dispatching based on minimum expected wait + travel time.",
            "Constrained single-lane roads handled as independent directional resources."
        ],
        "model_limitations": [
            "Truck speeds are independent of traffic unless on constrained segments.",
            "Breakdowns and operator delays are excluded."
        ],
        "additional_scenarios_proposed": []
    }

    for scenario_id in scenarios:
        config = load_scenario(scenario_id, "data/scenarios")
        
        sim_config = config.get("simulation", {})
        replications = sim_config.get("replications", 30)
        shift_length_hours = sim_config.get("shift_length_hours", 8)
        base_seed = sim_config.get("base_random_seed", 12345)
        
        scenario_tonnes = []
        scenario_tph = []
        scenario_cycle_times = []
        scenario_crusher_util = []
        scenario_truck_util = []
        
        # Loader queue wait times per replication
        scenario_loader_queue_times = []
        scenario_crusher_queue_times = []
        
        print(f"Running scenario {scenario_id} for {replications} replications...")
        
        for rep in range(replications):
            env = simpy.Environment()
            sim = MineSimulation(env, scenario_id, config, rep, base_seed + rep, 
                                 nodes_df, edges_df, trucks_df, loaders_df, dump_points_df)
            
            env.run(until=shift_length_hours * 60)
            
            all_event_logs.extend(sim.event_log)
            
            # Compute stats from log for this replication
            df_log = pd.DataFrame(sim.event_log)
            
            # Cycle time
            avg_cycle = np.mean(sim.truck_cycle_times) if sim.truck_cycle_times else 0
            
            # Utilizations
            if not df_log.empty:
                # Crusher util
                crush_starts = df_log[df_log["event_type"] == "dumping_start"]
                crush_ends = df_log[df_log["event_type"] == "dumping_end"]
                # Match them or simply sum differences if they ended. 
                # Better: sum the simulated dump times, or just total busy time.
                crush_busy_time = 0
                for _, row in crush_starts.iterrows():
                    # Find corresponding end
                    end_row = crush_ends[(crush_ends["truck_id"] == row["truck_id"]) & (crush_ends["time_min"] >= row["time_min"])]
                    if not end_row.empty:
                        crush_busy_time += end_row.iloc[0]["time_min"] - row["time_min"]
                    else:
                        crush_busy_time += (shift_length_hours * 60) - row["time_min"]
                c_util = crush_busy_time / (shift_length_hours * 60)
                
                # Loader util
                loader_busy_times = {}
                load_starts = df_log[df_log["event_type"] == "loading_start"]
                load_ends = df_log[df_log["event_type"] == "loading_end"]
                for l_id in loaders_df.index:
                    l_starts = load_starts[load_starts["resource_id"] == l_id]
                    l_ends = load_ends[load_ends["resource_id"] == l_id]
                    l_busy = 0
                    for _, row in l_starts.iterrows():
                        end_row = l_ends[(l_ends["truck_id"] == row["truck_id"]) & (l_ends["time_min"] >= row["time_min"])]
                        if not end_row.empty:
                            l_busy += end_row.iloc[0]["time_min"] - row["time_min"]
                        else:
                            l_busy += (shift_length_hours * 60) - row["time_min"]
                    loader_busy_times[l_id] = l_busy / (shift_length_hours * 60)
                
                # Queue times
                loader_joins = df_log[df_log["event_type"] == "join_loader_queue"]
                l_wait_times = []
                for _, row in loader_joins.iterrows():
                    start_row = load_starts[(load_starts["truck_id"] == row["truck_id"]) & (load_starts["time_min"] >= row["time_min"])]
                    if not start_row.empty:
                        l_wait_times.append(start_row.iloc[0]["time_min"] - row["time_min"])
                avg_l_wait = np.mean(l_wait_times) if l_wait_times else 0
                
                crusher_joins = df_log[df_log["event_type"] == "join_crusher_queue"]
                c_wait_times = []
                for _, row in crusher_joins.iterrows():
                    start_row = crush_starts[(crush_starts["truck_id"] == row["truck_id"]) & (crush_starts["time_min"] >= row["time_min"])]
                    if not start_row.empty:
                        c_wait_times.append(start_row.iloc[0]["time_min"] - row["time_min"])
                avg_c_wait = np.mean(c_wait_times) if c_wait_times else 0

                # Truck util (time not queuing)
                q_events = df_log[df_log["event_type"].str.contains("join")]
                q_end_events = df_log[df_log["event_type"].str.contains("start|enter_road")]
                total_q_time = 0
                for _, row in q_events.iterrows():
                    # For road, it's enter_road
                    ev_type = row["event_type"]
                    target_ev = "enter_road" if "road" in ev_type else ("loading_start" if "loader" in ev_type else "dumping_start")
                    end_row = q_end_events[(q_end_events["truck_id"] == row["truck_id"]) & (q_end_events["time_min"] >= row["time_min"]) & (q_end_events["event_type"] == target_ev)]
                    if not end_row.empty:
                        total_q_time += end_row.iloc[0]["time_min"] - row["time_min"]
                    else:
                        total_q_time += (shift_length_hours * 60) - row["time_min"]
                
                truck_count = len(sim.trucks)
                total_truck_time = truck_count * shift_length_hours * 60
                t_util = max(0, (total_truck_time - total_q_time) / total_truck_time) if total_truck_time > 0 else 0
                
            else:
                c_util = 0
                avg_l_wait = 0
                avg_c_wait = 0
                t_util = 0
            
            scenario_tonnes.append(sim.total_tonnes)
            scenario_tph.append(sim.total_tonnes / shift_length_hours)
            scenario_cycle_times.append(avg_cycle)
            scenario_crusher_util.append(c_util)
            scenario_truck_util.append(t_util)
            scenario_loader_queue_times.append(avg_l_wait)
            scenario_crusher_queue_times.append(avg_c_wait)
            
            all_results.append({
                "scenario_id": scenario_id,
                "replication": rep,
                "random_seed": base_seed + rep,
                "total_tonnes_delivered": sim.total_tonnes,
                "tonnes_per_hour": sim.total_tonnes / shift_length_hours,
                "average_truck_cycle_time_min": avg_cycle,
                "average_truck_utilisation": t_util,
                "crusher_utilisation": c_util,
                "average_loader_queue_time_min": avg_l_wait,
                "average_crusher_queue_time_min": avg_c_wait
            })

        def ci95(data):
            if not data: return 0, 0
            m = np.mean(data)
            se = scipy.stats.sem(data)
            h = se * scipy.stats.t.ppf((1 + 0.95) / 2., len(data)-1) if len(data) > 1 else 0
            return m - h, m + h

        import scipy.stats
        t_mean = np.mean(scenario_tonnes)
        t_low, t_high = ci95(scenario_tonnes)
        tph_mean = np.mean(scenario_tph)
        tph_low, tph_high = ci95(scenario_tph)
        
        summary["scenarios"][scenario_id] = {
            "replications": replications,
            "shift_length_hours": shift_length_hours,
            "total_tonnes_mean": round(t_mean, 2),
            "total_tonnes_ci95_low": round(t_low, 2),
            "total_tonnes_ci95_high": round(t_high, 2),
            "tonnes_per_hour_mean": round(tph_mean, 2),
            "tonnes_per_hour_ci95_low": round(tph_low, 2),
            "tonnes_per_hour_ci95_high": round(tph_high, 2),
            "average_cycle_time_min": round(np.mean(scenario_cycle_times), 2),
            "truck_utilisation_mean": round(np.mean(scenario_truck_util), 3),
            "loader_utilisation": {k: round(v, 3) for k, v in loader_busy_times.items()}, # using last rep for simplicity
            "crusher_utilisation": round(np.mean(scenario_crusher_util), 3),
            "average_loader_queue_time_min": round(np.mean(scenario_loader_queue_times), 2),
            "average_crusher_queue_time_min": round(np.mean(scenario_crusher_queue_times), 2),
            "top_bottlenecks": []
        }

        # Bottleneck detection logic
        if np.mean(scenario_crusher_util) > 0.85:
            summary["scenarios"][scenario_id]["top_bottlenecks"].append("crusher")
        if np.mean(scenario_loader_queue_times) > 5.0:
            summary["scenarios"][scenario_id]["top_bottlenecks"].append("loader_queues")
        # For road bottlenecks, we can check wait times in event log, but kept simple for now
        
    pd.DataFrame(all_results).to_csv("results.csv", index=False)
    pd.DataFrame(all_event_logs).to_csv("event_log.csv", index=False)
    with open("summary.json", "w") as f:
        json.dump(summary, f, indent=2)

if __name__ == "__main__":
    main()
