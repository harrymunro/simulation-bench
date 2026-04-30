"""Reproducible random number generation for replications.

The Seed contract requires:

    All randomness reproducible from base_random_seed in scenario YAML;
    per-replication seed = base_seed + replication_index.

This module is the *single point of truth* for that rule. Everywhere the
simulation needs randomness, it asks this module for a generator. Two
runs of the same (scenario, replication_index) therefore produce
bit-identical metric outputs, regardless of which scenario ran first or
how many other replications ran in the same process.

Design notes
------------
* We use ``numpy.random.SeedSequence(seed).spawn(n)`` to derive ``n``
  *independent* child generators from the per-replication seed. Spawning
  is the recommended numpy pattern for splitting one entropy source into
  uncorrelated streams.
* Each stochastic source in the simulation gets its own named stream
  (``loading``, ``dumping``, ``edge_noise``, ``dispatch``, ``misc``).
  Independent streams mean: drawing one extra load-time sample never
  shifts the lognormal edge noise sequence, so refactors that change
  call ordering inside a stream do not invalidate other streams.
* Adding a new stream at the *end* of :data:`STREAM_NAMES` preserves
  reproducibility for existing streams. Renaming or reordering is a
  breaking change and must bump scenario seeds intentionally.

The module is deliberately small, pure-Python, and free of SimPy imports
so it can be unit-tested in isolation and reused by any future tooling
(e.g. animation, debugging utilities).
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Final, Iterable, Mapping

import numpy as np

# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------
#: Ordered tuple of stream names. Order is part of the reproducibility
#: contract: spawning relies on positional indices into the SeedSequence
#: children. Append-only changes are safe; reorder/rename are not.
STREAM_NAMES: Final[tuple[str, ...]] = (
    "loading",      # truncated-normal load times at LOAD_N / LOAD_S
    "dumping",      # truncated-normal dump times at CRUSH
    "edge_noise",   # lognormal travel-time multiplier per edge traversal
    "dispatch",     # tie-breakers / future randomized dispatching
    "misc",         # reserved for ad-hoc draws (warmup jitter, etc.)
)

#: Maximum rejection-sampling attempts for truncated normals before we
#: fall back to a final clamp. Set high enough that even tightly
#: truncated distributions terminate quickly in practice.
_TRUNCATION_MAX_ATTEMPTS: Final[int] = 64

#: Default lower bound for truncated load/dump samples, per the Seed
#: contract: ``truncated at max(0.1, sample)``.
DEFAULT_TRUNCATION_FLOOR: Final[float] = 0.1


# ---------------------------------------------------------------------------
# Seed arithmetic
# ---------------------------------------------------------------------------
def replication_seed(base_seed: int, replication_index: int) -> int:
    """Return the per-replication seed: ``base_seed + replication_index``.

    Parameters
    ----------
    base_seed:
        Non-negative integer drawn from the scenario YAML
        (``simulation.base_random_seed``).
    replication_index:
        Zero-based replication index in ``[0, replications)``.

    Raises
    ------
    ValueError
        If either argument is negative. We require non-negative inputs
        so the resulting seed is itself non-negative and stable across
        platforms (numpy's ``SeedSequence`` accepts negatives but the
        contract speaks of indices, not signed offsets).
    """
    if base_seed < 0:
        raise ValueError(f"base_seed must be >= 0, got {base_seed}")
    if replication_index < 0:
        raise ValueError(
            f"replication_index must be >= 0, got {replication_index}"
        )
    return int(base_seed) + int(replication_index)


# ---------------------------------------------------------------------------
# Per-replication RNG bundle
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReplicationRNG:
    """Immutable bundle of independent generators for one replication.

    Use :func:`make_replication_rng` to construct instances; the
    ``__init__`` signature is considered internal.

    The streams mapping is wrapped in a ``MappingProxyType`` so callers
    cannot mutate it after construction — matching the project-wide
    immutability rule.
    """

    seed: int
    base_seed: int
    replication_index: int
    streams: Mapping[str, np.random.Generator]

    def __getitem__(self, name: str) -> np.random.Generator:
        try:
            return self.streams[name]
        except KeyError as exc:
            raise KeyError(
                f"Unknown RNG stream {name!r}. "
                f"Known streams: {tuple(self.streams)}"
            ) from exc

    def __contains__(self, name: object) -> bool:
        return name in self.streams

    @property
    def stream_names(self) -> tuple[str, ...]:
        return tuple(self.streams)


def make_replication_rng(
    base_seed: int,
    replication_index: int,
    stream_names: Iterable[str] = STREAM_NAMES,
) -> ReplicationRNG:
    """Build a :class:`ReplicationRNG` for a single replication.

    The construction is deterministic: identical ``(base_seed,
    replication_index, stream_names)`` always yields generators that
    produce identical sequences.
    """
    names = tuple(stream_names)
    if not names:
        raise ValueError("stream_names must be a non-empty iterable")
    if len(set(names)) != len(names):
        raise ValueError(f"stream_names must be unique, got {names}")

    seed = replication_seed(base_seed, replication_index)
    sequence = np.random.SeedSequence(seed)
    children = sequence.spawn(len(names))
    streams = MappingProxyType(
        {
            name: np.random.default_rng(child)
            for name, child in zip(names, children, strict=True)
        }
    )
    return ReplicationRNG(
        seed=seed,
        base_seed=int(base_seed),
        replication_index=int(replication_index),
        streams=streams,
    )


# ---------------------------------------------------------------------------
# Distribution helpers
# ---------------------------------------------------------------------------
def truncated_normal(
    rng: np.random.Generator,
    mean: float,
    sd: float,
    minimum: float = DEFAULT_TRUNCATION_FLOOR,
) -> float:
    """Draw a sample from ``N(mean, sd)`` truncated below at ``minimum``.

    The Seed contract phrases the rule as ``truncated at max(0.1,
    sample)``. We interpret this as rejection sampling against the
    half-line ``[minimum, +inf)``: a draw below ``minimum`` is rejected
    and re-drawn so the conditional distribution matches the truncated
    normal density. After :data:`_TRUNCATION_MAX_ATTEMPTS` rejections we
    fall back to a clamp; in practice this only triggers for pathological
    parameter combinations far outside our scenario space.

    Edge cases
    ----------
    * ``sd <= 0`` returns ``max(minimum, mean)`` deterministically.
    * Negative ``mean`` is allowed; truncation handles it.
    """
    if sd <= 0:
        return max(float(minimum), float(mean))

    for _ in range(_TRUNCATION_MAX_ATTEMPTS):
        sample = float(rng.normal(loc=mean, scale=sd))
        if sample >= minimum:
            return sample
    # Fallback — preserves determinism (one extra draw on the same RNG)
    # without infinite looping. Documented above.
    return max(float(minimum), float(rng.normal(loc=mean, scale=sd)))


def lognormal_noise_multiplier(
    rng: np.random.Generator,
    cv: float,
) -> float:
    """Return a lognormal multiplier with mean 1 and coefficient of variation ``cv``.

    For ``X = exp(N(mu, sigma))`` we want ``E[X] = 1`` and
    ``Var[X] / E[X]^2 = cv^2``. Solving yields::

        sigma^2 = ln(1 + cv^2)
        mu      = -sigma^2 / 2

    A ``cv`` of zero degenerates to a deterministic multiplier of 1.0
    (no noise), which we short-circuit so we never consume an RNG draw
    on a no-op — keeping seed alignment intuitive when noise is disabled.
    """
    if cv < 0:
        raise ValueError(f"cv must be non-negative, got {cv}")
    if cv == 0:
        return 1.0
    sigma_sq = float(np.log1p(cv * cv))
    sigma = float(np.sqrt(sigma_sq))
    mu = -0.5 * sigma_sq
    return float(np.exp(rng.normal(loc=mu, scale=sigma)))


__all__ = [
    "DEFAULT_TRUNCATION_FLOOR",
    "ReplicationRNG",
    "STREAM_NAMES",
    "lognormal_noise_multiplier",
    "make_replication_rng",
    "replication_seed",
    "truncated_normal",
]
