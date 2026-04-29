# Reviewer Form: Synthetic Mine Throughput

**Submission:** `2026-04-25 / 001_synthetic_mine_throughput / pi-agent / gemini-3-1-pro-preview / vanilla-customtools`
**Reviewer:** Independent human reviewer (opus subagent)
**Date:** 2026-04-27

## Automated report

- Automated report file: `results/evaluation_report.json`
- Runtime seconds: not recorded (`runtime_seconds: null`); harness ran agent in 297 s per `submission.yaml`
- Python LOC: 275 code lines across `sim.py` (72) + `sim_core.py` (203)
- Required scenarios present: 6/6
- Behavioural checks passed: 53/53 (incl. `trucks_12 > trucks_4`, `crusher_slowdown < baseline`, `ramp_closed <= baseline`)
- Token usage method: declared in `submission.yaml` (78k in / 21k out), but no `token_usage.json` per protocol

## Human quality score

| Category | Max | Score | Notes |
|---|---:|---:|---|
| Conceptual modelling | 20 | 14 | `conceptual_model.md` covers all eight required headings, separates derived vs introduced assumptions, and names limits. But it is thin: only two loaders enumerated, no listing of which constrained edges (E03/E05/E07/E09) are modelled as resources, no warm-up discussion, performance-measure section under-specifies how utilisation is calculated. Adequate but lacks operational depth. |
| Data and topology handling | 15 | 12 | Reads all five CSVs and YAML; builds a `networkx.DiGraph` with edge weight `distance / (speed*1000/60)`; correctly applies `edge_overrides`, `node_overrides`, `dump_point_overrides`, and `fleet.truck_count`; respects `closed: true` by skipping the edge. Constrained edges (capacity < 999) become `simpy.Resource` (`sim_core.py` lines 70-73), which is meaningful. Minor issues: graph weights ignore the loaded/empty speed factor (acceptable since factor is uniform across edges), the routing graph uses raw `max_speed` rather than scenario-aware time, and the magic constant `999` for "unconstrained" is hardcoded. |
| Simulation correctness | 20 | 14 | Genuine SimPy DES with truck processes, loader/dump/edge resources, and `with resource.request()` blocks (`sim_core.py` lines 160, 175, 212, 227). Tonnes are correctly accumulated only on dump completion (line 242). Single-lane edges are held for the entire traversal — correct. Concerns: (i) `random.gauss` is plain Gaussian clipped at 0.1, not the truncated-normal claimed in the conceptual model; (ii) **truck `truck_active_time` is double-counted** — every `actual_time` and `actual_load`/`actual_dump` is added even though the truck is idle while waiting in queue, which is fine, but the same minutes are counted whether the truck holds an edge or queues for one (active-time accumulates only after the timeout completes, so this is OK on inspection); (iii) the dispatch policy uses `q_len * mean_load_time_min` as expected wait, which ignores the residual service time of the truck currently being loaded — minor heuristic limitation; (iv) `loader_busy_time` dict is populated but never reported. No major correctness defects, but small simplifications. |
| Experimental design | 15 | 11 | 30 replications per scenario, deterministic seed `12345 + i` (`sim.py` lines 10, 47), 6 required scenarios run. CIs computed via Student-t in `mean_ci` (line 29). Stochasticity applied to load, dump, travel times (CV 0.10). Weaknesses: warm-up explicitly set to 0 with no justification (the README claims steady-state yet startup transient is included in throughput); no additional scenarios proposed despite the prompt inviting one (`additional_scenarios_proposed: []`); narrow CIs (~0.6%) suggest the noise model may be too tame given a 100-tonne discretisation. |
| Results and interpretation | 15 | 11 | All six decision questions are addressed in `README.md` with numerical values and a clear narrative (saturation at 8 trucks, crusher as primary bottleneck, ramp upgrade and ramp closure both immaterial). The interpretation that the ramp is irrelevant because "trucks only traverse it once" is correct given the topology and shortest-time routing — verified `T01` in baseline takes PARK→J1→J2→J7→J5 (bypass) initially, then never returns to J2. However, no per-loader utilisation reported (`loader_utilisation: {}` left empty in `summary.json`), `top_bottlenecks` is mechanical (single string, threshold-based), and there is no discussion of confidence interval widths or what would *improve* throughput beyond restating the crusher constraint. |
| Code quality and reproducibility | 10 | 7 | Two-file layout (`sim.py` orchestration, `sim_core.py` model) is reasonable. README has clean run instructions (`python3 sim.py`) and pip command. Negatives: hard-coded relative paths (`'data/nodes.csv'`) require running from the submission root; literal `'CRUSH'` destination string in `sim_core.py` line 193; `simulation` dict assumed to exist on line 251; only 12 comment lines across 275 code lines (per evaluation_report); no type annotations, no tests, no `requirements.txt`/`pyproject.toml`. Adequate for a 300-line script, not exemplary. |
| Traceability and auditability | 5 | 4 | `event_log.csv` has 392k rows with the required columns (`time_min, replication, scenario_id, truck_id, event_type, from_node, to_node, location, loaded, payload_tonnes, resource_id, queue_length`). Event types include travel_start/end, queue_start, load_start/end, dump_start/end. Traced T01 across one full cycle and the route is auditable end-to-end. Minor issues: `queue_length` only logged at `queue_start` (not on each departure); `resource_id` blank on travel events; no `loader_busy_time` output, so per-loader utilisation cannot be reconstructed without re-aggregation. |
| **Total** | **100** | **73** | |

## Top 3 strengths

1. **All behavioural sanity checks pass and the numbers tell a coherent story.** baseline 12,417 t, trucks_4 8,127 t, trucks_12 12,667 t (saturation), crusher_slowdown 6,440 t, ramp_closed = baseline. The crusher_utilisation ~0.91 in baseline is consistent with the saturation conclusion.
2. **Genuine SimPy DES with constrained-edge modelling.** Single-lane edges (`capacity < 999`) become `simpy.Resource` and trucks acquire/release them via `with` blocks — not a static spreadsheet calculation.
3. **Working dispatch heuristic and event log allow audit.** The shortest-time + queue-aware loader choice is documented in the README and visible in code (`sim_core.py` lines 117-136), and the event log permits per-truck cycle reconstruction.

## Top 3 concerns or gaps

1. **Loader utilisation tracked internally but never reported** (`stats['loader_busy_time']` populated, but `loader_utilisation: {}` empty in `summary.json`). The recommended schema explicitly asks for it, and it's needed to identify whether LOAD_N or LOAD_S is the binding loader.
2. **No warm-up handling and no additional scenario proposed.** Warm-up is set to 0 with no justification despite a known startup transient (8 trucks dispatched simultaneously from PARK), and the prompt's invitation to propose one extra scenario was not taken — a missed analytic opportunity.
3. **Conceptual model and code show small inconsistencies and shortcuts.** Truncated-normal claimed, plain Gaussian + clip used; `999` used as a sentinel for unconstrained capacity; bottleneck classification is a heuristic threshold rather than a derived measure; only 12 comment lines in 275 LOC; no `requirements.txt`.

## Failure modes observed

- Poor assumption management (truncated-normal vs Gaussian-clip mismatch)
- Did not propose an additional scenario / no warm-up justification

## Final judgement

**Marginal-to-acceptable submission. Trustworthy as a first-pass decision-support artefact, partially.**

The simulation is real DES, results are internally consistent, scenarios are correctly perturbed, and the decision questions are answered with defensible numbers. However, the analysis is shallow (no per-loader utilisation, no warm-up reasoning, no proposed scenarios, terse interpretation), the code is minimally documented, and the conceptual model glosses over operational detail. **Final score: 73/100.** Useful to bracket throughput estimates and inform the conversation, but would not commission capex on the ramp purely based on this output without additional analysis on the bypass-vs-ramp routing assumption.
