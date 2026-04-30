# Conceptual model — synthetic mine throughput

This document describes the discrete-event simulation built for benchmark
`001_synthetic_mine_throughput`. The implementation is in `src/` (model,
simulation, experiment, analysis) and is driven by `run.py`. The model
follows the data exactly where the data is unambiguous, and documents every
assumption it has had to introduce.

## 1. System boundary

**Included:**

- One 8-hour ore haulage shift (480 minutes simulated time per replication).
- Movement of ore from `LOAD_N` and `LOAD_S` to the primary crusher `CRUSH`.
- Truck cycles: empty travel from current node to a chosen loader, loading,
  loaded travel to the crusher, dumping, then dispatch to the next loader.
- Capacity-constrained roads (E03 ramp segments, E05 crusher approach,
  E07 north-pit access, E09 south-pit access) modelled as resources.
- Loaders (`L_N`, `L_S`) and the crusher dump point (`D_CRUSH`) as resources.
- Stochastic loading time, dumping time, and per-edge travel time.

**Excluded:**

- Waste and maintenance haulage. Baseline `production.dump_destination` is
  `CRUSH` — only ore movement is counted. `WASTE` and `MAINT` are present in
  the topology but no truck routes through them in any required scenario.
- Truck breakdowns, fuelling, operator breaks, shift handovers.
- Time-of-day effects (weather, lighting), grade-aware truck dynamics, and
  driver behaviour.
- Multi-shift continuity. Each replication starts with an empty system and
  trucks at PARK.

## 2. Entities

**Trucks (T01 … T0N)** are the only active entities. Each truck is a
SimPy process carrying:

- current node,
- loaded / empty status,
- payload (100 t when loaded, 0 t empty),
- per-truck statistics (cycles completed, busy time, queueing time,
  cycle-start timestamps).

Ore payloads are carried by trucks rather than modelled as independent
entities — the simulation only needs to track tonnes delivered, which is
incremented at every `dump_end` event.

## 3. Resources

| Resource          | SimPy capacity | Notes                                           |
| ----------------- | -------------- | ----------------------------------------------- |
| `L_N` loader      | 1              | North pit, mean load 6.5 min (slower face)      |
| `L_S` loader      | 1              | South pit, mean load 4.5 min (faster face)      |
| `D_CRUSH` crusher | 1              | Mean dump 3.5 min (7.0 min in `crusher_slowdown`) |
| `E03_UP`          | 1              | Narrow uphill ramp, designated bottleneck       |
| `E03_DOWN`        | 1              | Narrow downhill ramp                            |
| `E05_TO_CRUSH`    | 1              | Crusher approach (inbound)                      |
| `E05_FROM_CRUSH`  | 1              | Crusher approach (outbound)                     |
| `E07_TO_LOAD_N`   | 1              | Single-lane north-pit face access (in)          |
| `E07_FROM_LOAD_N` | 1              | Single-lane north-pit face access (out)         |
| `E09_TO_LOAD_S`   | 1              | Single-lane south-pit face access (in)          |
| `E09_FROM_LOAD_S` | 1              | Single-lane south-pit face access (out)         |

All other roads have capacity 999 (declared in `edges.csv`). They are
*not* modelled as SimPy resources — that would add bookkeeping overhead with
no queueing realism. They are simple `env.timeout(travel_min)` segments.

## 4. Events

Logged event types (written to `event_log.csv`):

- `truck_dispatched` — process started, truck released from PARK.
- `edge_queue_join` — truck arrives at a constrained edge resource.
- `edge_entered` — truck obtains the edge resource and begins travelling.
- `edge_exited` — truck has finished traversing the edge.
- `edge_traversed_unconstrained` — emitted once per traversal of an
  unconstrained edge; carries `from`, `to`, `resource_id` (the edge ID).
- `arrived_at_loader` — truck reached its dispatched loader node.
- `load_start` / `load_end` — bracket the loading service.
- `arrived_at_crusher` — truck reached the dump node loaded.
- `dump_start` / `dump_end` — bracket the dump service. Tonnes are credited
  at `dump_end` only.
- `shift_end_truncated` — truck process exits because the shift ended.
- `routing_error` — emitted only if the topology cannot route the truck
  (intentional fail-loud).

## 5. State variables

- Per-truck: location, loaded flag, payload, cycles completed, busy time,
  queue time, cycle-start timestamps.
- Per-resource: cumulative busy time, cumulative queue-wait time,
  queue-event count, queue-length samples (timestamped).
- System-wide: total tonnes delivered, total dump events, simulation clock.

## 6. Assumptions

### 6.1 Data-derived assumptions

- **The directed graph is authoritative.** Each `edges.csv` row is a single
  directed segment with its own capacity. `E03_UP` and `E03_DOWN` are
  modelled as independent capacity-1 resources, exactly as the data designer
  encoded them. The dataset metadata describes the up/down split as a
  "simplification" of the real shared physical channel.
- **`dump_points.csv` is authoritative for crusher service time.** The
  `crusher_slowdown` scenario also overrides `nodes.CRUSH.service_time_*`,
  which we apply for consistency, but the simulation reads from
  `dump_points`.
- **`production.dump_destination = CRUSH`** in baseline.yaml is honoured —
  the simulation routes all ore to `CRUSH` and ignores `WASTE`.
- **Loader and crusher capacities are 1** (one truck served at a time),
  consistent with `loaders.csv` and `dump_points.csv`.
- **Truck count and start node** come from `fleet.truck_count` and
  `trucks.csv` (`start_node = PARK`). The first N trucks of `trucks.csv`
  are used.

### 6.2 Introduced assumptions

- **Capacity threshold for SimPy resources = 100.** Any edge with
  declared capacity ≥ 100 is treated as effectively unlimited and is not
  modelled as a SimPy resource. This avoids spurious overhead on the
  capacity-999 edges while still honouring `road_capacity_enabled = true`
  for the genuinely narrow segments.
- **Truncated normal load and dump times.** Sampled from `N(mean, sd)` and
  rejected (resampled) below `0.1 * mean`; the floor prevents non-physical
  near-zero samples. With `sd << mean` rejection is rare (≤ 1 % of
  samples).
- **Lognormal travel-noise multiplier with unit mean.** Each edge
  traversal multiplies `travel_min` by `lognormal(μ, σ)` with
  `σ² = ln(1 + CV²)` and `μ = -σ²/2`, so `E[multiplier] = 1`. CV is read
  from `stochasticity.travel_time_noise_cv` (0.10 in baseline). This avoids
  the bias of a naive `lognormal(0, σ)` whose mean is `exp(σ²/2) > 1`.
- **Random initial dispatch stagger** uniformly over [0, 60] s per truck.
  Without this, all 8–12 trucks at PARK would request the same edge at
  `t = 0` and SimPy's deterministic insertion-order tie-break would create
  artefacts. The stagger is small relative to a multi-minute cycle and does
  not violate `warmup_minutes = 0`, which refers to statistical warm-up
  rather than initial conditions. Documented in `key_assumptions`.
- **Routing = Dijkstra shortest travel time.** Edge weights are
  `distance_m / (max_speed_kph * 1000 / 60)`. Routes are recomputed from
  scratch at every dispatch (so closures and per-scenario speed overrides
  apply). Trucks already en route do not re-plan.
- **Dispatching = `nearest_available_loader`.** Score
  `= travel_time_to_loader + queue_size * mean_load_time_loader`.
  Tie-breaker: shorter expected return cycle (loader → crusher).
- **End-of-shift policy.** No new loader requests start after
  `shift_end_min = 480`. Trucks already loaded complete their travel and
  dump (otherwise tonnes physically held in trucks would be discarded).
  Trucks empty when the shift ends finish their current edge then exit.
  Tonnes are counted only at `dump_end`.
- **Utilisation accounting clipped at the shift boundary.** Resource and
  truck busy-time accumulators record only the portion of each operation
  that falls within `[0, 480]` min, so utilisation values lie in `[0, 1]`
  even when tail dumping continues past 480 min.

### 6.3 Limitations

- E03_UP / E03_DOWN as two independent capacity-1 resources slightly
  understates contention versus a single shared bidirectional channel. A
  more conservative variant could be modelled as a single resource with
  direction switching, but the data does not provide switching parameters.
- Uniform speed factors per edge — gradient and curvature are not modelled
  separately beyond what is encoded in `max_speed_kph`.
- Travel-time noise is i.i.d. per edge traversal, with no temporal
  autocorrelation (no weather front, no shift fatigue effects).
- Loaders and the crusher are 100 % available within the shift
  (no breakdowns, no operator switches).
- Trucks already en route do not reroute when a downstream queue grows;
  routing decisions are made only at dispatch time.

## 7. Performance measures

Reported per scenario (mean across 30 replications, ± 95 % CI by Student's
t-distribution with df = 29):

- `total_tonnes_delivered` — sum of payloads at completed `dump_end`.
- `tonnes_per_hour` — `total_tonnes_delivered / 8`.
- `average_truck_cycle_time_min` — mean inter-cycle-start gap, averaged
  across all trucks and all cycles.
- `average_truck_utilisation` — fraction of shift each truck spent
  travelling, loading or dumping (excludes queueing).
- `crusher_utilisation` — fraction of shift the crusher was serving a
  truck, clipped at the shift boundary.
- `loader_utilisation` — same, per loader (`L_N`, `L_S`).
- `average_loader_queue_time_min` — mean queue-wait at loaders.
- `average_crusher_queue_time_min` — mean queue-wait at the crusher.
- `top_bottlenecks` — resources ranked by mean queue-wait time, used to
  identify the binding constraint in each scenario.
