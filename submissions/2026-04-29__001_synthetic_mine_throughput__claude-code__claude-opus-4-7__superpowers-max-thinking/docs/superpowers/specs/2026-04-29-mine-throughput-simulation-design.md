# Synthetic Mine Throughput Simulation — Design Spec

**Date:** 2026-04-29
**Submission:** `2026-04-29__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__superpowers-max-thinking`
**Benchmark:** `001_synthetic_mine_throughput`

## Goal

Build a discrete-event simulation in Python using SimPy that estimates ore throughput to the primary crusher over an 8-hour shift, runs six required scenarios with 30 replications each, and produces the required output artefacts (`conceptual_model.md`, `results.csv`, `summary.json`, `event_log.csv`, `README.md`).

The simulation must be reproducible (seeded), interpretable (event log + clear assumptions), and use the provided topology meaningfully (graph-based routing, not hard-coded paths).

## Architecture

### Module layout

```
mine_sim/
├── __init__.py
├── topology.py       # CSV loaders, NetworkX graph, scenario overrides, shortest paths
├── resources.py      # SimPy resource factory: loaders, crusher, paired-bidir road locks
├── truck.py          # Truck SimPy process (cycle: dispatch → travel → load → travel → dump → return)
├── scenario.py       # YAML loader with `inherits:` merging + override application
├── experiment.py     # Per-rep seeded run; aggregates results across replications
├── report.py         # results.csv, summary.json, event_log.csv, CI computation, bottleneck ranking
└── run.py            # CLI entry: `python -m mine_sim.run --scenario baseline ...`
```

Submission root holds `requirements.txt`, `README.md`, `conceptual_model.md`, and `results/` (per-scenario event logs plus aggregated `results.csv` and `summary.json`).

### Data flow per replication

1. `scenario.load_scenario("baseline")` — resolves `inherits:` chain, returns merged config.
2. `topology.build_graph(config)` — applies `edge_overrides` / `node_overrides`, drops `closed: true` edges, builds NetworkX `DiGraph`, computes all-pairs shortest paths weighted by travel-time (using empty-truck `max_speed_kph`).
3. `resources.build(env, config, graph)` — instantiates loaders, crusher, and road-lock `Resource`s.
4. `experiment.run_replication(seed)` — spawns one `Truck` SimPy process per truck, runs `env.run(until=480)`, returns metrics dict.
5. `report.aggregate(replications)` — emits CSVs, JSON, CIs, bottleneck ranking.

## Resources & contention model

### Resource inventory (per replication)

| Resource | Type | Capacity | Held during |
|---|---|---|---|
| `loader[L_N]`, `loader[L_S]` | `simpy.Resource` | 1 each | loading service time |
| `crusher` | `simpy.Resource` | 1 | dumping service time |
| `road_lock["RAMP"]` | `simpy.Resource` | 1 | E03_UP **or** E03_DOWN traversal |
| `road_lock["PIT_N"]` | `simpy.Resource` | 1 | E07_TO_LOAD_N **or** E07_FROM_LOAD_N |
| `road_lock["PIT_S"]` | `simpy.Resource` | 1 | E09_TO_LOAD_S **or** E09_FROM_LOAD_S |
| `road_lock["E05_TO"]` | `simpy.Resource` | 1 | E05_TO_CRUSH only |
| `road_lock["E05_FROM"]` | `simpy.Resource` | 1 | E05_FROM_CRUSH only |

### Edge → lock mapping

```python
EDGE_TO_LOCK = {
    "E03_UP":         "RAMP",   "E03_DOWN":         "RAMP",
    "E07_TO_LOAD_N":  "PIT_N",  "E07_FROM_LOAD_N":  "PIT_N",
    "E09_TO_LOAD_S":  "PIT_S",  "E09_FROM_LOAD_S":  "PIT_S",
    "E05_TO_CRUSH":   "E05_TO",
    "E05_FROM_CRUSH": "E05_FROM",
}
# All other edges are unconstrained (capacity=999, no lock).
```

This is the **hybrid (option C)** policy: ramp E03 and pit accesses E07/E09 are paired bidirectional locks (one truck on the physical road regardless of direction — supported by the edges.csv metadata note "same physical constraint simplified as separate edge"). Crusher approach E05 keeps per-direction locks (treated as a queueing lane, not a one-lane road).

### Override interactions

- `ramp_upgrade` sets `E03_UP/DOWN.capacity = 999`, `max_speed_kph = 28` → the RAMP lock is **not instantiated** (the resource factory only creates locks for edges with effective capacity == 1).
- `ramp_closed` sets `E03_UP/DOWN.closed = true` → edges dropped from graph before Dijkstra. Bypass route J2→J7→J8→J4 becomes shortest path automatically. RAMP lock unused.

### Traversal protocol

```python
def traverse(env, edge, truck):
    lock = EDGE_TO_LOCK.get(edge.id)   # may be None
    speed = effective_speed(truck, edge, rng)   # see speed model
    travel_time_min = (edge.distance_m / 1000.0) / speed * 60.0
    if lock is not None:
        with road_locks[lock].request() as req:
            t_request = env.now
            yield req
            metrics.record_road_wait(lock, env.now - t_request)
            yield env.timeout(travel_time_min)
    else:
        yield env.timeout(travel_time_min)
```

### Speed model

- Base speed = `edge.max_speed_kph * (truck.loaded_speed_factor if loaded else truck.empty_speed_factor)`
- Per-traversal noise factor `f ~ Normal(1.0, 0.10)`, drawn once per truck per edge per traversal
- Effective speed = `max(0.1 * edge.max_speed_kph, base * f)` (floor at 10% of edge max to prevent pathological tails)
- Travel time minutes = `(distance_m / 1000) / speed_kph * 60`

### Stochastic service times

Loading and dumping draws use `Normal(mean, sd)` truncated to `[0.1, mean + 5*sd]`. The 0.1-minute floor prevents negative or zero draws; the +5σ cap prevents runaway tails. One independent draw per service event.

### Bottleneck metrics per resource

- Cumulative busy time → `utilisation = busy_time / shift_minutes`
- Cumulative queue-wait time + queue-entry count → `avg_queue_wait_min`
- Max queue length observed (sampled at request entry)
- **Bottleneck score** = `utilisation * avg_queue_wait_min` (higher = worse)

`top_bottlenecks` reports the ranked list `[{resource_id, utilisation, avg_queue_wait_min, score}]`.

## Truck process & dispatching

### Truck state machine (one SimPy process per truck)

```
[IDLE] → choose_loader → [TRAVELLING_EMPTY] → [QUEUED_AT_LOADER] → [LOADING]
       → [TRAVELLING_LOADED] → [QUEUED_AT_CRUSHER] → [DUMPING] → [IDLE]
```

The process loops until `env.now >= shift_minutes`. A truck mid-cycle at shift end completes its current state transition (no mid-traversal kill) but its in-progress dump is **not counted** if not finished by `shift_minutes`. (Throughput is attributed at `dumping_ended` time only.)

### Dispatcher: `choose_loader(truck, current_node, sim)`

Implements `nearest_available_loader` with `shortest_expected_cycle_time` tiebreaker (per `baseline.yaml`):

```python
def choose_loader(truck, current_node, sim):
    candidates = []
    for loader in [L_N, L_S]:
        path_to_loader  = sim.shortest_paths[current_node][loader.node_id]
        path_to_crusher = sim.shortest_paths[loader.node_id]["CRUSH"]
        travel_to       = sum_nominal_travel(path_to_loader, loaded=False)
        travel_loaded   = sum_nominal_travel(path_to_crusher, loaded=True)
        queue_wait_est  = loader.queue_count() * loader.mean_load_time_min
        expected_cycle  = (travel_to + queue_wait_est + loader.mean_load_time_min
                           + travel_loaded + crusher.mean_dump_time_min)
        candidates.append((expected_cycle, loader.id, loader))
    candidates.sort()   # deterministic tiebreak by id
    return candidates[0][2]
```

Decision happens **once per cycle**, when the truck becomes idle. No mid-trip rerouting. Path is pre-computed; only loader choice is dynamic.

### Topology-failure mode

If `nx.shortest_path` raises `NetworkXNoPath` for any (current_node, loader) or (loader, CRUSH) pair, the simulation aborts with a `TopologyError` listing the unreachable pair. Per the prompt: "If a route is impossible because of the topology, the model should fail clearly rather than silently producing misleading results."

### Event log emission

Per the prompt's required schema (columns: `time_min, replication, scenario_id, truck_id, event_type, from_node, to_node, location, loaded, payload_tonnes, resource_id, queue_length`).

Event types: `truck_dispatched`, `traversal_started`, `traversal_ended`, `road_lock_requested`, `road_lock_acquired`, `loader_requested`, `loading_started`, `loading_ended`, `crusher_requested`, `dumping_started`, `dumping_ended`.

**`dumping_ended` at CRUSH is the throughput-recording event** — `payload_tonnes` is added to the cumulative total at this point.

### Default event log policy

The combined `results/event_log.csv` contains **all events for replication 0 of every scenario**, plus only `dumping_ended` events for replications 1–29 across all scenarios. This keeps file size manageable (~10⁵ rows) while preserving full traceability for one canonical replication per scenario. Per-scenario full traces of replication 0 are also written to `results/{scenario_id}__event_log.csv` for inspection. Documented in README.

## Scenarios, experiment & replications

### YAML loader (`scenario.py`)

```python
def load_scenario(scenario_id, scenarios_dir):
    raw = yaml.safe_load(open(scenarios_dir / f"{scenario_id}.yaml"))
    if "inherits" in raw:
        parent = load_scenario(raw["inherits"], scenarios_dir)
        merged = deep_merge(parent, raw)
    else:
        merged = raw
    merged.pop("inherits", None)
    return merged
```

`deep_merge`: recursive — child dicts merge into parent dicts; child scalars/lists fully replace parent values.

### Override application

- `edge_overrides[edge_id]` patches `capacity`, `max_speed_kph`, `closed` on that edge before graph build.
- `node_overrides[node_id]` patches node `service_time_mean_min`, `service_time_sd_min`.
- `dump_point_overrides[dump_id]` patches dump-resource service time.
- `loader_overrides[loader_id]` reserved for future scenarios.

### Seed control

```python
def run_replication(config, replication_idx):
    seed = config["simulation"]["base_random_seed"] + replication_idx
    rng = np.random.default_rng(seed)
    env = simpy.Environment()
    sim = Simulation(env, config, rng)
    sim.start()
    env.run(until=config["simulation"]["shift_length_hours"] * 60)
    return sim.collect_metrics(seed=seed, replication=replication_idx)
```

One `numpy.random.Generator` per replication, threaded through every stochastic draw. Reproducibility test: same `base_random_seed` + same `replication_idx` → bit-identical event log. Verified before completion.

### Replication driver

Replications run sequentially (no parallelism — runtime budget is small enough that parallelism adds complexity without benefit; documented).

### CLI entry (`run.py`)

```bash
python -m mine_sim.run                          # all 6 required scenarios
python -m mine_sim.run --scenario baseline      # single scenario
python -m mine_sim.run --replications 5         # smoke test override
python -m mine_sim.run --output-dir results/
python -m mine_sim.run --plot-topology          # writes topology.png
```

### Output assembly

- `results.csv`: one row per `(scenario_id, replication)`. Columns per prompt §results.csv: `scenario_id, replication, random_seed, total_tonnes_delivered, tonnes_per_hour, average_truck_cycle_time_min, average_truck_utilisation, crusher_utilisation, average_loader_queue_time_min, average_crusher_queue_time_min`. Plus optional `loader_L_N_utilisation`, `loader_L_S_utilisation`, `ramp_utilisation`.
- `summary.json`: schema per prompt with means + 95% CIs (Student-t, df = n-1) + per-loader utilisation + ranked `top_bottlenecks` + top-level `key_assumptions`, `model_limitations`, `additional_scenarios_proposed`.
- `event_log.csv`: combined trace per the policy above.

### 95% CI computation

```python
mean = np.mean(values)
sem  = np.std(values, ddof=1) / np.sqrt(n)
half = sem * scipy.stats.t.ppf(0.975, df=n-1)
ci   = (mean - half, mean + half)
```

## Analysis & operational decisions

### Mapping of decision questions to model outputs

| # | Question | Method |
|---|---|---|
| 1 | Expected baseline throughput | `summary.baseline.tonnes_per_hour_mean` ± CI |
| 2 | Likely bottlenecks | `top_bottlenecks` ranking |
| 3 | Does adding trucks help? | Compare `tonnes_per_hour_mean` across `trucks_4`/`baseline`/`trucks_12`; CI overlap test for saturation; report marginal tonnes/h per truck |
| 4 | Ramp upgrade payoff? | Compare `baseline` vs `ramp_upgrade`; CI separation + bottleneck shift |
| 5 | Crusher service-time sensitivity | Compare `baseline` vs `crusher_slowdown` (3.5 → 7.0 min); % throughput change + crusher-utilisation shift |
| 6 | Losing main ramp | Compare `baseline` vs `ramp_closed`; % throughput loss + new bottleneck under bypass routing |

### Optional 7th scenario

`loader_n_upgrade` — reduce LOAD_N mean load time from 6.5 to 4.5 min (matching LOAD_S). Tests whether the slower northern loader is binding independently of the ramp. Decision to run depends on whether baseline bottleneck ranking points at L_N. Either way, the scenario is listed in `summary.json.additional_scenarios_proposed` (as proposed-and-run, or proposed-but-not-run, with rationale).

## Deliverables (artefacts the implementation must produce)

Required:
- `conceptual_model.md` — all sections per prompt §conceptual_model
- `results.csv` — per-(scenario, replication) rows with all required columns
- `summary.json` — per-scenario summary with CIs + assumptions/limitations/proposals
- `event_log.csv` — combined trace per logging policy
- `README.md` — all 11 prompt-mandated sections
- `mine_sim/` — Python package per architecture
- `requirements.txt`

Optional:
- `topology.png` — generated if time allows; not at the expense of correctness.

## Reproducibility verification

Before declaring complete: re-run baseline twice, diff `event_log.csv` for replication 0 — must be byte-identical. Documented in README under "How to reproduce."

## Key design decisions (locked in)

1. **Hybrid road-lock policy (option C)**: paired-bidirectional locks for ramp/pit-access; per-direction locks for crusher approach.
2. **Pre-computed shortest-path routing + dynamic loader choice (option C)**: travel-time-weighted Dijkstra at scenario load; loader picked per cycle by `nearest_available_loader` + `shortest_expected_cycle_time` tiebreaker.
3. **Strict `normal_truncated` stochasticity (option C)**: `Normal(mean, sd)` truncated to `[0.1, mean+5σ]` for load/dump; multiplicative `Normal(1.0, 0.10)` per-edge-per-traversal travel noise.
4. **Modular package layout (option B)**: 7-module `mine_sim/` package + thin CLI.
