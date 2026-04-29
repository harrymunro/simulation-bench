# Reviewer Form: Synthetic Mine Throughput

**Submission:** `2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__max-thinking`
**Decoded:** Date 2026-04-25 | Benchmark 001 mine throughput | Harness Claude Code | Model Claude Opus 4.7 (max thinking)
**Reviewer:** Independent human reviewer (opus subagent)
**Date:** 2026-04-27

## Automated report

- Report file: `results/evaluation_report.json`
- Automated checks: 57/57 passed (100%)
- Behavioural sanity checks: all six passed (fleet ordering, ramp upgrade, crusher slowdown, ramp closed, saturation)
- Required scenarios present: yes (six required + extra `trucks_10`)
- Python LOC: 1,360 total / 1,128 code, 7 files
- Runtime, return code, token usage: not captured by harness (`null`); `submission.yaml` reports `time_s: 699` and `tokens: 116900`

## Human quality score

| Category | Max | Score | Notes |
|---|---:|---:|---|
| Conceptual modelling | 20 | 18 | `conceptual_model.md` is well-organised: explicit boundary (PARK→loader→CRUSH cycle, MAINT/WASTE excluded), entities, resources with parameters, event taxonomy, state vars, separation of *data-derived* vs *modeller-introduced* assumptions, performance measures, and limitations. The lane-merging heuristic (prefix before first underscore) is explicit and justified. Deductions: assumption that `E05_TO/FROM_CRUSH` are the same physical lane is asserted by analogy from the `E03_UP/DOWN` metadata note rather than verified — could materially affect crusher-side queueing. Otherwise excellent. |
| Data and topology handling | 15 | 14 | All five CSVs and YAML scenarios are read; `topology.py` builds a NetworkX `DiGraph` with nominal travel times computed from `distance_m`, `max_speed_kph`, and truck speed factors. Constrained edges (`capacity<999`) become SimPy `Resource`s with min-of-shared-prefix capacity; `closed=true` edges are dropped from the graph before routing, with a clear `RuntimeError` on no path (`topology.py:240`). Scenario edge/node/loader/dump overrides flow through `apply_*_overrides` helpers. The implementation is principled and reactive to perturbations. Minor deduction: lane grouping by prefix is heuristic — `E12_TO_CRUSH` and `E12_FROM_CRUSH` are both `capacity=999` so unaffected, but the rule could collide on a different topology. |
| Simulation correctness | 20 | 18 | Genuine SimPy DES: trucks are processes, loaders/crusher/lanes are `simpy.Resource`s, queue/request/release pattern is correct (`simulation.py:359-383, 398-422`). Loaded vs empty travel uses correct speed factors; lane resources are requested per-segment with proper release. Tonnes counted only on completed `dump_end` (`simulation.py:425-430`), matching the rubric. Loading/dumping use truncated normals; travel multiplied by lognormal noise (CV 0.10). Deductions: `_record_resource_busy` is dead code (defined but never used) — utilisation is computed via inline `t_start`/`env.now` accumulation, which is correct for capacity-1 resources but would mis-account for capacity>1 (the lane resources work because `min` capacity is taken across shared prefixes; harmless here). Trucks all start at PARK and on the first cycle are routed to the *same* loader (the event log shows all 8 trucks routed to LOAD_S at t=0) — the dispatcher picks the loader with shortest expected cycle time but does not consider already-dispatched trucks, so the initial dispatch is a "thundering herd". This is a legitimate modelling choice, not a bug, but worth noting. |
| Experimental design | 15 | 14 | 30 replications per scenario (210 across 7 scenarios) with reproducible seeds (`base_random_seed=12345 + replication_index`). 95% CIs computed via t-distribution in `experiment.py:19-31`. Stochasticity is sensible (truncated normal service, lognormal travel). Required six scenarios all run; one optional `trucks_10` proposed (saturation interpolation) — well-motivated. Deductions: README explicitly states "no warm-up" choice but does not justify it in detail; trucks dispatching simultaneously at t=0 from PARK introduces a transient ramp-up that's included in the 8-hour aggregate. Common random numbers are not used across scenarios (each scenario uses its own seed sequence starting at the same base), so paired comparisons across scenarios have less power than they could. Otherwise solid. |
| Results and interpretation | 15 | 14 | All six decision questions answered with quantitative backing and CIs (README §7). Bottlenecks correctly identified (crusher 88% utilisation under baseline, lanes E05/E09 next; tabulated per scenario in §8). Saturation analysis from 4→8→10→12 trucks is clean (+60%, +6%, <0.5%). The ramp upgrade null-result is well-explained mechanically (steady-state cycles bypass E03 via J3→J4) — this is genuine insight, not hand-waving. The ramp_closed finding (~0.8% drop) is consistent with the bypass topology. Crusher slowdown answer notes inverse proportionality for a saturated single-server, which is technically correct. Good improvement suggestions in §10 (feed-bin upgrade, MTBF/MTTR, surge stockpile, mixed fleet). Slight deduction: no explicit acknowledgement that the very tight CIs (≈±0.5% on 12 053 t baseline) reflect modelling determinism, not real-world uncertainty. |
| Code quality and reproducibility | 10 | 9 | Clean module split: `topology.py` (graph + routing), `simulation.py` (DES core), `experiment.py` (multi-rep + aggregation + writers), `scenario.py` (YAML inheritance), `run.py` (CLI). Type annotations throughout; immutable `@dataclass(frozen=True)` for `NodeRecord`/`EdgeRecord`. `requirements.txt` lists pinned-by-floor versions. CLI provides `--scenarios`, `--extras`, `--data-dir`, `--out-dir`. Paths are relative (no hard-coded local paths). Deductions: 32 comment lines across 1,128 LOC is light; dead `_record_resource_busy` method should have been removed; no automated tests; README §2 has a slightly misleading line `python3 -m src.experiment   # not a CLI; use run.py instead`. |
| Traceability and auditability | 5 | 5 | `event_log.csv` has all required columns plus `from_node`/`to_node`/`location`/`loaded`/`payload_tonnes`/`resource_id`/`queue_length` (≈18 k rows covering all 7 scenarios, replication 0). Event taxonomy spans dispatch → routing → enter/exit edge → arrive/queue loader → load_start/end → arrive/queue crusher → dump_start/end → shift_end. Truck movements are auditable edge-by-edge; queue lengths recorded at request points; 753 `dump_end` events match aggregate cycles (cycles_completed_mean 120.5 × ~6 scenarios with capture). `topology.png` is generated programmatically from the data via `plot_topology.py`. Full marks. |
| **Total** | **100** | **92** |  |

## Strengths

1. **Genuine, well-engineered SimPy DES** with correct queueing, lane resources, truncated/lognormal stochastics, seed control, and a clean module separation that any reviewer can follow.
2. **Mechanistic interpretation of results** — the explanation of why the ramp upgrade is a null result (steady-state cycles bypass E03) demonstrates the agent actually understood the topology rather than parroting numbers.
3. **Strong assumption hygiene**: `conceptual_model.md` explicitly separates data-derived from modeller-introduced assumptions, and the limitations list is honest (no breakdowns, no congestion on open roads, no dynamic rerouting).

## Concerns / gaps

1. **Lane-grouping heuristic is asserted, not validated** — only `E03_UP/DOWN` has explicit metadata calling it out as one physical lane; applying the same prefix rule to E05/E07/E09 is reasonable but unverified, and tightens the crusher-side bottleneck (E05 at 74% utilisation). A sensitivity check would have closed this gap.
2. **Initial-dispatch artefact**: at t=0 all trucks route to LOAD_S simultaneously; this transient is included in the 8-hour aggregate without warm-up exclusion. Material? Probably small at 8 trucks but unquantified.
3. **Dead code and minor polish**: `_record_resource_busy` is unused; comment density is low; no unit tests despite the modular structure inviting them.

## Failure modes observed

None of the standard failure modes apply. Behavioural checks all pass; conceptual model is present; SimPy is used genuinely; CIs and seeds are present; event log is rich; decision questions are answered.

## Final judgement

**Strong submission.** Would I trust this as a first-pass decision-support artefact? **Yes**, with the caveat that the lane-grouping assumption should be confirmed with the data owner before acting on the "ramp upgrade is not worth it" recommendation, and the absolute tonnage figures be treated as a theoretical upper bound (as the README itself flags). Final score **92/100**.
