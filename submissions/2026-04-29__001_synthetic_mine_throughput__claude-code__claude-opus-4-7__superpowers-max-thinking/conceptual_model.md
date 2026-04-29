# Conceptual Model: Synthetic Mine Throughput

## System boundary

**Included:** the truck haulage cycle from PARK to ore loaders (LOAD_N, LOAD_S) to the primary crusher (CRUSH) and back, traversing the road network defined in `data/edges.csv`. Loaders, the crusher, and capacity-constrained roads are modelled as constrained resources. The 8-hour shift is the simulated horizon.

**Excluded:** waste dump routing, the maintenance bay, breakdowns, refuelling, weather, blasting events, shift handover, operator skill variation, ore grade variation, and grade-resistance effects on truck speed beyond the loaded/empty speed factor.

## Entities

- **Trucks** — active SimPy processes that cycle through the network. Each truck has a fixed payload, empty/loaded speed factors, and a starting node.
- **Ore payload** — implicit; each truck carries `payload_tonnes` between loading and dumping.

## Resources

- **Loaders** L_N (mean 6.5 min, sd 1.2) and L_S (mean 4.5 min, sd 1.0). Capacity 1 each.
- **Primary crusher** (mean 3.5 min, sd 0.8). Capacity 1.
- **Paired bidirectional road locks** (capacity 1 — one truck on the physical road regardless of direction):
  - RAMP — E03_UP / E03_DOWN
  - PIT_N — E07_TO_LOAD_N / E07_FROM_LOAD_N
  - PIT_S — E09_TO_LOAD_S / E09_FROM_LOAD_S
- **Per-direction crusher approach locks** — E05_TO and E05_FROM (each capacity 1, treated as queueing lanes rather than a single physical road).
- All other edges have capacity 999 and are unconstrained.

## Events

- `truck_dispatched`
- `traversal_started`, `road_lock_requested`, `road_lock_acquired`, `traversal_ended` (per edge)
- `loader_requested`, `loading_started`, `loading_ended`
- `crusher_requested`, `dumping_started`, `dumping_ended`

`dumping_ended` at CRUSH is the throughput-recording event.

## State variables

- Per truck: current node, loaded flag, payload, cycle start time, cumulative travelling/loading/dumping minutes.
- Per resource: cumulative busy time, queue waits, queue lengths sampled on entry.
- Global: total tonnes delivered, simulation time.

## Assumptions

### Derived from data
- Loader and crusher service-time means/SDs from `loaders.csv` / `dump_points.csv`.
- Edge distances and speeds from `edges.csv`.
- Truck count from each scenario's `fleet.truck_count`; trucks selected in id-sorted order.
- Capacity-1 edges treated as constrained; capacity-999 edges treated as unconstrained.

### Introduced
- Capacity-1 ramp E03 and pit-access roads E07/E09 are modelled as paired bidirectional resources (one truck on the physical road regardless of direction). Crusher approach E05 keeps per-direction locks. The data's `metadata` for `E03_DOWN` ("same physical constraint simplified as separate edge") supports the paired interpretation.
- Loading and dumping times follow `Normal(mean, sd)` truncated to `[0.1 min, mean + 5 sd]`.
- Travel-time noise is multiplicative `Normal(1.0, cv=0.10)` per truck per edge per traversal; effective speed floored at 10% of edge max_speed_kph to avoid pathological tails.
- Routing uses pre-computed travel-time-weighted shortest paths via NetworkX Dijkstra (computed once per replication after applying scenario edge overrides).
- Loader choice is dynamic per cycle: `nearest_available_loader` with `shortest_expected_cycle_time` tiebreaker, where expected cycle = travel_to + queue_count × load_mean + load_mean + travel_loaded + crusher_mean.
- All trucks start at PARK at t=0 and are dispatched simultaneously.

### Limitations
- No breakdowns, refuelling, shift handover, weather, or operator skill variation.
- No mid-cycle re-dispatching; loader choice is fixed at cycle start.
- Trucks finish their current state transition at shift end (no mid-traversal kill); in-progress dumps that complete after `shift_minutes` are not counted.
- Initial simultaneous dispatch may overstate first-cycle loader contention compared with staggered start-up in practice.
- The dispatcher's queue-wait estimate uses `queue_count × load_mean`; it does not account for the residual service time of the truck currently being loaded.

## Performance measures

- `total_tonnes_delivered` — cumulative tonnes via `dumping_ended` events at CRUSH.
- `tonnes_per_hour` — total / shift length (8 h).
- `average_truck_cycle_time_min` — mean across all completed cycles, all trucks.
- `average_truck_utilisation` — mean across trucks of (travelling + loading + dumping) / shift.
- `crusher_utilisation`, per-loader utilisation (e.g. `loader_L_N_utilisation`, `loader_L_S_utilisation`).
- `average_loader_queue_time_min` — mean wait at any loader, averaged across loaders then across replications.
- `average_crusher_queue_time_min`.
- 95% confidence intervals (Student-t, df = n-1) for headline metrics across replications.
- `top_bottlenecks` — ranked list of resources by `utilisation × avg_queue_wait_min` (highest score first).
