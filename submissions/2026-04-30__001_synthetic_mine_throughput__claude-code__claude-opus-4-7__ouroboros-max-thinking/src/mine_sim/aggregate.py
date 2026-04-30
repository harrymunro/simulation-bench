"""Cross-replication KPI aggregation with Student-t 95% confidence intervals.

This is the "horizontal" counterpart to :mod:`mine_sim.metrics`. Where
``metrics`` produces one frozen :class:`~mine_sim.metrics.ReplicationMetrics`
per shift, this module collapses a list of such records into a single
:class:`ScenarioSummary` carrying the mean and Student-t n-1 95% CI for
every KPI the Seed asks us to report.

Design contracts (Seed-derived):

* Confidence intervals are computed as ``mean ± t_{n-1, 0.975} * s / sqrt(n)``
  using Student's t distribution (:func:`scipy.stats.t.ppf`). For
  degenerate cases (n < 2 or sample variance == 0) the half-width
  collapses to zero — both bounds equal the mean — rather than NaN, so
  downstream JSON serialisation remains numeric.
* ``top_bottlenecks`` is ranked by ``mean(utilisation) * mean(queue_wait)``
  across replications, the "composite bottleneck score" decided in the
  pre-implementation interview. Loaders, the crusher, and every
  capacity-1 edge participate in the same ranking.
* All return types are immutable (frozen dataclasses + ``MappingProxyType``)
  so a summary is safe to share across writers (CSV, JSON, README
  rendering) without anyone accidentally mutating a value mid-write.
* No I/O lives in this module — that is the next sub-AC's job. Callers
  hand in already-loaded :class:`ReplicationMetrics` records and get a
  pure-Python dataclass back.

The public surface is intentionally small:

* :func:`student_t_ci_95` — given any sequence of floats, returns a
  :class:`StatSummary(mean, ci_low, ci_high, std, n)`. Used by the
  scenario aggregator and re-exported for downstream tooling.
* :func:`aggregate_scenario` — takes a sequence of
  :class:`ReplicationMetrics` (all from the same scenario), returns a
  :class:`ScenarioSummary`.
* :func:`aggregate_run` — takes a :class:`MultiScenarioRunResult` (or a
  mapping of scenario_id -> reps) and returns a :class:`RunSummary`
  carrying one :class:`ScenarioSummary` per scenario.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Iterable, Mapping, Sequence

from scipy import stats  # type: ignore[import-untyped]

from mine_sim.metrics import ReplicationMetrics
from mine_sim.runner import ReplicationResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
#: Two-sided 95% confidence level — the number repeated in the Seed.
DEFAULT_CONFIDENCE_LEVEL: float = 0.95


# ---------------------------------------------------------------------------
# Statistical primitives
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class StatSummary:
    """Mean + Student-t CI bundle for a single KPI series.

    All four numeric fields are guaranteed finite: degenerate cases (n<2
    or zero variance) yield ``ci_low == ci_high == mean`` rather than
    NaN.

    Fields are deliberately ordered so the JSON dump reads naturally:
    ``mean`` first, then the bounds, then the supporting stats.
    """

    mean: float
    ci95_low: float
    ci95_high: float
    std: float
    n: int

    @property
    def half_width(self) -> float:
        """Half the CI width (``ci95_high - mean``)."""
        return self.ci95_high - self.mean


def _sample_std(values: Sequence[float]) -> float:
    """Sample standard deviation with n-1 degrees of freedom.

    Avoids ``numpy`` so this module's scientific dependency surface stays
    at ``scipy.stats`` only.
    """
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    sse = sum((v - mean) ** 2 for v in values)
    return math.sqrt(sse / (n - 1))


def student_t_ci_95(
    values: Sequence[float],
    *,
    confidence: float = DEFAULT_CONFIDENCE_LEVEL,
) -> StatSummary:
    """Return mean and Student-t (n-1) two-sided CI for ``values``.

    Parameters
    ----------
    values:
        Iterable of finite floats — typically one entry per replication.
    confidence:
        Two-sided confidence level (default 0.95).

    Notes
    -----
    * For n == 0 we return an all-zero summary so downstream JSON does
      not contain ``NaN``. Callers that care can inspect ``n == 0``.
    * For n == 1 or zero sample variance the half-width is zero by
      definition; the function returns ``mean ± 0``.
    * The critical value uses :func:`scipy.stats.t.ppf` so the result
      matches every standard simulation textbook within float precision.
    """
    if not 0.0 < confidence < 1.0:
        raise ValueError(
            f"confidence must be strictly between 0 and 1, got {confidence}"
        )
    n = len(values)
    if n == 0:
        return StatSummary(mean=0.0, ci95_low=0.0, ci95_high=0.0, std=0.0, n=0)

    mean = sum(values) / n
    if n < 2:
        return StatSummary(mean=mean, ci95_low=mean, ci95_high=mean, std=0.0, n=n)

    std = _sample_std(values)
    if std == 0.0:
        return StatSummary(mean=mean, ci95_low=mean, ci95_high=mean, std=0.0, n=n)

    alpha = 1.0 - confidence
    t_crit = float(stats.t.ppf(1.0 - alpha / 2.0, df=n - 1))
    half_width = t_crit * std / math.sqrt(n)
    return StatSummary(
        mean=mean,
        ci95_low=mean - half_width,
        ci95_high=mean + half_width,
        std=std,
        n=n,
    )


# ---------------------------------------------------------------------------
# Bottleneck ranking
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class BottleneckEntry:
    """One row of the ``top_bottlenecks`` ranking.

    The composite score is ``utilisation_mean * mean_queue_wait_min`` —
    the same definition recorded in the design memory.
    """

    resource_id: str
    resource_kind: str  # "loader" | "crusher" | "edge"
    utilisation_mean: float
    mean_queue_wait_min: float
    composite_score: float


# ---------------------------------------------------------------------------
# Per-resource summary records
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class LoaderSummary:
    """Aggregated KPIs for a single loader across replications."""

    loader_id: str
    utilisation: StatSummary
    mean_queue_wait_min: StatSummary
    services_completed: StatSummary


@dataclass(frozen=True)
class CrusherSummary:
    """Aggregated KPIs for the crusher across replications."""

    dump_id: str
    utilisation: StatSummary
    mean_queue_wait_min: StatSummary
    services_completed: StatSummary


@dataclass(frozen=True)
class EdgeSummary:
    """Aggregated KPIs for one capacity-1 edge across replications."""

    edge_id: str
    utilisation: StatSummary
    mean_queue_wait_min: StatSummary
    mean_traversal_time_min: StatSummary
    traversal_count: StatSummary


# ---------------------------------------------------------------------------
# Top-level scenario summary
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ScenarioSummary:
    """Cross-replication KPI summary for one scenario.

    The exact field set is dictated by the Seed AC for ``summary.json``:
    means and Student-t 95% CIs for the headline throughput KPIs, plus
    per-resource utilisation / queue-wait, plus a composite bottleneck
    ranking. Narrative fields (``key_assumptions``, ``model_limitations``,
    ``additional_scenarios_proposed``) are *not* this module's concern —
    they are loaded from disk by the writer.
    """

    scenario_id: str
    replications: int
    shift_length_hours: float

    total_tonnes_delivered: StatSummary
    tonnes_per_hour: StatSummary
    average_truck_cycle_time_min: StatSummary
    average_truck_utilisation: StatSummary
    crusher_utilisation: StatSummary
    average_loader_queue_time_min: StatSummary
    average_crusher_queue_time_min: StatSummary

    loaders: Mapping[str, LoaderSummary]
    crusher: CrusherSummary
    edges: Mapping[str, EdgeSummary]

    top_bottlenecks: tuple[BottleneckEntry, ...]


@dataclass(frozen=True)
class RunSummary:
    """A flat collection of :class:`ScenarioSummary` keyed by scenario_id.

    Iteration order matches the order the scenarios were aggregated
    (which itself matches the run order downstream of
    :func:`mine_sim.scenario_runner.run_all_scenarios`), so JSON dumps
    are deterministic.
    """

    scenarios: Mapping[str, ScenarioSummary]

    @property
    def scenario_ids(self) -> tuple[str, ...]:
        return tuple(self.scenarios.keys())


# ---------------------------------------------------------------------------
# Aggregation helpers
# ---------------------------------------------------------------------------
def _coerce_metrics(
    reps: Sequence[ReplicationMetrics] | Sequence[ReplicationResult],
) -> tuple[ReplicationMetrics, ...]:
    """Accept either ``ReplicationMetrics`` directly or ``ReplicationResult``."""
    out: list[ReplicationMetrics] = []
    for rep in reps:
        if isinstance(rep, ReplicationMetrics):
            out.append(rep)
        elif hasattr(rep, "metrics") and isinstance(rep.metrics, ReplicationMetrics):
            out.append(rep.metrics)
        else:
            raise TypeError(
                "Aggregation expected ReplicationMetrics or ReplicationResult, "
                f"got {type(rep).__name__}"
            )
    return tuple(out)


def _series(values: Iterable[float]) -> StatSummary:
    """Convenience wrapper: build a :class:`StatSummary` from an iterable."""
    return student_t_ci_95(tuple(float(v) for v in values))


def _validate_homogeneous_scenario(reps: Sequence[ReplicationMetrics]) -> str:
    if not reps:
        raise ValueError("Cannot aggregate an empty replication sequence.")
    scenario_ids = {rep.scenario_id for rep in reps}
    if len(scenario_ids) != 1:
        raise ValueError(
            "All replications passed to aggregate_scenario must share the "
            f"same scenario_id; got {sorted(scenario_ids)}"
        )
    return next(iter(scenario_ids))


def _resource_id_universe(
    reps: Sequence[ReplicationMetrics],
    attr: str,
) -> tuple[str, ...]:
    """Stable sorted union of resource IDs seen across replications.

    Different scenarios can have different fleet sizes / edge sets, but
    *within* one scenario every replication should expose the same
    resource ids. We still take the union (not the intersection) so a
    single missing edge does not silently drop a row.
    """
    ids: set[str] = set()
    for rep in reps:
        ids.update(getattr(rep, attr).keys())
    return tuple(sorted(ids))


def _loader_series(
    reps: Sequence[ReplicationMetrics],
    loader_id: str,
    extractor,
) -> StatSummary:
    return _series(extractor(rep.loaders[loader_id]) for rep in reps if loader_id in rep.loaders)


def _edge_series(
    reps: Sequence[ReplicationMetrics],
    edge_id: str,
    extractor,
) -> StatSummary:
    return _series(extractor(rep.edges[edge_id]) for rep in reps if edge_id in rep.edges)


# ---------------------------------------------------------------------------
# Public aggregation API
# ---------------------------------------------------------------------------
def aggregate_scenario(
    replications: Sequence[ReplicationMetrics] | Sequence[ReplicationResult],
    *,
    top_bottleneck_count: int = 5,
) -> ScenarioSummary:
    """Aggregate a single scenario's replications into a :class:`ScenarioSummary`.

    Parameters
    ----------
    replications:
        Sequence of :class:`ReplicationMetrics` or
        :class:`ReplicationResult` records, all sharing the same
        ``scenario_id``. Order is preserved but not semantically
        meaningful — every aggregation is symmetric in the sample.
    top_bottleneck_count:
        How many entries to include in ``top_bottlenecks``. Defaults to
        5 (the table the README renders); increase for diagnostics.

    Raises
    ------
    ValueError:
        If the sequence is empty or contains records from multiple
        scenarios. Failing loudly here prevents silent mis-aggregation.
    """
    reps = _coerce_metrics(replications)
    scenario_id = _validate_homogeneous_scenario(reps)

    shift_length_hours = reps[0].shift_length_min / 60.0

    # ----- Headline throughput KPIs -----------------------------------------
    total_tonnes = _series(rep.total_tonnes_delivered for rep in reps)
    tph = _series(rep.tonnes_per_hour for rep in reps)
    cycle_time = _series(rep.average_truck_cycle_time_min for rep in reps)
    truck_util = _series(rep.average_truck_utilisation for rep in reps)
    crusher_util = _series(rep.crusher.utilisation for rep in reps)
    loader_queue = _series(rep.average_loader_queue_time_min for rep in reps)
    crusher_queue = _series(rep.average_crusher_queue_time_min for rep in reps)

    # ----- Per-loader summaries ---------------------------------------------
    loader_ids = _resource_id_universe(reps, "loaders")
    loader_summaries: dict[str, LoaderSummary] = {}
    for loader_id in loader_ids:
        loader_summaries[loader_id] = LoaderSummary(
            loader_id=loader_id,
            utilisation=_loader_series(reps, loader_id, lambda lm: lm.utilisation),
            mean_queue_wait_min=_loader_series(
                reps, loader_id, lambda lm: lm.mean_queue_wait_min
            ),
            services_completed=_loader_series(
                reps, loader_id, lambda lm: lm.services_completed
            ),
        )

    # ----- Crusher summary --------------------------------------------------
    crusher_id = reps[0].crusher.dump_id
    crusher_summary = CrusherSummary(
        dump_id=crusher_id,
        utilisation=crusher_util,
        mean_queue_wait_min=crusher_queue,
        services_completed=_series(rep.crusher.services_completed for rep in reps),
    )

    # ----- Per-edge summaries -----------------------------------------------
    edge_ids = _resource_id_universe(reps, "edges")
    edge_summaries: dict[str, EdgeSummary] = {}
    for edge_id in edge_ids:
        edge_summaries[edge_id] = EdgeSummary(
            edge_id=edge_id,
            utilisation=_edge_series(reps, edge_id, lambda em: em.utilisation),
            mean_queue_wait_min=_edge_series(
                reps, edge_id, lambda em: em.mean_queue_wait_min
            ),
            mean_traversal_time_min=_edge_series(
                reps, edge_id, lambda em: em.mean_traversal_time_min
            ),
            traversal_count=_edge_series(
                reps, edge_id, lambda em: em.traversal_count
            ),
        )

    # ----- Bottleneck ranking ----------------------------------------------
    bottleneck_entries: list[BottleneckEntry] = []
    for loader_id, summary in loader_summaries.items():
        util = summary.utilisation.mean
        wait = summary.mean_queue_wait_min.mean
        bottleneck_entries.append(
            BottleneckEntry(
                resource_id=loader_id,
                resource_kind="loader",
                utilisation_mean=util,
                mean_queue_wait_min=wait,
                composite_score=util * wait,
            )
        )
    bottleneck_entries.append(
        BottleneckEntry(
            resource_id=crusher_id,
            resource_kind="crusher",
            utilisation_mean=crusher_summary.utilisation.mean,
            mean_queue_wait_min=crusher_summary.mean_queue_wait_min.mean,
            composite_score=(
                crusher_summary.utilisation.mean
                * crusher_summary.mean_queue_wait_min.mean
            ),
        )
    )
    for edge_id, summary in edge_summaries.items():
        util = summary.utilisation.mean
        wait = summary.mean_queue_wait_min.mean
        bottleneck_entries.append(
            BottleneckEntry(
                resource_id=edge_id,
                resource_kind="edge",
                utilisation_mean=util,
                mean_queue_wait_min=wait,
                composite_score=util * wait,
            )
        )
    # Sort: primary key composite_score desc, secondary util desc, then id asc
    # for a fully deterministic order (no Python "best effort" tie behaviour).
    bottleneck_entries.sort(
        key=lambda b: (-b.composite_score, -b.utilisation_mean, b.resource_id)
    )
    top_bottlenecks = tuple(bottleneck_entries[: max(0, int(top_bottleneck_count))])

    return ScenarioSummary(
        scenario_id=scenario_id,
        replications=len(reps),
        shift_length_hours=shift_length_hours,
        total_tonnes_delivered=total_tonnes,
        tonnes_per_hour=tph,
        average_truck_cycle_time_min=cycle_time,
        average_truck_utilisation=truck_util,
        crusher_utilisation=crusher_util,
        average_loader_queue_time_min=loader_queue,
        average_crusher_queue_time_min=crusher_queue,
        loaders=MappingProxyType(loader_summaries),
        crusher=crusher_summary,
        edges=MappingProxyType(edge_summaries),
        top_bottlenecks=top_bottlenecks,
    )


def aggregate_run(
    run: Mapping[str, Sequence[ReplicationMetrics] | Sequence[ReplicationResult]],
    *,
    top_bottleneck_count: int = 5,
) -> RunSummary:
    """Aggregate a multi-scenario run into a :class:`RunSummary`.

    Parameters
    ----------
    run:
        Mapping ``scenario_id -> Sequence[ReplicationMetrics|Result]``.
        The natural source is
        ``{sid: r.replications for sid, r in multi.results.items()}``
        from a :class:`MultiScenarioRunResult`. A small adapter
        (:func:`from_multi_scenario_result`) is provided for that case.
    """
    summaries: dict[str, ScenarioSummary] = {}
    for scenario_id, reps in run.items():
        summary = aggregate_scenario(
            reps, top_bottleneck_count=top_bottleneck_count
        )
        if summary.scenario_id != scenario_id:
            raise ValueError(
                f"Scenario id mismatch: key '{scenario_id}' vs metrics "
                f"'{summary.scenario_id}'. Refusing to mis-key the summary."
            )
        summaries[scenario_id] = summary
    return RunSummary(scenarios=MappingProxyType(summaries))


def from_multi_scenario_result(multi) -> RunSummary:  # pragma: no cover - adapter
    """Tiny adapter so callers don't have to inline the dict comprehension.

    Accepts a :class:`mine_sim.scenario_runner.MultiScenarioRunResult` and
    returns the corresponding :class:`RunSummary`. Imported lazily to
    keep this module's import graph minimal.
    """
    return aggregate_run(
        {sid: r.replications for sid, r in multi.results.items()}
    )


__all__ = [
    "BottleneckEntry",
    "CrusherSummary",
    "DEFAULT_CONFIDENCE_LEVEL",
    "EdgeSummary",
    "LoaderSummary",
    "RunSummary",
    "ScenarioSummary",
    "StatSummary",
    "aggregate_run",
    "aggregate_scenario",
    "from_multi_scenario_result",
    "student_t_ci_95",
]
