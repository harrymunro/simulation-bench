"""Event-log record schema for the mine throughput simulation.

The Seed contract pins a specific column set for ``event_log.csv``::

    time_min, replication, scenario_id, truck_id, event_type, from_node,
    to_node, location, loaded, payload_tonnes, resource_id, queue_length

Defining the schema as a frozen dataclass means:

* The simulation cannot accidentally emit malformed records — every field
  is named at construction time.
* The CSV header order is centralised here, so a future schema change can
  not drift between writer and reader.
* Tests can construct synthetic events without depending on simpy.

Records are append-only. Aggregation logic (cycle times, throughput, etc.)
runs on a separate pure-Python accumulator (see :mod:`mine_sim.metrics`).
The event log is for traceability and animation, not for KPI computation,
so the two paths can evolve independently.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Final

# ---------------------------------------------------------------------------
# Canonical event-type strings — the simulation must use these exact values
# so downstream tooling (event_log.csv, animation, tests) can pattern-match
# without copy-paste typos.
# ---------------------------------------------------------------------------
EVENT_DISPATCH: Final[str] = "dispatch"
EVENT_ARRIVE_LOADER: Final[str] = "arrive_loader"
EVENT_START_LOAD: Final[str] = "start_load"
EVENT_END_LOAD: Final[str] = "end_load"
EVENT_DEPART_LOADER: Final[str] = "depart_loader"
EVENT_ARRIVE_CRUSHER: Final[str] = "arrive_crusher"
EVENT_START_DUMP: Final[str] = "start_dump"
EVENT_END_DUMP: Final[str] = "end_dump"
EVENT_DEPART_CRUSHER: Final[str] = "depart_crusher"
EVENT_EDGE_ENTER: Final[str] = "edge_enter"
EVENT_EDGE_LEAVE: Final[str] = "edge_leave"


@dataclass(frozen=True)
class EventRecord:
    """One row of ``event_log.csv``.

    All fields are mandatory; pass ``None`` (or the empty string for str
    columns) when an attribute does not apply to a particular event type.
    """

    time_min: float
    replication: int
    scenario_id: str
    truck_id: str
    event_type: str
    from_node: str | None
    to_node: str | None
    location: str | None
    loaded: bool | None
    payload_tonnes: float | None
    resource_id: str | None
    queue_length: int | None

    def to_csv_row(self) -> dict[str, object]:
        """Render the record as a flat dict suitable for ``pandas.DataFrame``."""
        return {
            "time_min": round(self.time_min, 6),
            "replication": self.replication,
            "scenario_id": self.scenario_id,
            "truck_id": self.truck_id,
            "event_type": self.event_type,
            "from_node": _none_to_blank(self.from_node),
            "to_node": _none_to_blank(self.to_node),
            "location": _none_to_blank(self.location),
            "loaded": _bool_to_csv(self.loaded),
            "payload_tonnes": (
                round(self.payload_tonnes, 6)
                if self.payload_tonnes is not None
                else ""
            ),
            "resource_id": _none_to_blank(self.resource_id),
            "queue_length": (
                int(self.queue_length) if self.queue_length is not None else ""
            ),
        }


def _none_to_blank(value: str | None) -> str:
    return "" if value is None else value


def _bool_to_csv(value: bool | None) -> str:
    if value is None:
        return ""
    return "true" if value else "false"


#: CSV column order. Derived from the dataclass so they cannot drift.
EVENT_CSV_COLUMNS: Final[tuple[str, ...]] = tuple(f.name for f in fields(EventRecord))


__all__ = [
    "EVENT_ARRIVE_CRUSHER",
    "EVENT_ARRIVE_LOADER",
    "EVENT_CSV_COLUMNS",
    "EVENT_DEPART_CRUSHER",
    "EVENT_DEPART_LOADER",
    "EVENT_DISPATCH",
    "EVENT_EDGE_ENTER",
    "EVENT_EDGE_LEAVE",
    "EVENT_END_DUMP",
    "EVENT_END_LOAD",
    "EVENT_START_DUMP",
    "EVENT_START_LOAD",
    "EventRecord",
]
