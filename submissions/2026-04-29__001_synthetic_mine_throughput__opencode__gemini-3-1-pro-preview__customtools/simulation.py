import simpy
import pandas as pd
import numpy as np
import networkx as nx
import yaml
import json
import random
import os
import copy
import scipy.stats as stats

def deep_update(d, u):
    import collections.abc
    for k, v in u.items():
        if isinstance(v, collections.abc.Mapping):
            d[k] = deep_update(d.get(k, {}), v)
        else:
            d[k] = v
    return d

def load_scenario(scenario_name, scenarios_dir):
    with open(os.path.join(scenarios_dir, f"{scenario_name}.yaml"), 'r') as f:
        scenario = yaml.safe_load(f)
    if 'inherits' in scenario:
        base_scenario = load_scenario(scenario['inherits'], scenarios_dir)
        scenario = deep_update(base_scenario, scenario)
    return scenario

class ResourceProxy:
    def __init__(self, name, resource):
        self.name = name
        self.resource = resource

def run_simulation():
    data_dir = 'data'
    scenarios_dir = os.path.join(data_dir, 'scenarios')
    
    nodes_df = pd.read_csv(os.path.join(data_dir, 'nodes.csv'))
    edges_df = pd.read_csv(os.path.join(data_dir, 'edges.csv'))
    trucks_df = pd.read_csv(os.path.join(data_dir, 'trucks.csv'))
    loaders_df = pd.read_csv(os.path.join(data_dir, 'loaders.csv'))
    dumps_df = pd.read_csv(os.path.join(data_dir, 'dump_points.csv'))
    
    scenario_files = [f for f in os.listdir(scenarios_dir) if f.endswith('.yaml')]
    scenario_names = [f.split('.')[0] for f in scenario_files]
    
    # Required scenarios
    required_scenarios = ['baseline', 'trucks_4', 'trucks_12', 'ramp_upgrade', 'crusher_slowdown', 'ramp_closed']
    for req in required_scenarios:
        if req not in scenario_names:
            print(f"Warning: {req} not found in scenarios directory.")
            
    all_results = []
    all_events = []
    summary_data = {
        "benchmark_id": "001_synthetic_mine_throughput",
        "scenarios": {},
        "key_assumptions": [
            "Trucks wait at the start of constrained edges until clear",
            "Dispatch uses shortest expected cycle time heuristic",
            "Speeds and load/dump times follow normal distributions truncated at >0.1"
        ],
        "model_limitations": [
            "Continuous physical traffic flow is approximated using discrete edges and travel times"
        ],
        "additional_scenarios_proposed": []
    }
    
    for scenario_name in required_scenarios:
        if scenario_name not in scenario_names:
            continue
        
        scenario_config = load_scenario(scenario_name, scenarios_dir)
        shift_length_hours = scenario_config.get('simulation', {}).get('shift_length_hours', 8)
        sim_time_min = shift_length_hours * 60
        replications = scenario_config.get('simulation', {}).get('replications', 30)
        base_seed = scenario_config.get('simulation', {}).get('base_random_seed', 12345)
        
        truck_count = scenario_config.get('fleet', {}).get('truck_count', 8)
        travel_cv = scenario_config.get('stochasticity', {}).get('travel_time_noise_cv', 0.10)
        
        scenario_results = []
        
        for rep in range(replications):
            seed = base_seed + rep
            random.seed(seed)
            np.random.seed(seed)
            
            env = simpy.Environment()
            
            # Apply overrides
            cur_edges_df = edges_df.copy()
            cur_nodes_df = nodes_df.copy()
            cur_dumps_df = dumps_df.copy()
            
            edge_overrides = scenario_config.get('edge_overrides', {})
            for e_id, overrides in edge_overrides.items():
                idx = cur_edges_df[cur_edges_df['edge_id'] == e_id].index
                if len(idx) > 0:
                    for k, v in overrides.items():
                        cur_edges_df.loc[idx, k] = v
                        
            node_overrides = scenario_config.get('node_overrides', {})
            for n_id, overrides in node_overrides.items():
                idx = cur_nodes_df[cur_nodes_df['node_id'] == n_id].index
                if len(idx) > 0:
                    for k, v in overrides.items():
                        cur_nodes_df.loc[idx, k] = v
                        
            dump_overrides = scenario_config.get('dump_point_overrides', {})
            for d_id, overrides in dump_overrides.items():
                idx = cur_dumps_df[cur_dumps_df['dump_id'] == d_id].index
                if len(idx) > 0:
                    for k, v in overrides.items():
                        cur_dumps_df.loc[idx, k] = v
            
            # Build graph and resources
            road_resources = {}
            edge_resource_map = {}
            G_empty = nx.DiGraph()
            G_loaded = nx.DiGraph()
            
            for _, row in cur_edges_df.iterrows():
                # Handle 'closed' flag which might be boolean or string
                closed_val = row.get('closed', False)
                if str(closed_val).lower() == 'true':
                    continue
                    
                u, v = row['from_node'], row['to_node']
                dist = row['distance_m']
                speed_kph = row['max_speed_kph']
                cap = row.get('capacity', 999)
                edge_id = row['edge_id']
                
                base_time = dist / (speed_kph * 1000 / 60)
                G_empty.add_edge(u, v, weight=base_time / 1.0, distance_m=dist, max_speed_kph=speed_kph, edge_id=edge_id)
                G_loaded.add_edge(u, v, weight=base_time / 0.85, distance_m=dist, max_speed_kph=speed_kph, edge_id=edge_id)
                
                if cap == 1:
                    res_name = f"Road_{'-'.join(sorted([u, v]))}"
                    if res_name not in road_resources:
                        road_resources[res_name] = simpy.Resource(env, capacity=1)
                    edge_resource_map[edge_id] = ResourceProxy(res_name, road_resources[res_name])
            
            # Setup loaders
            loaders = []
            trucks_en_route = {}
            for _, row in loaders_df.iterrows():
                node_id = row['node_id']
                mean_t = row['mean_load_time_min']
                sd_t = row['sd_load_time_min']
                res = simpy.Resource(env, capacity=1)
                lid = row['loader_id']
                loaders.append({
                    'id': lid,
                    'node_id': node_id,
                    'resource': ResourceProxy(f"Loader_{node_id}", res),
                    'mean': mean_t,
                    'sd': sd_t
                })
                trucks_en_route[lid] = 0
                
            # Setup crusher
            crush_row = cur_dumps_df[cur_dumps_df['node_id'] == 'CRUSH'].iloc[0]
            crusher = {
                'id': crush_row['dump_id'],
                'node_id': 'CRUSH',
                'resource': ResourceProxy("Crusher", simpy.Resource(env, capacity=1)),
                'mean': crush_row['mean_dump_time_min'],
                'sd': crush_row['sd_dump_time_min']
            }
            
            # Tracking
            tracker = {
                'total_tonnes': 0,
                'cycle_times': [],
                'loader_queue_times': [],
                'crusher_queue_times': [],
                'truck_active_time': 0,
                'truck_total_time': 0,
                'loader_active_time': {l['id']: 0 for l in loaders},
                'crusher_active_time': 0
            }
            
            def log_event(time, t_id, ev_type, u='', v='', loc='', loaded=False, payload=0, res_id='', q_len=0):
                if rep < 5:  # Only save events for first 5 reps to save memory/file size
                    all_events.append({
                        'time_min': round(time, 3),
                        'replication': rep,
                        'scenario_id': scenario_name,
                        'truck_id': t_id,
                        'event_type': ev_type,
                        'from_node': u,
                        'to_node': v,
                        'location': loc,
                        'loaded': loaded,
                        'payload_tonnes': payload,
                        'resource_id': res_id,
                        'queue_length': q_len
                    })

            def traverse_path(truck_id, path, is_loaded, payload, speed_factor, graph):
                for i in range(len(path) - 1):
                    u, v = path[i], path[i+1]
                    edge_data = graph.get_edge_data(u, v)
                    edge_id = edge_data['edge_id']
                    base_time = (edge_data['distance_m'] / (edge_data['max_speed_kph'] * 1000 / 60)) / speed_factor
                    actual_time = max(0.1, random.gauss(base_time, base_time * travel_cv))
                    
                    res_proxy = edge_resource_map.get(edge_id)
                    if res_proxy:
                        log_event(env.now, truck_id, 'queue_start', u, v, res_id=res_proxy.name, q_len=len(res_proxy.resource.queue))
                        q_start = env.now
                        with res_proxy.resource.request() as req:
                            yield req
                            q_time = env.now - q_start
                            tracker['truck_total_time'] += q_time # Wait time is not active
                            
                            log_event(env.now, truck_id, 'queue_end', u, v, res_id=res_proxy.name)
                            log_event(env.now, truck_id, 'travel_start', u, v, res_id=res_proxy.name)
                            
                            start_travel = env.now
                            yield env.timeout(actual_time)
                            
                            tracker['truck_active_time'] += (env.now - start_travel)
                            tracker['truck_total_time'] += (env.now - start_travel)
                            
                            log_event(env.now, truck_id, 'travel_end', u, v, res_id=res_proxy.name)
                    else:
                        log_event(env.now, truck_id, 'travel_start', u, v)
                        start_travel = env.now
                        yield env.timeout(actual_time)
                        tracker['truck_active_time'] += (env.now - start_travel)
                        tracker['truck_total_time'] += (env.now - start_travel)
                        log_event(env.now, truck_id, 'travel_end', u, v)

            def truck_process(t_id, payload_cap, empty_sf, loaded_sf, start_node):
                location = start_node
                cycle_start = env.now
                
                while env.now < sim_time_min:
                    # Dispatch
                    best_loader = None
                    best_score = float('inf')
                    for l in loaders:
                        if not nx.has_path(G_empty, location, l['node_id']):
                            continue
                        travel_time = nx.shortest_path_length(G_empty, location, l['node_id'], weight='weight')
                        num_ahead = len(l['resource'].resource.queue) + l['resource'].resource.count + trucks_en_route[l['id']]
                        expected_wait = num_ahead * l['mean']
                        score = travel_time + expected_wait
                        if score < best_score:
                            best_score = score
                            best_loader = l
                            
                    if not best_loader:
                        # Cannot reach any loader
                        yield env.timeout(10)
                        tracker['truck_total_time'] += 10
                        continue
                        
                    # Travel to loader
                    trucks_en_route[best_loader['id']] += 1
                    path_to_loader = nx.shortest_path(G_empty, location, best_loader['node_id'], weight='weight')
                    yield from traverse_path(t_id, path_to_loader, False, 0, empty_sf, G_empty)
                    trucks_en_route[best_loader['id']] -= 1
                    
                    # Load
                    location = best_loader['node_id']
                    log_event(env.now, t_id, 'queue_start', loc=location, res_id=best_loader['resource'].name, q_len=len(best_loader['resource'].resource.queue))
                    q_start = env.now
                    with best_loader['resource'].resource.request() as req:
                        yield req
                        q_time = env.now - q_start
                        tracker['loader_queue_times'].append(q_time)
                        tracker['truck_total_time'] += q_time
                        
                        log_event(env.now, t_id, 'queue_end', loc=location, res_id=best_loader['resource'].name)
                        log_event(env.now, t_id, 'load_start', loc=location, res_id=best_loader['resource'].name)
                        
                        load_time = max(0.1, random.gauss(best_loader['mean'], best_loader['sd']))
                        yield env.timeout(load_time)
                        
                        tracker['loader_active_time'][best_loader['id']] += load_time
                        tracker['truck_active_time'] += load_time
                        tracker['truck_total_time'] += load_time
                        
                        log_event(env.now, t_id, 'load_end', loc=location, res_id=best_loader['resource'].name, loaded=True, payload=payload_cap)
                    
                    # Route to crusher
                    if not nx.has_path(G_loaded, location, 'CRUSH'):
                        yield env.timeout(10)
                        tracker['truck_total_time'] += 10
                        continue
                        
                    path_to_crush = nx.shortest_path(G_loaded, location, 'CRUSH', weight='weight')
                    yield from traverse_path(t_id, path_to_crush, True, payload_cap, loaded_sf, G_loaded)
                    
                    # Dump
                    location = 'CRUSH'
                    log_event(env.now, t_id, 'queue_start', loc=location, res_id=crusher['resource'].name, q_len=len(crusher['resource'].resource.queue))
                    q_start = env.now
                    with crusher['resource'].resource.request() as req:
                        yield req
                        q_time = env.now - q_start
                        tracker['crusher_queue_times'].append(q_time)
                        tracker['truck_total_time'] += q_time
                        
                        log_event(env.now, t_id, 'queue_end', loc=location, res_id=crusher['resource'].name)
                        log_event(env.now, t_id, 'dump_start', loc=location, res_id=crusher['resource'].name, loaded=True, payload=payload_cap)
                        
                        dump_time = max(0.1, random.gauss(crusher['mean'], crusher['sd']))
                        yield env.timeout(dump_time)
                        
                        tracker['crusher_active_time'] += dump_time
                        tracker['total_tonnes'] += payload_cap
                        tracker['truck_active_time'] += dump_time
                        tracker['truck_total_time'] += dump_time
                        
                        log_event(env.now, t_id, 'dump_end', loc=location, res_id=crusher['resource'].name, loaded=False, payload=0)
                    
                    # Cycle complete
                    tracker['cycle_times'].append(env.now - cycle_start)
                    cycle_start = env.now

            # Start processes
            for i in range(min(truck_count, len(trucks_df))):
                t_row = trucks_df.iloc[i]
                env.process(truck_process(t_row['truck_id'], t_row['payload_tonnes'], t_row['empty_speed_factor'], t_row['loaded_speed_factor'], t_row['start_node']))
                
            env.run(until=sim_time_min)
            
            # Record replication results
            total_t = tracker['total_tonnes']
            tph = total_t / shift_length_hours
            avg_cycle = np.mean(tracker['cycle_times']) if tracker['cycle_times'] else 0
            truck_util = (tracker['truck_active_time'] / tracker['truck_total_time']) if tracker['truck_total_time'] > 0 else 0
            crush_util = tracker['crusher_active_time'] / sim_time_min
            avg_l_q = np.mean(tracker['loader_queue_times']) if tracker['loader_queue_times'] else 0
            avg_c_q = np.mean(tracker['crusher_queue_times']) if tracker['crusher_queue_times'] else 0
            
            all_results.append({
                'scenario_id': scenario_name,
                'replication': rep,
                'random_seed': seed,
                'total_tonnes_delivered': total_t,
                'tonnes_per_hour': tph,
                'average_truck_cycle_time_min': avg_cycle,
                'average_truck_utilisation': truck_util,
                'crusher_utilisation': crush_util,
                'average_loader_queue_time_min': avg_l_q,
                'average_crusher_queue_time_min': avg_c_q
            })
            
            scenario_results.append({
                'total_tonnes': total_t,
                'tph': tph,
                'avg_cycle': avg_cycle,
                'truck_util': truck_util,
                'crush_util': crush_util,
                'avg_l_q': avg_l_q,
                'avg_c_q': avg_c_q,
                'loader_active': tracker['loader_active_time']
            })
            
        # Aggregate for summary
        if scenario_results:
            tonnes = [r['total_tonnes'] for r in scenario_results]
            tphs = [r['tph'] for r in scenario_results]
            
            def get_ci(data):
                if len(data) < 2: return 0, 0
                mean = np.mean(data)
                se = stats.sem(data)
                margin = se * stats.t.ppf((1 + 0.95) / 2., len(data)-1)
                return mean - margin, mean + margin
                
            t_ci = get_ci(tonnes)
            tph_ci = get_ci(tphs)
            
            l_utils = {}
            for l in loaders:
                vals = [r['loader_active'][l['id']] / sim_time_min for r in scenario_results]
                l_utils[l['id']] = float(np.mean(vals))
                
            summary_data["scenarios"][scenario_name] = {
                "replications": replications,
                "shift_length_hours": shift_length_hours,
                "total_tonnes_mean": float(np.mean(tonnes)),
                "total_tonnes_ci95_low": float(t_ci[0]),
                "total_tonnes_ci95_high": float(t_ci[1]),
                "tonnes_per_hour_mean": float(np.mean(tphs)),
                "tonnes_per_hour_ci95_low": float(tph_ci[0]),
                "tonnes_per_hour_ci95_high": float(tph_ci[1]),
                "average_cycle_time_min": float(np.mean([r['avg_cycle'] for r in scenario_results])),
                "truck_utilisation_mean": float(np.mean([r['truck_util'] for r in scenario_results])),
                "loader_utilisation": l_utils,
                "crusher_utilisation": float(np.mean([r['crush_util'] for r in scenario_results])),
                "average_loader_queue_time_min": float(np.mean([r['avg_l_q'] for r in scenario_results])),
                "average_crusher_queue_time_min": float(np.mean([r['avg_c_q'] for r in scenario_results])),
                "top_bottlenecks": []
            }
            
            # Simple bottleneck identification
            bottlenecks = []
            if summary_data["scenarios"][scenario_name]["crusher_utilisation"] > 0.85:
                bottlenecks.append("Crusher")
            for lid, u in l_utils.items():
                if u > 0.85:
                    bottlenecks.append(f"Loader {lid}")
            if summary_data["scenarios"][scenario_name]["average_loader_queue_time_min"] > 5:
                bottlenecks.append("Loader queueing")
            if not bottlenecks:
                bottlenecks.append("None evident")
            summary_data["scenarios"][scenario_name]["top_bottlenecks"] = bottlenecks

    pd.DataFrame(all_results).to_csv('results.csv', index=False)
    pd.DataFrame(all_events).to_csv('event_log.csv', index=False)
    
    with open('summary.json', 'w') as f:
        json.dump(summary_data, f, indent=2)

if __name__ == '__main__':
    run_simulation()
