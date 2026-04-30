"""Render a static topology figure.

Usage:
    python -m tools.draw_topology
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import networkx as nx

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.topology import Topology, load_topology  # noqa: E402


_NODE_COLORS = {
    "parking": "#9aa0a6",
    "junction": "#bdbdbd",
    "load_ore": "#2e7d32",
    "crusher": "#c62828",
    "waste_dump": "#6d4c41",
    "maintenance": "#1565c0",
}
_DEFAULT_NODE_COLOR = "#888888"


def _node_color(node_type: str) -> str:
    return _NODE_COLORS.get(node_type, _DEFAULT_NODE_COLOR)


def draw_topology(topology: Topology, output_path: Path) -> Path:
    output_path = Path(output_path)
    G = topology.G
    pos = {
        n: (data["x_m"], data["y_m"]) for n, data in G.nodes(data=True)
    }

    fig, ax = plt.subplots(figsize=(12, 9))

    constrained_edges = []
    open_edges = []
    closed_edges = []
    for u, v, data in G.edges(data=True):
        if data.get("closed"):
            closed_edges.append((u, v))
        elif data.get("is_capacity_constrained"):
            constrained_edges.append((u, v))
        else:
            open_edges.append((u, v))

    nx.draw_networkx_edges(
        G, pos, edgelist=open_edges, edge_color="#9e9e9e", width=1.2,
        arrows=True, arrowsize=8, ax=ax, connectionstyle="arc3,rad=0.06",
    )
    nx.draw_networkx_edges(
        G, pos, edgelist=constrained_edges, edge_color="#d32f2f", width=2.6,
        arrows=True, arrowsize=10, ax=ax, connectionstyle="arc3,rad=0.06",
    )
    if closed_edges:
        nx.draw_networkx_edges(
            G, pos, edgelist=closed_edges, edge_color="#000000", width=2.0,
            style="dashed", arrows=True, arrowsize=8, ax=ax,
            connectionstyle="arc3,rad=0.06",
        )

    node_colors = [_node_color(G.nodes[n]["node_type"]) for n in G.nodes]
    nx.draw_networkx_nodes(
        G, pos, node_color=node_colors, node_size=520,
        edgecolors="#212121", linewidths=1.2, ax=ax,
    )

    labels = {n: n for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8, font_weight="bold", ax=ax)

    edge_labels = {
        (u, v): data.get("edge_id", "")
        for u, v, data in G.edges(data=True)
        if data.get("is_capacity_constrained")
    }
    if edge_labels:
        nx.draw_networkx_edge_labels(
            G, pos, edge_labels=edge_labels, font_size=6,
            font_color="#b71c1c", ax=ax,
        )

    legend_handles = [
        mpatches.Patch(color=color, label=ntype.replace("_", " "))
        for ntype, color in _NODE_COLORS.items()
    ]
    legend_handles.append(
        mpatches.Patch(color="#d32f2f", label="capacity-constrained edge")
    )
    legend_handles.append(
        mpatches.Patch(color="#9e9e9e", label="unconstrained edge")
    )
    ax.legend(handles=legend_handles, loc="lower right", fontsize=8, framealpha=0.9)

    ax.set_title("Synthetic Mine Topology", fontsize=14)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.set_aspect("equal", adjustable="datalim")

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def main() -> int:
    data_dir = REPO_ROOT / "data"
    output_path = REPO_ROOT / "topology.png"
    topology = load_topology(data_dir)
    draw_topology(topology, output_path)
    print(f"Wrote {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
