# Captain's Log — Synthetic Mine Throughput Simulation

## Mission outcome

**Achieved.** All seven scenarios run; 30 replications each; every required artefact (`results.csv`, `summary.json`, `event_log.csv`, `conceptual_model.md`, `README.md`, `topology.png`, `animation.gif`) is produced; `submission.yaml` is set to `status: complete`. Total wall-clock for the experiment: **1.2 s**.

## Decisions and rationale

| Decision | Rationale |
|---|---|
| **Single-session mode** (no captains, no crew) | Heavy same-file editing on one cohesive Python package; linear dependency chain (data → routing → sim → experiment → docs). Multi-agent integration friction outweighs parallelism here. `becalmed-fleet` doctrine. |
| **Skipped The Estimate** | Design choices pinned by the interview-decisions memory. No ambiguity to resolve. Auto mode further authorised this. |
| **One `simpy.Resource(capacity=1)` per directed capacity-1 edge** | Per memory; mirrors `edges.csv` exactly. Each direction is an independent resource. |
| **Lognormal travel noise (cv = 0.10)** | Per memory. Parameters chosen so the arithmetic mean equals the free-flow time. |
| **Normal-truncated load / dump samples** | Per memory; floor `max(0.1, sample)`. |
| **Dispatch rule `min(travel + queue × mean_load + own_load)`** | Per memory. Equivalent to `min(travel + (q+1) × mean_load)`. |
| **Static shortest-time Dijkstra per scenario** | Per memory. Empty and loaded weight maps both pre-computed; closures and edge overrides propagate naturally. |
| **WASTE / MAINT stripped from routing** | Per memory; out-of-scope for ore haulage. |
| **Hard cut at 480 min via `env.run(until=480)`** | Per memory. Throughput counts only `dump_end` events at t ≤ 480. |
| **Per-rep seed = `base + rep_idx`** | Per memory. Each rep gets an independent `numpy.random.default_rng`. |
| **Student-t (n-1 df) 95% CIs** | Per memory; using `scipy.stats.t.ppf`. |
| **7th scenario = `trucks_12 + ramp_upgrade`** | Per memory. Tests whether the ramp upgrade unlocks value at a higher fleet size — answer: no, the crusher remains binding. |
| **Event log scope = first 3 reps per scenario** | Keeps `event_log.csv` to ~36 k rows / 2.5 MB. All 30 reps inform `results.csv` and `summary.json`. |

## Validation evidence

- Reachability self-check enforces non-existent paths to fail loudly. Verified via a synthetic "all edges closed" scenario; output: `Reachability self-check FAILED for scenario 'broken': - truck start PARK cannot reach loader node LOAD_N - truck start PARK cannot reach...`.
- All 7 scenarios pass reachability under their actual closures.
- `results.csv` has 210 rows = 7 × 30 replications. All scenario / replication / seed columns populate cleanly.
- `summary.json` has 7 scenarios, every numeric field non-zero, every scenario has 5 ranked top bottlenecks. CIs are tight (typical CI half-width on tonnes ≈ 50–90).
- `event_log.csv` has 36,503 rows, 9 distinct event types: `dispatched`, `enter_edge`, `leave_edge`, `arrive_loader`, `load_start`, `load_end`, `arrive_crusher`, `dump_start`, `dump_end`. All required columns present.
- `topology.png` (79 KB): nodes coloured by type; capacity-1 edges in red; closed edges in dashed grey. Verified visually.
- `animation.gif` (594 KB, ~80 frames): trucks rendered as coloured markers and animated along edges. Verified visually that trucks stack at PARK at t = 0 (synchronous dispatch artefact).

## Headline results

| Question | Answer | Numerical evidence |
|---|---|---|
| Q1: baseline throughput? | ~12,500 t / shift, 1,562 t/h | mean 12,503 t (95% CI 12,416–12,590) |
| Q2: bottlenecks? | Crusher dominant; L_S secondary; **ramp NOT a bottleneck** | crusher util 91 %; ramp util 5 % |
| Q3: more trucks help? | Saturates between 8 and 12 | +64 % from 4→8 trucks; only +3 % from 8→12 |
| Q4: ramp upgrade help? | No (< 1 %) | 12,503 → 12,557 t (+0.43 %) |
| Q5: crusher slowdown sensitivity? | Near-linear; doubling time halves throughput | 12,503 → 6,530 t (-48 %) |
| Q6: lose the main ramp? | Trivial impact (~ 1 %) | 12,503 → 12,393 t (-0.9 %) |

## Interesting findings

- The "narrow ramp" framing in `edges.csv` ("intended transport bottleneck") is a **modelling decoy**. The graph has alternative haul roads from the loader pits directly to the crusher junction (`E06_FROM_NORTH`, `E12_TO_CRUSH`) which Dijkstra prefers. The ramp is touched only on the first PARK→LOAD_S dispatch and amortises to ~5 % utilisation. A simple Dijkstra is enough to surface this — no clever logic required.
- Crusher saturation drives almost all behaviour; the model is a single-server queue dressed up with road network detail. The road network's main effect is the cycle time, not the bottleneck.
- The simultaneous t = 0 dispatch produces a deterministic LOAD_S surge in the first cycle: every truck sees the same loader queue snapshot (zero) and the same expected cost. This is visible in the event log (8 simultaneous `dispatched → LOAD_S` rows at t = 0). It self-balances within one cycle.

## Open risks and follow-ups

- **No live re-routing.** Static routes will under-use alternates when capacity-1 edges queue. A future iteration could add congestion-aware Dijkstra recomputation per dispatch.
- **Capacity-1 directional resources.** If the synthetic data intends bidirectional single-lane roads, the current model under-counts contention. The memory locks this choice ("mirror CSV") and the data uses distinct `_TO_` / `_FROM_` IDs, so this is consistent — but worth flagging.
- **Crusher buffer absent.** Truck-side queueing is conservative for throughput, but a hopper would change crusher saturation dynamics.

## Mentioned in despatches

This was a single-session run. The admiral handled all tasks; no captains were spawned. Particular cleanliness:

- `interview-decisions` memory carried the design weight — every contentious question was already settled before turn one. **Acknowledged: prior planning at the analysis-elicitation stage compounded into a tight, decision-free build.**
- The `evaluate-submission` skill scaffold and the `submission.yaml` taxonomy are well-shaped for downstream automation.

## Reusable patterns logged

1. **Pin design with `bd remember`.** The interview-decisions memory removed an entire planning round. Capture decisions there *before* attempting the build.
2. **Reachability self-check at scenario load** is cheap, runs before any SimPy work, and prevents silently-wrong runs when closures sever paths.
3. **Two precomputed weight maps (empty / loaded)** cleanly separate "go pick up" from "deliver" routing without re-doing Dijkstra per leg.
4. **`env.run(until=480)` + post-hoc filter `dump_end ≤ shift_min`** is a clean idiom for hard shift cuts in SimPy; avoids per-truck termination logic.
5. **First-3-replications-only event log** balances traceability against file size — full per-rep stats live in `results.csv`.

## Mission directory contents

```
.nelson/missions/2026-05-08_181050_c12e4f30/
├── battle-plan.json
├── battle-plan.md
├── captains-log.md          ← this file
├── damage-reports/
├── fleet-status.json
├── mission-log.json
├── plan-input.json
├── quarterdeck-report.md
├── sailing-orders.json
└── turnover-briefs/
```
