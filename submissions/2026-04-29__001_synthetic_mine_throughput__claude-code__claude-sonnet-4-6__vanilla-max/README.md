# Mine Haulage Throughput Simulation

A discrete-event simulation (DES) built with SimPy to estimate ore throughput to the primary crusher over an 8-hour shift under multiple scenarios.

---

## Installation

```bash
pip install simpy numpy pandas scipy matplotlib networkx pyyaml
```

Python 3.9+ required. No other dependencies.

---

## Running the Simulation

```bash
# Run all six required scenarios (30 replications each)
python sim.py

# Run a single scenario
python sim.py --scenario baseline

# Override replications (e.g. 5 for quick testing)
python sim.py --replications 5

# Include topology visualisation
python sim.py --plot

# All options combined
python sim.py --plot --replications 30
```

All output files are written to the same directory as `sim.py`.

---

## Output Files

| File | Description |
|------|-------------|
| `results.csv` | Per-replication metrics for all scenarios (180 rows) |
| `summary.json` | Scenario-level aggregated stats with 95% CI |
| `event_log.csv` | Truck event trace for the first replication of each scenario |
| `topology.png` | Network visualisation (generated with `--plot`) |
| `conceptual_model.md` | Full model design documentation |

---

## Conceptual Model (Summary)

Full details in `conceptual_model.md`.

**System boundary**: 8-truck (baseline) ore haulage fleet cycling between two ore loading faces and one primary crusher. Capacity-constrained single-lane road segments are modelled explicitly. Waste haulage is excluded.

**Entities**: Trucks (active agents with 100 t payload).

**Resources**:
- Two loaders (L_N, L_S): SimPy `Resource(capacity=1)`, FIFO queues
- Primary crusher: SimPy `Resource(capacity=1)`, FIFO queue
- Single-lane road segments (capacity=1 in data): SimPy resources, one truck at a time

**Truck cycle**:
```
PARK → [dispatch] → travel empty → queue at loader → load →
       travel loaded → queue at crusher → dump → [repeat from crusher]
```

**Events**: `dispatch`, `edge_depart`, `loader_queue_join`, `load_start`, `load_end`, `crusher_queue_join`, `dump_start`, `dump_end`.

---

## Assumptions

1. Shortest travel-time path (Dijkstra) recalculated at each dispatch decision
2. Dispatching: nearest-available-loader with queue-length penalty
3. Service times: truncated-normal at zero (loading, dumping)
4. Travel time noise: lognormal multiplier with mean=1, CV=0.10 per edge
5. Trucks cycle pit↔crusher continuously (do not return to PARK between cycles)
6. Fleet scenarios use the first N trucks from `trucks.csv`
7. Loaders 100% available throughout shift; no breakdowns modelled
8. Shift cutoff is strict: only dumps completing before 480 min are counted

---

## Routing and Dispatching Logic

### Routing

NetworkX `shortest_path` with `travel_time_min` as the edge weight. Travel time for each edge is `distance_m / (max_speed_kph × 1000/60)` in minutes. Loaded trucks travel at 85% of edge speed; empty trucks travel at 100%.

Closed edges are removed from the graph before route-finding, so ramp-closed scenarios automatically reroute via available paths (the bypass: J2→J7→J8→J4).

If no path exists, the simulation raises a `ValueError` with a clear message rather than continuing silently.

### Dispatching

At each dispatch decision (just before travelling to a loader), the truck scores each available loader as:

```
score = travel_time_to_loader + len(loader_queue) × mean_load_time
```

The loader with the lowest score is selected. This approximates expected cycle time before production begins, balancing distance and congestion.

---

## Key Results

### Scenario Summary Table

| Scenario | Mean tonnes | 95% CI | t/h | Crusher util | Avg crusher queue |
|----------|-------------|--------|-----|-------------|------------------|
| baseline | 12,447 | [12,362–12,531] | 1,556 | 90.7% | 3.84 min |
| trucks_4 | 8,163 | [8,125–8,202] | 1,020 | 59.2% | 0.30 min |
| trucks_12 | 12,677 | [12,579–12,774] | 1,585 | 92.4% | 14.85 min |
| ramp_upgrade | 12,467 | [12,384–12,549] | 1,558 | 90.8% | 3.84 min |
| crusher_slowdown | 6,423 | [6,356–6,491] | 803 | 93.7% | 28.18 min |
| ramp_closed | 12,447 | [12,362–12,531] | 1,556 | 90.7% | 3.84 min |

*30 replications, 8-hour shift, base seed 12345.*

---

## Operational Decision Questions

### 1. What is the expected ore throughput during the baseline 8-hour shift?

**12,447 t ± 84 t (95% CI)**, equivalent to **1,556 t/h**.

Mean truck cycle time is 29.9 min. The crusher runs at 90.7% utilisation with an average queue wait of 3.84 min, indicating the crusher is the system's primary constraint.

### 2. What are the likely bottlenecks?

The **primary crusher** is the dominant bottleneck:
- Crusher utilisation: 90.7% in baseline
- Crusher queue wait: 3.84 min on average
- Adding 50% more trucks (trucks_12) increases crusher utilisation to 92.4% and queue wait to 14.85 min — confirming the crusher cannot absorb additional feed

Secondary constraints:
- Loader queue at L_N (North Pit, slower loader): 2.6 min average wait
- Single-lane pit face roads (E07, E09) cause minor queuing at loading faces

The **ramp** (E03_UP/E03_DOWN) is **not** a bottleneck in steady-state operation. See question 4 for explanation.

### 3. Does adding more trucks improve throughput, or does the system saturate?

**Adding trucks yields diminishing returns — the system is saturated at the crusher.**

| Fleet | Mean tonnes | Change vs baseline |
|-------|------------|-------------------|
| 4 trucks | 8,163 | −34.5% |
| 8 trucks (baseline) | 12,447 | — |
| 12 trucks | 12,677 | +1.8% |

Going from 4→8 trucks adds 4,284 t (+52%). Going from 8→12 trucks adds only 230 t (+1.8%). Crusher utilisation rises from 90.7% to 92.4% with 12 trucks, and queue wait more than triples (3.84→14.85 min). The system is effectively saturated; additional trucks only pile up at the crusher.

**Recommendation**: the fleet of 8 trucks is already at or past the point of efficient crusher utilisation. Investment in additional trucks is not justified without also increasing crusher throughput.

### 4. Would improving the narrow ramp materially improve throughput?

**No. Ramp upgrade yields only +0.2% throughput improvement (+20 t).**

Two structural reasons:

1. **The ramp is not on the steady-state cycle.** After their initial dispatch from PARK, trucks cycle between pit loading faces (above the ramp, at J3/J5/J6 level) and the crusher (via J4, also above the ramp base). The path LOAD_N→J5→J3→J4→CRUSH and CRUSH→J4→J3→J5→LOAD_N does not pass through J2 or the ramp. Only the first trip of each truck (PARK→loader) traverses the ramp section.

2. **The bypass is already faster.** The bypass route PARK→J1→J2→J7→J5→LOAD_N takes 9.9 min, compared to 10.3 min via the ramp (which is slow at 18 kph). So even in the baseline scenario, trucks prefer the bypass for their initial dispatch, and the ramp's capacity constraint never activates.

**Implication**: capital investment in ramp widening or road upgrade would not improve throughput in this model. The design assumption that the ramp is the "intended bottleneck" does not translate to a steady-state constraint given the cycle structure.

### 5. How sensitive is throughput to crusher service time?

**Highly sensitive. Doubling crusher service time halves throughput.**

| Crusher mean service | Mean tonnes | vs baseline |
|---------------------|------------|-------------|
| 3.5 min (baseline) | 12,447 t | — |
| 7.0 min (crusher_slowdown) | 6,423 t | −48.4% |

The crusher_slowdown scenario (7.0 min vs. 3.5 min mean service time) reduces throughput by 48%, with crusher queue wait rising from 3.84 to 28.18 min. Crusher utilisation rises to 93.7% and trucks spend most of their time waiting.

**Recommendation**: crusher reliability and service rate are the highest-leverage intervention point. Preventive maintenance schedules, wear liner replacement timing, and feed optimisation should be prioritised over fleet expansion.

### 6. What is the operational impact of losing the main ramp route?

**No measurable impact on throughput (0% change).**

As explained in question 4, trucks do not use the ramp in steady-state cycling. When the ramp is closed, the model automatically routes the initial dispatch via the bypass (J2→J7→J5), which is already the preferred route. The result is statistically identical to baseline.

**Caveat**: this finding depends critically on the model assumption that trucks do not return to PARK (and therefore through the ramp) between cycles. If operational procedures require trucks to check in at a dispatch point below the ramp between loads, the ramp would become a meaningful constraint. This is a model limitation worth investigating with actual operational data.

### Additional scenario: Loader upgrade at North Pit

Reducing LOAD_N service time from 6.5 min to 4.5 min (matching LOAD_S) would eliminate the loader queue imbalance. Given that the crusher is the binding constraint, the expected throughput gain is modest — but it would reduce the 2.6 min average loader queue wait, improving truck utilisation and cycle predictability.

---

## Bottleneck Summary

1. **Primary crusher** — 90.7% utilised, avg 3.84 min queue. Adding trucks worsens congestion. This is the binding constraint.
2. **North Pit loader (L_N)** — slower service (6.5 vs 4.5 min), causing loader queue imbalance. Trucks preferentially dispatch to L_S.
3. **Single-lane face roads** (E07, E09) — minor constraint; trucks occasionally queue for access to loading faces.
4. **Main ramp** — not active in steady-state cycle; not a bottleneck in this model.

---

## Model Limitations

- Trucks do not return to PARK between cycles; ramp bottleneck not exercised in steady state
- No truck breakdowns, maintenance, or fuel stops
- Loader availability assumed 100%
- Travel time noise is independent between edges (no correlated disruptions)
- All trucks have identical performance; no individual variation
- Dispatch uses queue length at moment of dispatch; does not anticipate en-route congestion
- Waste haulage not modelled; all trucking effort is directed to ore

---

## Suggested Further Scenarios

1. **loader_upgrade**: Reduce LOAD_N service time to 4.5 min — test whether loader speed is a secondary constraint
2. **crusher_capacity_2**: Model a second crusher or parallel dump point to quantify throughput ceiling
3. **mixed_fleet**: Introduce larger-payload trucks (e.g., 150 t) to test payload sensitivity
4. **return_to_park**: Require trucks to return to PARK between cycles to activate ramp bottleneck and validate ramp sensitivity assumptions
