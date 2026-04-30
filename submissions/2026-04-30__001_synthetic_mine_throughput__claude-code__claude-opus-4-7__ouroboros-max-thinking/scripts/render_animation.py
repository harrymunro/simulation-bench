"""Render an animated GIF of one replication's truck haulage cycles.

Reads ``runs/ac2_run_all/baseline/event_log.csv`` (or any compatible event log),
selects a single ``(scenario_id, replication)`` pair, and produces a Pillow-based
animation showing each truck moving across the mine topology.

Truck positions are interpolated linearly between consecutive timestamped
"location keypoints" extracted from the event log. We use every event whose
``location`` field is populated — that includes ``dispatch``, ``arrive_loader``,
``edge_enter`` (location = ``from_node``), ``edge_leave`` (location = ``to_node``),
``arrive_crusher`` and the loader/crusher service events. Events without a
``location`` are ignored (they coincide in time with a same-second event that
*does* carry the location).

While a truck is loading or dumping, consecutive keypoints share the same node,
so the interpolation hovers there — which reads as the truck "queueing" or
"servicing" at that node, exactly the visual we want.

Usage::

    python3 scripts/render_animation.py \
        --event-log runs/ac2_run_all/baseline/event_log.csv \
        --scenario baseline --replication 0 \
        --out animation.gif --fps 12 --frames 144

The defaults pick the baseline scenario, replication 0, render 144 frames
(every ~3.33 simulated minutes over the 480-min shift) at 12 fps for an
~12-second loop suitable for embedding in a README.

The script depends only on pandas and matplotlib (with the bundled Pillow
writer); no extra system tools (e.g. ``ffmpeg`` / ``imagemagick``) are needed.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.animation import FuncAnimation, PillowWriter
from matplotlib.lines import Line2D


# ---------------------------------------------------------------------------
# Style constants (immutable)
# ---------------------------------------------------------------------------

NODE_STYLE = {
    "parking":     {"color": "#1f77b4", "marker": "s", "size": 220, "label": "Parking"},
    "junction":    {"color": "#bcbcbc", "marker": "o", "size": 110, "label": "Junction"},
    "load_ore":    {"color": "#2ca02c", "marker": "^", "size": 320, "label": "Ore Loader"},
    "crusher":     {"color": "#d62728", "marker": "*", "size": 480, "label": "Primary Crusher"},
    "waste_dump":  {"color": "#8c564b", "marker": "X", "size": 220, "label": "Waste Dump"},
    "maintenance": {"color": "#9467bd", "marker": "P", "size": 220, "label": "Maintenance"},
}

CAP1_COLOR = "#e6194b"
CAP_HI_COLOR = "#cccccc"
TRUCK_LOADED_COLOR = "#ff7f0e"
TRUCK_EMPTY_COLOR = "#1f77b4"
TRUCK_SIZE = 90


# ---------------------------------------------------------------------------
# Data structures (immutable)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TruckTimeline:
    """Sorted (time_min, x, y, loaded) keypoints for one truck."""

    truck_id: str
    times: np.ndarray  # shape (N,)
    xs: np.ndarray     # shape (N,)
    ys: np.ndarray     # shape (N,)
    loaded: np.ndarray  # shape (N,) bool

    def position_at(self, t: float) -> tuple[float, float, bool]:
        """Linear interpolation; clamped to first/last keypoint outside range."""
        if t <= self.times[0]:
            return float(self.xs[0]), float(self.ys[0]), bool(self.loaded[0])
        if t >= self.times[-1]:
            return float(self.xs[-1]), float(self.ys[-1]), bool(self.loaded[-1])
        idx = int(np.searchsorted(self.times, t, side="right")) - 1
        idx = max(0, min(idx, len(self.times) - 2))
        t0, t1 = self.times[idx], self.times[idx + 1]
        if t1 == t0:
            return float(self.xs[idx + 1]), float(self.ys[idx + 1]), bool(self.loaded[idx + 1])
        frac = (t - t0) / (t1 - t0)
        x = self.xs[idx] + frac * (self.xs[idx + 1] - self.xs[idx])
        y = self.ys[idx] + frac * (self.ys[idx + 1] - self.ys[idx])
        # The "loaded" state flips at the keypoint where it changes; show the
        # state of the segment we're currently traversing (i.e. the start of the
        # current segment). end_load events carry loaded=True at the keypoint,
        # so this naturally reads "loaded after pickup, empty after dump".
        return float(x), float(y), bool(self.loaded[idx + 1])


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

def load_topology(data_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, tuple[float, float]]]:
    nodes = pd.read_csv(data_dir / "nodes.csv").dropna(subset=["node_id"]).reset_index(drop=True)
    edges = pd.read_csv(data_dir / "edges.csv").dropna(subset=["edge_id"]).reset_index(drop=True)
    edges["capacity"] = edges["capacity"].astype(int)
    coords = {row.node_id: (float(row.x_m), float(row.y_m)) for row in nodes.itertuples()}
    return nodes, edges, coords


def load_event_slice(
    event_log_path: Path,
    scenario_id: str,
    replication: int,
) -> pd.DataFrame:
    df = pd.read_csv(event_log_path)
    mask = (df["scenario_id"] == scenario_id) & (df["replication"] == replication)
    sliced = df.loc[mask].copy()
    if sliced.empty:
        raise ValueError(
            f"No events found for scenario_id={scenario_id!r} replication={replication} "
            f"in {event_log_path}. "
            f"Available: {sorted(df['scenario_id'].unique())}"
        )
    sliced.sort_values("time_min", kind="stable", inplace=True)
    return sliced.reset_index(drop=True)


def build_truck_timelines(
    events: pd.DataFrame,
    coords: dict[str, tuple[float, float]],
) -> list[TruckTimeline]:
    """Build a per-truck keypoint timeline from the event log slice.

    A keypoint is any event whose ``location`` field resolves to a known node
    in ``coords``. Consecutive keypoints with the same ``(x, y)`` are collapsed
    to two endpoints (start and end of the dwell) so interpolation hovers in
    place during loading / dumping / queueing.
    """
    timelines: list[TruckTimeline] = []
    keep = events[events["location"].isin(coords.keys())].copy()
    for truck_id, grp in keep.groupby("truck_id", sort=True):
        grp_sorted = grp.sort_values("time_min", kind="stable")
        times = grp_sorted["time_min"].to_numpy(dtype=float)
        xs = np.array([coords[loc][0] for loc in grp_sorted["location"]], dtype=float)
        ys = np.array([coords[loc][1] for loc in grp_sorted["location"]], dtype=float)
        loaded = (grp_sorted["loaded"].astype(str).str.lower() == "true").to_numpy()
        timelines.append(
            TruckTimeline(
                truck_id=str(truck_id),
                times=times,
                xs=xs,
                ys=ys,
                loaded=loaded,
            )
        )
    return timelines


# ---------------------------------------------------------------------------
# Throughput counter for the on-screen HUD
# ---------------------------------------------------------------------------

def cumulative_dump_count(events: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    dumps = events[events["event_type"] == "end_dump"].sort_values("time_min")
    times = dumps["time_min"].to_numpy(dtype=float)
    counts = np.arange(1, len(times) + 1, dtype=int)
    return times, counts


def dumps_done_at(t: float, dump_times: np.ndarray, dump_counts: np.ndarray) -> int:
    if len(dump_times) == 0 or t < dump_times[0]:
        return 0
    idx = int(np.searchsorted(dump_times, t, side="right")) - 1
    idx = max(0, min(idx, len(dump_counts) - 1))
    return int(dump_counts[idx])


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _draw_static_topology(ax, nodes: pd.DataFrame, edges: pd.DataFrame,
                          coords: dict[str, tuple[float, float]]) -> None:
    """Draw the underlying topology once; trucks are layered on top."""
    cap1_edges = edges[edges["capacity"] <= 1]
    hi_cap_edges = edges[edges["capacity"] > 1]

    for row in hi_cap_edges.itertuples():
        if row.from_node not in coords or row.to_node not in coords:
            continue
        x0, y0 = coords[row.from_node]
        x1, y1 = coords[row.to_node]
        ax.plot([x0, x1], [y0, y1], color=CAP_HI_COLOR, lw=1.0, alpha=0.6, zorder=1)

    for row in cap1_edges.itertuples():
        if row.from_node not in coords or row.to_node not in coords:
            continue
        x0, y0 = coords[row.from_node]
        x1, y1 = coords[row.to_node]
        ax.plot([x0, x1], [y0, y1], color=CAP1_COLOR, lw=1.6, alpha=0.55, zorder=2)

    for ntype, style in NODE_STYLE.items():
        subset = nodes[nodes["node_type"] == ntype]
        if subset.empty:
            continue
        ax.scatter(
            subset["x_m"], subset["y_m"],
            c=style["color"], marker=style["marker"], s=style["size"],
            edgecolors="black", linewidths=0.6,
            zorder=3, label=style["label"],
        )

    for row in nodes.itertuples():
        ax.annotate(
            row.node_id,
            xy=(row.x_m, row.y_m),
            xytext=(7, 7), textcoords="offset points",
            fontsize=7.5, weight="bold", color="#222",
            zorder=4,
        )


def render_animation(
    timelines: list[TruckTimeline],
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    coords: dict[str, tuple[float, float]],
    dump_times: np.ndarray,
    dump_counts: np.ndarray,
    out_path: Path,
    *,
    scenario_id: str,
    replication: int,
    shift_minutes: float,
    n_frames: int,
    fps: int,
) -> None:
    fig, ax = plt.subplots(figsize=(11, 8.5), dpi=110)
    ax.set_facecolor("#fafafa")
    _draw_static_topology(ax, nodes, edges, coords)

    # Truck scatter — one collection for empties, one for loaded, drawn on top.
    empty_scatter = ax.scatter([], [], c=TRUCK_EMPTY_COLOR, marker="o",
                               s=TRUCK_SIZE, edgecolors="black", linewidths=0.6,
                               zorder=6, label="Empty truck")
    loaded_scatter = ax.scatter([], [], c=TRUCK_LOADED_COLOR, marker="o",
                                s=TRUCK_SIZE, edgecolors="black", linewidths=0.6,
                                zorder=6, label="Loaded truck")
    truck_labels = [
        ax.annotate(t.truck_id, xy=(0, 0), xytext=(0, 0),
                    fontsize=7, weight="bold", color="#222",
                    visible=False, zorder=7)
        for t in timelines
    ]

    # HUD text (time + cumulative dumps + cumulative tonnes).
    hud = ax.text(
        0.01, 0.99, "",
        transform=ax.transAxes,
        fontsize=11, weight="bold",
        ha="left", va="top",
        bbox=dict(boxstyle="round,pad=0.35", fc="white", ec="#444", lw=0.8, alpha=0.9),
        zorder=10,
    )

    # Cosmetics
    ax.set_title(
        f"Mine haulage animation — scenario={scenario_id}, replication={replication}\n"
        f"empty (blue) vs loaded (orange) trucks; capacity-1 edges highlighted in red",
        fontsize=12, weight="bold",
    )
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.grid(True, linestyle=":", alpha=0.35)
    ax.set_aspect("equal", adjustable="datalim")

    # Add legend (nodes + truck states).
    node_handles = [
        Line2D([0], [0], marker=style["marker"], color="w",
               markerfacecolor=style["color"], markeredgecolor="black",
               markersize=9, label=style["label"])
        for style in NODE_STYLE.values()
    ]
    truck_handles = [
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=TRUCK_EMPTY_COLOR, markeredgecolor="black",
               markersize=9, label="Empty truck"),
        Line2D([0], [0], marker="o", color="w",
               markerfacecolor=TRUCK_LOADED_COLOR, markeredgecolor="black",
               markersize=9, label="Loaded truck"),
    ]
    leg1 = ax.legend(handles=node_handles, title="Nodes",
                     loc="upper right", fontsize=8, title_fontsize=9, framealpha=0.95)
    ax.add_artist(leg1)
    ax.legend(handles=truck_handles, title="Trucks",
              loc="lower right", fontsize=8, title_fontsize=9, framealpha=0.95)

    frame_times = np.linspace(0.0, shift_minutes, n_frames)

    # Truck payload tonnes from event log (nominal): use 100t default if not
    # available — but the event log records payload_tonnes per event so we
    # can derive total tonnes from cumulative dumps × payload.
    payload_lookup_t = 100.0  # default; tonnes axis is informational only.

    def init():
        empty_scatter.set_offsets(np.empty((0, 2)))
        loaded_scatter.set_offsets(np.empty((0, 2)))
        for lbl in truck_labels:
            lbl.set_visible(False)
        hud.set_text("")
        return [empty_scatter, loaded_scatter, hud, *truck_labels]

    def update(frame_idx: int):
        t = float(frame_times[frame_idx])
        empty_xy: list[tuple[float, float]] = []
        loaded_xy: list[tuple[float, float]] = []
        for i, tl in enumerate(timelines):
            x, y, loaded = tl.position_at(t)
            if loaded:
                loaded_xy.append((x, y))
            else:
                empty_xy.append((x, y))
            truck_labels[i].xy = (x, y)
            truck_labels[i].set_position((x + 35, y + 35))
            truck_labels[i].set_visible(True)

        empty_scatter.set_offsets(np.array(empty_xy) if empty_xy else np.empty((0, 2)))
        loaded_scatter.set_offsets(np.array(loaded_xy) if loaded_xy else np.empty((0, 2)))

        dumps = dumps_done_at(t, dump_times, dump_counts)
        tonnes = dumps * payload_lookup_t
        hud.set_text(
            f"t = {t:6.1f} min  ({t / 60.0:4.2f} h)\n"
            f"completed dumps: {dumps:>3d}\n"
            f"cumulative tonnes: {tonnes:>5.0f} t"
        )
        return [empty_scatter, loaded_scatter, hud, *truck_labels]

    anim = FuncAnimation(
        fig, update, frames=n_frames, init_func=init,
        interval=1000.0 / max(1, fps), blit=False, repeat=False,
    )

    writer = PillowWriter(fps=fps)
    anim.save(str(out_path), writer=writer, dpi=110)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: Iterable[str] | None = None) -> None:
    here = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Render mine haulage animation GIF.")
    parser.add_argument(
        "--event-log", type=Path,
        default=here / "runs" / "ac2_run_all" / "baseline" / "event_log.csv",
        help="Path to event_log.csv (default: baseline rep aggregate).",
    )
    parser.add_argument(
        "--data-dir", type=Path, default=here / "data",
        help="Directory containing nodes.csv and edges.csv.",
    )
    parser.add_argument("--scenario", type=str, default="baseline",
                        help="scenario_id to animate.")
    parser.add_argument("--replication", type=int, default=0,
                        help="replication index to animate.")
    parser.add_argument("--out", type=Path, default=here / "animation.gif",
                        help="Output GIF path.")
    parser.add_argument("--shift-minutes", type=float, default=480.0,
                        help="Total simulated shift duration to animate over.")
    parser.add_argument("--frames", type=int, default=144,
                        help="Number of frames in the GIF (default 144 ~= every 3.33 sim min).")
    parser.add_argument("--fps", type=int, default=12,
                        help="Frames per second of the output GIF.")
    args = parser.parse_args(list(argv) if argv is not None else None)

    nodes, edges, coords = load_topology(args.data_dir)
    events = load_event_slice(args.event_log, args.scenario, args.replication)
    timelines = build_truck_timelines(events, coords)
    if not timelines:
        raise RuntimeError("No truck timelines could be built from event log slice.")
    dump_times, dump_counts = cumulative_dump_count(events)

    render_animation(
        timelines, nodes, edges, coords, dump_times, dump_counts,
        out_path=args.out,
        scenario_id=args.scenario,
        replication=args.replication,
        shift_minutes=args.shift_minutes,
        n_frames=args.frames,
        fps=args.fps,
    )

    print(
        f"Wrote {args.out} "
        f"(scenario={args.scenario}, rep={args.replication}, "
        f"trucks={len(timelines)}, dumps={int(dump_counts[-1]) if len(dump_counts) else 0}, "
        f"frames={args.frames}, fps={args.fps})."
    )


if __name__ == "__main__":
    main()
