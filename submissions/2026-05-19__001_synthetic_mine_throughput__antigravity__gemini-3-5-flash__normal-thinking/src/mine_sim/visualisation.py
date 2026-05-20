import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.animation as animation
import networkx as nx

class MineVisualiser:
    def __init__(self, mine_graph, output_dir):
        self.mine_graph = mine_graph
        self.output_dir = output_dir
        
    def generate_topology_plot(self):
        """
        Generates a 2D scale map of the mine layout showing nodes, coordinates, 
        edge routes, and capacity constraints, saving it to topology.png.
        """
        plt.figure(figsize=(12, 10))
        
        # Get coordinates
        pos = {node_id: (d['x'], d['y']) for node_id, d in self.mine_graph.G.nodes(data=True)}
        
        # Classify nodes for visual styling
        node_colors = []
        node_sizes = []
        node_shapes = [] # matplotlib draw doesn't support multiple shapes easily in one call, so we do separate draws
        
        node_groups = {
            "parking": [],
            "load_ore": [],
            "crusher": [],
            "junction": [],
            "other": []
        }
        
        for node_id, d in self.mine_graph.G.nodes(data=True):
            ntype = d['node_type']
            if ntype == 'parking':
                node_groups["parking"].append(node_id)
            elif ntype == 'load_ore':
                node_groups["load_ore"].append(node_id)
            elif ntype == 'crusher':
                node_groups["crusher"].append(node_id)
            elif ntype == 'junction':
                node_groups["junction"].append(node_id)
            else:
                node_groups["other"].append(node_id)
                
        # Draw edges
        edges_unconstrained = []
        edges_constrained = []
        
        for u, v, d in self.mine_graph.G.edges(data=True):
            if d['capacity'] == 1:
                edges_constrained.append((u, v))
            else:
                edges_unconstrained.append((u, v))
                
        # Base network drawing
        nx.draw_networkx_edges(
            self.mine_graph.G, pos, edgelist=edges_unconstrained, 
            edge_color='darkgray', width=1.5, arrowsize=15, 
            arrows=True, min_source_margin=15, min_target_margin=15
        )
        nx.draw_networkx_edges(
            self.mine_graph.G, pos, edgelist=edges_constrained, 
            edge_color='orangered', width=3.0, arrowsize=18, 
            arrows=True, min_source_margin=15, min_target_margin=15
        )
        
        # Draw each node group with dedicated aesthetics
        nx.draw_networkx_nodes(
            self.mine_graph.G, pos, nodelist=node_groups["parking"],
            node_color='#3498db', node_shape='s', node_size=600, label='Parking'
        )
        nx.draw_networkx_nodes(
            self.mine_graph.G, pos, nodelist=node_groups["load_ore"],
            node_color='#2ecc71', node_shape='^', node_size=700, label='Ore Face'
        )
        nx.draw_networkx_nodes(
            self.mine_graph.G, pos, nodelist=node_groups["crusher"],
            node_color='#e74c3c', node_shape='p', node_size=800, label='Primary Crusher'
        )
        nx.draw_networkx_nodes(
            self.mine_graph.G, pos, nodelist=node_groups["junction"],
            node_color='#95a5a6', node_shape='o', node_size=300, label='Junction'
        )
        if node_groups["other"]:
            nx.draw_networkx_nodes(
                self.mine_graph.G, pos, nodelist=node_groups["other"],
                node_color='#f1c40f', node_shape='o', node_size=450, label='Other Facility'
            )
            
        # Draw node labels
        nx.draw_networkx_labels(self.mine_graph.G, pos, font_size=9, font_weight='bold', font_family='sans-serif')
        
        # Build nice legends and details
        plt.title("Synthetic Mine Spatial Topology & Infrastructure", fontsize=15, fontweight='bold', pad=20)
        plt.xlabel("X Coordinate (meters)", fontsize=11, labelpad=10)
        plt.ylabel("Y Coordinate (meters)", fontsize=11, labelpad=10)
        plt.grid(True, linestyle=':', alpha=0.5)
        
        # Add manual legends for constraints
        from matplotlib.lines import Line2D
        custom_lines = [
            Line2D([0], [0], color='darkgray', lw=1.5, label='High-Capacity Haul Road'),
            Line2D([0], [0], color='orangered', lw=3.0, label='Single-Lane Constraint (Capacity=1)'),
            Line2D([0], [0], marker='s', color='w', markerfacecolor='#3498db', markersize=10, label='Parking Node'),
            Line2D([0], [0], marker='^', color='w', markerfacecolor='#2ecc71', markersize=11, label='Ore Load Node'),
            Line2D([0], [0], marker='p', color='w', markerfacecolor='#e74c3c', markersize=12, label='Crusher Dump Node'),
            Line2D([0], [0], marker='o', color='w', markerfacecolor='#95a5a6', markersize=8, label='Intersection Junction')
        ]
        plt.legend(handles=custom_lines, loc='upper left', frameon=True, facecolor='white', framealpha=0.9)
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "topology.png"), dpi=150)
        plt.close()
        print("Generated topology.png successfully.")

    def generate_animation(self, event_log_path, duration_min=45):
        """
        Parses event logs of baseline replication 0 and builds a physical 
        simulation flow animation of truck traffic, saved as animation.gif.
        """
        print("Generating haulage traffic flow animation (animation.gif)...")
        if not os.path.exists(event_log_path):
            print(f"Skipping animation: event log {event_log_path} not found.")
            return
            
        # Load event log
        df = pd.read_csv(event_log_path)
        
        # Filter for baseline replication 0
        df_base = df[(df["scenario_id"] == "baseline") & (df["replication"] == 0)].copy()
        if df_base.empty:
            print("Skipping animation: baseline replication 0 has no logs.")
            return
            
        # Gather truck journeys
        # A journey starts on: dispatch, travel_start, edge_queue_start, edge_enter, loader_queue_start, load_start, crusher_queue_start, dump_start
        # We can construct intervals of time where we know exactly where a truck is!
        # Let's reconstruct truck locations for every integer minute up to duration_min
        time_steps = np.arange(0, duration_min + 0.5, 0.5)
        
        truck_ids = sorted(df_base["truck_id"].unique())
        node_coords = {node_id: (d['x'], d['y']) for node_id, d in self.mine_graph.G.nodes(data=True)}
        
        # Build coordinates for each truck at each time step
        # Initialize dictionary to hold trajectories
        truck_coords = {t_id: [] for t_id in truck_ids}
        
        for t in time_steps:
            for t_id in truck_ids:
                df_truck = df_base[df_base["truck_id"] == t_id].sort_values("time_min")
                
                # Default position: PARK
                x_pos, y_pos = node_coords["PARK"]
                
                # Find log records surrounding time t
                prev_record = df_truck[df_truck["time_min"] <= t]
                next_record = df_truck[df_truck["time_min"] > t]
                
                if not prev_record.empty:
                    last_evt = prev_record.iloc[-1]
                    evt_type = last_evt["event_type"]
                    from_node = last_evt["from_node"]
                    to_node = last_evt["to_node"]
                    
                    if evt_type in ["travel_start", "edge_enter"]:
                        # We are currently traveling along edge from_node -> to_node
                        # Find when we finish this travel
                        if not next_record.empty:
                            nxt_evt = next_record.iloc[0]
                            t_start = last_evt["time_min"]
                            t_end = nxt_evt["time_min"]
                            
                            if t_end > t_start:
                                frac = (t - t_start) / (t_end - t_start)
                                frac = max(0.0, min(1.0, frac))
                                x_u, y_u = node_coords[from_node]
                                x_v, y_v = node_coords[to_node]
                                x_pos = x_u + frac * (x_v - x_u)
                                y_pos = y_u + frac * (y_v - y_u)
                            else:
                                x_pos, y_pos = node_coords[to_node]
                        else:
                            x_pos, y_pos = node_coords[to_node]
                    else:
                        # At a node, queueing or servicing
                        loc = last_evt["location"]
                        if loc in node_coords:
                            x_pos, y_pos = node_coords[loc]
                        else:
                            x_pos, y_pos = node_coords[from_node]
                            
                truck_coords[t_id].append((x_pos, y_pos))
                
        # Build animation
        fig, ax = plt.subplots(figsize=(10, 8))
        
        # Plot static graph as background
        pos = {node_id: (d['x'], d['y']) for node_id, d in self.mine_graph.G.nodes(data=True)}
        
        # Highlight constrained edges in orange
        edges_unconstrained = []
        edges_constrained = []
        for u, v, d in self.mine_graph.G.edges(data=True):
            if d['capacity'] == 1:
                edges_constrained.append((u, v))
            else:
                edges_unconstrained.append((u, v))
                
        nx.draw_networkx_edges(self.mine_graph.G, pos, edgelist=edges_unconstrained, edge_color='#ecf0f1', width=1.5, ax=ax)
        nx.draw_networkx_edges(self.mine_graph.G, pos, edgelist=edges_constrained, edge_color='#f39c12', width=2.5, ax=ax)
        
        nx.draw_networkx_nodes(self.mine_graph.G, pos, node_color='#7f8c8d', node_size=150, ax=ax)
        nx.draw_networkx_labels(self.mine_graph.G, pos, font_size=8, font_weight='bold', ax=ax)
        
        # Animated scatter plot for trucks
        scatter_plots = {}
        colors = plt.cm.get_cmap('tab10', len(truck_ids))
        
        for idx, t_id in enumerate(truck_ids):
            scatter_plots[t_id] = ax.plot(
                [], [], marker='o', ls='', color=colors(idx), 
                markersize=9, label=f"Truck {t_id}", markeredgecolor='black'
            )[0]
            
        time_text = ax.text(0.02, 0.95, '', transform=ax.transAxes, fontsize=12, fontweight='bold')
        ax.set_title(f"Dynamic Haulage Operations Flow (First {duration_min} mins)", fontsize=13, fontweight='bold')
        ax.legend(loc='lower left', ncol=3, frameon=True)
        ax.set_xlabel("X (meters)")
        ax.set_ylabel("Y (meters)")
        ax.grid(True, linestyle=':', alpha=0.3)
        
        def init():
            for t_id in truck_ids:
                scatter_plots[t_id].set_data([], [])
            time_text.set_text('')
            return list(scatter_plots.values()) + [time_text]
            
        def update(frame_idx):
            t_val = time_steps[frame_idx]
            for t_id in truck_ids:
                x, y = truck_coords[t_id][frame_idx]
                scatter_plots[t_id].set_data([x], [y])
            time_text.set_text(f"Simulation Time: {t_val:.1f} min")
            return list(scatter_plots.values()) + [time_text]
            
        ani = animation.FuncAnimation(
            fig, update, frames=len(time_steps), init_func=init, 
            blit=True, interval=150
        )
        
        # Save as GIF
        gif_path = os.path.join(self.output_dir, "animation.gif")
        try:
            # Requires pillow writer
            ani.save(gif_path, writer='pillow')
            print(f"Compiled and saved {gif_path} successfully.")
        except Exception as e:
            print(f"Could not save animation.gif: {e}")
            
        plt.close()
