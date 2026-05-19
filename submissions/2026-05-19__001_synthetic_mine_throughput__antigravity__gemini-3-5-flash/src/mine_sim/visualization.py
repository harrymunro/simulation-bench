import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation, PillowWriter
import networkx as nx
from .simulation import MineSimulation, TruckState

class Visualizer:
    def __init__(self, data_dir, output_dir):
        self.data_dir = data_dir
        self.output_dir = output_dir
        
        # Load topology data
        self.nodes_df = pd.read_csv(os.path.join(data_dir, 'nodes.csv'))
        self.edges_df = pd.read_csv(os.path.join(data_dir, 'edges.csv'))
        
        # Positions
        self.pos = {row['node_id']: (row['x_m'], row['y_m']) for _, row in self.nodes_df.iterrows()}

    def generate_topology_plot(self):
        """Generates a static topology map of the mine."""
        print("Generating static topology map (topology.png)...")
        fig, ax = plt.subplots(figsize=(10, 8), dpi=150)
        
        # Create a NetworkX graph for drawing
        G = nx.DiGraph()
        for _, row in self.nodes_df.iterrows():
            G.add_node(row['node_id'], type=row['node_type'])
            
        for _, row in self.edges_df.iterrows():
            G.add_edge(row['from_node'], row['to_node'], capacity=row['capacity'])
            
        # Draw edges
        # Differentiate capacity-constrained (capacity < 999) from normal
        constrained_edges = [(u, v) for u, v, d in G.edges(data=True) if d['capacity'] < 999]
        normal_edges = [(u, v) for u, v, d in G.edges(data=True) if d['capacity'] >= 999]
        
        nx.draw_networkx_edges(
            G, self.pos, edgelist=normal_edges, ax=ax,
            edge_color='#95a5a6', width=1.5, arrows=True, arrowsize=12, style='dashed'
        )
        nx.draw_networkx_edges(
            G, self.pos, edgelist=constrained_edges, ax=ax,
            edge_color='#e74c3c', width=3.0, arrows=True, arrowsize=15, style='solid'
        )
        
        # Draw nodes by type
        colors = {
            'parking': '#34495e',
            'junction': '#7f8c8d',
            'load_ore': '#27ae60',
            'crusher': '#d35400',
            'waste_dump': '#9b59b6',
            'maintenance': '#c0392b'
        }
        
        for n_type, col in colors.items():
            nodes = [n for n, attr in G.nodes(data=True) if attr['type'] == n_type]
            if nodes:
                nx.draw_networkx_nodes(
                    G, self.pos, nodelist=nodes, ax=ax,
                    node_color=col, node_size=300, label=n_type.replace('_', ' ').title()
                )
                
        # Node labels
        labels = {n: n for n in G.nodes()}
        nx.draw_networkx_labels(G, self.pos, labels, font_size=8, font_weight='bold', font_color='white')
        
        # Title and styling
        ax.set_title("Synthetic Mine Topology Map\n(Solid Red: Capacity Constrained Road Segments)", fontsize=14, fontweight='bold', pad=15)
        ax.legend(scatterpoints=1, loc='upper left', frameon=True, facecolor='#f8f9f9', framealpha=0.9)
        ax.set_xlabel("X (meters)", fontsize=10)
        ax.set_ylabel("Y (meters)", fontsize=10)
        ax.grid(True, linestyle=':', alpha=0.5)
        ax.set_facecolor('#f4f6f7')
        
        plt.tight_layout()
        plt.savefig(os.path.join(self.output_dir, "topology.png"), bbox_inches='tight')
        plt.close()
        print("topology.png saved.")

    def generate_animation_gif(self, scenario_config, duration_minutes=60, step_minutes=0.5):
        """Generates an animated GIF of truck movements over the first hour of a baseline shift."""
        print("Generating truck cycle movement animation (animation.gif)...")
        
        # We run a single replication of the simulation and log events
        sim = MineSimulation(scenario_config, self.data_dir, replication_idx=0)
        # We need a slightly modified run or we can parse the event_log to reconstruct truck positions at each step_minutes!
        sim.run()
        event_df = pd.DataFrame(sim.event_log)
        
        # Filter for time within duration_minutes
        event_df = event_df[event_df['time_min'] <= duration_minutes]
        
        # Generate time steps
        time_steps = np.arange(0, duration_minutes + step_minutes, step_minutes)
        
        # Reconstruct positions of each truck at each time step
        # Initialize truck positions at PARK at t=0
        truck_ids = sorted(event_df['truck_id'].unique())
        
        # To reconstruct positions, we parse the event log chronologically for each truck
        positions_over_time = {t_id: [] for t_id in truck_ids}
        states_over_time = {t_id: [] for t_id in truck_ids}
        
        # Node coordinates
        node_coords = {row['node_id']: (row['x_m'], row['y_m']) for _, row in self.nodes_df.iterrows()}
        
        for t_id in truck_ids:
            t_events = event_df[event_df['truck_id'] == t_id].sort_values(by='time_min')
            
            for t_step in time_steps:
                # Find the last event before or at t_step, and the next event after t_step
                past_events = t_events[t_events['time_min'] <= t_step]
                future_events = t_events[t_events['time_min'] > t_step]
                
                if past_events.empty:
                    # Truck is at start_node (PARK)
                    positions_over_time[t_id].append(node_coords['PARK'])
                    states_over_time[t_id].append('empty')
                    continue
                    
                last_event = past_events.iloc[-1]
                
                # Check what state the truck is in
                ev_type = last_event['event_type']
                
                if ev_type in ['ENTER_EDGE', 'REQUEST_EDGE']:
                    # Truck is travelling or queueing to enter an edge
                    # We need to know when it leaves/reaches the destination
                    leave_events = future_events[future_events['event_type'] == 'LEAVE_EDGE']
                    if not leave_events.empty:
                        next_leave = leave_events.iloc[0]
                        u = last_event['from_node']
                        v = last_event['to_node']
                        
                        # Interpolate position
                        t_start = last_event['time_min']
                        t_end = next_leave['time_min']
                        
                        if t_end > t_start:
                            frac = (t_step - t_start) / (t_end - t_start)
                            # clamp
                            frac = max(0.0, min(1.0, frac))
                        else:
                            frac = 1.0
                            
                        x_u, y_u = node_coords[u]
                        x_v, y_v = node_coords[v]
                        x = x_u + frac * (x_v - x_u)
                        y = y_u + frac * (y_v - y_u)
                        positions_over_time[t_id].append((x, y))
                        states_over_time[t_id].append('loaded' if last_event['loaded'] else 'empty')
                    else:
                        # No future leave event, truck is stuck or simulation ended
                        u = last_event['from_node']
                        positions_over_time[t_id].append(node_coords[u])
                        states_over_time[t_id].append('loaded' if last_event['loaded'] else 'empty')
                        
                elif ev_type in ['LEAVE_EDGE', 'ARRIVE_LOADER', 'START_LOADING', 'END_LOADING', 'ARRIVE_CRUSHER', 'START_DUMPING', 'END_DUMPING', 'DISPATCH']:
                    # Truck is at a node
                    loc = last_event['location']
                    if pd.isna(loc) or loc is None:
                        # Fallback to last known coordinates
                        loc = last_event['to_node'] if not pd.isna(last_event['to_node']) else 'PARK'
                    positions_over_time[t_id].append(node_coords[loc])
                    states_over_time[t_id].append('loaded' if last_event['loaded'] else 'empty')
                else:
                    positions_over_time[t_id].append(node_coords['PARK'])
                    states_over_time[t_id].append('empty')

        # Create animation figure
        fig, ax = plt.subplots(figsize=(10, 8), dpi=100)
        
        # Background network
        G = nx.DiGraph()
        for _, row in self.nodes_df.iterrows():
            G.add_node(row['node_id'], type=row['node_type'])
        for _, row in self.edges_df.iterrows():
            G.add_edge(row['from_node'], row['to_node'], capacity=row['capacity'])
            
        constrained_edges = [(u, v) for u, v, d in G.edges(data=True) if d['capacity'] < 999]
        normal_edges = [(u, v) for u, v, d in G.edges(data=True) if d['capacity'] >= 999]
        
        nx.draw_networkx_edges(G, self.pos, edgelist=normal_edges, ax=ax, edge_color='#bdc3c7', width=1.0, arrows=True, style='dashed')
        nx.draw_networkx_edges(G, self.pos, edgelist=constrained_edges, ax=ax, edge_color='#e74c3c', width=2.0, arrows=True)
        
        colors = {
            'parking': '#34495e',
            'junction': '#7f8c8d',
            'load_ore': '#27ae60',
            'crusher': '#d35400',
            'waste_dump': '#9b59b6',
            'maintenance': '#c0392b'
        }
        for n_type, col in colors.items():
            nodes = [n for n, attr in G.nodes(data=True) if attr['type'] == n_type]
            if nodes:
                nx.draw_networkx_nodes(G, self.pos, nodelist=nodes, ax=ax, node_color=col, node_size=150)
                
        labels = {n: n for n in G.nodes()}
        nx.draw_networkx_labels(G, self.pos, labels, font_size=7, font_color='white', font_weight='bold', ax=ax)
        
        ax.set_facecolor('#fdfefe')
        ax.grid(True, linestyle=':', alpha=0.3)
        ax.set_title("Live Simulation Feed - First 60 Minutes\n(Green = Empty Truck, Gold = Loaded Truck)", fontsize=12, fontweight='bold')
        ax.set_xlabel("X (meters)")
        ax.set_ylabel("Y (meters)")
        
        # Scatters for trucks
        empty_scatter = ax.scatter([], [], c='#2ecc71', s=80, marker='o', edgecolors='black', label='Empty Trucks', zorder=5)
        loaded_scatter = ax.scatter([], [], c='#f1c40f', s=100, marker='s', edgecolors='black', label='Loaded Trucks', zorder=5)
        
        time_text = ax.text(0.02, 0.95, '', transform=ax.transAxes, fontsize=12, fontweight='bold', bbox=dict(facecolor='white', alpha=0.8, boxstyle='round,pad=0.5'))
        ax.legend(loc='lower right')
        
        plt.tight_layout()

        def update(frame_idx):
            t_val = time_steps[frame_idx]
            time_text.set_text(f"Simulation Time: {t_val:.1f} min")
            
            # Filter truck positions
            empty_x, empty_y = [], []
            loaded_x, loaded_y = [], []
            
            for t_id in truck_ids:
                pos_xy = positions_over_time[t_id][frame_idx]
                state = states_over_time[t_id][frame_idx]
                if state == 'loaded':
                    loaded_x.append(pos_xy[0])
                    loaded_y.append(pos_xy[1])
                else:
                    empty_x.append(pos_xy[0])
                    empty_y.append(pos_xy[1])
                    
            empty_scatter.set_offsets(np.column_stack([empty_x, empty_y]) if empty_x else np.empty((0, 2)))
            loaded_scatter.set_offsets(np.column_stack([loaded_x, loaded_y]) if loaded_x else np.empty((0, 2)))
            return empty_scatter, loaded_scatter, time_text

        # Create animation
        anim = FuncAnimation(fig, update, frames=len(time_steps), blit=True)
        anim_path = os.path.join(self.output_dir, "animation.gif")
        
        # Save GIF
        writer = PillowWriter(fps=5)
        anim.save(anim_path, writer=writer)
        plt.close()
        print("animation.gif saved.")
