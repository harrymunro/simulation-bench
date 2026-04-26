"""Render the mine topology as a static PNG using matplotlib + networkx."""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

from src.simulation import load_input_dataframes
from src.topology import build_graph, lane_id_of


NODE_COLOR = {
    "parking": "#9aa0a6",
    "junction": "#b0c4de",
    "load_ore": "#e6a23c",
    "crusher": "#c0392b",
    "waste_dump": "#7f8c8d",
    "maintenance": "#8e44ad",
}


def main(out_path: Path = Path("topology.png")) -> None:
    nodes, edges, *_ = load_input_dataframes(Path("data"))
    g = build_graph(nodes, edges)

    pos = {nid: (n.x_m, n.y_m) for nid, n in nodes.items()}

    fig, ax = plt.subplots(figsize=(11, 8))

    constrained_lanes = {
        e.edge_id for e in edges if e.capacity < 999 and not e.closed
    }

    # Edges: thicker red for constrained, grey otherwise.
    for u, v, data in g.edges(data=True):
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        is_constrained = data["edge_id"] in constrained_lanes
        color = "#c0392b" if is_constrained else "#7f8c8d"
        lw = 2.4 if is_constrained else 0.9
        alpha = 0.85 if is_constrained else 0.55
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, alpha=alpha,
                            shrinkA=10, shrinkB=10),
        )

    # Nodes
    for nid, n in nodes.items():
        x, y = n.x_m, n.y_m
        c = NODE_COLOR.get(n.node_type, "#cccccc")
        ax.scatter([x], [y], s=520, c=c, edgecolors="black", linewidths=1.2, zorder=4)
        ax.annotate(
            nid, (x, y), textcoords="offset points", xytext=(0, -22),
            ha="center", fontsize=8, zorder=5,
        )

    # Legend
    legend_handles = []
    for k, c in NODE_COLOR.items():
        legend_handles.append(plt.Line2D([0], [0], marker='o', linestyle='',
                                          markersize=10, markerfacecolor=c,
                                          markeredgecolor='black', label=k))
    legend_handles.append(plt.Line2D([0], [0], color="#c0392b", lw=2.4,
                                      label="capacity-constrained edge"))
    legend_handles.append(plt.Line2D([0], [0], color="#7f8c8d", lw=1.0,
                                      label="open haul edge"))
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8, framealpha=0.95)

    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_title("Mine topology — capacity-constrained lanes highlighted")
    ax.set_aspect("equal", adjustable="datalim")
    ax.grid(True, linestyle=":", alpha=0.4)
    plt.tight_layout()
    plt.savefig(out_path, dpi=140)
    print(f"wrote {out_path}")


if __name__ == "__main__":
    main()
