"""Render a static topology diagram from the input data.

Standalone helper (not part of run.py). Produces ``topology.png`` showing
nodes coloured by type, edges coloured by capacity (red = constrained), and
labels for the key infrastructure nodes.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd


NODE_COLOURS = {
    "load_ore": "#1f77b4",     # blue
    "crusher": "#d62728",      # red
    "waste_dump": "#8c564b",   # brown
    "junction": "#7f7f7f",     # grey
    "parking": "#2ca02c",      # green
    "maintenance": "#ff7f0e",  # orange
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path(__file__).parent / "data")
    parser.add_argument("--output", type=Path, default=Path(__file__).parent / "topology.png")
    args = parser.parse_args()

    nodes = pd.read_csv(args.data_dir / "nodes.csv").dropna(how="all")
    edges = pd.read_csv(args.data_dir / "edges.csv").dropna(how="all")

    g = nx.DiGraph()
    pos: dict[str, tuple[float, float]] = {}
    for _, n in nodes.iterrows():
        g.add_node(n["node_id"], **n.to_dict())
        pos[n["node_id"]] = (float(n["x_m"]), float(n["y_m"]))

    for _, e in edges.iterrows():
        g.add_edge(e["from_node"], e["to_node"], **e.to_dict())

    fig, ax = plt.subplots(figsize=(12, 9))

    # Edges: red if capacity-constrained, grey otherwise.
    constrained = [(u, v) for u, v, d in g.edges(data=True) if int(d["capacity"]) < 100]
    unconstrained = [(u, v) for u, v, d in g.edges(data=True) if int(d["capacity"]) >= 100]
    nx.draw_networkx_edges(g, pos, edgelist=unconstrained, edge_color="#cccccc",
                           width=1.0, arrows=True, arrowsize=8, ax=ax,
                           connectionstyle="arc3,rad=0.05")
    nx.draw_networkx_edges(g, pos, edgelist=constrained, edge_color="#d62728",
                           width=2.5, arrows=True, arrowsize=10, ax=ax,
                           connectionstyle="arc3,rad=0.05")

    # Nodes coloured by type.
    for ntype, colour in NODE_COLOURS.items():
        ids = [n for n, d in g.nodes(data=True) if d.get("node_type") == ntype]
        if not ids:
            continue
        nx.draw_networkx_nodes(g, pos, nodelist=ids, node_color=colour,
                               node_size=420, ax=ax, label=ntype,
                               edgecolors="black", linewidths=0.7)

    # Labels.
    nx.draw_networkx_labels(g, pos, font_size=8, ax=ax)

    # Legend overlay for constrained edges.
    handles = [plt.Line2D([0], [0], color=c, lw=4, label=label)
               for label, c in [("constrained edge (capacity<100)", "#d62728"),
                                ("unconstrained edge", "#cccccc")]]
    ax.add_artist(ax.legend(handles=handles, loc="lower left", fontsize=8))
    # Re-add node-type legend.
    leg_handles = [plt.Line2D([0], [0], marker="o", color="w",
                              markerfacecolor=c, markersize=10, label=t)
                   for t, c in NODE_COLOURS.items()]
    ax.legend(handles=leg_handles, loc="upper right", fontsize=8, title="node type")

    ax.set_title("Mine topology — capacity-constrained edges in red")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, linestyle=":", alpha=0.4)

    fig.tight_layout()
    fig.savefig(args.output, dpi=130)
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
