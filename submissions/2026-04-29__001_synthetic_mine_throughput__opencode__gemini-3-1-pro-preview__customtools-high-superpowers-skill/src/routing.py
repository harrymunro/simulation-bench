import networkx as nx
from typing import Optional
from src.topology import get_base_travel_time

def get_shortest_path_time(graph: nx.DiGraph, start: str, end: str, speed_factor: float) -> float:
    # Custom weight function
    def weight(u, v, d):
        base = get_base_travel_time(d['distance_m'], d['max_speed_kph'])
        return base / speed_factor
        
    try:
        return nx.shortest_path_length(graph, start, end, weight=weight)
    except nx.NetworkXNoPath:
        return float('inf')

def choose_best_destination(graph: nx.DiGraph, resources: dict, current_node: str, destinations: list[str], speed_factor: float, default_service_mean: float) -> Optional[str]:
    best_dest = None
    min_expected_time = float('inf')
    
    for dest in destinations:
        travel_time = get_shortest_path_time(graph, current_node, dest, speed_factor)
        
        # Estimate wait time: queue length * mean service time
        queue_len = len(resources[dest].queue)
        mean_service = graph.nodes[dest].get('service_time_mean_min', default_service_mean)
        expected_wait = (queue_len + 1) * mean_service
        
        total_time = travel_time + expected_wait
        if total_time < min_expected_time:
            min_expected_time = total_time
            best_dest = dest
            
    return best_dest
