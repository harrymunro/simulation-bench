import pandas as pd
import networkx as nx
import numpy as np

class MineGraph:
    def __init__(self, nodes_df, edges_df, scenario_cfg):
        self.nodes_df = nodes_df.copy()
        self.edges_df = edges_df.copy()
        self.scenario_cfg = scenario_cfg
        
        # Parse edge overrides
        self.edge_overrides = scenario_cfg.get("edge_overrides", {})
        
        # Build the graph
        self.G = nx.DiGraph()
        
        # Add nodes
        for _, row in self.nodes_df.iterrows():
            node_id = row['node_id']
            # Apply node overrides if any
            node_overrides = scenario_cfg.get("node_overrides", {}).get(node_id, {})
            self.G.add_node(
                node_id,
                node_name=row.get('node_name', node_id),
                node_type=row.get('node_type', ''),
                x=float(row['x_m']),
                y=float(row['y_m']),
                z=float(row['z_m']),
                capacity=row.get('capacity', None),
                service_time_mean_min=float(node_overrides.get('service_time_mean_min', row.get('service_time_mean_min', 0.0) if not pd.isna(row.get('service_time_mean_min')) else 0.0)),
                service_time_sd_min=float(node_overrides.get('service_time_sd_min', row.get('service_time_sd_min', 0.0) if not pd.isna(row.get('service_time_sd_min')) else 0.0))
            )
            
        # Add edges
        for _, row in self.edges_df.iterrows():
            edge_id = row['edge_id']
            from_node = row['from_node']
            to_node = row['to_node']
            
            # Start with default csv properties
            distance_m = float(row['distance_m'])
            max_speed_kph = float(row['max_speed_kph'])
            capacity = int(row['capacity'])
            closed = str(row['closed']).lower() == 'true'
            
            # Apply edge overrides
            if edge_id in self.edge_overrides:
                overrides = self.edge_overrides[edge_id]
                distance_m = float(overrides.get('distance_m', distance_m))
                max_speed_kph = float(overrides.get('max_speed_kph', max_speed_kph))
                capacity = int(overrides.get('capacity', capacity))
                closed = overrides.get('closed', closed)
                
            if not closed:
                self.G.add_edge(
                    from_node,
                    to_node,
                    edge_id=edge_id,
                    distance_m=distance_m,
                    max_speed_kph=max_speed_kph,
                    capacity=capacity,
                    road_type=row.get('road_type', 'haul')
                )
                
        # Run self-checks for reachability
        self.verify_reachability()
        
    def verify_reachability(self):
        """
        Loudly verifies that all required paths are reachable:
        - From PARK to loaders (LOAD_N, LOAD_S)
        - From loaders to CRUSH
        - From CRUSH back to loaders
        """
        ore_sources = self.scenario_cfg.get("production", {}).get("ore_sources", ["LOAD_N", "LOAD_S"])
        dump_dest = self.scenario_cfg.get("production", {}).get("dump_destination", "CRUSH")
        
        # Checks starting PARK reachability
        for loader in ore_sources:
            if not nx.has_path(self.G, "PARK", loader):
                raise ValueError(f"Unreachable topology: PARK has no path to loader {loader}")
                
        # Checks cycle reachability between loaders and crusher
        for loader in ore_sources:
            if not nx.has_path(self.G, loader, dump_dest):
                raise ValueError(f"Unreachable topology: Loader {loader} has no path to crusher {dump_dest}")
            if not nx.has_path(self.G, dump_dest, loader):
                raise ValueError(f"Unreachable topology: Crusher {dump_dest} has no path back to loader {loader}")
                
    def get_edge_details(self, from_node, to_node):
        """
        Returns edge properties dictionary or None if edge doesn't exist.
        """
        if self.G.has_edge(from_node, to_node):
            return self.G[from_node][to_node]
        return None

    def calculate_free_flow_travel_time(self, from_node, to_node, is_loaded, empty_speed_factor, loaded_speed_factor):
        """
        Calculates the exact deterministic free-flow travel time (minutes) for a single edge.
        """
        edge_data = self.get_edge_details(from_node, to_node)
        if edge_data is None:
            raise ValueError(f"No edge exists between {from_node} and {to_node}")
            
        distance_m = edge_data['distance_m']
        max_speed_kph = edge_data['max_speed_kph']
        
        factor = loaded_speed_factor if is_loaded else empty_speed_factor
        speed_kph = max_speed_kph * factor
        
        # Travel time in minutes
        return (distance_m / 1000.0) / speed_kph * 60.0

    def compute_shortest_path(self, source, target, is_loaded, empty_speed_factor, loaded_speed_factor):
        """
        Uses NetworkX Dijkstra to find the shortest-time path (list of nodes and list of edge ids) 
        and the total free-flow travel time.
        """
        # Define weight function for Dijkstra
        def weight_func(u, v, d):
            distance_m = d['distance_m']
            max_speed_kph = d['max_speed_kph']
            factor = loaded_speed_factor if is_loaded else empty_speed_factor
            speed_kph = max_speed_kph * factor
            return (distance_m / 1000.0) / speed_kph * 60.0
            
        try:
            path_nodes = nx.dijkstra_path(self.G, source, target, weight=weight_func)
            path_edges = []
            total_time = 0.0
            
            for i in range(len(path_nodes) - 1):
                u, v = path_nodes[i], path_nodes[i+1]
                edge_data = self.G[u][v]
                path_edges.append(edge_data['edge_id'])
                total_time += weight_func(u, v, edge_data)
                
            return path_nodes, path_edges, total_time
        except nx.NetworkXNoPath:
            raise ValueError(f"No path found between {source} and {target}")
            
    def get_coordinates(self, node_id):
        """
        Returns (x, y, z) coordinates of a node.
        """
        node = self.G.nodes[node_id]
        return node['x'], node['y'], node['z']
