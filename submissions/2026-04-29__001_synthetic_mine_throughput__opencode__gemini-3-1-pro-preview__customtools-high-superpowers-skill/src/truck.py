import networkx as nx
from src.topology import get_base_travel_time
from src.simulation import MineSimulation

def get_shortest_path_time(graph: nx.DiGraph, start: str, end: str, speed_factor: float) -> float:
    # Custom weight function
    def weight(u, v, d):
        base = get_base_travel_time(d['distance_m'], d['max_speed_kph'])
        return base / speed_factor
        
    try:
        return nx.shortest_path_length(graph, start, end, weight=weight)
    except nx.NetworkXNoPath:
        return float('inf')

def choose_best_loader(sim: MineSimulation, current_node: str, loaders: list[str], speed_factor: float) -> str:
    best_loader = None
    min_expected_time = float('inf')
    
    for loader in loaders:
        travel_time = get_shortest_path_time(sim.graph, current_node, loader, speed_factor)
        
        # Estimate wait time: queue length * mean service time
        queue_len = len(sim.resources[loader].queue)
        mean_service = sim.graph.nodes[loader].get('service_time_mean_min', 5.0)
        expected_wait = (queue_len + 1) * mean_service
        
        total_time = travel_time + expected_wait
        if total_time < min_expected_time:
            min_expected_time = total_time
            best_loader = loader
            
    return best_loader
