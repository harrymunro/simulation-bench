# Synthetic Mine Throughput — SimPy Discrete-Event Simulation

A reproducible discrete-event simulation of an open-pit mine ore-haulage system,
built on SimPy. Estimates ore throughput to the primary crusher across six
scenarios over 30 replications each, and answers six operational decision
questions.

## 1. Install dependencies

Tested on Python 3.13.

```bash
pip install -r requirements.txt
```

Required packages: `simpy`, `numpy`, `pandas`, `scipy`, `networkx`, `pyyaml`,
`matplotlib`, `pytest`.

## 2. Run the simulation

From the `code/` directory:

```bash
# default — 6 scenarios × 30 replications, reads from .ShipofTheseus/_input/synthetic_mine_throughput_001/data
python run_experiment.py

# subset of scenarios
python run_experiment.py --scenarios baseline,ramp_closed

# fewer replications (for fast smoke tests)
python run_experiment.py --replications 3

# explicit data and output dirs
python run_experiment.py \
    --data-dir /path/to/data \
    --out-dir  /path/to/outputs
```

Outputs are written to `outputs/`:

- `outputs/results.csv` — one row per (scenario, replication) (180 rows)
- `outputs/summary.json` — per-scenario aggregates with 95 % CI Student-t
- `outputs/event_log.csv` — per-event truck trace (≈ 285 000 rows)

End-to-end runtime on a developer laptop: **< 5 seconds** for the full 6 × 30 sweep.

## 3. Reproduce

The reference run uses `base_random_seed = 12345` (from `baseline.yaml`). Per-(
scenario, replication) seed is `12345 + 1000 × scenario_index + replication_index`,
so any scenario/replication can be re-run independently and reproduce bit-for-bit.

```bash
python -m pytest tests/ -q
```

All four test files (`test_topology.py`, `test_conservation.py`, `test_repro.py`,
`test_analytical.py`) must pass before the model is considered ready.

## 4. Conceptual model

See `conceptual_model.md` for the full system boundary, entities, resources,
events, state variables, assumptions, and performance measures.

In short:

- Trucks are SimPy generator processes; loaders, crusher, and capacity-1 road
  segments are SimPy `Resource` instances.
- Routing is shortest-time Dijkstra on the directed graph rebuilt per scenario
  (closed edges removed; `edge_overrides` applied).
- Dispatching: nearest-available-loader by expected (path-time + queue-wait),
  tie-break by shortest-expected-cycle.
- Tonnes are credited only on the `dump_end` event at the crusher.

## 5. Main assumptions

- Homogeneous trucks (100 t payload; empty 1.00 / loaded 0.85 speed factors).
- Loading and dumping times are truncated normals, clamped to [0.5×mean, 2.0×mean].
- Travel-time noise is mean-preserving lognormal with σ = `travel_time_noise_cv`
  (default 0.10).
- Capacity-bounded edges with `capacity ≤ 10` are SimPy resources; high-capacity
  haul roads are unconstrained pass-through.
- 8-hour shift; trucks may complete an in-flight cycle up to 30 minutes past
  shift end (drain) but never start a new dispatch after shift end.
- Tonnes counted only at completed `dump_end`. Partial cycles do not count.

## 6. Routing & dispatching logic

- **Routing (per scenario)**: at scenario start, the directed graph is rebuilt
  with `closed: true` edges removed and `edge_overrides` applied. Shortest-time
  Dijkstra is precomputed for the (PARK / CRUSH) ↔ (LOAD_N / LOAD_S) pairs and
  cached.
- **Dispatching (per truck cycle)**: each truck, on entering its cycle, picks the
  loader minimising `expected (path_time + queue_wait_estimate)`. Queue wait is
  estimated as `(in_use + queued) × mean_load_min`. Ties are broken by shortest
  expected total cycle time. Dispatch is dynamic — trucks rebalance as loader
  queues grow.
- If a route is impossible (e.g. catastrophic topology change), the truck logs
  `no_route_to_loader` / `no_route_to_crusher` and exits the loop. None of the
  six required scenarios trigger this.

## 7. Key results (6 scenarios × 30 replications, 8-hour shift)

All values are means with 95 % CI Student-t (df = 29). Full CI bounds are in
`outputs/summary.json`.

| Scenario | Total tonnes | t/h | Crusher util | L_N util | L_S util | Mean cycle (min) | Crusher Q (min) | Loader Q (min) |
|----------|-------------:|----:|-------------:|---------:|---------:|-----------------:|----------------:|---------------:|
| `baseline` (8 trucks) | 12 960 | 1620.0 | 0.948 | 0.732 | 0.715 | 30.15 | 55.34 | 45.36 |
| `trucks_4` | 7 877 | 984.6 | 0.572 | 0.376 | 0.481 | 24.65 | 12.60 | 17.15 |
| `trucks_12` | 13 633 | 1704.2 | 0.987 | 0.773 | 0.745 | 43.08 | 164.97 | 48.12 |
| `ramp_upgrade` | 12 943 | 1617.9 | 0.950 | 0.726 | 0.708 | 30.19 | 57.17 | 44.88 |
| `crusher_slowdown` | 6 827 | 853.3 | 0.998 | 0.402 | 0.380 | 56.47 | 231.40 | 15.89 |
| `ramp_closed` | 12 887 | 1610.8 | 0.944 | 0.731 | 0.704 | 30.26 | 56.40 | 45.51 |

## 8. Answers to the operational decision questions

### Q1. Expected ore throughput at the baseline 8-truck shift?

**~12 960 t per shift** (95 % CI [12 895, 13 025]) — equivalently
**1 620 t/h** (95 % CI [1 612, 1 628]). At 100 t per truck, this is ~130 truck
cycles per shift, distributed roughly evenly across LOAD_N and LOAD_S.

### Q2. Likely bottlenecks?

The **primary crusher is the binding bottleneck** at the baseline 8-truck
configuration. Evidence:

- Crusher utilisation 0.948 — close to saturation.
- Average crusher queue time 55.3 min/truck per shift.
- Loader utilisations are well below 1.0 (0.73 / 0.72) and loader queue time is
  smaller (45.4 min) and partly an artefact of the dispatch policy.
- The narrow ramp (`E03_UP/_DOWN` capacity 1) is **not** binding — see Q4.

### Q3. Does adding more trucks materially improve throughput?

**The system saturates around 8 trucks.** Going from 8 → 12 trucks moves
throughput only from 1 620 → 1 704 t/h (+ 5.2 %), while crusher utilisation rises
from 0.948 → 0.987 and crusher queue time triples (55 → 165 min). Going from 8 →
4 trucks drops throughput to 985 t/h (− 39 %), because the system is
fleet-bound at low truck counts.

Recommendation: 8 trucks is the right operating point for the current crusher
service rate. Further trucks add queueing without throughput.

### Q4. Would improving the narrow ramp materially improve throughput?

**No — at 8 trucks the ramp is not binding.** `ramp_upgrade` (capacity 1 → 999,
speed 18 → 28 kph) yields 1 617.9 t/h vs the baseline's 1 620.0 t/h — within
noise. The crusher is the binding constraint, so easing the ramp only shortens
the loaded-leg time slightly and feeds the crusher's queue faster.

If a future scenario combined a faster crusher with more trucks, the ramp could
become binding (we propose `trucks_10_ramp_upgrade` as a follow-up scenario).

### Q5. How sensitive is throughput to crusher service time?

**Very sensitive.** Increasing mean dump time from 3.5 → 7.0 min in
`crusher_slowdown` cuts throughput from 1 620 → 853 t/h (− 47 %), and crusher
utilisation rises to 0.998 (essentially saturated). Crusher queue time per truck
jumps to 231 min — every truck spends ~half its shift waiting at the crusher.

This is the key sensitivity: **throughput is approximately linearly proportional
to crusher service rate** in the operating range that matters (loaders and
ramps stay sub-saturated).

### Q6. Operational impact of losing the main ramp?

**Surprisingly small at 8 trucks.** `ramp_closed` yields 1 610.8 t/h vs 1 620.0
baseline (− 0.6 %). The bypass route via J1 → J2 → J7 → J5 / J8 → J4 has higher
speed limits (24–30 kph vs the ramp's 18 kph) and unconstrained capacity, so the
total cycle time barely moves.

This is a real operational insight: the ramp was *thought* to be a potential
choke, but at the current crusher service rate the bypass absorbs the diversion
without measurable throughput loss. The ramp matters only if (a) the crusher is
upgraded (lifting the binding constraint upward), or (b) more trucks are added
beyond 12.

## 9. Likely bottlenecks (ranked)

1. **Primary crusher** — utilisation > 0.94 in 5 / 6 scenarios; saturates at 0.99
   under `crusher_slowdown` and `trucks_12`.
2. **Loaders L_N and L_S** — utilisation 0.71–0.78 at baseline; never saturated.
   They could become binding only at fleet sizes beyond 12 with a faster crusher.
3. **Narrow ramp (E03_UP / E03_DOWN)** — non-binding at all tested fleet sizes.
   Capacity-1 single-lane property would bind only if cycle time is dominated by
   ramp queueing — not the case here.

## 10. Limitations

- No truck breakdowns, refuelling, shift changes, or operator variability.
- Truncated normal stochasticity is symmetric (clamped to [0.5×mean, 2.0×mean]);
  extreme delays (>2× mean) are not represented.
- Edge resources are FIFO without preemption — reality may include passing on
  wide haul roads, not relevant given capacity-999 modelling.
- The crusher is modelled as a single SimPy queue; no separate hopper buffer.
- Waste haulage is not modelled — none of the six scenarios direct trucks to the
  WASTE dump.
- Routing uses deterministic edge weights for path search; actual traversal
  applies stochastic noise. This is conservative (path choice does not reroute
  based on realised noise).

## 11. Suggested improvements / further scenarios

- **`trucks_10_ramp_upgrade`** (proposed): combine ramp upgrade with 10 trucks to
  isolate whether the ramp becomes binding before the crusher when the fleet
  grows.
- Add stochastic truck breakdowns (Poisson with mean MTBF) to test resilience
  against availability < 1.0.
- Model crusher as a 2-stage process (hopper buffer + crusher), allowing
  decoupled buffer absorption of arrival bursts.
- Replace the symmetric-clamped truncated normal with a lognormal for load /
  dump durations to capture tail delays.
- Add a fleet-mix scenario (mixed payload trucks) once heterogeneous fleet
  data is available.

## 12. File layout

```
code/
├── README.md                  ← this file
├── conceptual_model.md
├── requirements.txt
├── run_experiment.py          ← CLI entry point
├── mine_sim/
│   ├── __init__.py
│   ├── topology.py            ← graph build, scenario overrides, edge time draws
│   ├── scenario.py            ← yaml loader + inheritance merge
│   ├── resources.py           ← SimPy Resource pool (loaders, crusher, edges)
│   ├── entities.py            ← truck process generator
│   ├── experiment.py          ← single replication driver
│   ├── analysis.py            ← 95% CI Student-t + bottleneck ranking
│   └── event_log.py           ← streaming event recorder
├── tests/
│   ├── test_topology.py
│   ├── test_conservation.py
│   ├── test_repro.py
│   └── test_analytical.py
└── outputs/
    ├── results.csv
    ├── summary.json
    └── event_log.csv
```

## 13. Recommendation confidence map (re: hallucination cost)

This section directly addresses the maintainer's open issue requesting a separate
"safety / hallucination cost" track for engineering recommendations. Each
operational claim made in §8 / §9 is tagged with an evidence grade:

| Recommendation | Grade | Evidence |
|----------------|:-----:|----------|
| Crusher is the binding bottleneck at ≥ 8 trucks (Q2) | **A** | Analytical bound (1 714 t/h) and simulation (1 620 t/h, ratio 0.945) agree. Direct measurement: crusher utilisation 0.948–0.998 in 5 / 6 scenarios. |
| 8 trucks is the saturation point (Q3) | **A** | Marginal tonnage from 8 → 12 (+ 5 %) is < 1 / 7 of marginal from 4 → 8 (+ 65 %), behavioural saturation check passes. |
| Ramp upgrade does not materially help at 8 trucks (Q4) | **A** | Both analytical (crusher binds before ramp at 1 893 vs 1 714 t/h) and simulation (sim difference − 0.1 %, well within CI) agree. |
| Crusher service rate is the dominant lever (Q5) | **A** | Doubling dump time roughly halves throughput: 1 620 → 853 t/h (− 47 %), matching the ratio of crusher service rates. |
| Losing the main ramp causes negligible throughput loss (Q6) | **B** | Sim shows − 0.6 %; analytical bypass-vs-ramp comparison shows bypass is faster because it has higher speed limits and unconstrained capacity. The *direction* (≤ baseline) is robust; the *magnitude* (− 0.6 %) is sensitive to the assumed truncated-normal travel-time noise. |
| Loaders are not at risk of becoming binding within the tested range | **B** | Loader utilisation 0.71–0.78 at baseline. Could shift to grade A with a wider sweep; not run in this submission. |
| Proposed `trucks_10_ramp_upgrade` follow-up scenario | **C** | Speculation. The agent has not run this scenario; it is offered as a hypothesis for the operator/maintainer to test. No quantitative claim is attached. |
| Stochastic-tail risk under 2× mean delays | **C** | Limitation acknowledgement; not modelled. The agent is not claiming the model is robust to extreme delays. |

**Reading guide.** Grade A claims are safe to act on with the documented
assumptions. Grade B claims are directionally safe but the magnitudes carry
model-assumption risk; treat as ranked priorities, not as commitments. Grade C
claims are *not* engineering recommendations — they are open questions or
acknowledged limitations.

The agent is intentionally narrow: every operational sentence in §8–§9 maps to
one of these grades. The point is to make the hallucination surface visible,
not to suppress it.

## 14. Pointers and trace
- `TRACE_POINTER.md` — file inventory, reproduction commands, and the location of
  the full 15-phase agentic trace in the producing repo
  `whyjp/ShipofTheseus`.
- `submission.yaml` — harness / model / run_tag / intervention metadata.
- `run_metrics.json` — wall clock + LOC, generated by upstream `measure_run.py`.
- `token_usage.json` — `token_count_method: unknown` (Claude Code agentic
  session does not expose token totals to the agent).
- `results/evaluation_report.json` — 53/53 automated + 6/6 behavioural checks
  passing.

