# Reviewer Form: Synthetic Mine Throughput

**Submission:** `2026-04-25__001_synthetic_mine_throughput__codex-cli__gpt-5-5__xhigh`
**Reviewer:** Independent human reviewer (opus subagent)
**Date:** 2026-04-27

## Automated report

- Automated report file: `results/evaluation_report.json`
- Automated checks: 53/53 passed (100%)
- Required scenarios present: yes (all 6, 30 replications each)
- Behavioural checks passed: all 6 (trucks_12 > trucks_4, baseline > trucks_4, ramp_upgrade >= baseline, crusher_slowdown < baseline, ramp_closed <= baseline, saturation plausible)
- Python LOC: 753 code lines (1 file)
- Token usage method: not reported in evaluation_report.json (submission.yaml records 503k tokens, 400s wall time)

## Human quality score

| Category | Max | Score | Notes |
|---|---:|---:|---|
| Conceptual modelling | 20 | 17 | Clean, complete `conceptual_model.md` covering boundary, entities, resources, events, state, performance measures. Crucially **separates "Assumptions Derived From Data" from "Introduced Assumptions"** as the rubric explicitly rewards. Limitations are honest, including the insightful note that the main ramp "primarily affects startup access from parking … after trucks enter the upper network, the crusher-to-loader loop usually does not use it." Slight deduction: no explicit warm-up discussion, and entity definition is light (no operator/dispatcher entities even acknowledged as omitted). |
| Data and topology handling | 15 | 13 | `simulate.py:128-147` builds a `nx.DiGraph` from `edges.csv`, respects `closed` flags, uses `shortest_path` weighted by travel time computed from `distance_m / max_speed_kph`. Capacity-constrained edges (capacity < 999) become SimPy resources, and opposite directions of the same physical road share one resource via `physical_road_id` (`simulate.py:589`) — a thoughtful modelling choice. Scenario perturbations are applied via `apply_overrides` on copied DataFrames. Minor concern: `_build_road_resources` takes `min(capacities)` of paired-edge capacities, which is reasonable but undocumented. `_validate_routes` (line 231) actively checks reachability before run. No hard-coded answers. |
| Simulation correctness | 20 | 17 | Genuine SimPy: trucks are processes (`truck_process`), loaders/crusher/roads are `simpy.Resource` wrappers (`TrackedResource`). Cycle covers dispatch -> empty travel -> loader queue -> load -> loaded travel -> crusher queue -> dump -> redispatch (`simulate.py:487-532`). Tonnes are recorded **only when `env.now <= shift_end_min`** at dump completion (line 474), exactly per spec. Busy time is correctly clipped by the shift boundary in `add_busy_time`. Behavioural checks all pass and ordering of throughput across scenarios is sensible. Concerns: (1) cycle time is measured from `cycle_start` to dump-end, which mixes cycle phases incorrectly when a cycle straddles the shift cutoff — though they only count completed dumps. (2) `traverse_route` holds the road resource across only that edge's traversal, but the road `request` is released *while still inside the `with` block on the next yield* — actually the `with` ensures release after timeout, so OK. (3) Truck utilisation excludes resource queue waits (called "productive utilisation"); this is a defensible but non-standard definition that should be flagged more loudly. (4) `_build_loader_resources` only creates loaders for `ore_sources` — fine. |
| Experimental design | 15 | 13 | 30 replications × 6 scenarios = 180 rows (`results.csv` confirms). Seeds are `base_random_seed + replication - 1` with base 12345 (deterministic, reproducible, `simulate.py:704-705`). Reports 95% CIs using Student's t (`ci95`, line 612). Stochasticity in loading, dumping (truncated normal), and travel times (lognormal CV=0.1). Concerns: same seed sequence across scenarios means common-random-numbers is *not* explicitly applied across paired scenarios (each scenario uses independent base_seed=12345 from baseline-inherited config), so CRN is unintentional but consistent. **Warm-up is set to 0 and never discussed** — `warmup_minutes: 0` from baseline.yaml is silently inherited; the `conceptual_model.md` and `README.md` do not justify lack of warm-up despite the scoring guide explicitly asking for it. One additional scenario was *proposed* in `summary.json` but not actually run. |
| Results and interpretation | 15 | 13 | Answers all six decision questions in `README.md` with specific numbers (e.g., +5.2% from 8 to 12 trucks, -46.9% from crusher slowdown). Bottleneck identification is plausible and data-driven (`identify_bottlenecks` ranks by utilisation × queue wait; `summary.json` lists D_CRUSH, L_S, road:J6-LOAD_S as top three). The honest call-out that ramp upgrade barely helps because the haul cycle does not use the ramp post-startup is genuinely insightful. Loader-specific utilisation shows clear north/south asymmetry (L_S 0.87 vs L_N 0.45 in baseline) which the report could exploit further but at least flags. No overclaiming. Minor gap: no explicit answer to "what would improve throughput?" beyond the proposed loader_upgrade_south scenario, and the link between crusher saturation (~89%) and the 5.2% trucks_12 ceiling could be drawn more crisply. |
| Code quality and reproducibility | 10 | 7 | Single 863-line file, one comment line — well below the rubric's "many small files > few large files" preference. That said, code is well-structured with `MineSimulation` class, dataclasses for state, named helpers, and full type annotations. No hard-coded paths (uses `Path` and CLI args for `--data-dir`, `--output-dir`, `--scenarios`). Clean `requirements.txt`. README install/run instructions are clear. Deductions: monolithic file (rubric explicitly favours modular layout); the `encode_resource_id`/`decode_resource_id` round-trip with `__underscore__`/`__colon__`/`__dash__` is ugly — pandas column names with dashes would have been fine. No tests at all (rubric expects 80% coverage but is more lenient for single-shot benchmarks). |
| Traceability and auditability | 5 | 5 | `event_log.csv` has 351,381 rows across 10 distinct event types: `truck_dispatched`, `dispatch_to_loader`, `road_queue`, `road_enter`, `loader_queue`, `loading_start`, `loading_end`, `crusher_queue`, `dumping_start`, `dumping_end`. Every state transition and queue event is captured with `time_min`, `replication`, `scenario_id`, `truck_id`, `from_node`, `to_node`, `loaded`, `payload_tonnes`, `resource_id`, `queue_length`. A reviewer can fully reconstruct a single truck's path through the topology and observe queueing at any constrained resource. Excellent. |
| **Total** | **100** | **85** | |

## Top 3 strengths

1. **Faithful, complete SimPy implementation.** Truck cycles, loader/crusher/road resources, queue tracking, and post-cutoff exclusion of partial cycles are all done correctly. The shared physical road resource for opposite-direction edges is a thoughtful modelling choice that goes beyond a literal reading of the data.
2. **Excellent traceability.** The event log is comprehensive (10 event types, ~350k rows, queue lengths captured) and the bottleneck ranking in `summary.json` is derived from per-resource utilisation/queue metrics rather than asserted.
3. **Honest, evidence-led interpretation.** The agent correctly identifies that the ramp scenarios are largely cosmetic in this topology (because the haul loop bypasses the ramp), and quantifies the crusher as the dominant bottleneck — both of which match the structure of the data.

## Top 3 concerns or gaps

1. **No warm-up discussion.** The scoring guide explicitly asks for warm-up justification; `warmup_minutes: 0` is silently inherited from baseline.yaml and never addressed. With trucks starting at PARK, there is genuine startup transient (visible in `road_enter` events), so this matters.
2. **Monolithic 863-line single file.** Rubric and Python style guide prefer many small files. While the code is internally well-organised, a `model.py` / `experiment.py` / `report.py` split would be more reproducible/maintainable.
3. **Additional scenario proposed but not run.** `loader_upgrade_south` is described in `summary.json` but never actually executed. Since the prompt explicitly invites one optional scenario, running it would have strengthened the value-of-information argument substantially.

## Failure modes observed

- None of the listed failure modes apply substantively. Truck utilisation definition is non-standard (excludes queue waits) but is documented in the conceptual model.

## Final recommendation

**Strong submission.** Final score 85/100. This is a competent, traceable, defensible discrete-event simulation that would be trusted as a first-pass decision-support artefact, with the caveat that a reviewer should double-check the warm-up choice and the productive-utilisation definition before quoting numbers externally.
