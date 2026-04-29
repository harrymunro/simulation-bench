import pandas as pd
import networkx as nx
import simpy
import yaml
import random
import os
import json
import numpy as np

def load_data(scenario_name):
    nodes = pd.read_csv('data/nodes.csv').set_index('node_id')
    edges = pd.read_csv('data/edges.csv').set_index('edge_id')
    trucks = pd.read_csv('data/trucks.csv').set_index('truck_id')
    loaders = pd.read_csv('data/loaders.csv').set_index('loader_id')
    dump_points = pd.read_csv('data/dump_points.csv').set_index('dump_id')
    
    with open(f'data/scenarios/{scenario_name}.yaml', 'r') as f:
        scenario = yaml.safe_load(f)
        
    if 'inherits' in scenario and scenario['inherits'] == 'baseline':
        with open('data/scenarios/baseline.yaml', 'r') as f:
            base = yaml.safe_load(f)
            # update base with scenario
            for k, v in scenario.items():
                if isinstance(v, dict) and k in base and isinstance(base[k], dict):
                    base[k].update(v)
                else:
                    base[k] = v
            scenario = base
            
    # Apply overrides
    if 'edge_overrides' in scenario:
        for eid, overrides in scenario['edge_overrides'].items():
            for k, v in overrides.items():
                edges.at[eid, k] = v
                
    if 'dump_point_overrides' in scenario:
        for did, overrides in scenario['dump_point_overrides'].items():
            for k, v in overrides.items():
                dump_points.at[did, k] = v

    if 'node_overrides' in scenario:
        for nid, overrides in scenario['node_overrides'].items():
            for k, v in overrides.items():
                nodes.at[nid, k] = v

    if 'fleet' in scenario and 'truck_count' in scenario['fleet']:
        count = scenario['fleet']['truck_count']
        trucks = trucks.head(count)
        
    return nodes, edges, trucks, loaders, dump_points, scenario

def run_replication(scenario_name, rep_id, seed, event_log):
    nodes, edges, trucks, loaders, dump_points, scenario = load_data(scenario_name)
    random.seed(seed)
    np.random.seed(seed)
    
    env = simpy.Environment()
    
    # Resources
    loader_resources = {}
    for lid, row in loaders.iterrows():
        loader_resources[row['node_id']] = simpy.Resource(env, capacity=int(row['capacity']))
        
    dump_resources = {}
    for did, row in dump_points.iterrows():
        dump_resources[row['node_id']] = simpy.Resource(env, capacity=int(row['capacity']))
        
    edge_resources = {}
    for eid, row in edges.iterrows():
        cap = int(row['capacity'])
        if cap < 999:
            edge_resources[eid] = simpy.Resource(env, capacity=cap)
            
    # Graph for routing
    G_empty = nx.DiGraph()
    G_loaded = nx.DiGraph()
    for nid, row in nodes.iterrows():
        G_empty.add_node(nid)
        G_loaded.add_node(nid)
    for eid, row in edges.iterrows():
        if not row['closed']:
            dist = row['distance_m']
            speed = row['max_speed_kph']
            G_empty.add_edge(row['from_node'], row['to_node'], id=eid, distance=dist, max_speed=speed,
                             time=dist / (speed * 1000 / 60))
            G_loaded.add_edge(row['from_node'], row['to_node'], id=eid, distance=dist, max_speed=speed,
                              time=dist / (speed * 1000 / 60))
            
    # Stats
    stats = {
        'total_tonnes': 0,
        'truck_cycle_times': [],
        'truck_active_time': 0,
        'crusher_busy_time': 0,
        'loader_busy_time': {nid: 0 for nid in loader_resources},
        'loader_queue_times': [],
        'crusher_queue_times': [],
    }
    
    cv = scenario.get('stochasticity', {}).get('travel_time_noise_cv', 0.1)
    
    def log_event(time, truck_id, event_type, from_node, to_node, loc, loaded, payload, res_id, qlen):
        event_log.append({
            'time_min': time, 'replication': rep_id, 'scenario_id': scenario_name,
            'truck_id': truck_id, 'event_type': event_type, 'from_node': from_node,
            'to_node': to_node, 'location': loc, 'loaded': loaded,
            'payload_tonnes': payload, 'resource_id': res_id, 'queue_length': qlen
        })

    def truck_process(truck_id, start_node, payload_capacity, empty_speed, loaded_speed):
        current_node = start_node
        
        while True:
            cycle_start = env.now
            
            # 1. Decide loader
            best_loader = None
            best_score = float('inf')
            
            for lid, row in loaders.iterrows():
                lnode = row['node_id']
                try:
                    path = nx.shortest_path(G_empty, current_node, lnode, weight='time')
                    dist_time = nx.shortest_path_length(G_empty, current_node, lnode, weight='time')
                    est_time = dist_time / empty_speed
                    
                    q_len = len(loader_resources[lnode].queue)
                    est_wait = q_len * row['mean_load_time_min']
                    score = est_time + est_wait
                    
                    if score < best_score:
                        best_score = score
                        best_loader = lnode
                except nx.NetworkXNoPath:
                    continue
                    
            if not best_loader:
                break # No path to loader
                
            # 2. Travel to loader
            try:
                path = nx.shortest_path(G_empty, current_node, best_loader, weight='time')
            except nx.NetworkXNoPath:
                break
                
            for i in range(len(path)-1):
                u = path[i]
                v = path[i+1]
                eid = G_empty.edges[u, v]['id']
                dist = G_empty.edges[u, v]['distance']
                speed = G_empty.edges[u, v]['max_speed']
                
                mean_time = dist / (speed * 1000 / 60) / empty_speed
                actual_time = max(0.1, random.gauss(mean_time, mean_time * cv))
                
                log_event(env.now, truck_id, 'travel_start', u, v, eid, False, 0, '', 0)
                
                if eid in edge_resources:
                    with edge_resources[eid].request() as req:
                        yield req
                        yield env.timeout(actual_time)
                else:
                    yield env.timeout(actual_time)
                    
                log_event(env.now, truck_id, 'travel_end', u, v, eid, False, 0, '', 0)
                current_node = v
                stats['truck_active_time'] += actual_time
                
            # 3. Load
            lrow = loaders[loaders['node_id'] == current_node].iloc[0]
            log_event(env.now, truck_id, 'queue_start', '', '', current_node, False, 0, lrow.name, len(loader_resources[current_node].queue))
            q_start = env.now
            
            with loader_resources[current_node].request() as req:
                yield req
                wait_time = env.now - q_start
                stats['loader_queue_times'].append(wait_time)
                
                log_event(env.now, truck_id, 'load_start', '', '', current_node, False, 0, lrow.name, 0)
                
                load_time_mean = lrow['mean_load_time_min']
                load_time_sd = lrow['sd_load_time_min']
                actual_load = max(0.1, random.gauss(load_time_mean, load_time_sd))
                
                yield env.timeout(actual_load)
                stats['loader_busy_time'][current_node] += actual_load
                stats['truck_active_time'] += actual_load
                
                log_event(env.now, truck_id, 'load_end', '', '', current_node, True, payload_capacity, lrow.name, 0)
                
            # 4. Travel to Crusher
            dest = 'CRUSH'
            try:
                path = nx.shortest_path(G_loaded, current_node, dest, weight='time')
            except nx.NetworkXNoPath:
                break
                
            for i in range(len(path)-1):
                u = path[i]
                v = path[i+1]
                eid = G_loaded.edges[u, v]['id']
                dist = G_loaded.edges[u, v]['distance']
                speed = G_loaded.edges[u, v]['max_speed']
                
                mean_time = dist / (speed * 1000 / 60) / loaded_speed
                actual_time = max(0.1, random.gauss(mean_time, mean_time * cv))
                
                log_event(env.now, truck_id, 'travel_start', u, v, eid, True, payload_capacity, '', 0)
                
                if eid in edge_resources:
                    with edge_resources[eid].request() as req:
                        yield req
                        yield env.timeout(actual_time)
                else:
                    yield env.timeout(actual_time)
                    
                log_event(env.now, truck_id, 'travel_end', u, v, eid, True, payload_capacity, '', 0)
                current_node = v
                stats['truck_active_time'] += actual_time
                
            # 5. Dump
            drow = dump_points[dump_points['node_id'] == current_node].iloc[0]
            log_event(env.now, truck_id, 'queue_start', '', '', current_node, True, payload_capacity, drow.name, len(dump_resources[current_node].queue))
            q_start = env.now
            
            with dump_resources[current_node].request() as req:
                yield req
                wait_time = env.now - q_start
                stats['crusher_queue_times'].append(wait_time)
                
                log_event(env.now, truck_id, 'dump_start', '', '', current_node, True, payload_capacity, drow.name, 0)
                
                dump_time_mean = drow['mean_dump_time_min']
                dump_time_sd = drow['sd_dump_time_min']
                actual_dump = max(0.1, random.gauss(dump_time_mean, dump_time_sd))
                
                yield env.timeout(actual_dump)
                
                stats['crusher_busy_time'] += actual_dump
                stats['truck_active_time'] += actual_dump
                stats['total_tonnes'] += payload_capacity
                
                log_event(env.now, truck_id, 'dump_end', '', '', current_node, False, 0, drow.name, 0)
                
            stats['truck_cycle_times'].append(env.now - cycle_start)

    for tid, row in trucks.iterrows():
        env.process(truck_process(tid, row['start_node'], row['payload_tonnes'], row['empty_speed_factor'], row['loaded_speed_factor']))
        
    shift_len = scenario['simulation'].get('shift_length_hours', 8) * 60
    env.run(until=shift_len)
    
    num_trucks = len(trucks)
    
    return {
        'scenario_id': scenario_name,
        'replication': rep_id,
        'random_seed': seed,
        'total_tonnes_delivered': stats['total_tonnes'],
        'tonnes_per_hour': stats['total_tonnes'] / (shift_len / 60),
        'average_truck_cycle_time_min': np.mean(stats['truck_cycle_times']) if stats['truck_cycle_times'] else 0,
        'average_truck_utilisation': stats['truck_active_time'] / (num_trucks * shift_len) if num_trucks else 0,
        'crusher_utilisation': stats['crusher_busy_time'] / shift_len,
        'average_loader_queue_time_min': np.mean(stats['loader_queue_times']) if stats['loader_queue_times'] else 0,
        'average_crusher_queue_time_min': np.mean(stats['crusher_queue_times']) if stats['crusher_queue_times'] else 0
    }
