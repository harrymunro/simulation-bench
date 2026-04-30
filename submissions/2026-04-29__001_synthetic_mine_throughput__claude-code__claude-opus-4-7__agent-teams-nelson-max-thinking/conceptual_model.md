# Conceptual Model: Synthetic Mine Throughput Simulation

This document describes the conceptual model underlying the discrete-event simulation (DES)
of a synthetic open-pit mine haulage system. The simulation is built with SimPy and is
designed to answer six operational decision questions about mine throughput under varying
fleet sizes, road configurations, and crusher conditions.

---

## System Boundary

**Included in the model:**
- Truck fleet operating over an 8-hour shift
- Road network connecting parking, loading points, the crusher, and bypass routes
- Two ore loading points (North Pit and South Pit faces)
- One primary crusher (dump destination)
- Capacity-constrained road segments that limit simultaneous truck occupancy
- Stochastic loading, dumping, and travel times
- Dispatcher that assigns trucks to loaders and routes them via shortest-time paths

**Excluded from the model:**
- Equipment breakdowns and unplanned downtime
- Shift changes and crew availability
- Fuel consumption, tyre wear, and maintenance schedules
- Weather and ground condition variability
- Ore grade and blending requirements
- Blast cycles and face advance
- Waste haulage (trucks run ore-to-crusher cycles only)
- Multi-payload trucks (each truck carries a single 100-tonne bucket per cycle)

---

## Entities

**Trucks** are the only active entities. Each truck is characterised by:
- `truck_id` — unique identifier
- `payload_tonnes` — 100 t per truck
- `empty_speed_factor` — 1.00 (full road speed when empty)
- `loaded_speed_factor` — 0.85 (15 % speed reduction when carrying ore)
- `start_node` — PARK (all trucks begin at the parking area)

Ore payloads are not modelled as separate entities; a loaded truck implicitly carries
100 tonnes and delivers them when it completes a dump cycle.

---

## Resources

Resources limit simultaneous access and cause queuing when saturated.

| Resource | Node / Edge | Capacity | Notes |
|---|---|---|---|
| Loader North | LOAD\_N | 1 | Mean load time 6.5 min, SD 1.2 min |
| Loader South | LOAD\_S | 1 | Mean load time 4.5 min, SD 1.0 min |
| Crusher | CRUSH | 1 | Mean dump time 3.5 min, SD 0.8 min |
| Ramp outbound | E03\_UP (J2→J3) | 1 | Narrow uphill ramp; primary bottleneck |
| Ramp inbound | E03\_DOWN (J3→J2) | 1 | Same physical constraint, separate edge |
| Crusher approach outbound | E05\_TO\_CRUSH (J4→CRUSH) | 1 | Single-lane dump approach |
| Crusher approach inbound | E05\_FROM\_CRUSH (CRUSH→J4) | 1 | Single-lane return |
| North pit face access outbound | E07\_TO\_LOAD\_N (J5→LOAD\_N) | 1 | Single-lane face road |
| North pit face access inbound | E07\_FROM\_LOAD\_N (LOAD\_N→J5) | 1 | Single-lane face road |
| South pit face access outbound | E09\_TO\_LOAD\_S (J6→LOAD\_S) | 1 | Single-lane face road |
| South pit face access inbound | E09\_FROM\_LOAD\_S (LOAD\_S→J6) | 1 | Single-lane face road |

All edges with `capacity < 999` are wrapped as SimPy `Resource` objects with that capacity.
Edges with `capacity = 999` are treated as unconstrained (trucks travel freely after a
travel-time delay).

---

## Events

Each truck cycles through the following events repeatedly until the shift ends:

1. **Truck dispatched** — Dispatcher assigns a truck (at PARK or returning from crusher)
   to an available loader or the loader with the shortest expected wait.
2. **Truck departs toward loader** — Truck acquires capacity on each road segment in
   sequence along the shortest-time path.
3. **Truck arrives at loader queue** — Truck requests the loader resource.
4. **Loading starts** — Loader resource granted; loading time sampled from truncated normal.
5. **Loading ends** — Truck now carries 100 t; loader resource released.
6. **Truck departs toward crusher** — Truck travels loaded at 85 % of road speed,
   acquiring segment resources along the route.
7. **Truck arrives at crusher queue** — Truck requests the crusher resource.
8. **Dumping starts** — Crusher resource granted; dump time sampled from truncated normal.
9. **Dumping ends** — Truck delivers 100 t to the crusher; crusher resource released;
   tonnes\_delivered counter incremented.
10. **Truck returns empty** — Truck travels empty back to PARK (or is immediately
    re-dispatched if a loader is waiting).
11. **Shift end** — At `shift_length_hours * 3600` simulation seconds, in-flight cycles
    are counted if the truck has already completed loading (ore is already in transit);
    cycles not yet loaded are abandoned.

---

## State Variables

| Variable | Description |
|---|---|
| `truck.location` | Current node or edge of each truck |
| `truck.loaded` | Boolean — whether the truck is carrying ore |
| `truck.assigned_loader` | Loader currently assigned to this truck (None when idle) |
| `queue_length[resource]` | Number of trucks waiting for each loader/crusher/road segment |
| `resource_busy_time[resource]` | Cumulative seconds each resource has been in use |
| `tonnes_delivered` | Running total of ore (tonnes) dumped at the crusher per replication |
| `cycle_times` | List of full cycle durations (dispatch → dump end) per truck per replication |
| `truck_wait_time[loader|crusher]` | Cumulative time trucks spend waiting for each resource |

---

## Assumptions

### Derived from Data

- Loader service times are normally distributed with parameters from `loaders.csv`
  (L\_N: mean 6.5 min, SD 1.2 min; L\_S: mean 4.5 min, SD 1.0 min).
- Crusher dump times are normally distributed (mean 3.5 min, SD 0.8 min) from `dump_points.csv`.
- Edge distances, maximum speeds, road types, and capacity limits are taken directly
  from `edges.csv`.
- Truck payload (100 t) and speed factors are taken from `trucks.csv`.
- The ramp edges (E03\_UP, E03\_DOWN) have capacity 1, making them the intended
  structural bottleneck.
- The bypass route (J2→J7→J8→J4) exists as an alternative when the ramp is closed or
  congested, with edges E15, E16, E17 having capacity 999.

### Introduced by the Model

- **Routing policy**: shortest-time path computed with Dijkstra's algorithm over
  open edges, where edge traversal time = distance / (max\_speed × speed\_factor).
  Capacity-constrained edges include expected wait time in the cost estimate.
- **Dispatch policy**: `nearest_available_loader` — assign the idle loader with the
  shortest expected travel time from the truck's current position. Tie-breaker:
  `shortest_expected_cycle_time` — prefer the loader that minimises total expected
  cycle duration including queue wait.
- **Travel time noise**: Each edge traversal time is perturbed by a multiplicative
  factor sampled from a truncated normal distribution with coefficient of variation
  CV = 0.10 (i.e., SD = 10 % of mean travel time, truncated at ±30 %).
- **Loading/dumping time floor**: Truncated normal distributions are lower-bounded at
  1 minute to avoid zero or negative service times.
- **In-flight cycle counting**: At shift end, trucks that have completed loading but
  have not yet dumped are counted as partial credit (ore in transit); trucks still
  loading or travelling empty are not counted.
- **No warmup period**: The baseline scenario uses no warmup (warmup\_minutes = 0);
  all trucks start from PARK at time 0.
- **Reproducibility**: Each replication uses seed `base_random_seed + replication_index`
  to ensure independent, reproducible streams.

### Limitations

- No equipment failures or random breakdowns.
- No shift-change effects (continuous 8-hour operation).
- No fuel or maintenance constraints.
- No ore blending or grade tracking.
- Single loader per loading point (no shovel relocation).
- Road capacity modelled as a count of simultaneous trucks, not a physical queue length.
- No interaction between loaded and empty trucks on shared edges (both directions
  modelled as separate, independent resources).
- Bypass route capacity is unlimited (999); in reality a bypass may also have width
  constraints.
- The model does not account for truck acceleration/deceleration profiles.

---

## Performance Measures

| Measure | Definition | How Computed |
|---|---|---|
| **Tonnes per hour (t/h)** | Total ore delivered to crusher divided by shift duration | `tonnes_delivered / shift_length_hours` per replication; mean and 95 % CI across replications |
| **Total tonnes delivered** | Cumulative ore dumped at CRUSH per shift | Sum of 100 t increments at each dump event |
| **Truck cycle time (min)** | Time from truck dispatch to end of dump | Recorded for each completed cycle; mean and SD reported |
| **Loader utilisation** | Fraction of shift time a loader is actively loading | `resource_busy_time[loader] / shift_length_seconds` |
| **Crusher utilisation** | Fraction of shift time the crusher is actively dumping | `resource_busy_time[crusher] / shift_length_seconds` |
| **Queue wait time (min)** | Mean time trucks wait for each resource | `total_wait_time[resource] / number_of_service_events` |
| **Top bottlenecks** | Resources with highest utilisation or wait time | Ranked by utilisation across all resources |
| **95 % confidence interval** | Uncertainty estimate on mean t/h | `mean ± 1.96 × (SD / sqrt(replications))` |

Results are aggregated across 30 replications per scenario and written to `results.csv`
(one row per replication) and `summary.json` (scenario-level statistics).
