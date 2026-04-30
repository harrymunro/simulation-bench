"""Render a topology diagram of the synthetic mine.

Renders ``topology.png`` from ``data/nodes.csv`` and ``data/edges.csv`` showing:
  * Nodes coloured and shaped by ``node_type`` (parking, junction, load_ore,
    crusher, waste_dump, maintenance).
  * Directed edges drawn as light-grey arrows for high-capacity (capacity > 1)
    segments and as bold red arrows for capacity-1 (single-lane / shared-resource)
    segments, which are the SimPy ``Resource`` candidates.
  * Edge IDs annotated for every capacity-1 segment so the bottleneck topology
    is easy to inspect at a glance.

Usage:

    python3 scripts/render_topology.py [--out topology.png]

The script is deliberately self-contained (only stdlib + matplotlib + pandas)
so it can be run without invoking the full ``mine_sim`` package, and is safe
for other agents working on sibling tasks (e.g. the simulation core) to import
or ignore.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D


# ---------------------------------------------------------------------------
# Style constants (immutable)
# ---------------------------------------------------------------------------

NODE_STYLE = {
    "parking":     {"color": "#1f77b4", "marker": "s", "size": 360, "label": "Parking"},
    "junction":    {"color": "#7f7f7f", "marker": "o", "size": 220, "label": "Junction"},
    "load_ore":    {"color": "#2ca02c", "marker": "^", "size": 420, "label": "Ore Loader"},
    "crusher":     {"color": "#d62728", "marker": "*", "size": 620, "label": "Primary Crusher"},
    "waste_dump":  {"color": "#8c564b", "marker": "X", "size": 360, "label": "Waste Dump"},
    "maintenance": {"color": "#9467bd", "marker": "P", "size": 360, "label": "Maintenance Bay"},
}

CAP1_COLOR = "#e6194b"  # bold red for capacity-1 (bottleneck) edges
CAP_HI_COLOR = "#bfbfbf"  # light grey for high-capacity edges
CAP1_LW = 2.4
CAP_HI_LW = 1.0


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_data(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    nodes = pd.read_csv(data_dir / "nodes.csv")
    edges = pd.read_csv(data_dir / "edges.csv")
    # Drop completely blank rows that sometimes trail CSVs.
    nodes = nodes.dropna(subset=["node_id"]).reset_index(drop=True)
    edges = edges.dropna(subset=["edge_id"]).reset_index(drop=True)
    edges["capacity"] = edges["capacity"].astype(int)
    return nodes, edges


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render(nodes: pd.DataFrame, edges: pd.DataFrame, out_path: Path) -> None:
    coords = {row.node_id: (float(row.x_m), float(row.y_m)) for row in nodes.itertuples()}

    fig, ax = plt.subplots(figsize=(13, 10), dpi=150)
    ax.set_facecolor("#fafafa")

    # ---- Edges -----------------------------------------------------------
    cap1_edges = edges[edges["capacity"] <= 1]
    hi_cap_edges = edges[edges["capacity"] > 1]

    # Draw high-capacity edges first (background)
    for row in hi_cap_edges.itertuples():
        if row.from_node not in coords or row.to_node not in coords:
            continue
        x0, y0 = coords[row.from_node]
        x1, y1 = coords[row.to_node]
        ax.annotate(
            "",
            xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(
                arrowstyle="->",
                color=CAP_HI_COLOR,
                lw=CAP_HI_LW,
                shrinkA=12, shrinkB=12,
                alpha=0.7,
            ),
            zorder=1,
        )

    # Draw capacity-1 edges on top, with annotations.
    # For each (from,to) pair we offset the arrow perpendicular to the line so
    # both directions are visible and their labels do not overlap.
    import math
    OFFSET_M = 55.0  # metres perpendicular offset for parallel arrows
    for row in cap1_edges.itertuples():
        if row.from_node not in coords or row.to_node not in coords:
            continue
        x0, y0 = coords[row.from_node]
        x1, y1 = coords[row.to_node]
        dx, dy = x1 - x0, y1 - y0
        length = math.hypot(dx, dy) or 1.0
        # Perpendicular unit vector (rotated 90 deg counter-clockwise relative
        # to direction of travel); applied uniformly so each direction sits on
        # its own side of the centreline (right-hand-side convention).
        px, py = -dy / length, dx / length
        ox, oy = px * OFFSET_M, py * OFFSET_M

        ax.annotate(
            "",
            xy=(x1 + ox, y1 + oy), xytext=(x0 + ox, y0 + oy),
            arrowprops=dict(
                arrowstyle="->",
                color=CAP1_COLOR,
                lw=CAP1_LW,
                shrinkA=14, shrinkB=14,
            ),
            zorder=3,
        )
        # Edge label at midpoint of the offset arrow
        mx = (x0 + x1) / 2.0 + ox
        my = (y0 + y1) / 2.0 + oy
        ax.text(
            mx, my, row.edge_id,
            fontsize=7, color=CAP1_COLOR, weight="bold",
            ha="center", va="center",
            bbox=dict(boxstyle="round,pad=0.18", fc="white", ec=CAP1_COLOR, lw=0.6, alpha=0.9),
            zorder=4,
        )

    # ---- Nodes -----------------------------------------------------------
    for ntype, style in NODE_STYLE.items():
        subset = nodes[nodes["node_type"] == ntype]
        if subset.empty:
            continue
        ax.scatter(
            subset["x_m"], subset["y_m"],
            c=style["color"], marker=style["marker"], s=style["size"],
            edgecolors="black", linewidths=0.8,
            zorder=5, label=style["label"],
        )

    # Node labels
    for row in nodes.itertuples():
        ax.annotate(
            row.node_id,
            xy=(row.x_m, row.y_m),
            xytext=(8, 8), textcoords="offset points",
            fontsize=9, weight="bold",
            zorder=6,
        )

    # ---- Legend ----------------------------------------------------------
    node_handles = [
        Line2D(
            [0], [0],
            marker=style["marker"], color="w",
            markerfacecolor=style["color"], markeredgecolor="black",
            markersize=10, label=style["label"],
        )
        for style in NODE_STYLE.values()
    ]
    edge_handles = [
        Line2D([0], [0], color=CAP1_COLOR, lw=CAP1_LW,
               label="Capacity-1 edge (SimPy Resource)"),
        Line2D([0], [0], color=CAP_HI_COLOR, lw=CAP_HI_LW,
               label="High-capacity edge"),
    ]
    leg1 = ax.legend(handles=node_handles, title="Nodes", loc="upper left",
                     fontsize=9, title_fontsize=10, framealpha=0.95)
    ax.add_artist(leg1)
    ax.legend(handles=edge_handles, title="Edges", loc="lower right",
              fontsize=9, title_fontsize=10, framealpha=0.95)

    # ---- Cosmetics -------------------------------------------------------
    n_cap1 = len(cap1_edges)
    n_total = len(edges)
    ax.set_title(
        f"Synthetic Mine Topology (benchmark 001)\n"
        f"{len(nodes)} nodes, {n_total} directed edges, "
        f"{n_cap1} capacity-1 segments highlighted",
        fontsize=13, weight="bold",
    )
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(True, linestyle=":", alpha=0.4)
    ax.set_aspect("equal", adjustable="datalim")

    # Add a small footer note about WASTE/MAINT being out-of-scope for ore haul
    ax.text(
        0.99, 0.01,
        "WASTE & MAINT are excluded from active simulation (no truck traffic).",
        transform=ax.transAxes, fontsize=8, color="#444",
        ha="right", va="bottom", style="italic",
    )

    fig.tight_layout()
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Render mine topology diagram.")
    parser.add_argument(
        "--data-dir", type=Path,
        default=Path(__file__).resolve().parent.parent / "data",
        help="Path to the data directory containing nodes.csv and edges.csv.",
    )
    parser.add_argument(
        "--out", type=Path,
        default=Path(__file__).resolve().parent.parent / "topology.png",
        help="Output PNG path (default: ./topology.png at submission root).",
    )
    args = parser.parse_args()

    nodes, edges = load_data(args.data_dir)
    render(nodes, edges, args.out)
    cap1 = int((edges["capacity"] <= 1).sum())
    print(
        f"Wrote {args.out} ({len(nodes)} nodes, {len(edges)} edges, "
        f"{cap1} capacity-1 segments highlighted)."
    )


if __name__ == "__main__":
    main()
