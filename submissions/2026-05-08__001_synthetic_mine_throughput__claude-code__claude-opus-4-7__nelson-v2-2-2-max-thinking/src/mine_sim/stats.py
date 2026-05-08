"""Aggregation and Student-t 95% confidence interval helpers."""

from __future__ import annotations

import math
from typing import Iterable, List, Tuple

from scipy import stats as sstats


def mean_ci(values: Iterable[float], confidence: float = 0.95) -> Tuple[float, float, float]:
    """Return ``(mean, ci95_low, ci95_high)`` using Student-t with ``n-1`` df.

    For ``n <= 1`` the half-width is undefined; we return ``(mean, mean, mean)``
    so downstream consumers don't hit NaNs.
    """
    vals = list(values)
    n = len(vals)
    if n == 0:
        return (0.0, 0.0, 0.0)
    mean = sum(vals) / n
    if n == 1:
        return (mean, mean, mean)
    sd = math.sqrt(sum((v - mean) ** 2 for v in vals) / (n - 1))
    t_crit = float(sstats.t.ppf(0.5 + confidence / 2.0, df=n - 1))
    half = t_crit * sd / math.sqrt(n)
    return (mean, mean - half, mean + half)


def busy_minutes(intervals: Iterable[Tuple[float, float]], shift_min: float) -> float:
    """Sum of clamped busy intervals within ``[0, shift_min]``."""
    total = 0.0
    for s, e in intervals:
        s_c = max(0.0, s)
        e_c = min(shift_min, e)
        if e_c > s_c:
            total += e_c - s_c
    return total


def utilisation(intervals: Iterable[Tuple[float, float]], shift_min: float) -> float:
    """Fraction of shift the resource was busy, in [0, 1]."""
    if shift_min <= 0:
        return 0.0
    return min(1.0, busy_minutes(intervals, shift_min) / shift_min)


def mean_or_zero(values: Iterable[float]) -> float:
    vals = list(values)
    if not vals:
        return 0.0
    return sum(vals) / len(vals)
