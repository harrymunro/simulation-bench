"""Streaming event recorder for the simulation."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


EVENT_COLUMNS = [
    "time_min", "replication", "scenario_id", "truck_id", "event_type",
    "from_node", "to_node", "location", "loaded", "payload_tonnes",
    "resource_id", "queue_length",
]


@dataclass
class EventRecorder:
    scenario_id: str
    replication: int
    rows: List[tuple] = field(default_factory=list)

    def log(self, time_min: float, truck_id: str, event_type: str,
            from_node: Optional[str] = None, to_node: Optional[str] = None,
            location: Optional[str] = None, loaded: Optional[bool] = None,
            payload_tonnes: float = 0.0, resource_id: Optional[str] = None,
            queue_length: Optional[int] = None):
        self.rows.append((
            round(float(time_min), 4),
            self.replication,
            self.scenario_id,
            truck_id,
            event_type,
            from_node or "",
            to_node or "",
            location or "",
            "" if loaded is None else int(bool(loaded)),
            float(payload_tonnes),
            resource_id or "",
            "" if queue_length is None else int(queue_length),
        ))


def write_event_log(rows: List[tuple], path: Path, append: bool = False):
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append and path.exists() else "w"
    with open(path, mode, newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        if mode == "w":
            w.writerow(EVENT_COLUMNS)
        w.writerows(rows)
