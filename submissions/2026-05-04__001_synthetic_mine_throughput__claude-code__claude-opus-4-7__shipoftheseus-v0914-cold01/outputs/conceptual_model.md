# Conceptual Model — Synthetic Mine Throughput

## 1. Modelling purpose

Estimate ore throughput to the primary crusher over an 8-hour shift in a synthetic
open-pit mine, and answer six operational decision questions:

1. Expected ore throughput at the crusher under the baseline 8-truck configuration?
2. Likely bottlenecks in the haulage system?
3. Does adding more trucks materially improve throughput, or does the system saturate?
4. Would improving the narrow ramp materially improve throughput?
5. How sensitive is throughput to crusher service time?
6. Operational impact of losing the main ramp route?

## 2. System boundary

| In scope | Out of scope |
|----------|--------------|
| Truck cycles: travel empty → load → travel loaded → dump → travel empty | Truck breakdowns, refuelling, shift changes |
| Loaders (LOAD_N, LOAD_S) as constrained resources | Operator skill variation, weather |
| Crusher (CRUSH) as constrained resource | Stockpile / blending / metallurgy |
| Capacity-bounded road segments (capacity ≤ 10 → SimPy Resource) | Traffic-light / passing rules on wide haul roads |
| Routing on a directed graph derived from `edges.csv` | Tyre-wear, fuel consumption, emissions |
| Stochastic load / dump / travel times | Operator decision-making during the shift |
| Six required scenarios + one proposed scenario | Maintenance bay (MAINT), waste haulage (WASTE) |

## 3. Entities

- **Truck** (active entity). Attributes: `truck_id`, `payload_tonnes` (100 t),
  `empty_speed_factor` (1.00), `loaded_speed_factor` (0.85), `start_node` (PARK).
  Modelled as one SimPy generator process per truck.

The model does not separately track ore payloads — every truck carries the same
deterministic payload, so payload state collapses into truck state (`loaded /
empty`).

## 4. Resources

| Resource | SimPy capacity | Source field |
|----------|----------------|--------------|
| Loader L_N | 1 | `loaders.csv` |
| Loader L_S | 1 | `loaders.csv` |
| Crusher CRUSH | 1 | `dump_points.csv` |
| Edge E03_UP / E03_DOWN (ramp) | 1 each | `edges.csv` capacity |
| Edge E05_TO_CRUSH / E05_FROM_CRUSH | 1 each | crusher approach |
| Edge E07_*, E09_* (single-lane pit roads) | 1 each | pit_road |
| Other haul/bypass roads (capacity 999) | unconstrained | bypass / haul_road |

Edges with capacity ≤ 10 are wrapped in `simpy.Resource`; high-capacity haul roads
bypass resource holds (no-op pass-through to keep SimPy queues short).

## 5. Events

Per truck cycle, the recorder emits the following events (column `event_type`):

| Event | When |
|-------|------|
| `shift_start` | t=0, truck enters simulation |
| `dispatched_to_loader` | After loader selection, before travel |
| `edge_traversed` | After each road-segment traversal |
| `arrive_loader` | When truck reaches loader node |
| `load_start` | After acquiring loader resource |
| `load_end` | When loading completes (truck now loaded) |
| `arrive_crusher` | When truck reaches CRUSH node |
| `dump_start` | After acquiring crusher resource |
| `dump_end` | When dumping completes (**tonnes credited here**) |
| `shift_end` | At simulation end, per truck |
| `no_route_to_*` | Diagnostic if topology breaks (none observed in any scenario) |

## 6. State variables

- Truck location (current `node_id`)
- Truck `loaded` flag
- Loader queue length (`len(loader.queue)`)
- Crusher queue length (`len(crusher.queue)`)
- Loader busy time (cumulative)
- Crusher busy time (cumulative)
- Edge resource busy time per edge_id (cumulative)
- Per-truck cycle count, tonnes delivered, cycle times list
- Per-truck loader queue wait time, crusher queue wait time

## 7. Assumptions

### From the data
- Two loaders, single-bucket truck (one truck per loader at a time).
- Edge `capacity` field interpreted as max simultaneous trucks on that segment.
- `closed: true` removes the edge from the routing graph.
- Loaded trucks travel slower by `loaded_speed_factor` (0.85).
- All trucks start at PARK and return to PARK is **not** required (they cycle
  loader↔crusher after first dispatch).

### Introduced
- Stochasticity: load and dump times follow a truncated normal clamped to
  [0.5 × mean, 2.0 × mean] (avoids negative or pathological draws).
- Travel-time noise: each edge traversal multiplies the deterministic time by
  `exp(N(0, σ) − σ²/2)` (mean-preserving lognormal) with `σ = 0.10`.
- Routing: shortest-time Dijkstra over the directed graph (edge weight =
  deterministic time at `max_speed_kph`, ignoring loaded factor and noise during
  path search; actual traversal time still respects them).
- Dispatching: nearest-available-loader by expected (path-time + queue-wait).
  Tie-break by shortest-expected-cycle-time. Recomputed each truck cycle so the
  dispatch is dynamic.
- Truck process may complete an in-flight cycle up to 30 minutes past `shift_end`
  (drain), but never starts a new dispatch after `shift_end`.
- Tonnes credited only at `dump_end`. Partial cycles do not count.

### Limitations
- Truncated normal clamping is symmetric — extreme delays (>2×mean) are not
  captured. For the configured CV (≈ 0.18 for loaders, 0.23 for crusher) this is
  acceptable, but the model may under-estimate worst-case queue build-up.
- Edge resources are FIFO without preemption — reality may include passing on
  wide haul roads (we treat capacity = 999 as effectively unconstrained, so this
  matters only on capacity-1 segments where overtaking is genuinely impossible).
- No metallurgical or hopper buffer is modelled at the crusher — capacity is a
  single SimPy queue.
- Heterogeneous trucks would require duplicating the truck state machine; the
  input has homogeneous trucks so this is not exercised.

## 8. Performance measures

Per replication, `results.csv` records:

| Column | Definition |
|--------|------------|
| `total_tonnes_delivered` | Σ payload over all `dump_end` events |
| `tonnes_per_hour` | total_tonnes / shift_length_hours |
| `average_truck_cycle_time_min` | mean of per-truck per-cycle elapsed times |
| `average_truck_utilisation` | mean of `min(busy_time / shift, 1)` per truck |
| `crusher_utilisation` | crusher_busy_time / shift |
| `loader_utilisation_L_N`, `loader_utilisation_L_S` | per-loader busy fraction |
| `average_loader_queue_time_min` | mean per-truck waited time before load_start |
| `average_crusher_queue_time_min` | mean per-truck waited time before dump_start |
| `total_cycles_completed` | Σ cycles across trucks |

Per scenario, `summary.json` records mean + 95 % CI Student-t (df = n−1) for each
metric, plus a top-3 bottleneck ranking (by utilisation, tie-break queue time).

## 9. Verification & validation strategy

- **Verification (does the model do what we intended)**:
  - `tests/test_topology.py` — graph build, ramp-closed reroute, ramp-upgrade speed
  - `tests/test_conservation.py` — tonnes only credited on `dump_end`; utilisations ∈ [0,1]; tonnes/h ≤ crusher analytical bound
  - `tests/test_repro.py` — same seed → identical totals; different seeds → different totals
  - `tests/test_analytical.py` — simulated baseline ratio in [0.80, 1.00] of crusher-bound

- **Validation (does the model represent reality plausibly)**:
  - Hand-computed analytical bounds for crusher, loader pair, ramp (see
    `intent/03-cold-read.md`).
  - Comparing simulated bottlenecks to expected (crusher saturates at ≥8 trucks;
    ramp is *not* binding at 8 trucks because crusher binds first).

## 10. Routing & dispatching logic

- **Routing (per scenario)**: directed graph from `edges.csv` minus closed edges
  and with `edge_overrides` applied. Shortest-time Dijkstra precomputed for the
  small set of (PARK / CRUSH / LOAD_N / LOAD_S) pairs; cached per scenario.
- **Dispatching (per truck cycle)**: nearest available loader by
  `expected (path_time + queue_wait)`; tie-break by shortest expected total cycle
  time. The expected queue wait uses `(in_use + queued) × mean_load_min`. The
  truck takes the cached path from current node to chosen loader, then from the
  loader node to CRUSH.

This makes dispatching dynamic: as loader queues grow, trucks rebalance toward
the less-busy loader. The routing graph itself is static within a scenario.
