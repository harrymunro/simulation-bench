from __future__ import annotations

# Lightweight copy of the expected summary structure.
# This file exists so runners can import expected keys without reading JSON schema.

REQUIRED_SCENARIOS = [
    "baseline",
    "trucks_4",
    "trucks_12",
    "ramp_upgrade",
    "crusher_slowdown",
    "ramp_closed",
]

REQUIRED_SCENARIO_METRICS = [
    "replications",
    "shift_length_hours",
    "total_tonnes_mean",
    "tonnes_per_hour_mean",
]

