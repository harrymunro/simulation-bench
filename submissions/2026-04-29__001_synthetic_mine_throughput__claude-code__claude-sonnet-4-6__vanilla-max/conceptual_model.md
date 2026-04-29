# Conceptual Model: Synthetic Mine Throughput Simulation

---

## System Boundary

### Included

- Truck haulage fleet cycling between ore loading faces and the primary crusher
- Two ore loading points (North Pit and South Pit) each served by a single loader
- One primary crusher as the sole ore dump destination
- The directed road network connecting parking, loading faces, crusher, and junctions
- Capacity-constrained road segments (single-lane sections)
- Stochastic loading, dumping, and travel times
- Queue formation at loaders, crusher, and constrained road segments

### Excluded

- Waste haulage (dump to waste dump not modelled; all trucks haul ore to crusher)
- Truck breakdowns, maintenance, and fuel stops
- Shift-change delays and handover procedures
- Blasting and face preparation schedules
- Ore grade and quality (all tonnes treated as equivalent)
- Environmental conditions (weather, dust, road wear)
- Variable truck payload (all trucks carry 100 t per load)

---

## Entities

### Trucks

The primary active entity. Each truck moves through the system in a continuous cycle:

```
Dispatch → Travel (empty) → Queue at loader → Load →
Travel (loaded) → Queue at crusher → Dump → [repeat]
```

Trucks carry a fixed payload of 100 t. Loaded trucks travel at 85% of the empty speed on each road segment. All 12 trucks start the shift at the parking node (PARK). A fleet scenario uses the first N trucks from the list.

---

## Resources

### Loaders

One loader per ore face (L_N at LOAD_N, L_S at LOAD_S), each modelled as a SimPy `Resource` with capacity 1. Only one truck can be served at a time; others queue in FIFO order.

- L_N (North Pit): service time ~ Truncated-Normal(6.5 min, 1.2 min)
- L_S (South Pit): service time ~ Truncated-Normal(4.5 min, 1.0 min)

### Primary Crusher

Modelled as a SimPy `Resource` with capacity 1. One truck dumps at a time; others queue.

- Baseline: service time ~ Truncated-Normal(3.5 min, 0.8 min)
- `crusher_slowdown`: Truncated-Normal(7.0 min, 1.5 min)

### Capacity-Constrained Road Segments

Road segments with `capacity = 1` are modelled as SimPy `Resource` objects, allowing only one truck to traverse the segment at a time. The affected segments are:

| Edge ID | Description | Direction |
|---------|-------------|-----------|
| E03_UP | Main ramp (uphill) | J2 → J3 |
| E03_DOWN | Main ramp (downhill) | J3 → J2 |
| E05_TO_CRUSH | Crusher approach | J4 → CRUSH |
| E05_FROM_CRUSH | Crusher approach return | CRUSH → J4 |
| E07_TO_LOAD_N | North pit face access | J5 → LOAD_N |
| E07_FROM_LOAD_N | North pit face return | LOAD_N → J5 |
| E09_TO_LOAD_S | South pit face access | J6 → LOAD_S |
| E09_FROM_LOAD_S | South pit face return | LOAD_S → J6 |

---

## Events

| Event | Description |
|-------|-------------|
| `dispatch` | Truck selects a loader and begins travel from its current node |
| `edge_depart` | Truck departs from one node toward the next on its route |
| `loader_queue_join` | Truck arrives at loader and joins queue |
| `load_start` | Truck acquires loader resource and loading begins |
| `load_end` | Loading complete; truck becomes loaded |
| `crusher_queue_join` | Truck arrives at crusher and joins queue |
| `dump_start` | Truck acquires crusher resource and dumping begins |
| `dump_end` | Dump complete; ore tonnage recorded as delivered |

---

## State Variables

| Variable | Description |
|----------|-------------|
| `truck.current_node` | Current location of each truck in the graph |
| `truck.loaded` | Boolean flag: loaded or empty |
| `truck.active_time` | Cumulative time spent in productive cycle activity |
| `loader_resource.queue` | Number of trucks waiting at each loader |
| `crusher_resource.queue` | Number of trucks waiting at crusher |
| `road_resource.queue` | Number of trucks waiting for a constrained road segment |
| `state.tonnes_delivered` | Running total of ore delivered to crusher in the replication |
| `state.cycle_times` | List of per-cycle durations (dispatch to dump-end) |
| `state.loader_queue_times` | List of time each truck spent waiting at a loader |
| `state.crusher_queue_times` | List of time each truck spent waiting at the crusher |
| `state.crusher_service_times` | List of dump service durations (for utilisation calculation) |
| `state.loader_service_times` | Per-loader list of load service durations |

---

## Assumptions

### Derived from data

- Loader capacities and service time distributions taken directly from `loaders.csv`
- Crusher service time distribution taken from `dump_points.csv`
- Truck payload (100 t), speed factors (empty=1.0, loaded=0.85), start node (PARK) from `trucks.csv`
- Road capacity constraints taken from `edges.csv` (capacity=1 → single-lane resource)
- Shift length, replications, and base seed taken from scenario YAML files
- Travel time noise CV = 0.10 as specified in baseline scenario

### Introduced assumptions

- **Dispatching policy**: nearest-available-loader with a queue-length penalty. For each available loader, the dispatch score is `travel_time + len(loader_queue) × mean_load_time`. The truck goes to the loader with the lowest score.
- **Routing**: shortest travel-time path using Dijkstra's algorithm on the directed graph. Routes are recalculated at each dispatch decision. Loaded trucks use `speed × 0.85`; path selection uses unloaded time to avoid preference flipping.
- **Travel time stochasticity**: each edge traversal is multiplied by a lognormal random variable with mean 1.0 and CV = 0.10. The lognormal preserves the mean exactly while adding right-skewed variability consistent with real traffic.
- **Shift cutoff**: only dump events that complete before `shift_length_min` are counted. Trucks mid-cycle at shift end do not contribute.
- **Initial position**: all trucks start at PARK at time 0. No warmup period.
- **Fleet selection**: for fleet-size scenarios, the first N rows of `trucks.csv` are used.
- **Truncated normals**: service times are sampled from a normal distribution truncated at zero to prevent negative durations.
- **Loader availability**: loaders are assumed 100% available throughout the shift (no breakdowns).

### Model note on the main ramp

The main ramp (E03_UP/E03_DOWN, J2↔J3) connects the lower haul road to the upper pit area. In steady-state cycling, trucks travel between loaders (at J5/J6 level, above J3) and the crusher (via J4, also above the ramp base). This means the ramp is only traversed during the **initial dispatch** from PARK at the start of the shift.

Additionally, the alternative bypass route (J2→J7→J8→J4) is marginally **faster** than the ramp route (J2→J3→J4) due to the ramp's low speed (18 kph vs. 24–30 kph on bypass roads), so even the initial dispatch prefers the bypass. As a result, the ramp capacity constraint does not activate during normal operation in this model — a finding documented clearly under `ramp_upgrade` and `ramp_closed` results.

### Limitations

- No return to parking between truck cycles (trucks cycle continuously pit↔crusher)
- Dispatch does not account for road congestion en route; route selection is static per dispatch
- Travel noise is independent between edges; no correlated delay events (e.g., road incident blocking multiple trucks)
- All trucks are identical; no truck-specific performance variation
- Loader availability is constant at 100%
- No blasting delays or face moves
- Single shift with no handover modelled

---

## Performance Measures

| Measure | Definition | Unit |
|---------|-----------|------|
| `total_tonnes_delivered` | Sum of payload_tonnes for all dump events completing before shift end | tonnes |
| `tonnes_per_hour` | `total_tonnes_delivered / shift_length_hours` | t/h |
| `average_truck_cycle_time_min` | Mean duration of completed truck cycles (dispatch-to-dump-end) | minutes |
| `average_truck_utilisation` | Mean fraction of shift time each truck spent in an active cycle | dimensionless |
| `crusher_utilisation` | `sum(dump_service_times) / shift_length_min` | dimensionless |
| `loader_utilisation` | `sum(load_service_times) / shift_length_min` per loader | dimensionless |
| `average_loader_queue_time_min` | Mean time trucks waited to be served by a loader | minutes |
| `average_crusher_queue_time_min` | Mean time trucks waited to be served by the crusher | minutes |

Uncertainty is reported as 95% t-distribution confidence intervals across 30 independent replications.
