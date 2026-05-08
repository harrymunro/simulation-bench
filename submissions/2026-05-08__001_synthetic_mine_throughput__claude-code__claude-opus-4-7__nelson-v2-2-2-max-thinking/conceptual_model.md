# Conceptual Model — Synthetic Mine Throughput

## System boundary

**In scope.** A single 8-hour ore-haulage shift on the synthetic mine topology in `data/`. The model represents trucks cycling between two ore loaders (`LOAD_N`, `LOAD_S`) and the primary crusher (`CRUSH`) over a directed road graph (junctions, ramps, haul roads, bypass). Capacity-1 road segments, loader service, and crusher service are modelled as constrained SimPy resources. All seven scenarios in `data/scenarios/` are runnable.

**Out of scope.**
- Waste haulage (`WASTE`) and maintenance (`MAINT`) are excluded from routing.
- Truck refuelling, breakdowns, and shift changes (truck `availability` = 1.0 across the data; no maintenance windows configured).
- Crusher stockpile / hopper buffer; backed-up trucks queue at the crusher rather than discharging into a buffer.
- Driver behaviour heterogeneity beyond the empty / loaded speed factors.
- Multi-shift planning, energy use, and emissions.

## Entities

- **Trucks** — active SimPy processes that loop dispatch → empty travel → load → loaded travel → dump until the shift cut. They carry the cycle state, accumulate productive minutes, and are responsible for resource requests.
- **Ore payloads** — implicit; tonnes are charged to the truck on `load_end` and credited to the mine on `dump_end` (only for dumps completed at or before t = 480 min).

## Resources

- **Loaders** (`L_N`, `L_S`): one `simpy.Resource(capacity=1)` each. Service mean / sd taken from `loaders.csv` (or scenario overrides).
- **Crusher** (`D_CRUSH`): one `simpy.Resource(capacity=1)` at `CRUSH`. Service mean / sd from `dump_points.csv` (or scenario override under `dump_point_overrides`).
- **Capacity-1 directed road edges**: one `simpy.Resource(capacity=1)` per directed edge with `capacity == 1` in `edges.csv`. Each direction is an independent resource (mirroring the CSV). Multi-capacity edges (capacity 999) are unconstrained — modelled as plain time delays.
- Closed edges (`closed: true` in scenario overrides) are absent from both the routing graph and the resource set.

## Events

Per cycle, in order:
1. `dispatched` — truck departs current node with a chosen loader.
2. `enter_edge` / `leave_edge` — once per capacity-1 edge traversed (in either direction).
3. `arrive_loader` — truck reaches the loader node (queue length recorded).
4. `load_start` — loader resource granted.
5. `load_end` — loading service completes; truck is loaded.
6. `arrive_crusher` — truck reaches the crusher node loaded.
7. `dump_start` — crusher resource granted.
8. `dump_end` — dumping completes; truck is empty. Throughput credited iff t ≤ 480 min.

## State variables

- Per-truck: current node, loaded/empty status, current edge segment, productive minutes, loader queue minutes, crusher queue minutes, capacity-1 edge queue minutes, completed cycles, tonnes delivered, cycle times.
- Per-resource (loaders, crusher, capacity-1 edges): list of `(busy_start, busy_end)` intervals and per-request queue waits.
- Per-replication: total tonnes delivered, tonnes per hour, replication seed.

## Routing and dispatching

- **Routing.** Static shortest-time routing per scenario, computed once via Dijkstra over the closure-applied directed graph. Two weight maps are precomputed: empty-leg weights (using `empty_speed_factor`) and loaded-leg weights (using `loaded_speed_factor`). Closures and edge overrides (capacity, max_speed_kph) propagate into routing automatically. WASTE and MAINT are stripped from the routing graph.
- **Dispatch rule.** A truck arriving at `current_node` and ready for a new cycle minimises:
  ```
  cost(L) = travel_empty(current_node → loader_node(L))
            + queue_len(L) × mean_load(L)
            + own_load_time(L)
          = travel_empty(...) + (queue_len(L) + 1) × mean_load(L)
  ```
  Ties broken by enumeration order (deterministic). All trucks dispatch simultaneously at t = 0 from `PARK`.

## Stochasticity

- **Edge traversal time:** lognormal noise around free-flow with coefficient of variation 0.10. Lognormal parameters are matched so the arithmetic mean equals the free-flow time:
  ```
  σ²_log = ln(1 + cv²);  μ_log = ln(mean) − σ²_log / 2
  ```
- **Load and dump time:** normal samples truncated from below at 0.1 min (`max(0.1, N(μ, σ))`). Means and sds are taken from the loaders / dump_points data, with scenario overrides applied.
- **Per-replication seed:** `seed_rep_i = base_random_seed + i`. Each replication uses an independent `numpy.random.default_rng`.

## Performance measures

- **Throughput per shift** (tonnes): sum of payloads from `dump_end` events at t ≤ 480 min.
- **Tonnes per hour:** throughput / shift hours.
- **Average truck cycle time** (min): mean over all completed cycles across replications.
- **Truck utilisation:** *productive* minutes (loading + dumping + edge traversal) / shift, averaged across trucks; queueing time is excluded.
- **Loader / crusher utilisation:** clamped busy-interval coverage of the shift.
- **Average loader / crusher queue wait** (min): mean wait per cycle to acquire the resource.
- **Top bottlenecks:** ranked by composite score = `utilisation × mean_queue_wait`, computed across loaders, the crusher, and capacity-1 edges.
- **Uncertainty:** Student-t (n-1 degrees of freedom) 95% confidence intervals on tonnes and tonnes/hour over the 30 replications.

## Assumptions

### Derived from the data
- Two ore loaders (one per node `LOAD_N` / `LOAD_S`); single crusher (`CRUSH`).
- 12 trucks defined; scenarios use a prefix of size `truck_count`.
- Loader and dump-point service means / sds come straight from the CSVs.
- Capacity-1 edges identified from `edges.csv` (8 in baseline; 6 under `ramp_upgrade` / `ramp_closed`).
- Truck speed factors: empty = 1.00, loaded = 0.85.

### Introduced for the model
- Hard cut at t = 480 min; dumps that complete after the cut do not count toward throughput.
- Lognormal travel-time noise with cv = 0.10 (per scenario stochasticity setting).
- Normal-truncated load / dump samples with floor 0.1 min (per scenario stochasticity setting).
- Dispatch minimises `(travel + queue_len × mean_load + own_load)`; ties broken deterministically.
- All trucks dispatch simultaneously at t = 0 from `PARK`.
- One independent SimPy resource per directed capacity-1 edge (no shared bidirectional lock).
- WASTE and MAINT stripped from routing.
- Routing is static within a scenario; no live re-routing under congestion.

## Limitations

- Static routing means trucks do not exploit alternate paths when their preferred path queues. A live shortest-time-with-congestion model could change findings on the bypass.
- Capacity-1 edges in opposite directions are independent resources here. If the underlying physical road is genuinely a single bidirectional lane, modelling each direction independently *underestimates* contention. The interview-decisions memory locks this choice (mirror CSV) and the synthetic dataset names the directions distinctly.
- Crusher buffering is absent — congestion at the crusher is modelled as truck queue rather than as an upstream stockpile.
- Initial all-trucks-at-PARK simultaneous dispatch creates a synchronous LOAD_S surge in the first cycle (one-shot artefact; see `event_log.csv` reps). Steady-state behaviour dominates a 480-minute shift.
- The event log retains only the first three replications per scenario to keep the file size small while still allowing visual / animation inspection. All 30 replications inform the per-rep `results.csv` and the aggregated `summary.json`.
