"""Analytical bound cross-validation:
   simulated baseline tonnes/h must lie within [0.80, 1.00] of the binding bound."""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"


# Crusher-bound: 100 t / 3.5 min × 60 = 1714.286 t/h
CRUSHER_BOUND_TPH = 100.0 / 3.5 * 60.0
CRUSHER_BOUND_TPH_SLOWDOWN = 100.0 / 7.0 * 60.0  # 857.14


def _summary():
    with open(OUT / "summary.json", "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_baseline_within_analytical_envelope():
    s = _summary()["scenarios"]["baseline"]
    mean_tph = s["tonnes_per_hour"]["mean"]
    ratio = mean_tph / CRUSHER_BOUND_TPH
    assert 0.80 <= ratio <= 1.00, f"baseline ratio {ratio:.3f} outside [0.80, 1.00]"


def test_trucks_12_saturates_crusher():
    s = _summary()["scenarios"]["trucks_12"]
    mean_tph = s["tonnes_per_hour"]["mean"]
    ratio = mean_tph / CRUSHER_BOUND_TPH
    assert 0.90 <= ratio <= 1.00, f"trucks_12 ratio {ratio:.3f} should saturate crusher"


def test_crusher_slowdown_uses_new_bound():
    s = _summary()["scenarios"]["crusher_slowdown"]
    mean_tph = s["tonnes_per_hour"]["mean"]
    ratio = mean_tph / CRUSHER_BOUND_TPH_SLOWDOWN
    assert 0.80 <= ratio <= 1.00, f"crusher_slowdown ratio {ratio:.3f} outside [0.80, 1.00]"


def test_trucks_4_below_baseline():
    s = _summary()["scenarios"]
    assert s["trucks_4"]["tonnes_per_hour"]["mean"] < s["baseline"]["tonnes_per_hour"]["mean"]
