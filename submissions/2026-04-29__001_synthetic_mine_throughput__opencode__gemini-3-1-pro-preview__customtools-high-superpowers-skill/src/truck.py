import scipy.stats as stats
import networkx as nx
from src.topology import get_base_travel_time
from src.simulation import MineSimulation

DEFAULT_LOADER_SERVICE_TIME_MEAN = 5.0
DEFAULT_LOADER_SERVICE_TIME_SD = 1.0
DEFAULT_CRUSHER_SERVICE_TIME_MEAN = 3.5
DEFAULT_CRUSHER_SERVICE_TIME_SD = 0.8

def get_shortest_path_time(graph: nx.DiGraph, start: str, end: str, speed_factor: float) -> float:
    # Custom weight function
    def weight(u, v, d):
        base = get_base_travel_time(d['distance_m'], d['max_speed_kph'])
        return base / speed_factor
        
    try:
        return nx.shortest_path_length(graph, start, end, weight=weight)
    except nx.NetworkXNoPath:
        return float('inf')

def choose_best_destination(sim: MineSimulation, current_node: str, destinations: list[str], speed_factor: float, default_service_mean: float) -> str:
    best_dest = None
    min_expected_time = float('inf')
    
    for dest in destinations:
        travel_time = get_shortest_path_time(sim.graph, current_node, dest, speed_factor)
        
        # Estimate wait time: queue length * mean service time
        queue_len = len(sim.resources[dest].queue)
        mean_service = sim.graph.nodes[dest].get('service_time_mean_min', default_service_mean)
        expected_wait = (queue_len + 1) * mean_service
        
        total_time = travel_time + expected_wait
        if total_time < min_expected_time:
            min_expected_time = total_time
            best_dest = dest
            
    return best_dest

def get_truncated_normal(mean, sd, lower=0):
    if sd == 0:
        return mean
    a = (lower - mean) / sd
    return stats.truncnorm(a, float('inf'), loc=mean, scale=sd).rvs()

def traverse_path(env, sim, truck_id, path, speed, is_loaded, payload):
    stochasticity_cv = getattr(sim.config, 'stochasticity_cv', 0)
    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        edge_data = sim.graph.edges[u, v]
        edge_id = edge_data['edge_id']
        
        base_t = get_base_travel_time(edge_data['distance_m'], edge_data['max_speed_kph']) / speed
        actual_t = get_truncated_normal(base_t, base_t * stochasticity_cv)
        
        # Request edge capacity if constrained
        if edge_id in sim.edge_resources:
            with sim.edge_resources[edge_id].request() as req:
                yield req
                sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "enter_edge", u, v, edge_id, is_loaded, payload, edge_id, 0)
                yield env.timeout(actual_t)
        else:
            yield env.timeout(actual_t)

def truck_process(env, sim, truck_id, start_node, payload_capacity, empty_speed, loaded_speed):
    current_node = start_node
    loaders = [n for n, d in sim.graph.nodes(data=True) if d.get('node_type') == 'load_ore']
    crushers = [n for n, d in sim.graph.nodes(data=True) if d.get('node_type') == 'dump_ore']
    
    if not crushers:
        crushers = ["CRUSH"]
    
    while True:
        cycle_start = env.now
        
        # 1. Choose loader & travel
        target_loader = choose_best_destination(sim, current_node, loaders, empty_speed, DEFAULT_LOADER_SERVICE_TIME_MEAN)
        if not target_loader:
            yield env.timeout(1) # wait if nowhere to go
            continue
            
        path = nx.shortest_path(sim.graph, current_node, target_loader)
        
        # Traverse path
        yield from traverse_path(env, sim, truck_id, path, empty_speed, False, 0)
                
        current_node = target_loader
        
        # 2. Queue & Load
        arrive_time = env.now
        sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "arrive_loader", current_node, "", current_node, False, 0, current_node, len(sim.resources[current_node].queue))
        
        with sim.resources[current_node].request() as req:
            yield req
            wait_time = env.now - arrive_time
            sim.metrics.record_queue_time('loader', wait_time)
            
            mean_lt = sim.graph.nodes[current_node].get('service_time_mean_min', DEFAULT_LOADER_SERVICE_TIME_MEAN)
            sd_lt = sim.graph.nodes[current_node].get('service_time_sd_min', DEFAULT_LOADER_SERVICE_TIME_SD)
            load_t = get_truncated_normal(mean_lt, sd_lt)
            yield env.timeout(load_t)
            
        # 3. Travel Loaded to Crusher
        target_crusher = choose_best_destination(sim, current_node, crushers, loaded_speed, DEFAULT_CRUSHER_SERVICE_TIME_MEAN)
        if not target_crusher:
            yield env.timeout(1)
            continue
            
        path = nx.shortest_path(sim.graph, current_node, target_crusher)
        
        # Traverse path
        yield from traverse_path(env, sim, truck_id, path, loaded_speed, True, payload_capacity)
                
        current_node = target_crusher
        
        # 4. Queue & Dump
        arrive_time = env.now
        sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "arrive_crusher", current_node, "", current_node, True, payload_capacity, current_node, len(sim.resources[current_node].queue))
        
        with sim.resources[current_node].request() as req:
            yield req
            wait_time = env.now - arrive_time
            sim.metrics.record_queue_time('crusher', wait_time)
            
            mean_dt = sim.graph.nodes[current_node].get('service_time_mean_min', DEFAULT_CRUSHER_SERVICE_TIME_MEAN)
            sd_dt = sim.graph.nodes[current_node].get('service_time_sd_min', DEFAULT_CRUSHER_SERVICE_TIME_SD)
            dump_t = get_truncated_normal(mean_dt, sd_dt)
            yield env.timeout(dump_t)
            
        sim.metrics.record_cycle(truck_id, env.now - cycle_start, payload_capacity)
        sim.logger.log(env.now, sim.replication, sim.config.scenario_id, truck_id, "finish_dump", current_node, "", current_node, False, 0, current_node, 0)
