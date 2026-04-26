# Synthetic mine throughput simulation

Discrete-event simulation of an 8-hour ore haulage shift, built with **SimPy**.
Reads the provided topology and scenario data, runs 30 replications per
scenario with controlled random seeds, and produces machine-readable outputs
plus answers to the operational decision questions.

## 1. Install

```bash
python3 -m pip install -r requirements.txt
```

Tested with Python 3.11 / 3.13. Dependencies: `simpy`, `numpy`, `pandas`,
`scipy`, `networkx`, `pyyaml`, `matplotlib`.

## 2. Run

From the submission directory:

```bash
python3 run.py                    # the six required scenarios
python3 run.py --extras           # also runs the optional trucks_10 scenario
python3 run.py --scenarios baseline   # any subset by name
python3 plot_topology.py          # regenerate topology.png
```

Outputs land in the submission directory:

| File | Contents |
|---|---|
| `results.csv` | One row per (scenario, replication) with all metrics |
| `summary.json` | Scenario-level mean + 95 % CI summaries, key assumptions, limitations |
| `event_log.csv` | Per-event trace (1 replication captured per scenario by default) |
| `topology.png` | Static topology diagram with constrained lanes highlighted |

Reproducing a single scenario after the fact:

```bash
python3 -m src.experiment           # not a CLI; use run.py instead
python3 run.py --scenarios baseline trucks_12
```

Random seeds: `seed = base_random_seed + replication_index` where
`base_random_seed = 12345` is set in `data/scenarios/baseline.yaml`. All 30
replications are reproducible from those seeds.

## 3. Conceptual model

Full description in [`conceptual_model.md`](./conceptual_model.md). Key
elements:

- **Entities**: trucks (homogeneous, 100 t payload).
- **Resources**: 2 loaders (`L_N`, `L_S`), 1 crusher (`D_CRUSH`), and a SimPy
  `Resource` for every capacity-constrained lane in the road graph.
- **Routing**: NetworkX shortest-time path on the directed graph; closed edges
  are dropped before routing so blocked routes fail loudly.
- **Dispatching**: `nearest_available_loader` with shortest expected cycle
  time as tie-breaker.

## 4. Main assumptions

- Loading and dumping times are normal-truncated using means/SDs from the
  data; travel times are nominal distance/speed multiplied by a lognormal
  noise factor (CV = 0.10).
- Edges with `capacity < 999` model single-lane segments. Edges sharing a
  lane prefix (e.g. `E03_UP` and `E03_DOWN`) share one physical-lane
  resource.
- Trucks dispatch immediately at `t = 0` from PARK, do not refuel, and do
  not break down.
- Throughput is counted only on completed `dump_end` events at CRUSH within
  the shift.
- See `summary.json → key_assumptions` and `model_limitations` for the full
  list.

## 5. Routing and dispatching

The graph is built once per scenario from `nodes.csv` and `edges.csv` after
applying scenario edge/node overrides. Edge weights are the mean of the
empty and loaded nominal travel times. Closed edges are removed.

For each cycle, the truck:

1. Picks the loader whose expected cycle time (travel + load + travel-to-
   crusher + dump + queue penalty) is shortest. Idle loaders are preferred
   over busy ones.
2. Walks the shortest-time path edge by edge. On a constrained lane it
   `request`s the corresponding `simpy.Resource` and holds it for the
   travel time before releasing.
3. Loads, hauls, queues, dumps, then loops.

If `data/scenarios/<scenario>.yaml` closes an edge that breaks all paths to
the target, the simulation raises `RuntimeError("No path from X to Y in
current topology")` rather than silently completing.

## 6. Key results

Mean values across 30 replications (95 % CI in brackets where shown).

| Scenario | Trucks | Tonnes / shift | Tonnes / hour | Cycle (min) | Crusher util | Loader L_N | Loader L_S |
|---|---:|---:|---:|---:|---:|---:|---:|
| baseline          |  8 | 12 053 [11 999, 12 107] | 1 506.7 | 30.8 | 0.88 | 0.58 | 0.77 |
| trucks_4          |  4 |  7 507 [ 7 474,  7 539] |   938.3 | 24.9 | 0.55 | 0.31 | 0.51 |
| trucks_12         | 12 | 12 850 [12 767, 12 933] | 1 606.2 | 42.9 | 0.93 | 0.63 | 0.84 |
| ramp_upgrade      |  8 | 12 003 [11 949, 12 057] | 1 500.4 | 31.0 | 0.88 | 0.57 | 0.77 |
| crusher_slowdown  |  8 |  6 483 [ 6 424,  6 542] |   810.4 | 55.7 | 0.94 | 0.32 | 0.45 |
| ramp_closed       |  8 | 11 953 [11 901, 12 006] | 1 494.2 | 31.1 | 0.87 | 0.57 | 0.76 |
| trucks_10 (extra) | 10 | 12 787 [12 696, 12 878] | 1 598.3 | 36.2 | 0.93 | 0.61 | 0.83 |

## 7. Operational decision questions

### Q1. Expected baseline throughput
**~12 050 tonnes per shift (≈1 507 t/h), 95 % CI [11 999, 12 107].** This is
the mean across 30 independent replications with the 8-truck fleet.

### Q2. Likely bottlenecks
The **crusher (88 % utilisation)** is the dominant bottleneck under the
baseline. The single-lane crusher approach (`E05`, 74 % utilisation) and the
South Pit face access (`E09`, 74 %) are the next constraints. Loader `L_S`
runs at 77 % because the dispatcher prefers it (shorter cycle). At
`trucks_12`, crusher utilisation hits 93 % and `E09` rises to 82 % — the
crusher is the wall.

### Q3. Does adding trucks help?
Diminishing returns. Going from 4 → 8 trucks adds ~4 547 t/shift (+60 %).
Going 8 → 10 adds only ~733 t (+6 %), and 10 → 12 adds another ~63 t
(<0.5 %). The system is essentially saturated by ~10 trucks; beyond that the
extra trucks queue at the crusher and the loaders.

### Q4. Would improving the narrow ramp help?
**No — within rounding of zero (12 003 vs 12 053 t/shift, well inside the CI
overlap).** The ramp `E03` is only used for the *initial* dispatch from PARK
to the South Pit; the steady-state cycle goes pit → J3 → J4 → CRUSH and
back, never re-traversing the ramp. The bypass via J7/J8 is also faster
than the ramp for North Pit dispatch, so empirically the ramp is not on the
hot path. Capital spent on the ramp upgrade in this configuration would
**not** materially improve throughput.

### Q5. Sensitivity to crusher service time
Doubling the mean dump time from 3.5 to 7.0 min (the `crusher_slowdown`
scenario) reduces throughput from ~12 053 to ~6 483 t/shift, a drop of
**~46 %**. Crusher utilisation actually *rises* (94 %), confirming it is the
binding constraint. Throughput is therefore highly sensitive to crusher
service time — roughly inversely proportional, as expected for a saturated
single-server bottleneck.

### Q6. Operational impact of losing the main ramp
Closing `E03_UP/E03_DOWN` reduces baseline throughput by only ~100 t/shift
(0.8 %), within the 95 % CI of baseline. The bypass `J2 → J7 → J8 → J4`
plus the lateral connectors `J7 ↔ J5` and `J8 ↔ J6` provide a workable
alternative for initial dispatch to either pit. Operators could lose the
main ramp for the shift with negligible production impact.

### Optional extra scenario (proposed)
`trucks_10`: an interpolated fleet point between 8 and 12 trucks. It
confirms that saturation begins between 8 and 10 trucks; adding the
last two trucks beyond 10 yields essentially zero additional throughput.

## 8. Likely bottlenecks (top 3 by utilisation)

| Scenario | 1 | 2 | 3 |
|---|---|---|---|
| baseline | crusher (0.88) | loader L_S (0.77) | lane E05 (0.74) |
| trucks_4 | crusher (0.55) | loader L_S (0.51) | lane E09 (0.49) |
| trucks_12 | crusher (0.93) | loader L_S (0.84) | lane E09 (0.82) |
| ramp_upgrade | crusher (0.88) | loader L_S (0.77) | lane E09 (0.75) |
| crusher_slowdown | crusher (0.94) | loader L_S (0.45) | lane E09 (0.43) |
| ramp_closed | crusher (0.87) | loader L_S (0.76) | lane E09 (0.74) |

## 9. Limitations

See `summary.json → model_limitations` for the canonical list. The most
material ones for interpreting these results:

- No truck breakdowns or maintenance — real-world availability will be
  lower, so the absolute tonnage figures should be treated as theoretical
  upper bounds for the modelled configuration.
- Routing is static; in reality dispatchers will sometimes re-route trucks
  to balance queues. The model therefore likely *under-states* the
  benefit of better dispatching and *over-states* the impact of static
  bottlenecks.
- The crusher is modelled as a single-server resource; in practice the
  feed bin and downstream conveyor introduce additional buffering.
- Open haul roads have no congestion model; on a real site, a 12-truck
  fleet would slow down somewhat even on wide haul roads.

## 10. Suggested improvements / further scenarios

- **Reduce crusher service time** (e.g. through a feed-bin upgrade or chute
  redesign): the model says this is the only intervention that materially
  raises throughput.
- **Crusher availability scenarios**: model crusher MTBF/MTTR. With the
  crusher already saturated, even short downtimes will translate
  directly into lost tonnes.
- **Loader re-balancing**: shifting some demand from `L_S` to `L_N` (or
  upgrading `L_S` to a faster bucket) would reduce the secondary
  bottleneck.
- **Buffer / stockpile**: add a surge stockpile between trucks and
  crusher to decouple haulage variability from the crusher.
- **Mixed fleet**: introduce a faster, smaller truck class to fill the
  small operational gaps.
