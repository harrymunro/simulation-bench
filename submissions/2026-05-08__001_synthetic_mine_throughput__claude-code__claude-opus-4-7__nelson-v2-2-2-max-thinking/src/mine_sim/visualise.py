"""Static topology plot and event-log-driven animation."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib
matplotlib.use("Agg")
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .data import load_static_data
from .scenarios import load_scenario
from .topology import build_scenario_topology

# Visual palette by node type.
NODE_COLOURS = {
    "parking": "#888888",
    "junction": "#bbbbbb",
    "load_ore": "#2ca02c",
    "crusher": "#d62728",
    "waste_dump": "#8c564b",
    "maintenance": "#9467bd",
}


def _node_xy(static, scenario_id: str = "baseline") -> Dict[str, Tuple[float, float]]:
    return {nid: (n.x_m, n.y_m) for nid, n in static.nodes.items()}


def write_topology_png(*, data_dir: Path, output_path: Path, scenario_id: str = "baseline") -> None:
    """Render a static topology overview, highlighting capacity-1 edges."""
    static = load_static_data(data_dir)
    scenario = load_scenario(data_dir / "scenarios", scenario_id)
    topology = build_scenario_topology(static, scenario)
    pos = _node_xy(static)

    fig, ax = plt.subplots(figsize=(11, 9))
    ax.set_aspect("equal")
    ax.set_facecolor("#fafafa")

    # Edges first.
    for eid, e in topology.edges.items():
        if e.closed:
            x1, y1 = pos[e.from_node]
            x2, y2 = pos[e.to_node]
            ax.annotate(
                "", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="->", linestyle="dashed", color="#cccccc", lw=0.8, alpha=0.7),
            )
            continue
        x1, y1 = pos[e.from_node]
        x2, y2 = pos[e.to_node]
        is_cap1 = e.capacity == 1
        colour = "#d62728" if is_cap1 else "#999999"
        lw = 2.2 if is_cap1 else 1.0
        ax.annotate(
            "", xy=(x2, y2), xytext=(x1, y1),
            arrowprops=dict(arrowstyle="->", color=colour, lw=lw, alpha=0.85),
        )

    # Nodes.
    for nid, (x, y) in pos.items():
        ntype = topology.nodes_effective[nid]["node_type"]
        c = NODE_COLOURS.get(ntype, "#444444")
        ax.scatter([x], [y], s=380, c=c, edgecolor="black", zorder=3)
        ax.text(x, y - 110, nid, fontsize=8, ha="center", va="top", zorder=4)

    # Legend.
    handles = [mpatches.Patch(color=v, label=k) for k, v in NODE_COLOURS.items()]
    handles.append(mpatches.Patch(color="#d62728", label="capacity-1 edge"))
    handles.append(mpatches.Patch(color="#999999", label="multi-capacity edge"))
    handles.append(mpatches.Patch(color="#cccccc", label="closed edge"))
    ax.legend(handles=handles, loc="upper left", fontsize=8, framealpha=0.9)

    ax.set_title(f"Mine topology — scenario: {scenario_id}", fontsize=12)
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(True, alpha=0.25)

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(output_path, dpi=120)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Animation


def _interpolate_positions_at(
    *,
    truck_states: Dict[str, Dict],
    pos: Dict[str, Tuple[float, float]],
    t_now: float,
) -> Dict[str, Tuple[float, float, str]]:
    """Return per-truck (x, y, state) at time ``t_now`` using current truck_states."""
    out = {}
    for tid, st in truck_states.items():
        seg = st.get("segment")
        if seg is None:
            x, y = pos.get(st.get("node", "PARK"), (0, 0))
            out[tid] = (x, y, st.get("status", "idle"))
            continue
        u, v, t_start, t_end = seg
        if t_end <= t_start:
            frac = 1.0
        else:
            frac = (t_now - t_start) / (t_end - t_start)
            frac = max(0.0, min(1.0, frac))
        x1, y1 = pos[u]
        x2, y2 = pos[v]
        x = x1 + (x2 - x1) * frac
        y = y1 + (y2 - y1) * frac
        out[tid] = (x, y, st.get("status", "moving"))
    return out


def write_animation_gif(
    *,
    data_dir: Path,
    event_log_path: Path,
    output_path: Path,
    scenario_id: str = "baseline",
    replication: int = 0,
    fps: int = 10,
    step_min: float = 2.0,
    max_minutes: float = 480.0,
) -> None:
    """Replay the chosen replication's event log as truck markers moving along edges.

    Truck position is interpolated along the most recent ``enter_edge``/``leave_edge``
    pair. When a truck is at a node (loader / crusher / dispatched-from-park),
    it sits stationary on that node. Frames are produced at ``step_min`` minute
    intervals up to ``max_minutes`` and stitched into a GIF at ``fps`` frames/s.
    """
    import imageio.v2 as imageio

    static = load_static_data(data_dir)
    scenario = load_scenario(data_dir / "scenarios", scenario_id)
    topology = build_scenario_topology(static, scenario)
    pos = _node_xy(static)

    df = pd.read_csv(event_log_path)
    df = df[(df["scenario_id"] == scenario_id) & (df["replication"] == replication)].copy()
    if df.empty:
        raise RuntimeError(
            f"No event log rows for scenario={scenario_id} rep={replication}. "
            f"Re-run experiment with --event-log-reps >= {replication+1}."
        )
    df = df.sort_values("time_min").reset_index(drop=True)

    truck_ids = sorted(df["truck_id"].astype(str).unique())
    # Initialise each truck at PARK (start_node) doing 'idle'.
    truck_states: Dict[str, Dict] = {
        tid: {"node": "PARK", "segment": None, "status": "idle"} for tid in truck_ids
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    frames: List[np.ndarray] = []
    event_idx = 0
    n_events = len(df)

    t = 0.0
    while t <= max_minutes + 1e-9:
        # Advance event_idx, applying every event with time <= t.
        while event_idx < n_events and df.iloc[event_idx]["time_min"] <= t:
            ev = df.iloc[event_idx]
            tid = str(ev["truck_id"])
            etype = ev["event_type"]
            st = truck_states.setdefault(tid, {"node": "PARK", "segment": None, "status": "idle"})
            if etype == "enter_edge":
                u, v = str(ev["from_node"]), str(ev["to_node"])
                # Compute end time from next leave_edge for same truck/edge id.
                # We only know start now; we'll set end heuristically using free-flow.
                # Find matching leave_edge later in df.
                leave_t = float(ev["time_min"])
                eid = str(ev["resource_id"])
                future = df[(df.index > event_idx)
                            & (df["truck_id"].astype(str) == tid)
                            & (df["resource_id"].astype(str) == eid)
                            & (df["event_type"] == "leave_edge")]
                if not future.empty:
                    leave_t = float(future.iloc[0]["time_min"])
                st["segment"] = (u, v, float(ev["time_min"]), leave_t)
                st["node"] = v
                st["status"] = "loaded" if int(ev.get("loaded", 0) or 0) == 1 else "empty"
            elif etype == "leave_edge":
                st["segment"] = None
                st["node"] = str(ev["to_node"])
                st["status"] = "loaded" if int(ev.get("loaded", 0) or 0) == 1 else "empty"
            elif etype == "arrive_loader":
                st["segment"] = None
                st["node"] = str(ev["location"])
                st["status"] = "queue_load"
            elif etype == "load_start":
                st["status"] = "loading"
            elif etype == "load_end":
                st["status"] = "loaded"
            elif etype == "arrive_crusher":
                st["segment"] = None
                st["node"] = str(ev["location"])
                st["status"] = "queue_dump"
            elif etype == "dump_start":
                st["status"] = "dumping"
            elif etype == "dump_end":
                st["status"] = "empty"
            event_idx += 1

        positions = _interpolate_positions_at(
            truck_states=truck_states, pos=pos, t_now=t
        )

        fig, ax = plt.subplots(figsize=(9, 7))
        ax.set_aspect("equal")
        ax.set_facecolor("#fafafa")

        for eid, e in topology.edges.items():
            if e.closed:
                continue
            x1, y1 = pos[e.from_node]
            x2, y2 = pos[e.to_node]
            colour = "#d62728" if e.capacity == 1 else "#aaaaaa"
            ax.plot([x1, x2], [y1, y2], color=colour, lw=1.2, alpha=0.65, zorder=1)

        for nid, (x, y) in pos.items():
            ntype = topology.nodes_effective[nid]["node_type"]
            c = NODE_COLOURS.get(ntype, "#444444")
            ax.scatter([x], [y], s=180, c=c, edgecolor="black", zorder=2)
            ax.text(x, y - 90, nid, fontsize=7, ha="center", va="top", zorder=4)

        # Trucks.
        for tid, (x, y, status) in positions.items():
            colour = {
                "loading": "#1f77b4", "queue_load": "#aec7e8",
                "dumping": "#d62728", "queue_dump": "#ff9896",
                "loaded": "#2ca02c", "empty": "#ff7f0e",
                "idle": "#888888",
            }.get(status, "#666666")
            ax.scatter([x], [y], s=70, c=colour, edgecolor="black", linewidth=0.6, zorder=5)

        ax.set_title(f"{scenario_id} rep={replication}  t={t:5.1f} min", fontsize=10)
        ax.set_xlim(-300, 4000)
        ax.set_ylim(-700, 2400)
        ax.grid(True, alpha=0.25)

        buf = io.BytesIO()
        fig.tight_layout()
        fig.savefig(buf, format="png", dpi=80)
        plt.close(fig)
        buf.seek(0)
        frame = imageio.imread(buf)
        frames.append(frame)

        t += step_min

    imageio.mimsave(output_path, frames, fps=fps, loop=0)
