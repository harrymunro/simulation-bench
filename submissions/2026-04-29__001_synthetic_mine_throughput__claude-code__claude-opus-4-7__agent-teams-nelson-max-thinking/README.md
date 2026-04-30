# Synthetic Mine Throughput — SimPy Discrete-Event Simulation

A discrete-event simulation of an open-pit mine haulage system built with SimPy.
Six operational scenarios are modelled over an 8-hour shift with 30 replications each.

---

## Install

Python 3.11+ is recommended.

```bash
pip install -r requirements.txt
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync
```

---

## How to Run

Run all six required scenarios:

```bash
python run.py
```

Run a single scenario:

```bash
python run.py --scenario baseline
```

Run with a custom replication count:

```bash
python run.py --scenario baseline --replications 30
```

Available scenario IDs: `baseline`, `trucks_4`, `trucks_12`, `ramp_upgrade`,
`crusher_slowdown`, `ramp_closed`.

Run with a warmup period (excludes the first N minutes from queue / utilisation
statistics; throughput denominator becomes `shift - warmup`):

```bash
python run.py --scenario baseline --warmup-minutes 30
```

Shipped scenarios use `warmup_minutes: 0`; the CLI flag overrides that for ad hoc
steady-state analysis.

---

## How to Reproduce Results

Seeds are controlled per replication: `seed = base_random_seed + replication_index`.
The baseline scenario uses `base_random_seed = 12345`, giving seeds 12345–12374
across 30 replications. All other scenarios inherit this setting unless overridden
in their YAML. Running `python run.py` with no arguments reproduces the published
`results.csv`, `summary.json`, and `event_log.csv` exactly.

---

## Conceptual Model

See [conceptual_model.md](conceptual_model.md) for the full model description.

**Summary:** Trucks cycle from a central parking area to one of two ore loaders
(North Pit or South Pit), then travel loaded to the primary crusher, dump 100 t,
and return empty. Resources that can form queues — loaders, crusher, and single-lane
road segments — are modelled as SimPy `Resource` objects. The dispatcher assigns each
idle truck to the nearest available loader, breaking ties by shortest expected cycle
time. Routing uses shortest-time Dijkstra over open edges, so the bypass route
(J2→J7→J8→J4) is used automatically when it is faster than the main ramp.

---

## Main Assumptions

- Loader and crusher service times are sampled from truncated normal distributions
  parameterised by mean and SD from the input CSV files.
- Travel time per edge has multiplicative noise with CV = 0.10 (10 % standard deviation).
- All trucks start at PARK at time 0; no warmup period.
- A dump cycle is counted if `dump_start < shift_end`; a 60-minute grace window allows
  trucks already at the crusher at shift end to complete their delivery.
- Capacity-constrained edges (capacity < 999 in `edges.csv`) are modelled as SimPy
  `Resource` objects with that capacity; all other edges are delay-only.
- No breakdowns, maintenance, shift changes, or fuel constraints.

For the full assumptions list see [conceptual_model.md](conceptual_model.md).

---

## Routing and Dispatching Logic

**Routing:** Shortest-time Dijkstra over open edges. Edge traversal time is computed as
`distance / (max_speed_kph × speed_factor)`, where `speed_factor = 0.85` when loaded
and `1.00` when empty. Closed edges are excluded from the graph. If no path exists the
simulation raises an error rather than producing silent wrong results.

**Dispatching:** `nearest_available_loader` — the idle truck is assigned to the loader
with the shortest expected travel time from the truck's current position. When two
loaders have equal travel time the tie is broken by `shortest_expected_cycle_time`,
which accounts for estimated queue wait at each loader.

**Capacity-constrained segments:** Edges with `capacity = 1` in `edges.csv` are wrapped
as SimPy `Resource(env, capacity=1)`. A truck must acquire the resource before
traversing the edge and releases it on arrival. Separate resources are used for each
direction. Affected edges in the baseline topology:

| Edge | Route | Direction |
|---|---|---|
| E03\_UP | J2 → J3 (main ramp) | Outbound |
| E03\_DOWN | J3 → J2 (main ramp) | Inbound |
| E05\_TO\_CRUSH | J4 → CRUSH | Outbound |
| E05\_FROM\_CRUSH | CRUSH → J4 | Inbound |
| E07\_TO\_LOAD\_N | J5 → LOAD\_N | Outbound |
| E07\_FROM\_LOAD\_N | LOAD\_N → J5 | Inbound |
| E09\_TO\_LOAD\_S | J6 → LOAD\_S | Outbound |
| E09\_FROM\_LOAD\_S | LOAD\_S → J6 | Inbound |

The bypass route (E15/E16/E17) has capacity 999 and is treated as unconstrained.

---

## Key Results

All figures are from `summary.json`, 30 replications × 8-hour shift.
95 % CI computed using Student's t-distribution with `df = n − 1`
(`scipy.stats.t.interval(0.95, df=29)`).

| Scenario | Trucks | t/h (mean) | 95 % CI | Crusher util | Avg cycle (min) |
|---|---|---|---|---|---|
| baseline | 8 | 1620 | [1611, 1629] | 0.95 | 28.9 |
| trucks\_4 | 4 | 977 | [972, 981] | 0.57 | 24.1 |
| trucks\_12 | 12 | 1625 | [1612, 1637] | 0.95 | 42.7 |
| ramp\_upgrade | 8 | 1629 | [1620, 1639] | 0.95 | 28.8 |
| crusher\_slowdown | 8 | 820 | [812, 828] | 0.96 | 55.9 |
| ramp\_closed | 8 | 1610 | [1599, 1621] | 0.95 | 29.1 |

---

## Answers to the 6 Operational Decision Questions

### Q1: What is the baseline throughput?

**1620 t/h [95 % CI: 1611–1629]**, equivalent to 12,960 t per 8-hour shift.
Mean truck cycle time is 28.9 minutes. The crusher runs at 95 % utilisation,
indicating it is near saturation under the baseline 8-truck fleet.

### Q2: What are the likely bottlenecks?

The `top_bottlenecks` ranking in `summary.json` (sorted by utilisation, then queue time)
lists **D\_CRUSH (crusher)** first in every scenario:

| Scenario | Top bottleneck | Utilisation | Mean queue (min) |
|---|---|---|---|
| baseline | D\_CRUSH | 0.95 | 4.6 |
| trucks\_4 | D\_CRUSH | 0.57 | 0.8 |
| trucks\_12 | D\_CRUSH | 0.96 | 17.2 |
| ramp\_upgrade | D\_CRUSH | 0.95 | 4.6 |
| crusher\_slowdown | D\_CRUSH | 0.96 | 27.9 |
| ramp\_closed | D\_CRUSH | 0.95 | 4.7 |

The crusher is the binding resource in every configuration except `trucks_4`, where it
runs at 0.57 utilisation and the fleet is the binding constraint instead. The South
loader (L\_S) is consistently second-highest by utilisation (0.91 baseline, 0.92
trucks\_12) because the dispatcher preferentially sends trucks to the faster loader when
it is idle.

**Note on the narrow ramp (E03\_UP).** A naive ranking by mean queue time would surface
E03\_UP at the top of the baseline list (6.0 min mean queue), but its utilisation is
only 3.3 % — inconsistent with a true bottleneck. This queue is a **startup-stampede
artifact**: at t = 0 all 8 trucks dispatch simultaneously, the nearest-loader policy
sends them all toward L\_S via E03\_UP, and they queue once. After the first cycle, the
fleet has spread across both loaders and E03\_UP is essentially unused — routing for
L\_N already bypasses it via J2→J7→J5. Sorting `top_bottlenecks` by utilisation (with
queue time as tiebreaker) removes this misleading artifact while leaving the underlying
data visible in `results.csv`.

### Q3: How sensitive is throughput to fleet size?

| Fleet | t/h | Change vs. baseline |
|---|---|---|
| 4 trucks | 977 | −40 % |
| 8 trucks (baseline) | 1620 | — |
| 12 trucks | 1625 | +0.3 % |

The system is **strongly fleet-limited below 8 trucks** and **crusher-saturated above 8**.
Adding trucks beyond the baseline provides almost no gain (1625 vs. 1620 t/h, within
the confidence intervals). The crusher service rate (~3.5 min per dump, capacity 1)
sets a theoretical ceiling of approximately 1629 t/h under the baseline payload and
shift length. Any further throughput gain requires either a faster crusher or a
second crusher rather than additional trucks.

### Q4: What is the impact of upgrading the main ramp?

**Marginal: 1629 t/h vs. 1620 t/h baseline — a 0.6 % improvement, within noise.**

The ramp upgrade (E03\_UP/DOWN capacity raised to 999, speed raised from 18/22 to
28 km/h) removes the capacity constraint on the main ramp. However, the baseline
routing already directs L\_N-bound trucks via the bypass (J2→J7→J5), which is faster
than the narrow ramp. Only L\_S-bound trucks use E03, and these are spread out enough
in steady state that the ramp is not a binding constraint. The ramp is correctly absent
from the `top_bottlenecks` list in both baseline and ramp\_upgrade once results are
ranked by utilisation, confirming the ramp was not limiting throughput.

**Recommendation:** Do not invest in a ramp upgrade to increase throughput. The crusher
is the binding resource.

### Q5: How sensitive is throughput to crusher service time?

**Highly sensitive: a doubling of mean dump time (3.5 → 7.0 min) drops throughput
by 49 % (1620 → 820 t/h).**

Under crusher\_slowdown, the crusher remains at 0.96 utilisation but now processes
trucks at half the rate. Mean crusher queue time rises from 4.6 to 27.9 minutes, and
average truck cycle time extends from 28.9 to 55.9 minutes. Loader utilisations drop
sharply (L\_S: 0.91 → 0.42; L\_N: 0.50 → 0.37) as trucks spend most of their cycle
waiting at the crusher. The system is highly sensitive to crusher throughput because
the crusher is the single-server bottleneck for the entire fleet.

**Recommendation:** Crusher reliability and service rate are the most critical
operational parameters. Even moderate crusher slowdowns (e.g. blocked chutes, liner
wear) will have a disproportionate effect on shift tonnage.

### Q6: What happens if the main ramp is closed?

**Small impact: 1610 t/h vs. 1620 t/h baseline — a 0.6 % reduction. Rerouting via
the bypass is fully viable.**

When E03\_UP and E03\_DOWN are closed, the router automatically finds paths through
the western bypass (J2→J7→J8→J4 for L\_S-bound trucks; J2→J7→J5 for L\_N-bound
trucks). The bypass adds some travel distance but the route times are comparable.
Crusher utilisation remains at 0.95 and truck utilisation is essentially unchanged
(0.783 baseline vs. 0.782 ramp\_closed). The confidence intervals overlap substantially
([1611–1629] baseline vs. [1599–1621] ramp\_closed), so the difference is not
statistically significant at the 95 % level.

**Note:** In `results.csv`, the `edge_E03_UP_queue_time` and `edge_E03_DOWN_queue_time`
columns are 0.0 for ramp\_closed and ramp\_upgrade scenarios — this is correct because
those edges do not exist as resources in those scenarios (closed or unconstrained
respectively), not a data error.

**Recommendation:** The bypass provides adequate rerouting capacity. A ramp closure
need not halt production, though travel times are slightly longer for L\_S-bound trucks.

---

## Likely Bottlenecks

Based on utilisation and queue-time analysis across all scenarios:

1. **Crusher (D\_CRUSH)** — the primary steady-state bottleneck in all scenarios except
   trucks\_4. Utilisation 0.95–0.96; mean queue wait 4.6–27.9 min depending on service
   rate. Any reduction in crusher throughput has an immediate and disproportionate
   effect on overall t/h.

2. **Loader South (L\_S)** — consistently second-highest utilisation (0.91 baseline,
   0.92 trucks\_12). The South loader is faster (4.5 min mean) but heavily loaded
   because the dispatcher preferentially assigns trucks there when it is idle. Queue
   time 1.6 min baseline, rising to 2.2 min with 12 trucks.

3. **Crusher approach road (E05\_TO\_CRUSH)** — single-lane access to the crusher,
   utilisation ~0.43–0.45. Not a bottleneck at current fleet sizes but could become
   one if throughput increases.

4. **South pit return road (E09\_FROM\_LOAD\_S)** — single-lane pit access, utilisation
   ~0.48 baseline. Co-occupies the South pit cycle alongside L\_S; not currently
   binding but the highest-utilisation road segment.

A startup-transient artifact appears on E03\_UP (high queue time, ~3 % utilisation) for
the first ~20 minutes of each replication while the fleet spreads from PARK. This is
correctly excluded from the bottleneck ranking by sorting on utilisation; see Q2.

---

## Limitations

- No equipment breakdowns or random downtime for trucks, loaders, or crusher.
- No shift changes, refuelling stops, or operator breaks during the 8-hour window.
- Opposing-direction traffic on physically single-lane segments does not interact via
  meet-and-pass logic; each direction is an independent SimPy resource.
- Bypass route (E15–E17) is treated as unconstrained (capacity 999); in reality a bypass
  may have width or grade limits.
- The shipped scenarios use `warmup_minutes: 0`, so a startup-stampede transient on
  E03\_UP is visible in the early minutes of each replication. Warmup support is
  implemented in the runner — pass `--warmup-minutes 30` on the CLI to exclude the
  transient from queue and utilisation statistics for ad-hoc analysis.
- Ore is delivered in fixed 100-tonne increments; no partial payloads or blend control.
- Truck speed is a constant factor per edge; no acceleration/deceleration or switchback
  effects.
- Service time distributions are simple truncated normals; bimodal or heavy-tailed
  effects (e.g. blocked chutes, swell factors) are not captured.
- The `edge_E03_UP_queue_time` and `edge_E03_DOWN_queue_time` columns in `results.csv`
  are 0.0 for `ramp_upgrade` and `ramp_closed` scenarios because those edges are
  removed as constrained resources in those scenarios — this is expected behaviour,
  not missing data.

---

## Suggested Improvements and Further Scenarios

1. **Warmup period in shipped scenarios** — `warmup_minutes` support is implemented in
   the runner but the shipped YAMLs use `0`. Bump baseline to 30–60 min in the YAML to
   make the bottleneck ranking and queue-time statistics reflect steady-state operation
   only. The CLI override (`--warmup-minutes 30`) provides the same effect ad hoc.

2. **Stochastic breakdowns** — model loader and crusher failures using exponential
   time-to-failure and lognormal repair times to assess availability risk.

3. **Second crusher scenario** — add a second crusher unit to test whether a parallel
   dump point breaks the current throughput ceiling.

4. **Shift-change scenario** — introduce a 15-minute production pause at hour 4 to
   quantify the tonnage cost of crew changeover.

5. **Dynamic dispatch with real-time queue feedback** — upgrade the dispatcher to use
   live queue lengths rather than estimated wait times for assignment decisions.

6. **Bypass capacity constraint scenario** — set E15/E16/E17 capacity to 1 or 2 to
   test whether the bypass becomes a bottleneck if the ramp is closed long-term.

7. **Sensitivity analysis on CV** — vary travel time noise (CV = 0.05, 0.10, 0.20)
   to quantify how road condition variability affects throughput confidence intervals.

---

## Output Files

| File | Description |
|---|---|
| `results.csv` | One row per replication per scenario (180 rows); scenario-level and replication-level metrics |
| `summary.json` | Scenario-level statistics: mean t/h, 95 % CI, utilisations, queue times, bottleneck ranking |
| `event_log.csv` | Full event trace (~92,000 events); columns: time, truck\_id, event\_type, node, tonnes |
| `topology.png` | Visualisation of the road network graph with node types and edge capacities |
| `conceptual_model.md` | Formal conceptual model document |
