"""Metrics collector and confidence-interval helper."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy import stats


def ci95_t(values: list[float]) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) using Student-t at 95% confidence."""
    arr = np.asarray(values, dtype=float)
    n = arr.size
    if n == 0:
        return 0.0, 0.0, 0.0
    mean = float(arr.mean())
    if n < 2:
        return mean, mean, mean
    sd = float(arr.std(ddof=1))
    if sd == 0.0:
        return mean, mean, mean
    sem = sd / math.sqrt(n)
    half = sem * float(stats.t.ppf(0.975, df=n - 1))
    return mean, mean - half, mean + half


@dataclass
class _ResourceStats:
    busy_minutes: float = 0.0
    queue_waits: list[float] = field(default_factory=list)
    queue_lengths_on_entry: list[int] = field(default_factory=list)


@dataclass
class _CycleStats:
    truck_id: str
    cycle_times_min: list[float] = field(default_factory=list)
    travelling_minutes: float = 0.0
    loading_minutes: float = 0.0
    dumping_minutes: float = 0.0
    queue_minutes: float = 0.0
    tonnes_delivered: float = 0.0


@dataclass
class MetricsCollector:
    scenario_id: str
    replication: int
    shift_minutes: float
    seed: int = 0
    _resources: dict[str, _ResourceStats] = field(default_factory=dict)
    _trucks: dict[str, _CycleStats] = field(default_factory=dict)
    _events: list[dict[str, Any]] = field(default_factory=list)

    def _res(self, resource_id: str) -> _ResourceStats:
        if resource_id not in self._resources:
            self._resources[resource_id] = _ResourceStats()
        return self._resources[resource_id]

    def record_resource_busy(self, resource_id: str, minutes: float) -> None:
        self._res(resource_id).busy_minutes += minutes

    def record_queue_wait(
        self,
        resource_id: str,
        queue_len_on_entry: int,
        wait_minutes: float,
    ) -> None:
        rs = self._res(resource_id)
        rs.queue_waits.append(wait_minutes)
        rs.queue_lengths_on_entry.append(queue_len_on_entry)

    def utilisation(self, resource_id: str) -> float:
        return self._res(resource_id).busy_minutes / self.shift_minutes

    def avg_queue_wait(self, resource_id: str) -> float:
        waits = self._res(resource_id).queue_waits
        return float(sum(waits) / len(waits)) if waits else 0.0

    def max_queue_length(self, resource_id: str) -> int:
        lens = self._res(resource_id).queue_lengths_on_entry
        return int(max(lens)) if lens else 0

    def resource_ids(self) -> list[str]:
        return list(self._resources.keys())

    def truck(self, truck_id: str) -> _CycleStats:
        if truck_id not in self._trucks:
            self._trucks[truck_id] = _CycleStats(truck_id=truck_id)
        return self._trucks[truck_id]

    def record_dump(self, time_min: float, truck_id: str, payload_tonnes: float) -> None:
        self.truck(truck_id).tonnes_delivered += payload_tonnes

    def total_tonnes(self) -> float:
        return float(sum(t.tonnes_delivered for t in self._trucks.values()))

    def tonnes_per_hour(self) -> float:
        hours = self.shift_minutes / 60.0
        return self.total_tonnes() / hours if hours > 0 else 0.0

    def average_cycle_time_min(self) -> float:
        all_cycles: list[float] = []
        for t in self._trucks.values():
            all_cycles.extend(t.cycle_times_min)
        return float(sum(all_cycles) / len(all_cycles)) if all_cycles else 0.0

    def average_truck_utilisation(self) -> float:
        if not self._trucks:
            return 0.0
        utilisations = []
        for t in self._trucks.values():
            busy = t.travelling_minutes + t.loading_minutes + t.dumping_minutes
            utilisations.append(busy / self.shift_minutes)
        return float(sum(utilisations) / len(utilisations))

    def log_event(
        self,
        *,
        time_min: float,
        truck_id: str,
        event_type: str,
        from_node: str | None,
        to_node: str | None,
        location: str | None,
        loaded: bool,
        payload_tonnes: float,
        resource_id: str | None,
        queue_length: int | None,
    ) -> None:
        self._events.append({
            "time_min": float(time_min),
            "replication": self.replication,
            "scenario_id": self.scenario_id,
            "truck_id": truck_id,
            "event_type": event_type,
            "from_node": from_node,
            "to_node": to_node,
            "location": location,
            "loaded": bool(loaded),
            "payload_tonnes": float(payload_tonnes),
            "resource_id": resource_id,
            "queue_length": queue_length,
        })

    def event_log_rows(self) -> list[dict[str, Any]]:
        return list(self._events)
