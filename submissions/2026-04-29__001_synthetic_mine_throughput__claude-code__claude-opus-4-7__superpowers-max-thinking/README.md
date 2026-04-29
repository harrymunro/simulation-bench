# Mine Throughput Simulation

A SimPy discrete-event simulation of an open-pit mine haulage system. Estimates ore throughput to the primary crusher over an 8-hour shift across six required scenarios with 30 replications each.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate           # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run

All six required scenarios with 30 replications each (default):

```bash
python -m mine_sim.run
```

Single scenario or smoke test:

```bash
python -m mine_sim.run --scenario baseline
python -m mine_sim.run --replications 5
```

Outputs (in `results/`):
- `results.csv` — one row per `(scenario_id, replication)` with all required columns
- `summary.json` — per-scenario summary with 95% CIs, loader utilisation, ranked bottlenecks
- `event_log.csv` — combined trace: full events for replication 0 of each scenario; only `dumping_ended` events for replications 1–N (keeps file size manageable while preserving end-to-end traceability for one canonical replication per scenario)
- `{scenario_id}__event_log.csv` — full replication-0 trace per scenario

Total runtime is well under one minute on a modern laptop (~2.5 s for all 6 scenarios × 30 reps).

## Reproduce

The simulation uses one `numpy.random.Generator` per replication, seeded from `config["simulation"]["base_random_seed"] + replication_idx` (12345 by default). Same seed → byte-identical event log. To verify:

```bash
python -m mine_sim.run --scenario baseline
cp results/baseline__event_log.csv /tmp/run1.csv
python -m mine_sim.run --scenario baseline
diff /tmp/run1.csv results/baseline__event_log.csv   # must be empty
```

## Conceptual model

See `conceptual_model.md` for the full system boundary, entities, resources, events, state, assumptions, and performance measures.

In short: trucks loop PARK → loader → crusher → loader → … . Loaders and the crusher are capacity-1 SimPy resources. The narrow ramp E03 and pit-access roads E07/E09 are paired bidirectional resources (one physical road, capacity 1 across both directions — supported by the dataset's metadata note "same physical constraint simplified as separate edge"). E05 crusher approach has per-direction capacity-1 lanes. All other roads are unconstrained.

## Main assumptions

- Service times: `Normal(mean, sd)` truncated to `[0.1 min, mean + 5 sd]`.
- Travel-time noise: multiplicative `Normal(1.0, cv=0.10)` per truck per edge per traversal; effective speed floored at 10% of edge max speed.
- Routing: travel-time-weighted Dijkstra paths, computed once per replication after applying scenario edge overrides (`closed: true` edges are dropped before graph build, so the bypass route emerges naturally for `ramp_closed`).
- Dispatching: `nearest_available_loader` with `shortest_expected_cycle_time` tiebreaker. Decision once per cycle when the truck becomes idle. No mid-cycle re-routing.
- Throughput attributed at `dumping_ended` events at CRUSH only; in-progress dumps at shift end are not counted.
- All trucks start at PARK at t=0 and dispatch simultaneously.

## Routing and dispatching

- Routing objective: shortest travel time. Edge weight = `(distance_m / 1000) / max_speed_kph * 60`. Closed edges (per scenario `edge_overrides`) are dropped before graph build.
- All-pairs shortest paths are pre-computed once per replication via NetworkX. Reachability is validated for every (PARK, loader_node), (loader_node, CRUSH), and (CRUSH, loader_node) pair; if any required pair is unreachable the simulation aborts with a `TopologyError`.
- Dispatcher (per cycle): for each loader, compute expected cycle time = `travel_to_loader + queue_count × load_mean + load_mean + travel_to_crusher + crusher_mean`. Pick the loader with the lowest expected cycle time, tie-broken alphabetically by loader id.

## Key results

Headline tonnes/hour with 95% CI (Student-t, df=29) per scenario, from `results/summary.json`:

| Scenario          | tonnes/h mean | 95% CI               | total tonnes mean | avg cycle (min) | crusher util |
|-------------------|--------------:|---------------------:|------------------:|----------------:|-------------:|
| baseline          |       1,532.1 | (1,525.5, 1,538.6)   |            12,257 |            30.4 |        0.895 |
| trucks_4          |         991.2 |   (985.7,   996.8)   |             7,930 |            23.6 |        0.579 |
| trucks_12         |       1,577.5 | (1,568.8, 1,586.2)   |            12,620 |            43.6 |        0.927 |
| ramp_upgrade      |       1,522.9 | (1,514.4, 1,531.4)   |            12,183 |            30.6 |        0.886 |
| crusher_slowdown  |         815.8 |   (807.6,   824.0)   |             6,527 |            55.5 |        0.945 |
| ramp_closed       |       1,515.0 | (1,506.1, 1,523.9)   |            12,120 |            30.7 |        0.886 |

Loader utilisation is asymmetric in every scenario: the dispatcher strongly prefers `LOAD_S` (faster service: 4.5 min vs 6.5 min) so `L_S` runs near 87 % under baseline while `L_N` is used as a spillover at ~46 %.

## Answers to operational decision questions

### 1. Expected ore throughput in baseline 8-hour shift

**~1,532 tonnes/hour (95 % CI 1,526 – 1,539), or ~12,257 tonnes per shift (CI 12,204 – 12,309)** with 8 trucks. Average truck cycle time ~30.4 min; trucks are productive ~75 % of the shift.

### 2. Likely bottlenecks

The **primary crusher dominates** in all configurations except `trucks_4`. Baseline ranking by `utilisation × avg_queue_wait_min`:

| Resource     | Utilisation | Avg queue wait (min) | Score |
|--------------|------------:|---------------------:|------:|
| crusher      |       0.895 |                 2.82 |  2.52 |
| loader_L_S   |       0.871 |                 2.24 |  1.95 |
| road_PIT_S   |       0.853 |                 1.24 |  1.06 |
| loader_L_N   |       0.458 |                 1.87 |  0.86 |

The **southern pit access road (PIT_S)** ranks third — it is congested because the dispatcher routes most traffic to LOAD_S. The **main ramp (E03)** is **not** a binding constraint in any scenario at baseline truck counts (utilisation < 0.10 in every run except the trucks_12 scenario).

### 3. Does adding more trucks materially improve throughput?

**No — the system saturates between 8 and 12 trucks.** Marginal gain per added truck:

| Step | Δ tonnes/h | Δ tph per truck |
|------|-----------:|----------------:|
| 4 → 8  trucks |    +540.9   |        +135 |
| 8 → 12 trucks |     +45.4   |         +11 |

The 95 % CI for `trucks_12` (1,569 – 1,586) barely separates from `baseline` (1,526 – 1,539); meanwhile crusher queue wait grows from 2.8 min at baseline to 13.1 min at 12 trucks, and average truck utilisation drops from 0.75 → 0.53. **Operationally, ~8 trucks is near optimal under current crusher capacity.**

### 4. Would improving the narrow ramp materially improve throughput?

**No.** `ramp_upgrade` (capacity 999, max speed 28 kph) gives 1,522.9 tph vs baseline 1,532.1 tph — the difference is **within statistical noise** (CIs overlap heavily; the ramp_upgrade mean is even slightly *lower*, which is plausible random variation). Ramp utilisation under baseline is < 10 %, so freeing it has nothing to free up. The crusher is the binding constraint.

### 5. How sensitive is throughput to crusher service time?

**Highly sensitive.** Doubling the crusher mean dump time from 3.5 → 7.0 min (`crusher_slowdown`) reduces throughput by **47 %** (1,532 → 816 tph). Crusher utilisation rises to 0.94 and crusher queue wait jumps to 27 min — the crusher becomes a hard bottleneck and cycle time nearly doubles to 55.5 min. Any operational change that even modestly slows the crusher will cost throughput roughly proportional to the slowdown.

### 6. Operational impact of losing the main ramp route

**Minor, ~1 %.** `ramp_closed` (E03 unavailable; trucks reroute via the western bypass J2 → J7 → J8 → J4) gives 1,515 tph vs baseline 1,532 tph — about a 1 % drop, well within the bench's CI for either scenario. The bypass adds a few minutes per cycle but the crusher remains the binding constraint, so cycle slack absorbs the rerouting cost. The model would still run safely without the main ramp.

## Limitations

See `conceptual_model.md` for the full list. Headline limitations:

- No truck breakdowns, refuelling, shift handover, weather, or operator skill variation.
- No mid-cycle re-dispatch — once a truck picks a loader it commits to that loader.
- Trucks finish their current state transition at shift end; in-progress dumps that complete after `shift_minutes` are not counted (so reported throughput is slightly conservative).
- Initial dispatch from PARK is simultaneous, which may overstate first-cycle loader contention compared with realistic staggered start-up.
- The dispatcher's queue-wait estimate uses `queue_count × load_mean`; it ignores the residual service time of the truck currently being loaded.
- Loader-overrides are supported but no required scenario uses them — so that pathway is exercised only by unit tests.

## Suggested improvements / further scenarios

- **`loader_n_upgrade`** — drop LOAD_N service time from 6.5 to 4.5 min (matching LOAD_S). Tests whether the slower northern loader is binding once the dispatcher can use it without penalty. Expected: would shift load to L_N, but only marginally because the crusher is still the binding constraint.
- **`crusher_capacity_2`** — model two parallel crusher lines. Likely the highest-leverage operational change given the bottleneck profile.
- **Staggered initial dispatch** — model trucks departing PARK at small time offsets to reduce first-cycle contention.
- **Truck reliability and refuelling** — add a per-truck failure rate and a refuelling cycle via the maintenance bay node.
- **Sensitivity sweep over `travel_time_noise_cv`** — currently fixed at 0.10; test 0.05 and 0.20 to bound the effect of travel-time uncertainty on the headline numbers.
