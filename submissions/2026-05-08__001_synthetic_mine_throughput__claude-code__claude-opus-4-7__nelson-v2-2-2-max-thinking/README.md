# Synthetic Mine Throughput Simulation

Discrete-event simulation of an 8-hour ore-haulage shift on a synthetic mine
topology, built with **SimPy**. Estimates throughput to the primary crusher
across seven scenarios, with Student-t 95% confidence intervals over 30
replications each.

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The simulation needs `simpy`, `numpy`, `pandas`, `scipy`, `networkx`, `pyyaml`,
`matplotlib`, `imageio`, `pillow`. Tested on Python 3.11+.

## 2. Run

```bash
# Run all seven scenarios (six required + one combined) at 30 reps each.
PYTHONPATH=src python3 -m mine_sim run --data-dir data --output-dir .

# Or run a subset:
PYTHONPATH=src python3 -m mine_sim run --scenarios baseline,ramp_closed --output-dir .

# Generate the static topology image:
PYTHONPATH=src python3 -m mine_sim viz --data-dir data --output-dir . --scenario baseline

# Generate animation.gif from the existing event log (baseline rep 0):
PYTHONPATH=src python3 -m mine_sim viz --data-dir data --output-dir . --scenario baseline --animation --replication 0 --fps 8 --step-min 6.0

# Run the full pipeline end-to-end (experiment + topology + animation):
PYTHONPATH=src python3 -m mine_sim all --data-dir data --output-dir .
```

## 3. Outputs

| File | Contents |
|---|---|
| `results.csv` | Per-replication metrics for all 7 scenarios × 30 reps. |
| `summary.json` | Per-scenario aggregated means, 95% CIs, utilisations, top bottlenecks, plus model-wide assumptions and limitations. |
| `event_log.csv` | Trace of dispatch, arrive/load/dump, and capacity-1 edge enter/leave events for the first three replications of each scenario (~36 k rows). |
| `topology.png` | Static plot of the directed graph; capacity-1 edges in red. |
| `animation.gif` | Replay of baseline replication 0 truck movements. |

## 4. Reproducibility

- Each replication uses `seed = base_random_seed + replication_index`. The
  `base_random_seed` is `12345` from `data/scenarios/baseline.yaml` and is
  inherited by all scenarios (or override it under
  `simulation.base_random_seed`).
- A reachability self-check runs before each scenario; any closure that severs
  trucks from loaders or the crusher raises a loud `RuntimeError`.
- All seven scenarios run in roughly 1 second on a laptop.

## 5. Conceptual model

See [`conceptual_model.md`](conceptual_model.md) for the full system boundary,
entities, resources, events, state, and assumptions. Key design points:

- One `simpy.Resource(capacity=1)` per directed capacity-1 edge — mirrors
  `edges.csv` exactly.
- Lognormal travel-time noise (`cv = 0.10`) preserves the free-flow mean.
- Normal-truncated load / dump samples, floored at 0.1 min.
- Hard shift cut at t = 480 min; only dumps completing within the shift count.
- Per-rep seed = `base_random_seed + rep_idx`.

## 6. Routing and dispatching

- **Routing**: static shortest-time per scenario via Dijkstra on the directed
  graph (closures applied). Two weight maps — empty / loaded — using each
  truck's speed factors (1.00 / 0.85). WASTE and MAINT nodes are stripped.
- **Dispatch**: a truck ready for a new cycle picks the loader minimising
  `travel_empty + (queue_len + 1) × mean_load`. All trucks dispatch
  simultaneously at t = 0 from `PARK`, which produces a deliberate first-cycle
  LOAD_S surge before steady-state balances the loaders.

## 7. Key results (30 reps × 8 h shift)

| Scenario | Trucks | Tonnes (95% CI) | t/h | Cycle (min) | Truck util | Crusher util | Loader util (N / S) |
|---|---:|---|---:|---:|---:|---:|---|
| `baseline` | 8 | 12,503 [12,416 – 12,590] | 1,562.9 | 29.8 | 77 % | 91 % | 0.60 / 0.80 |
| `trucks_4` | 4 | 7,623 [7,594 – 7,652] | 952.9 | 24.5 | 92 % | 56 % | 0.32 / 0.51 |
| `trucks_12` | 12 | 12,897 [12,810 – 12,983] | 1,612.1 | 42.7 | 55 % | 94 % | 0.64 / 0.85 |
| `ramp_upgrade` | 8 | 12,557 [12,488 – 12,625] | 1,569.6 | 29.7 | 77 % | 91 % | 0.61 / 0.81 |
| `crusher_slowdown` | 8 | 6,530 [6,455 – 6,605] | 816.2 | 55.3 | 49 % | 95 % | 0.33 / 0.44 |
| `ramp_closed` | 8 | 12,393 [12,342 – 12,445] | 1,549.2 | 30.0 | 77 % | 90 % | 0.66 / 0.75 |
| `trucks_12_ramp_upgrade` | 12 | 12,877 [12,790 – 12,963] | 1,609.6 | 42.7 | 54 % | 94 % | 0.64 / 0.85 |

## 8. Operational decisions

### Q1. What is expected throughput on the baseline 8-hour shift?

**~12,500 tonnes / shift (1,562 t/h).** The 95% CI is [12,416, 12,590] t — a
narrow band, consistent with replicated observation that the shift is
constrained by a saturated crusher rather than by stochastic variation.

### Q2. What are the likely bottlenecks?

**The primary crusher dominates.** Composite bottleneck score
(`utilisation × mean_queue_wait`) is the highest-ranking resource in every
balanced scenario:

| Scenario | Top bottleneck (composite) | 2nd | 3rd |
|---|---|---|---|
| `baseline` | `D_CRUSH` 3.05 | `L_S` 1.97 | `L_N` 1.54 |
| `trucks_12` | `D_CRUSH` 13.36 | `L_S` 3.09 | `L_N` 1.99 |
| `crusher_slowdown` | `D_CRUSH` 25.05 | `E03_UP` 0.58 | `L_S` 0.39 |
| `ramp_closed` | `L_N` 3.14 | `D_CRUSH` 2.81 | `L_S` 1.65 |

The crusher is the binding constraint at 91–95% utilisation across baseline,
trucks_12, and crusher_slowdown. Loader L_S (faster) is the secondary
constraint; L_N is materially under-loaded in baseline.

The narrow ramp `E03_UP` is **not** a bottleneck in steady-state cycles,
because the haul roads from `J5` and `J6` reach the crusher junction `J4`
directly (via `E06_FROM_NORTH` + `E04_TO_CRUSH` and `E12_TO_CRUSH`) without
ever traversing the ramp. Ramp utilisation is ~5%, used only in the first
cycle for `PARK → LOAD_S` dispatch.

### Q3. Does adding more trucks materially improve throughput?

**No — the system saturates between 8 and 12 trucks.** Going from 4 → 8 trucks
lifts throughput +64% (7,623 → 12,503 t/shift). Going from 8 → 12 trucks adds
just **+3.2%** (12,503 → 12,897 t/shift), while truck utilisation falls
from 77% to 55% and the crusher queue wait per truck triples (3.4 → 14.4 min
per cycle). Marginal benefit per added truck collapses once the crusher
saturates above 90% utilisation.

### Q4. Would improving the narrow ramp materially improve throughput?

**No — the gain is < 1 %.** `ramp_upgrade` lifts baseline from 12,503 →
12,557 t (+0.43%, well within the CI). The reason: the ramp is bypassed in
steady-state cycles. Loaded trucks return from the loaders to the crusher via
`J5 → J3 → J4` (north) and `J6 → J4` (south), neither of which uses `E03_UP`
or `E03_DOWN`. The ramp matters only for the initial `PARK → LOAD_S`
dispatch and is rapidly amortised. Combining `ramp_upgrade` with `trucks_12`
also produces no extra value (12,877 vs 12,897, statistically a tie).

**Operator implication:** capital spent on widening or speeding up the main
ramp would not pay back in additional ore at the crusher under the current
fleet. The capital should be directed at the crusher (faster service, or
adding a second crusher / hopper buffer) and at L_S (the busier loader).

### Q5. How sensitive is throughput to crusher service time?

**Highly sensitive — it scales nearly inversely.** Doubling the crusher's
mean dump time from 3.5 → 7.0 min (`crusher_slowdown`) cuts throughput
by **48%** (12,503 → 6,530 t/shift). The crusher queue per cycle balloons from
3.4 to 26.9 min, while loader queues *fall* (because trucks now spend their
time queued at the crusher, not at the loaders). Truck utilisation drops to
49%. Investments that shave service time at the crusher have direct
near-linear throughput payoff.

### Q6. What is the operational impact of losing the main ramp route?

**Very small in steady state — about 1 %.** `ramp_closed` reroutes the
`PARK → LOAD_S` first dispatch via the longer western bypass (PARK → J1 → J2
→ J7 → J8 → J6 → LOAD_S, +2.6 min loaded). Throughput drops 12,503 →
12,393 t/shift (-0.9%). Loader L_N picks up share (utilisation 0.60 → 0.66)
because trucks initially routed to LOAD_S see the longer alternative path
and the dispatch rule occasionally prefers L_N. **The mine can safely operate
without the main ramp**; closing it for maintenance would barely move the
production needle, contradicting the intuition that a "narrow ramp" implies
a meaningful constraint.

### Additional scenario: `trucks_12_ramp_upgrade`

This combination tests whether the ramp upgrade releases value once trucks
are abundant. It does not — throughput tracks `trucks_12` exactly (12,877
vs 12,897 t, statistically indistinguishable), confirming that the crusher
remains the binding constraint regardless of upstream haul-road improvements.

## 9. Bottleneck summary

| Resource | Role | Note |
|---|---|---|
| Crusher (`D_CRUSH`) | **Primary** | 91–95% util in all balanced scenarios; near-linear sensitivity to service time. |
| Loader L_S | Secondary | Faster service (4.5 vs 6.5 min) means the dispatch rule prefers it; util ≈ 80 %. |
| Loader L_N | Reserve | Util 60 % in baseline; absorbs traffic when alternatives queue up (e.g. `ramp_closed`). |
| Ramp `E03_UP/DOWN` | Non-binding | Bypassed in steady state; ~5 % util. |
| Pit roads `E07`, `E09` | Non-binding | Single-lane, but cycle frequency keeps utilisation < 50 %. |

## 10. Limitations

- **Static routing.** Trucks do not adapt to live congestion; a re-routing
  policy could lift throughput modestly when capacity-1 edges queue.
- **Independent directional resources.** The CSV defines each direction of a
  capacity-1 edge as a separate resource. If the physical road is in fact a
  single bidirectional lane, this model under-estimates contention.
- **No crusher buffer / stockpile.** Backed-up trucks queue at the crusher
  rather than emptying into a hopper; this is conservative for throughput
  estimates when the crusher saturates.
- **Truck availability = 1.0.** No breakdowns, refuelling, or shift changes.
- **Simultaneous t = 0 dispatch** creates a synchronous LOAD_S surge in the
  first cycle that is visible in the event log; steady-state metrics dominate
  the 480-minute window.
- **Event log retains 3 reps per scenario** to keep the file small (~36 k
  rows). All 30 replications inform `results.csv` and `summary.json`.

## 11. Suggested improvements

- **Crusher capacity:** add a second crusher line, an upstream hopper, or
  invest in faster discharge. Sensitivity analysis suggests near-linear
  payback up to roughly 8 trucks worth of feed.
- **Dynamic routing:** recompute shortest-time on the fly using current
  queue lengths. Likely most impactful when trucks are abundant.
- **Truck availability modelling:** scenarios with realistic `availability`
  < 1.0 and breakdown distributions to stress-test the production target.
- **Loader rebalancing:** the dispatch rule already biases toward the faster
  loader; an enforced floor on L_N usage might smooth queueing.
- **Bidirectional capacity-1 lanes** as a single resource where the physical
  road is one lane in reality.

## 12. Project layout

```
.
├── data/                             # Static inputs (provided)
├── src/mine_sim/
│   ├── __init__.py
│   ├── __main__.py                   # CLI: run / viz / all / list-scenarios
│   ├── data.py                       # Typed CSV loaders
│   ├── scenarios.py                  # YAML scenario loader + inheritance + combo
│   ├── topology.py                   # Override-applied DiGraph + reachability check
│   ├── routing.py                    # Static shortest-time + dispatch rule
│   ├── simulation.py                 # SimPy DES core (one rep)
│   ├── stats.py                      # Student-t CI + utilisation helpers
│   ├── experiment.py                 # Multi-rep runner + summary aggregation
│   └── visualise.py                  # topology.png + animation.gif
├── conceptual_model.md
├── README.md                         # this file
├── results.csv
├── summary.json
├── event_log.csv
├── topology.png
└── animation.gif
```
