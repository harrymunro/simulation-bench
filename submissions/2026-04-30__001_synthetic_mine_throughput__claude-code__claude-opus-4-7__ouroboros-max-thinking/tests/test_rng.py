"""Tests for the reproducible seed-management module.

These tests pin down the determinism contract: identical
``(base_seed, replication_index)`` pairs must yield bit-identical
random sequences regardless of process state, scenario ordering, or
how many other replications have run.
"""

from __future__ import annotations

import numpy as np
import pytest

from mine_sim.rng import (
    DEFAULT_TRUNCATION_FLOOR,
    STREAM_NAMES,
    ReplicationRNG,
    lognormal_noise_multiplier,
    make_replication_rng,
    replication_seed,
    truncated_normal,
)


# ---------------------------------------------------------------------------
# replication_seed
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_replication_seed_is_base_plus_index() -> None:
    assert replication_seed(12345, 0) == 12345
    assert replication_seed(12345, 1) == 12346
    assert replication_seed(12345, 29) == 12374


@pytest.mark.unit
@pytest.mark.parametrize("bad_index", [-1, -100])
def test_replication_seed_rejects_negative_index(bad_index: int) -> None:
    with pytest.raises(ValueError, match="replication_index"):
        replication_seed(12345, bad_index)


@pytest.mark.unit
def test_replication_seed_rejects_negative_base() -> None:
    with pytest.raises(ValueError, match="base_seed"):
        replication_seed(-1, 0)


# ---------------------------------------------------------------------------
# make_replication_rng
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_make_replication_rng_produces_all_streams() -> None:
    bundle = make_replication_rng(12345, 0)
    assert isinstance(bundle, ReplicationRNG)
    assert bundle.seed == 12345
    assert bundle.base_seed == 12345
    assert bundle.replication_index == 0
    assert bundle.stream_names == STREAM_NAMES
    for name in STREAM_NAMES:
        assert name in bundle
        assert isinstance(bundle[name], np.random.Generator)


@pytest.mark.unit
def test_streams_are_independent() -> None:
    """Drawing from one stream must not advance any other stream."""
    bundle_a = make_replication_rng(12345, 0)
    bundle_b = make_replication_rng(12345, 0)

    # Burn 100 draws on bundle_a's "loading" stream only.
    bundle_a["loading"].random(100)

    # Other streams in bundle_a must still match bundle_b's untouched ones.
    for name in STREAM_NAMES:
        if name == "loading":
            continue
        a_draws = bundle_a[name].random(5)
        b_draws = bundle_b[name].random(5)
        np.testing.assert_array_equal(a_draws, b_draws)


@pytest.mark.unit
def test_same_inputs_yield_identical_sequences() -> None:
    """The core determinism contract: same (base, idx) -> same draws."""
    bundle_first = make_replication_rng(12345, 7)
    bundle_second = make_replication_rng(12345, 7)
    for name in STREAM_NAMES:
        np.testing.assert_array_equal(
            bundle_first[name].random(50),
            bundle_second[name].random(50),
        )


@pytest.mark.unit
def test_different_replication_indices_diverge() -> None:
    """Adjacent replication indices must produce different sequences."""
    bundle_zero = make_replication_rng(12345, 0)
    bundle_one = make_replication_rng(12345, 1)
    sample_zero = bundle_zero["loading"].random(50)
    sample_one = bundle_one["loading"].random(50)
    assert not np.allclose(sample_zero, sample_one)


@pytest.mark.unit
def test_different_base_seeds_diverge() -> None:
    """Different base_random_seed values must yield different sequences."""
    bundle_a = make_replication_rng(12345, 0)
    bundle_b = make_replication_rng(99999, 0)
    sample_a = bundle_a["dumping"].random(50)
    sample_b = bundle_b["dumping"].random(50)
    assert not np.allclose(sample_a, sample_b)


@pytest.mark.unit
def test_unknown_stream_raises_keyerror() -> None:
    bundle = make_replication_rng(12345, 0)
    with pytest.raises(KeyError, match="Unknown RNG stream"):
        bundle["does_not_exist"]


@pytest.mark.unit
def test_streams_mapping_is_immutable() -> None:
    """Streams mapping must reject mutation, per project immutability rule."""
    bundle = make_replication_rng(12345, 0)
    with pytest.raises(TypeError):
        bundle.streams["new_stream"] = np.random.default_rng(0)  # type: ignore[index]


@pytest.mark.unit
def test_make_replication_rng_rejects_duplicate_stream_names() -> None:
    with pytest.raises(ValueError, match="unique"):
        make_replication_rng(12345, 0, stream_names=("a", "b", "a"))


@pytest.mark.unit
def test_make_replication_rng_rejects_empty_streams() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        make_replication_rng(12345, 0, stream_names=())


@pytest.mark.unit
def test_cross_replication_independence_for_30_reps() -> None:
    """Spot-check the standard 30-replication setup: every pair differs."""
    base = 12345
    first_draws = [
        make_replication_rng(base, idx)["loading"].random(10)
        for idx in range(30)
    ]
    for i in range(len(first_draws)):
        for j in range(i + 1, len(first_draws)):
            assert not np.array_equal(first_draws[i], first_draws[j]), (
                f"Replications {i} and {j} produced identical samples"
            )


# ---------------------------------------------------------------------------
# truncated_normal
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_truncated_normal_respects_floor() -> None:
    rng = np.random.default_rng(0)
    samples = [
        truncated_normal(rng, mean=0.05, sd=0.5, minimum=0.1)
        for _ in range(2000)
    ]
    assert min(samples) >= 0.1


@pytest.mark.unit
def test_truncated_normal_zero_sd_is_deterministic() -> None:
    rng = np.random.default_rng(0)
    assert truncated_normal(rng, mean=3.5, sd=0.0) == 3.5
    # Below the floor, should clamp.
    assert truncated_normal(rng, mean=0.0, sd=0.0) == DEFAULT_TRUNCATION_FLOOR


@pytest.mark.unit
def test_truncated_normal_is_reproducible() -> None:
    rng_a = np.random.default_rng(42)
    rng_b = np.random.default_rng(42)
    samples_a = [truncated_normal(rng_a, mean=6.5, sd=1.0) for _ in range(20)]
    samples_b = [truncated_normal(rng_b, mean=6.5, sd=1.0) for _ in range(20)]
    assert samples_a == samples_b


# ---------------------------------------------------------------------------
# lognormal_noise_multiplier
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_lognormal_multiplier_zero_cv_returns_one() -> None:
    rng = np.random.default_rng(0)
    assert lognormal_noise_multiplier(rng, cv=0.0) == 1.0


@pytest.mark.unit
def test_lognormal_multiplier_negative_cv_raises() -> None:
    rng = np.random.default_rng(0)
    with pytest.raises(ValueError, match="non-negative"):
        lognormal_noise_multiplier(rng, cv=-0.1)


@pytest.mark.unit
def test_lognormal_multiplier_has_unit_mean() -> None:
    """Empirical mean over many draws should be ~1 for cv=0.10."""
    rng = np.random.default_rng(0)
    draws = np.array(
        [lognormal_noise_multiplier(rng, cv=0.10) for _ in range(20_000)]
    )
    # Tolerance covers Monte Carlo error at n=20k for cv=0.10.
    assert abs(draws.mean() - 1.0) < 0.01
    # Coefficient of variation should be close to 0.10.
    assert abs(draws.std(ddof=1) - 0.10) < 0.005


@pytest.mark.unit
def test_lognormal_multiplier_is_strictly_positive() -> None:
    rng = np.random.default_rng(0)
    for _ in range(5000):
        assert lognormal_noise_multiplier(rng, cv=0.10) > 0.0


# ---------------------------------------------------------------------------
# Cross-cutting: scenario integration
# ---------------------------------------------------------------------------
@pytest.mark.unit
def test_scenario_replication_seed_matches_module_function() -> None:
    """ScenarioConfig.replication_seed must agree with rng.replication_seed."""
    from mine_sim.scenarios import ScenarioConfig, SimulationParams

    config = ScenarioConfig(
        scenario_id="baseline",
        simulation=SimulationParams(base_random_seed=12345),
    )
    for idx in (0, 1, 7, 29):
        assert config.replication_seed(idx) == replication_seed(12345, idx)
