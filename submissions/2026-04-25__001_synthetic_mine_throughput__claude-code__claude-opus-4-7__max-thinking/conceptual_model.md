# Conceptual model — synthetic mine throughput

## System boundary

**Included.** Truck dispatch from the parking node (PARK), travel along a directed
road graph, queueing for capacity-constrained road segments, queueing and
service at ore loaders (LOAD_N, LOAD_S), travel to the primary crusher (CRUSH),
queueing and service at the crusher, and the empty return to a loader. The
simulation clock advances in minutes over a fixed 8-hour shift.

**Excluded.** Truck breakdowns, fuelling, driver shift changes, tyre changes,
operator skill differences, weather, blast cycles, ore grade variation, and any
explicit waste haulage. The MAINT and WASTE nodes appear in the topology but
are unused under the production-objective dispatching policy. Energy
consumption, emissions, and mine planning over multi-shift horizons are out of
scope.

## Entities

- **Trucks** — homogeneous CAT-class haul trucks (100 t payload, empty speed
  factor 1.00, loaded factor 0.85). Fleet size is set per scenario. Each truck
  is a SimPy process that loops loader → crusher → loader.

## Resources

- **Loaders** — `L_N` at LOAD_N (mean 6.5 min, SD 1.2 min, capacity 1) and
  `L_S` at LOAD_S (mean 4.5 min, SD 1.0 min, capacity 1). Modelled as
  `simpy.Resource`.
- **Crusher** — `D_CRUSH` at CRUSH (mean 3.5 min, SD 0.8 min, capacity 1).
  Modelled as `simpy.Resource`.
- **Capacity-constrained lanes** — every directed edge with `capacity < 999` in
  the edges file. Edges that share a `lane_id` (the prefix before the first
  underscore in the `edge_id`, e.g. `E03_UP` and `E03_DOWN` both map to lane
  `E03`) are merged into a single physical-lane SimPy resource because the
  data flags them as the same physical constraint. The constrained lanes that
  matter in this topology are:
  - `E03` — narrow main ramp (J2 ↔ J3)
  - `E05` — single-lane crusher approach (J4 ↔ CRUSH)
  - `E07` — single-lane North Pit face access (J5 ↔ LOAD_N)
  - `E09` — single-lane South Pit face access (J6 ↔ LOAD_S)

  Open haul roads (`capacity = 999`) are *not* modelled as resources; multiple
  trucks may traverse them concurrently.

## Events

Events emitted to the event log per truck cycle:

| Event | Meaning |
|---|---|
| `dispatched` | Truck enters service at the start of the shift |
| `route_to_loader` | Routing decision made for the next loading destination |
| `enter_edge` / `exit_edge` | Truck crosses a road segment (capacity request and release on constrained lanes) |
| `arrive_loader`, `queue_loader`, `load_start`, `load_end` | Loading sequence |
| `arrive_crusher`, `queue_crusher`, `dump_start`, `dump_end` | Dumping sequence (the `dump_end` event is when tonnes are credited to throughput) |
| `shift_end` | Truck stops because the shift clock has expired |

## State variables

- Per truck: current node, loaded/empty flag, cumulative cycles, cumulative
  tonnes delivered, cumulative busy time, time queued at loaders, crusher and
  lanes, and full cycle-time history.
- Per resource (loader/crusher/lane): cumulative busy time, queue wait
  samples, request count.
- Per scenario: replication results aggregated to means and 95% confidence
  intervals.

## Routing and dispatching

- Routing uses NetworkX's `shortest_path` over the directed graph with the edge
  weight set to the average of empty and loaded nominal travel times. Closed
  edges are dropped from the graph before routing, so unreachable routes raise
  a clear `RuntimeError("No path from … to …")` rather than silently producing
  bad results.
- Dispatching policy: `nearest_available_loader` with tie-breaker
  `shortest_expected_cycle_time`. The expected cycle time used for tie-breaking
  is travel-to-loader + load + travel-to-crusher + dump + an estimated queue
  penalty proportional to the loader's current count plus queue length.

## Stochasticity

- Loading and dumping times: normal distributions truncated below at
  `max(0.05 min, mean − 3·SD)`.
- Travel times: each segment's nominal `distance/(speed × loaded_factor)` is
  multiplied by an independent lognormal noise factor with the scenario's
  `travel_time_noise_cv` (default CV = 0.10).
- Per replication, all stochastic draws are produced from a single
  `numpy.random.default_rng(base_seed + replication_index)` so results are
  reproducible.

## Assumptions

**Derived from the data.**
- Edge `capacity = 999` is treated as effectively unbounded.
- Edge `capacity = 1` defines a single-lane segment that can hold one truck.
- Edges with the same prefix before the first underscore share one physical
  lane (the metadata on `E03_UP` / `E03_DOWN` calls this out explicitly; the
  same logic is applied to the other approach roads).
- Loading/dumping service distributions are normal with truncation at the
  lower tail.
- Truck speeds are scaled by the truck's empty/loaded factor relative to the
  edge `max_speed_kph`.

**Introduced by the modeller.**
- Trucks always carry 100 t per cycle (no partial bucket counts).
- Loader and crusher availability are 1.0 (no downtime within the shift).
- Trucks dispatch immediately at `t = 0` and continue cycling until the shift
  clock expires; partially-completed cycles do not count toward throughput.
- The shortest-time path is recomputed once per scenario (not dynamically per
  request) given the open graph; congestion does not influence routing.
- The dispatching tie-break uses a simple analytic estimate of queue penalty;
  more sophisticated dispatching (e.g. a centralised optimiser) is out of
  scope.

## Performance measures

- `total_tonnes_delivered` — sum of `payload_tonnes` over completed `dump_end`
  events at CRUSH.
- `tonnes_per_hour` — `total_tonnes_delivered` divided by shift hours.
- `average_truck_cycle_time_min` — mean of completed cycle durations.
- `average_truck_utilisation` — fraction of shift time each truck is in any
  active activity (loading, dumping, travelling).
- `crusher_utilisation` — fraction of shift time the crusher is busy.
- `loader_utilisation[<id>]` — fraction of shift time each loader is busy.
- `lane_utilisation[<id>]` — fraction of shift time × capacity each constrained
  lane is busy.
- `average_loader_queue_time_min`, `average_crusher_queue_time_min` —
  average queue wait at loaders and crusher.
- `top_bottlenecks` — resources sorted by mean utilisation.
- All scenario-level metrics are reported as the mean and 95% confidence
  interval across 30 replications.

## Limitations

- No mechanical breakdowns or unscheduled maintenance — real fleets will lose
  perhaps 10-25 % of theoretical availability.
- No explicit congestion model on open haul roads — only single-lane segments
  queue. In a real mine wide haul roads still slow down with traffic.
- Routing is static given the open graph; trucks do not re-route when they
  observe a queue ahead.
- Trucks do not stop for fuelling, refuelling, or operator shift changes.
- Crusher feed bin behaviour, surge piles and conveyor downstream of the
  crusher are abstracted away — the crusher service time is the entire dump
  cycle.
- The fleet is homogeneous; in practice trucks have different ages, payloads
  and speed factors.
