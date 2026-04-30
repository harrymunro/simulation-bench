# Conceptual Model: Synthetic Mine Throughput Simulation

Benchmark: `001_synthetic_mine_throughput`
Engine: SimPy discrete-event simulation
Shift length: 480 minutes (8 hours), hard cut at `t = 480`

This document specifies the conceptual model that the SimPy implementation under
`src/mine_sim/` realises. It follows the modelling-and-simulation convention of
separating *system boundary*, *entities*, *resources*, *events*, *state
variables*, *assumptions* (split between data-derived and introduced), *model
limitations*, and *performance measures*.

---

## 1. System boundary

### 1.1 Inside the boundary

The model represents one ore haulage shift on the synthetic open-pit mine
described by `data/nodes.csv`, `data/edges.csv`, `data/trucks.csv`,
`data/loaders.csv`, and `data/dump_points.csv`. Inside the boundary we include:

- **The ore production cycle** `PARK -> LOAD_{N|S} -> CRUSH -> LOAD_{N|S} -> ...`
  for every truck, as a sequence of travel, queue, load, and dump events.
- **All directed road segments** in `edges.csv` that lie on a path between
  `PARK`, `LOAD_N`, `LOAD_S`, and `CRUSH` (including the `J3-J4` ramp and
  bypass alternatives `J7`-`J8`).
- **Capacity-constrained edges** (`capacity <= 1` in the CSV) modelled as
  independent SimPy `Resource` objects, one per directed edge: `E03_UP`,
  `E03_DOWN`, `E05_TO_CRUSH`, `E05_FROM_CRUSH`, `E07_TO_LOAD_N`,
  `E07_FROM_LOAD_N`, `E09_TO_LOAD_S`, `E09_FROM_LOAD_S`.
- **The two ore loaders** `L_N` (at `LOAD_N`, mean 6.5 min) and `L_S`
  (at `LOAD_S`, mean 4.5 min), each capacity 1.
- **The primary crusher** `D_CRUSH` (at `CRUSH`, mean dump 3.5 min,
  sd 0.8 min), capacity 1.
- **Dispatching logic**: an *empty* truck chooses the loader that minimises
  `travel_to_loader + current_queue_len * mean_load_time + own_load_time`.
- **Routing logic**: static shortest-time Dijkstra paths per
  `(scenario, origin, destination)`, recomputed once per scenario load
  (so closures in `ramp_closed` are honoured).
- **Stochastic effects** on per-edge travel (lognormal multiplier, mean 1,
  cv 0.10), per-load time, and per-dump time (normal-truncated at
  `max(0.1, sample)`).
- **Seven scenarios**: `baseline`, `trucks_4`, `trucks_12`, `ramp_upgrade`,
  `crusher_slowdown`, `ramp_closed`, plus the proposed combo
  `trucks_12_ramp_upgrade`.

### 1.2 Outside the boundary

These elements are deliberately excluded so the model stays focused on ore
throughput to the primary crusher:

- **Waste haulage and the `WASTE` dump** (`D_WASTE`, edges `E13_*`).
  Trucks never visit `WASTE` in this model.
- **Maintenance / refuelling at `MAINT`** (edges `E14_*`). The `availability`
  field on trucks is treated as `1.0` for the active shift; we do not model
  random breakdown, refuelling, or shift breaks.
- **Operator behaviour**: shift handovers, lunch breaks, manual overrides.
- **Weather, dust, visibility, grade-dependent fuel burn**, and any non-time
  effects on cycle execution.
- **Ore quality / blending** at the crusher; tonnes are treated as a single
  homogeneous bulk material.
- **Crusher downstream stockpile** dynamics; the crusher is always *able* to
  receive a dump (only its service time constrains it).
- **Network effects between adjacent shifts**: the simulated shift starts
  empty (all trucks at `PARK`, all queues empty) and ends with a hard cut at
  `t = 480`.

### 1.3 Time horizon and termination

A single simulated shift lasts exactly 480 minutes. We enforce a **hard cut at
`t = 480`**: only `end_dump` events with `time_min < 480` contribute tonnes to
throughput. In-flight cycles at the cut are discarded. This is a deliberate
modelling choice that mirrors how an operator would value the *closed* tonnes
they can actually report at end-of-shift.

---

## 2. Entities

The dynamic, attribute-bearing things that flow through the system.

| Entity | Population | Key attributes | Lifecycle |
|---|---|---|---|
| **Truck** | 4, 8, or 12 (scenario-dependent), each starting at `PARK` | `truck_id`, `payload_tonnes` (100), `empty_speed_factor` (1.00), `loaded_speed_factor` (0.85), `availability` (1.00), current node, loaded flag, current loader assignment | dispatched at `t=0` -> repeat ore cycle until shift end |

A truck always carries either zero tonnes (empty) or `payload_tonnes` (loaded).
We treat the *ore payload* as an attribute on the truck rather than as a
separate entity, because no payload-level transformation occurs between the
loader and the crusher.

---

## 3. Resources

The static, capacity-bound things that *constrain* truck flow. All are SimPy
`Resource` objects so the engine handles waiting and FIFO queueing for us.

| Resource | Type | Capacity | Where in graph | Service-time distribution |
|---|---|---|---|---|
| `L_N` | Loader | 1 | node `LOAD_N` | `normal_truncated(mean=6.5, sd=1.2, lower=0.1)` min |
| `L_S` | Loader | 1 | node `LOAD_S` | `normal_truncated(mean=4.5, sd=1.0, lower=0.1)` min |
| `D_CRUSH` | Crusher (dump) | 1 | node `CRUSH` | `normal_truncated(mean=3.5, sd=0.8, lower=0.1)` min |
| `E03_UP` | Edge resource | 1 (or 999 in `ramp_upgrade`) | `J2 -> J3` | n/a (transit) |
| `E03_DOWN` | Edge resource | 1 (or 999 in `ramp_upgrade`, closed in `ramp_closed`) | `J3 -> J2` | n/a (transit) |
| `E05_TO_CRUSH` | Edge resource | 1 | `J4 -> CRUSH` | n/a |
| `E05_FROM_CRUSH` | Edge resource | 1 | `CRUSH -> J4` | n/a |
| `E07_TO_LOAD_N` | Edge resource | 1 | `J5 -> LOAD_N` | n/a |
| `E07_FROM_LOAD_N` | Edge resource | 1 | `LOAD_N -> J5` | n/a |
| `E09_TO_LOAD_S` | Edge resource | 1 | `J6 -> LOAD_S` | n/a |
| `E09_FROM_LOAD_S` | Edge resource | 1 | `LOAD_S -> J6` | n/a |

Edges with `capacity = 999` are treated as effectively unconstrained and are
modelled as plain time delays without a SimPy resource (SimPy resources have
fixed overhead per request, so this avoids spurious queue records on free
roads). Each direction of a single physical lane is mirrored *literally* from
the CSV as an independent `Resource`, in line with the Seed constraint.

---

## 4. Events

Every truck cycle produces the events below. They are recorded into
`event_log.csv` with columns `time_min, replication, scenario_id, truck_id,
event_type, from_node, to_node, location, loaded, payload_tonnes, resource_id,
queue_length`.

| Event type | Trigger | Notes |
|---|---|---|
| `dispatch` | `t = 0` for every truck | Initial release, all trucks released simultaneously |
| `arrive_loader` | Truck reaches the assigned loader's node | Recorded *before* requesting the loader resource |
| `start_load` | Loader resource granted | Records loader queue length at start |
| `end_load` | Truncated-normal load duration elapses | Truck flips to `loaded = True` |
| `depart_loader` | Truck releases the loader and starts travelling toward `CRUSH` | |
| `arrive_crusher` | Truck reaches `CRUSH` node | Recorded before requesting `D_CRUSH` |
| `start_dump` | `D_CRUSH` granted | Records crusher queue length |
| `end_dump` | Truncated-normal dump duration elapses; tonnes credited if `time_min < 480` | The throughput-defining event |
| `depart_crusher` | Truck releases `D_CRUSH` and starts travelling back to a loader | |
| `edge_enter` | Truck acquires a capacity-1 edge resource | `resource_id = edge_id` |
| `edge_leave` | Truck releases that edge resource | |

Travel along a non-capacity-constrained edge is a `simpy.Environment.timeout`
of `(distance / (max_speed * speed_factor)) * lognormal_multiplier`, with no
explicit event log entry. Travel along a capacity-constrained edge is the same
delay *while holding* the edge `Resource`, bracketed by `edge_enter` /
`edge_leave` events for traceability.

---

## 5. State variables

State that must be tracked to produce the required metrics, derived primarily
from SimPy's own bookkeeping plus a small per-replication accumulator object.

### 5.1 Per truck

- `current_node`: most recently arrived node.
- `loaded`: boolean.
- `current_loader_assignment`: `L_N` / `L_S` / `None`.
- `cycle_start_time` and `cycle_count`: rolling counters used to compute mean
  cycle time.
- `productive_busy_time`: cumulative minutes spent in the productive part of
  the cycle (loaded travel + dumping + dump-side queue + empty travel +
  loading + load-side queue). Used for `truck_utilisation = productive / 480`.

### 5.2 Per resource

- For `L_N`, `L_S`, `D_CRUSH`: total `busy_time` (sum of service durations),
  total `queue_wait_time` (sum of waits before a request is granted), and
  number of services completed. Utilisation is `busy_time / 480`.
- For each capacity-1 edge resource: `busy_time`, `queue_wait_time`, and
  number of traversals.

### 5.3 Per replication

- `total_tonnes_delivered`: `100 t * count(end_dump events with time < 480)`.
- `tonnes_per_hour`: `total_tonnes_delivered / 8`.
- `average_truck_cycle_time_min`: mean over completed full cycles (defined as
  consecutive `end_dump` -> `end_dump` intervals, with the very first cycle
  using `dispatch` -> `end_dump`).
- `average_truck_utilisation`: mean `productive_busy_time / 480` across trucks.
- `crusher_utilisation`: `D_CRUSH.busy_time / 480`.
- `loader_utilisation_{L_N, L_S}`: `loader.busy_time / 480`.
- `average_loader_queue_time_min`, `average_crusher_queue_time_min`: mean wait
  time per service event at the loaders / crusher.

### 5.4 Per scenario

- Across the 30 replications, every per-replication metric is summarised as a
  mean and a 95% Student-t confidence interval with `n - 1 = 29` degrees of
  freedom.
- `top_bottlenecks`: ranked by composite score
  `utilisation * mean_queue_wait_min`, computed for every loader, the
  crusher, and every capacity-1 edge resource.

---

## 6. Assumptions

The benchmark prompt explicitly asks us to separate assumptions sourced from
the data from those we have introduced.

### 6.1 Data-derived assumptions

These come directly from the CSV / YAML inputs and are reproduced literally
in the model:

- **Topology**: 15 nodes (`PARK`, `J1`-`J8`, `LOAD_N`, `LOAD_S`, `CRUSH`,
  `WASTE`, `MAINT`) and 35 directed edges, taken verbatim from `nodes.csv` /
  `edges.csv`.
- **Capacity-constrained edges**: edges with `capacity <= 1` are modelled as
  shared single-lane resources. From the CSV these are `E03_UP`, `E03_DOWN`,
  `E05_TO_CRUSH`, `E05_FROM_CRUSH`, `E07_TO_LOAD_N`, `E07_FROM_LOAD_N`,
  `E09_TO_LOAD_S`, `E09_FROM_LOAD_S`.
- **Loaders**: two loaders, capacity 1, with means 6.5 / 4.5 min and standard
  deviations 1.2 / 1.0 min from `loaders.csv`.
- **Crusher**: single dump with capacity 1, mean 3.5 min, sd 0.8 min from
  `dump_points.csv`.
- **Truck fleet**: 12 trucks defined in `trucks.csv`, each with payload
  100 t, `empty_speed_factor = 1.00`, `loaded_speed_factor = 0.85`,
  `availability = 1.00`, starting at `PARK`. Scenarios cap the active fleet
  at 4, 8, or 12.
- **Free-flow edge times**: `distance_m / (max_speed_kph * 1000 / 60)`
  minutes per edge, again with the speed-factor multiplier.
- **Scenario semantics**: closures, capacity overrides, and crusher service
  changes are read from the YAML override blocks (`edge_overrides`,
  `dump_point_overrides`, `fleet`).
- **Stochasticity recipe**: the YAML specifies
  `loading_time_distribution: normal_truncated`,
  `dumping_time_distribution: normal_truncated`, and
  `travel_time_noise_cv: 0.10`.

### 6.2 Introduced assumptions

These choices fill in gaps the data does not specify; each is required to
make the simulation runnable and is documented here.

1. **Routing is static shortest-time per scenario**, recomputed by Dijkstra on
   free-flow edge times whenever a scenario changes the edge set (closures or
   capacity upgrades). Trucks do *not* re-plan during a replication, even if
   queues form on capacity-1 edges. This trades a small amount of realism for
   reproducibility and traceability.
2. **Travel-time noise** is a per-edge-traversal lognormal multiplier with
   mean 1 and coefficient of variation 0.10. This honours
   `travel_time_noise_cv: 0.10` while keeping multipliers strictly positive.
3. **Loading and dumping** are sampled as `normal_truncated` with the
   loader/crusher mean and sd, truncated at `max(0.1, sample)` so a sample
   below 0.1 min is replaced with 0.1 min rather than rejected and
   resampled. This avoids zero / negative durations without biasing the mean.
4. **Dispatch policy**: each empty truck is assigned to
   `argmin(travel_to_loader + current_queue_len * mean_load_time + own_load_time)`.
   `current_queue_len` includes the truck currently being served. Ties are
   broken by lower `loader_id` (`L_N` before `L_S`).
5. **Initial dispatch**: all trucks are released simultaneously at `t = 0`
   from `PARK`. There is no staged ramp-up.
6. **Hard cut at `t = 480`**: only dumps completed strictly before 480 min
   count toward throughput. In-flight loads or dumps at the cut are
   discarded. This is consistent with the operator-facing "tonnes closed at
   end of shift" interpretation.
7. **Truck utilisation = productive only**: time spent travelling, queueing,
   loading, or dumping inside the ore cycle counts; idle time at `PARK` does
   not. Specifically, post-shift idle time after the hard cut is excluded.
8. **Reachability self-check** at scenario load: if any of the OD pairs
   `PARK<->LOAD_N`, `PARK<->LOAD_S`, `LOAD_N<->CRUSH`, `LOAD_S<->CRUSH` is
   unreachable in the post-override graph, the scenario fails loudly rather
   than silently producing zero throughput.
9. **Per-replication seed**: `seed_r = base_random_seed + replication_index`.
   This makes individual replications independently reproducible while the
   scenario as a whole is deterministic.
10. **`WASTE` and `MAINT` are out of scope** for this throughput study and
    their edges are kept in the graph but never used. Routing therefore never
    detours to them.
11. **Edge resources are independent per direction**, mirroring `edges.csv`
    literally (`E03_UP` and `E03_DOWN` are two separate `Resource` objects).
    A more realistic single-physical-lane model would couple them, but
    the data treats them as separate edges and we follow the data.
12. **Crusher tonnes are credited at `end_dump`**, not at `start_dump` or
    `arrive_crusher`. This matches the standard SimPy convention for
    "service complete" and aligns with the prompt's instruction that
    throughput is measured by completed dump events.

### 6.3 Combo scenario rationale

In addition to the six required scenarios, we propose
**`trucks_12_ramp_upgrade`**: 12 trucks combined with the upgraded ramp.
The rationale is that `trucks_12` alone is expected to saturate at the
capacity-1 ramp, and `ramp_upgrade` alone is expected to be limited by fleet
size at 8. The combo isolates the joint effect, telling the operator whether
the two investments are complementary (super-additive), substitutive
(sub-additive), or independent.

---

## 7. Limitations

These are areas where the model is deliberately simpler than the real system,
and a user of the results should keep them in mind.

- **No re-routing during the shift**: trucks commit to the static
  shortest-time path even if a capacity-1 edge develops a long queue. In
  reality, a dispatcher might divert a truck through the bypass.
- **Independent edge directions**: `E03_UP` and `E03_DOWN` are treated as two
  separate single-lane resources. If the physical ramp is genuinely a single
  lane shared by both directions, real congestion will be worse than
  modelled.
- **No truck-truck interaction on free-flow edges**: capacity 999 edges are
  treated as effectively infinite. Real haul roads have finite headway.
- **Deterministic mechanical availability**: no random truck breakdowns,
  flat tyres, or refuelling; `availability = 1.00` for all 480 minutes.
- **No operator-level decisions**: no shift change, lunch break, or manual
  override. Trucks cycle continuously.
- **No queue-length feedback in dispatch**: dispatch uses *current* queue
  length at the moment of decision, but a truck en route does not influence
  later dispatch decisions until it physically arrives.
- **Single-replication horizon**: a single 480-minute shift, no warmup
  trimming. The empty-system bias is small because trucks reach steady state
  within the first few cycles, but it is not zero.
- **Crusher always available**: the crusher never blocks (no full-bin
  back-pressure from downstream stockpile, no maintenance windows).
- **Single ore type / single payload**: every dump is exactly 100 t and
  treated as homogeneous.
- **Deterministic node coordinates**: animation uses Euclidean coordinates
  from `nodes.csv` even though real haul roads bend. This affects the
  visualisation only, not metrics.

---

## 8. Performance measures

The performance measures below are computed per replication and aggregated
per scenario across 30 replications using a Student-t 95% CI with `n - 1 = 29`
degrees of freedom.

### 8.1 Primary throughput measures

- **`total_tonnes_delivered`** (t):
  `payload_tonnes * count(end_dump events at CRUSH with time_min < 480)`.
  This is the headline number and the answer to operational question 1.
- **`tonnes_per_hour`** (t/h): `total_tonnes_delivered / 8`.

### 8.2 Cycle-level measures

- **`average_truck_cycle_time_min`**: mean wall-clock duration of completed
  full cycles (between consecutive `end_dump` events for a truck, with the
  first cycle measured from `dispatch`).
- **`average_truck_utilisation`**: mean per-truck
  `productive_busy_time / 480`. "Productive" = travel + queue + load + dump.

### 8.3 Resource-level measures

- **`crusher_utilisation`** = `D_CRUSH.busy_time / 480`.
- **`loader_utilisation`** per loader = `loader.busy_time / 480`.
- **`average_loader_queue_time_min`** = mean wait per loader-service event,
  averaged across loaders.
- **`average_crusher_queue_time_min`** = mean wait per crusher-service event.
- **Edge resource utilisation and queue wait** for every capacity-1 edge.

### 8.4 Bottleneck ranking

`top_bottlenecks` lists every constraining resource (loaders, crusher,
capacity-1 edges) ranked by

```
composite_score = utilisation * mean_queue_wait_min
```

This composite captures both *how busy* a resource is and *how much actual
delay* it imposes. A near-saturated resource with no queue (e.g. a fast
loader with a very short queue) is correctly down-weighted relative to a
near-saturated resource that is also creating long waits.

### 8.5 Uncertainty quantification

For every reported scalar `x`, the 95% confidence interval is

```
mean(x) +/- t_{0.975, n-1} * std(x) / sqrt(n)
```

with `n = 30`. This is reported as `xxx_ci95_low` / `xxx_ci95_high` in
`summary.json`.

### 8.6 Decision-question linkage

The operational decision questions are answered using these measures:

| Question | Primary measure(s) |
|---|---|
| Q1 baseline throughput | `tonnes_per_hour_mean` and CI for `baseline` |
| Q2 likely bottlenecks | `top_bottlenecks` for `baseline` |
| Q3 more trucks helps? | `tonnes_per_hour` for `trucks_4` vs `baseline` vs `trucks_12` |
| Q4 ramp upgrade helps? | `tonnes_per_hour` for `baseline` vs `ramp_upgrade`; cross-checked with combo |
| Q5 crusher sensitivity | `tonnes_per_hour` and `crusher_utilisation` for `crusher_slowdown` vs `baseline` |
| Q6 ramp closed impact | `tonnes_per_hour` for `ramp_closed` vs `baseline` and route lengths |
| Combo (proposed) | `tonnes_per_hour` for `trucks_12_ramp_upgrade` vs `trucks_12` and `ramp_upgrade` individually |

All numerical answers in `README.md` reference values from `summary.json` so
that the conceptual model and the reported answers stay in lockstep.
