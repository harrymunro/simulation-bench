# Synthetic Mine Throughput Simulation

> Benchmark `001_synthetic_mine_throughput` — SimPy discrete-event simulation of
> ore haulage from `PARK` to the primary crusher over an 8-hour shift, with seven
> scenarios and 30 replications each.

This submission implements the requirements in [`prompt.md`](./prompt.md) under
the package `src/mine_sim/`. The conceptual model is described in
[`conceptual_model.md`](./conceptual_model.md); the canonical numerical outputs
are at [`results.csv`](./results.csv), [`summary.json`](./summary.json), and
[`event_log.csv`](./event_log.csv); a topology figure is at
[`topology.png`](./topology.png) and a one-replication animation is at
[`animation.gif`](./animation.gif).

---

## 1. Repository layout

```text
.
├── data/                       # Input CSVs + scenario YAMLs (read-only)
│   ├── nodes.csv
│   ├── edges.csv
│   ├── trucks.csv
│   ├── loaders.csv
│   ├── dump_points.csv
│   └── scenarios/
│       ├── baseline.yaml
│       ├── trucks_4.yaml
│       ├── trucks_12.yaml
│       ├── ramp_upgrade.yaml
│       ├── crusher_slowdown.yaml
│       ├── ramp_closed.yaml
│       └── trucks_12_ramp_upgrade.yaml   # combo (proposed extra)
├── src/mine_sim/               # Implementation package
│   ├── __main__.py             # `python -m mine_sim` entry point
│   ├── cli.py                  # argparse CLI (run / run-all / list)
│   ├── scenarios.py            # YAML loader (inheritance, overrides)
│   ├── topology.py             # nodes/edges -> immutable Topology graph
│   ├── routing.py              # Dijkstra shortest-time + reachability check
│   ├── runner.py               # one SimPy replication
│   ├── scenario_runner.py      # batch replications per scenario
│   ├── model.py                # SimPy processes (truck cycle, loaders, crusher)
│   ├── events.py               # EventRecord schema
│   ├── metrics.py              # per-replication KPI rollups
│   ├── aggregate.py            # cross-replication Student-t CI summary
│   ├── rng.py                  # seed pinning + truncated/lognormal samplers
│   └── io_writers.py           # results.csv / event_log.csv / summary.json
├── scripts/                    # Auxiliary visualisations and post-processing
│   ├── render_topology.py      # generates topology.png
│   ├── render_animation.py     # generates animation.gif from an event log
│   └── refresh_summary_narrative.py
├── tests/                      # pytest suite (unit + integration)
├── runs/                       # CLI output artefacts (gitignored content)
│   ├── ac2_run_all/            # Canonical run that produced top-level CSVs
│   └── ac7_combo/              # Combo-scenario run
├── results.csv                 # Top-level: 7 scenarios × 30 reps = 210 rows
├── summary.json                # Top-level: cross-replication summary
├── event_log.csv               # Top-level: every event from every replication
├── conceptual_model.md         # Modelling-and-simulation conceptual model
├── topology.png                # Static rendering of the mine graph
├── animation.gif               # Animated single replication
├── seed.yaml                   # Seed contract (goal, constraints, ACs)
├── submission.yaml             # Submission metadata
├── prompt.md                   # Original benchmark brief
└── pytest.ini                  # `pythonpath = src`
```

---

## 2. Install

### 2.1 Requirements

- **Python 3.11+** (developed and tested on 3.11; type hints use PEP 604 unions)
- A POSIX-style shell (`bash`, `zsh`)
- ~50 MB of free disk for `event_log.csv` (≈30 MB on the canonical run)

### 2.2 Allowed dependencies

Per the Seed constraints, the simulation uses **only** the following libraries
(all installable from PyPI):

| Package | Used for |
|---|---|
| `simpy` | Discrete-event simulation engine (Resources, Environments, processes) |
| `numpy` | RNG streams (`numpy.random.Generator`) and array maths |
| `pandas` | Reading/writing CSVs, results aggregation |
| `scipy` | Student-t critical values for 95% CIs (`scipy.stats.t`) |
| `matplotlib` | `topology.png` and `animation.gif` rendering |
| `networkx` | Dijkstra shortest-time routing on the topology graph |
| `pyyaml` | Scenario YAML loading |

Test-only extras: `pytest`.

### 2.3 Clean-environment install

From a fresh checkout of this submission folder:

```bash
# 1. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 2. Upgrade pip and install the allowed runtime dependencies
pip install --upgrade pip
pip install simpy numpy pandas scipy matplotlib networkx pyyaml

# 3. (Optional) install pytest for the test suite
pip install pytest
```

Equivalently, the submission ships a [`pyproject.toml`](./pyproject.toml) and a
pinned [`requirements.txt`](./requirements.txt), so a one-shot install also
works:

```bash
pip install --upgrade pip
pip install -r requirements.txt   # exact pins (matches shipped artefacts)
pip install -e .                  # registers `python -m mine_sim`
```

When installed via `pip install -e .` the `PYTHONPATH=src` prefix is no longer
needed — `python -m mine_sim run-all` just works. To reproduce the shipped
`results.csv`, `summary.json`, and `event_log.csv` byte-for-byte from a clean
virtual environment in one command, run
[`scripts/verify_reproducibility.sh`](./scripts/verify_reproducibility.sh).

### 2.4 Smoke test

Verify the install with a fast end-to-end check (one replication of the baseline
scenario, ~1 s on a laptop):

```bash
PYTHONPATH=src python -m mine_sim run baseline --reps 1 --quiet \
  --output-dir runs/_smoke
```

Expected output: a non-empty `runs/_smoke/results.csv`, `event_log.csv`, and
`summary.json` for `scenario_id=baseline`.

To run the full pytest suite (unit + integration):

```bash
PYTHONPATH=src pytest -q
```

---

## 3. Run

The package exposes a single CLI entry point — `python -m mine_sim` — with three
subcommands: `run` (one scenario), `run-all` (every required scenario), and
`list` (enumerate available scenarios).

### 3.1 List available scenarios

```bash
PYTHONPATH=src python -m mine_sim list
```

Marks the seven canonical scenarios with `*`; lists each scenario's replication
count, truck count, and description. Scenarios live under `data/scenarios/` and
are loaded by `mine_sim.scenarios.load_scenario`.

### 3.2 Run a single scenario

```bash
# Default: 30 replications, output under runs/<scenario_id>/
PYTHONPATH=src python -m mine_sim run baseline

# Smoke test: one replication, custom output directory
PYTHONPATH=src python -m mine_sim run baseline --reps 1 --output-dir runs/dev

# Run a specific replication index (e.g. for debugging a single trace)
PYTHONPATH=src python -m mine_sim run baseline --rep-indices 7 \
  --output-dir runs/rep7
```

Per-scenario artefacts are written to `<output-dir>/<scenario_id>/`:

- `results.csv` — one row per replication (KPI columns per Seed AC 2)
- `event_log.csv` — every `EventRecord` from every replication for that scenario
- `summary.json` — cross-replication `ScenarioSummary` with Student-t 95% CIs

CLI flags (all `run`/`run-all` share the same shape):

| Flag | Default | Notes |
|---|---|---|
| `--data-dir DIR` | `./data` | Directory holding `nodes.csv`, `edges.csv`, etc. |
| `--scenarios-dir DIR` | `./data/scenarios` | Directory holding `*.yaml` scenarios |
| `--output-dir DIR` | `./runs/<scenario_id>` (run) / `./runs/<UTC>__run_all` (run-all) | Override target directory |
| `--reps N` | YAML value (30) | Override replication count for fast iteration |
| `--rep-indices "0,3,5"` | (none) | Run an explicit subset of indices; overrides `--reps` |
| `--quiet` | off | Suppress per-replication progress lines |

### 3.3 Run every required scenario (canonical batch)

```bash
PYTHONPATH=src python -m mine_sim run-all
```

This runs all seven scenarios listed in
`mine_sim.scenarios.REQUIRED_SCENARIO_IDS`:

1. `baseline` (8 trucks, baseline ramp)
2. `trucks_4`
3. `trucks_12`
4. `ramp_upgrade`
5. `crusher_slowdown`
6. `ramp_closed`
7. `trucks_12_ramp_upgrade` (combo — the proposed seventh scenario)

Each runs with **30 replications** under reproducible seeds. Output structure:

```text
runs/<UTC-timestamp>__run_all/
├── results.csv          # 210 rows (7 scenarios × 30 reps)
├── event_log.csv        # all events from all replications
├── summary.json         # one entry per scenario + top-level narrative fields
├── baseline/
│   ├── results.csv
│   ├── event_log.csv
│   └── summary.json
├── trucks_4/...
├── trucks_12/...
├── ramp_upgrade/...
├── crusher_slowdown/...
├── ramp_closed/...
└── trucks_12_ramp_upgrade/...
```

To run a subset only (e.g. for a focused experiment):

```bash
PYTHONPATH=src python -m mine_sim run-all \
  --scenario-ids "baseline,ramp_upgrade,trucks_12_ramp_upgrade"
```

### 3.4 Generate visualisations

These are **not** part of the simulation engine and live under `scripts/`:

```bash
# Render the static topology figure
PYTHONPATH=src python scripts/render_topology.py \
  --data-dir data --out topology.png

# Render an animation from a replication's event_log.csv
PYTHONPATH=src python scripts/render_animation.py \
  --data-dir data --event-log runs/ac2_run_all/baseline/event_log.csv \
  --replication 0 --out animation.gif
```

Both scripts read pre-existing data and event-log files; they never invoke the
simulation themselves, which keeps animation generation cheap and decoupled
from a re-run.

---

## 4. Reproduce

### 4.1 The canonical numbers in `results.csv` / `summary.json`

The top-level files at the repository root were produced by the canonical
`run-all` command and copied up:

```bash
# 1. Activate the venv from §2.3
source .venv/bin/activate

# 2. Reproduce the canonical run (≈30–60 s on a modern laptop)
PYTHONPATH=src python -m mine_sim run-all --output-dir runs/ac2_run_all

# 3. Promote the canonical artefacts to the repository root
cp runs/ac2_run_all/results.csv     ./results.csv
cp runs/ac2_run_all/event_log.csv   ./event_log.csv
cp runs/ac2_run_all/summary.json    ./summary.json
```

The values in `results.csv` and `summary.json` are **bit-identical** across
runs on the same Python + NumPy version because the model uses pinned per-stream
RNGs (see §4.3). The hash in `event_log.csv` is identical too, modulo Python
floating-point determinism (NumPy guarantees same-seed determinism on a fixed
platform).

### 4.2 Reproduce a single decision question

To rebuild only the artefacts that answer a particular operational question
without paying for all seven scenarios:

```bash
# Q1: baseline expected throughput
PYTHONPATH=src python -m mine_sim run baseline

# Q3: does adding more trucks help?
PYTHONPATH=src python -m mine_sim run-all \
  --scenario-ids "baseline,trucks_4,trucks_12"

# Q4 + Q6: ramp interventions (upgrade vs closed)
PYTHONPATH=src python -m mine_sim run-all \
  --scenario-ids "baseline,ramp_upgrade,ramp_closed"

# Q5: crusher sensitivity
PYTHONPATH=src python -m mine_sim run-all \
  --scenario-ids "baseline,crusher_slowdown"

# "Combo" question (proposed scenario): does trucks_12 only pay off after the upgrade?
PYTHONPATH=src python -m mine_sim run-all \
  --scenario-ids "baseline,trucks_12,ramp_upgrade,trucks_12_ramp_upgrade"
```

### 4.3 Seed and reproducibility notes

The simulation is **fully deterministic given a fixed Python + NumPy
version on a fixed CPU**. The contract is:

1. Each scenario YAML carries a `simulation.base_random_seed` (default `12345`
   for `baseline`; some scenarios override).
2. **Per-replication seed = `base_random_seed + replication_index`**. This is
   the value persisted as the `random_seed` column in `results.csv`. So
   replication 0 of `baseline` always uses seed `12345`, replication 1 uses
   `12346`, etc. Source: `mine_sim.rng.replication_seed` and
   `mine_sim.runner.run_replication`.
3. The replication seed is used to spawn a `numpy.random.Generator` (PCG64
   under the hood); from that we derive **independent named streams** via
   `Generator.spawn` for each stochastic primitive: edge travel-time noise,
   loader service time, crusher dump time, and dispatching tie-breakers. See
   `mine_sim.rng.STREAM_NAMES` and `make_replication_rng`.
4. SimPy itself does no internal RNG calls — every random draw is requested
   from one of those named streams, which means re-running with the same seed
   reproduces *the same event sequence* as well as the same KPIs.
5. The reachability self-check at scenario load (`mine_sim.routing.assert_reachable`)
   runs *before* any RNG draws, so a topology error fails loudly without
   touching the simulation state.

To verify determinism locally:

```bash
PYTHONPATH=src python -m mine_sim run baseline --rep-indices 0 \
  --output-dir runs/repro_a --quiet
PYTHONPATH=src python -m mine_sim run baseline --rep-indices 0 \
  --output-dir runs/repro_b --quiet
diff runs/repro_a/baseline/results.csv runs/repro_b/baseline/results.csv
diff runs/repro_a/baseline/event_log.csv runs/repro_b/baseline/event_log.csv
```

Both diffs should be empty.

### 4.4 Reproducing the figures

```bash
# topology.png — purely a function of data/nodes.csv + data/edges.csv
PYTHONPATH=src python scripts/render_topology.py \
  --data-dir data --out topology.png

# animation.gif — function of one replication's event log
PYTHONPATH=src python scripts/render_animation.py \
  --data-dir data \
  --event-log runs/ac2_run_all/baseline/event_log.csv \
  --replication 0 \
  --out animation.gif
```

The animation script is single-replication by design (it reads
`replication == <index>` rows from the event log) so it's stable and cheap to
re-render.

### 4.5 Test suite

```bash
PYTHONPATH=src pytest -q                  # full suite
PYTHONPATH=src pytest -q tests/test_runner.py  # determinism + reachability
PYTHONPATH=src pytest --cov=src --cov-report=term-missing
```

Notable tests covering reproducibility:

- `test_runner.py::test_run_replication_is_deterministic` — same seed, same
  KPIs, same event ordering.
- `test_runner.py::test_different_replication_indices_produce_different_outputs`
  — distinct seeds produce distinct outputs (sanity check that the seed is
  actually wired through).
- `test_runner.py::test_reachability_required_od_pairs_all_scenarios` —
  parametric across all seven scenarios; ensures every required `(origin,
  destination)` pair is reachable under the scenario's edge closures.
- `test_rng.py` — verifies stream isolation, truncation floors, and lognormal
  multiplier mean/cv.

---

## 5. Conceptual model summary

This is a one-screen summary of the model. The full specification — system
boundary, entities, resources, events, state variables, performance measures,
and limitations — lives in [`conceptual_model.md`](./conceptual_model.md);
this section is the executive briefing that makes the rest of the README
self-contained.

### 5.1 System boundary

**Inside** the boundary: the ore production cycle
`PARK -> LOAD_{N|S} -> CRUSH -> LOAD_{N|S} -> ...` for every truck, expressed
as travel, queue, load, and dump events on the directed graph in
`data/edges.csv`. Specifically:

- **Trucks** (4 / 8 / 12, scenario-dependent) — entities with payload 100 t,
  empty/loaded speed factors `1.00 / 0.85`, all starting at `PARK`.
- **Two loaders** `L_N` (mean 6.5 min, sd 1.2) and `L_S` (mean 4.5 min,
  sd 1.0), each capacity 1.
- **Single crusher** `D_CRUSH` (mean 3.5 min, sd 0.8), capacity 1.
- **Eight capacity-1 directed edge resources**: `E03_UP`, `E03_DOWN`,
  `E05_TO_CRUSH`, `E05_FROM_CRUSH`, `E07_TO_LOAD_N`, `E07_FROM_LOAD_N`,
  `E09_TO_LOAD_S`, `E09_FROM_LOAD_S` — modelled literally per the CSV as
  independent SimPy `Resource` objects (one per direction).
- **Stochastic effects**: per-edge-traversal lognormal travel multiplier
  (mean 1, cv 0.10); normal-truncated load and dump times.
- **Static shortest-time routing** per `(scenario, origin, destination)`
  computed by Dijkstra on free-flow times, recomputed when a scenario
  changes the edge set.
- **Dispatch policy**: an empty truck picks the loader minimising
  `travel_to_loader + current_queue_len * mean_load_time + own_load_time`.

**Outside** the boundary: waste haulage to `WASTE`, maintenance / refuelling
at `MAINT`, operator-level events (shift change, lunch), weather effects,
ore-quality blending, downstream stockpile back-pressure, and any
inter-shift carryover. The shift starts cold (all trucks at `PARK`, all
queues empty) and ends with a hard cut at `t = 480`.

### 5.2 Time horizon

Exactly **480 minutes (8 hours), hard cut**: only `end_dump` events with
`time_min < 480` credit tonnes to throughput. In-flight loads or dumps at
the cut are discarded — this matches an operator's "tonnes closed at
end-of-shift" interpretation.

### 5.3 Performance measures

Per replication: `total_tonnes_delivered`, `tonnes_per_hour`,
`average_truck_cycle_time_min`, `average_truck_utilisation`,
`crusher_utilisation`, per-loader `loader_utilisation_*`,
`average_loader_queue_time_min`, `average_crusher_queue_time_min`. Per
scenario: each metric is summarised across 30 replications as a mean and a
**95% Student-t CI** with `n - 1 = 29` degrees of freedom. Bottlenecks are
ranked by `composite_score = utilisation * mean_queue_wait_min`.

---

## 6. Assumptions

The benchmark prompt asks us to separate assumptions sourced from the data
from those we have introduced; the conceptual model documents both in full
in §6 of [`conceptual_model.md`](./conceptual_model.md). The summary:

### 6.1 Data-derived (read literally from CSV / YAML)

- **Topology**: 15 nodes and 35 directed edges from `nodes.csv` /
  `edges.csv`, used verbatim.
- **Capacity-constrained edges**: every edge with `capacity <= 1` becomes an
  independent SimPy `Resource`; every `capacity = 999` edge is a free
  timeout. We never collapse a directed pair into a single shared lane —
  the CSV treats them as distinct edges and we follow the data.
- **Service-time parameters**: loader means / sds (`6.5 ± 1.2` and
  `4.5 ± 1.0` min) come from `loaders.csv`; crusher mean / sd
  (`3.5 ± 0.8` min) comes from `dump_points.csv`.
- **Truck fleet**: 12 trucks with `payload_tonnes = 100`,
  `empty_speed_factor = 1.00`, `loaded_speed_factor = 0.85`,
  `availability = 1.00`, all starting at `PARK`. Scenarios cap the active
  fleet at 4, 8, or 12.
- **Free-flow edge times**:
  `distance_m / (max_speed_kph * 1000 / 60)` minutes per edge, multiplied by
  the truck's loaded / empty speed factor for the actual traversal.
- **Scenario semantics**: closures, capacity overrides, and crusher service
  changes are read from each YAML's `edge_overrides`,
  `dump_point_overrides`, and `fleet` blocks.
- **Stochasticity recipe**: `loading_time_distribution: normal_truncated`,
  `dumping_time_distribution: normal_truncated`,
  `travel_time_noise_cv: 0.10`.

### 6.2 Introduced (chosen by us where the data is silent)

1. **Static shortest-time routing per scenario**, recomputed by Dijkstra on
   free-flow edge times whenever the scenario changes the edge set
   (closures or capacity upgrades). Trucks do **not** re-plan during a
   replication, even if a capacity-1 edge develops a queue.
2. **Travel-time noise** is a per-traversal lognormal multiplier with
   mean 1 and cv 0.10 — keeps multipliers strictly positive while honouring
   `travel_time_noise_cv`.
3. **Load and dump durations** are `normal_truncated` with the configured
   mean and sd, truncated at `max(0.1, sample)` — replaces a sub-0.1 draw
   with 0.1 rather than rejecting and resampling. (Mean shift is < 0.1 % at
   the configured cv.)
4. **Dispatch rule**:
   `argmin(travel_to_loader + current_queue_len * mean_load_time + own_load_time)`.
   `current_queue_len` includes the truck currently being served. Ties are
   broken by lower `loader_id` (`L_N` before `L_S`).
5. **Initial dispatch**: all trucks released simultaneously at `t = 0` from
   `PARK`. No staged ramp-up.
6. **Hard cut at `t = 480`**: only dumps completed strictly before 480 min
   count toward throughput; in-flight loads / dumps are discarded.
7. **Truck utilisation = productive only**: travel + queue + load + dump
   inside the ore cycle counts; idle time after the hard cut does not.
8. **Reachability self-check** at scenario load: the four required OD
   pairs (`PARK<->LOAD_N`, `PARK<->LOAD_S`, `LOAD_N<->CRUSH`,
   `LOAD_S<->CRUSH`) must all be reachable in the post-override graph; if
   any is not, the scenario fails loudly with a `ReachabilityError`.
9. **Per-replication seed** = `base_random_seed + replication_index`.
   Each replication is independently reproducible while the scenario as a
   whole is deterministic.
10. **`WASTE` and `MAINT` are out of scope** for ore throughput. Their
    edges are kept in the graph but never used; routing never detours to
    them.
11. **Edge resources are independent per direction** (e.g. `E03_UP` and
    `E03_DOWN` are two separate `Resource` objects). Mirrors the CSV
    literally; if the physical ramp is a single shared lane, real
    congestion will be worse than modelled.
12. **Crusher tonnes are credited at `end_dump`**, not at `start_dump` or
    `arrive_crusher`. Standard SimPy "service complete" convention and
    matches the prompt's instruction that throughput is measured by
    completed dump events.

### 6.3 Combo scenario rationale

In addition to the six required scenarios, we add **`trucks_12_ramp_upgrade`**
(12 trucks + upgraded ramp). `trucks_12` alone is expected to saturate the
capacity-1 ramp; `ramp_upgrade` alone is expected to be limited by an
8-truck fleet. The combo isolates the joint effect — telling the operator
whether the two investments are complementary, substitutive, or independent.

---

## 7. Routing and dispatching logic

The model separates *where a truck goes* (routing) from *which loader it
chooses* (dispatching). Both are deliberately simple and reproducible.

### 7.1 Routing — static shortest-time Dijkstra per scenario

Implemented in `src/mine_sim/routing.py`. The contract:

1. **Graph construction**: at scenario load, `mine_sim.topology.build_topology`
   constructs a directed graph from `data/edges.csv`. The scenario's
   `edge_overrides` are then applied — closed edges are *removed* from the
   graph, capacity overrides change a `Resource`'s capacity, and any other
   override fields propagate.
2. **Edge weight = free-flow traversal time**:
   `distance_m / (max_speed_kph * 1000 / 60)` minutes per edge — i.e. the
   minimum-conceivable transit time independent of any speed factor or
   stochastic noise. Speed factors are applied only at simulation time, not
   when planning the route.
3. **Shortest-time paths via Dijkstra** (`networkx.shortest_path`,
   `weight='time_min'`). For each `(origin, destination)` pair we cache
   both the node sequence and the cumulative free-flow time. The cache is
   keyed by scenario, so closures in `ramp_closed` are honoured without
   re-computing during a replication.
4. **Required OD pairs and reachability**:
   `routing.REQUIRED_OD_PAIRS = [(PARK, LOAD_N), (LOAD_N, PARK),
   (PARK, LOAD_S), (LOAD_S, PARK), (LOAD_N, CRUSH), (CRUSH, LOAD_N),
   (LOAD_S, CRUSH), (CRUSH, LOAD_S)]`. `routing.assert_reachable` is
   invoked once per scenario load and raises `ReachabilityError` if any of
   the eight pairs has no path. This fails *before* any RNG draw, so a
   topology error never silently produces a zero-throughput result.
5. **Per-replication immutability**: trucks do not re-route during a
   replication, even if a capacity-1 edge develops a long queue. This is
   the deliberate trade-off documented in assumption §6.2 (1) — it costs a
   small amount of realism (a real dispatcher might divert via the bypass)
   but buys reproducibility and lets the bottleneck ranking attribute
   queueing cleanly to specific edges.
6. **Speed factors at execution time**: the actual traversal time of an
   edge by truck `t` is
   `(distance_m / (max_speed_kph * 1000 / 60)) / speed_factor(t) * lognormal_multiplier`
   where `speed_factor(t) = loaded_speed_factor` if the truck is loaded
   else `empty_speed_factor`. Capacity-1 edges hold the SimPy `Resource`
   for the full traversal duration, with `edge_enter` / `edge_leave` log
   entries bracketing the hold.

### 7.2 Dispatching — minimum-expected-completion-time loader choice

Implemented in `src/mine_sim/model.py`. When a truck becomes empty (just
dispatched at `t = 0`, or just released the crusher after `end_dump`), it
chooses a loader by the rule below:

```
score(loader L) = travel_time_to(L)                # cached free-flow Dijkstra time
                + queue_len(L) * mean_load_time(L) # current waiting trucks * loader's mean
                + mean_load_time(L)                # the truck's own expected load duration
chosen_loader = argmin_L score(L)
```

Notes on the rule:

- **`queue_len(L)` includes the truck currently being served**, not just
  those waiting in the SimPy queue. This is the "how many trucks are still
  ahead of me" interpretation — pessimistic but accurate to what a
  dispatcher would compute.
- **`mean_load_time(L)` is the configured loader mean from `loaders.csv`**
  (6.5 min for `L_N`, 4.5 min for `L_S`), *not* a sampled value. Dispatch
  is a planning step, not an execution step; using the mean keeps the
  decision deterministic given `(travel_time, queue_len, loader_means)`.
- **`travel_time_to(L)` is the free-flow Dijkstra time** from the truck's
  current position to the loader's node. We do not add per-edge stochastic
  noise into the dispatch score — again, dispatch is planning, not
  execution.
- **Tie-breaking**: if two loaders yield equal scores, the truck picks the
  one with the lexicographically smaller `loader_id` (`L_N` before `L_S`).
  In practice this is rare because the loader means and travel times
  differ.
- **Decision moments**: the decision is made *only* at the moment the truck
  becomes empty (initial dispatch or `depart_crusher`). A truck en route
  to a loader does not re-plan even if another truck arrives at that
  loader and lengthens the queue.
- **Asymmetric loader speeds drive the "fast loader pull"**: `L_S` has a
  shorter mean (4.5 min) than `L_N` (6.5 min), so an empty truck at `J5` /
  `J6` will preferentially pick `L_S` until its queue grows enough that
  `queue_len(L_S) * 4.5` exceeds `queue_len(L_N) * 6.5 + (travel_N -
  travel_S)`. This is visible in `summary.json` as systematically higher
  `loader_utilisation_L_S` than `loader_utilisation_L_N` in baseline-class
  scenarios.

### 7.3 Where these decisions show up in the output

- **`event_log.csv`**: every `arrive_loader` / `start_load` carries the
  loader the truck was dispatched to, so the dispatch decisions are
  fully auditable from the log alone.
- **`results.csv`**: per-replication `loader_utilisation_L_N`,
  `loader_utilisation_L_S`, and `average_loader_queue_time_min`
  collectively summarise the dispatch's fairness / saturation across
  replications.
- **`summary.json`**: the `top_bottlenecks` list ranks every
  capacity-1 resource by `utilisation * mean_queue_wait_min`. If the
  loaders dominate, the dispatch policy is the proximal cause; if the
  edges dominate, routing is. This is the lens we use in §8 to answer
  the operational decision questions.

---

## 8. Key results

All numbers below are from the canonical run-all (`runs/ac2_run_all/`) copied
to the repository-root `summary.json`. Every scenario uses **30 replications**;
all confidence intervals are **95% Student-t** with `n - 1 = 29` degrees of
freedom. `tph` = tonnes-per-hour; `qwait` = mean queue wait at the resource.

### 8.1 Headline throughput by scenario

| Scenario | Trucks | `tonnes_per_hour` (mean) | 95% CI | Total tonnes | Δ vs baseline |
|---|---:|---:|---|---:|---:|
| `baseline` | 8 | **1568.33** | [1561.43, 1575.24] | 12 546.67 | — |
| `trucks_4` | 4 | 956.25 | [951.39, 961.11] | 7 650.00 | **−39.0 %** |
| `trucks_12` | 12 | 1613.33 | [1603.31, 1623.36] | 12 906.67 | +2.9 % |
| `ramp_upgrade` | 8 | 1575.83 | [1568.18, 1583.48] | 12 606.67 | +0.5 % |
| `crusher_slowdown` | 8 | 814.17 | [807.05, 821.29] | 6 513.33 | **−48.1 %** |
| `ramp_closed` | 8 | 1545.42 | [1537.24, 1553.59] | 12 363.33 | −1.5 % |
| `trucks_12_ramp_upgrade` (combo) | 12 | **1619.17** | [1608.71, 1629.62] | 12 953.33 | **+3.2 %** |

### 8.2 Resource saturation by scenario

| Scenario | Crusher util | L_N util | L_S util | Crusher qwait (min) | Loader qwait (min) | Cycle time (min) |
|---|---:|---:|---:|---:|---:|---:|
| `baseline` | **0.912** | 0.602 | 0.803 | 3.28 | 2.51 | 29.66 |
| `trucks_4` | 0.557 | 0.323 | 0.517 | 0.70 | 0.69 | 24.42 |
| `trucks_12` | 0.937 | 0.641 | 0.845 | **14.24** | 3.47 | 42.68 |
| `ramp_upgrade` | 0.916 | 0.603 | 0.807 | 3.30 | 2.72 | 29.55 |
| `crusher_slowdown` | **0.948** | 0.329 | 0.445 | **26.57** | 0.64 | 55.49 |
| `ramp_closed` | 0.898 | **0.658** | 0.744 | 3.21 | 3.18 | 30.11 |
| `trucks_12_ramp_upgrade` | 0.941 | 0.641 | **0.850** | 14.30 | 3.96 | 42.54 |

### 8.3 Single-figure summary

The baseline 8-hour shift produces **12 547 t (95% CI [12 491, 12 602])** at
**1 568 tph (95% CI [1 561, 1 575])**, with the crusher running at 91.2 %
utilisation as the dominant constraint. Doubling the fleet (`trucks_4` →
`trucks_12`) only buys +2.9 % throughput because the crusher saturates. Halving
the crusher's service rate (`crusher_slowdown`) costs nearly half the shift's
tonnes (−48.1 %), confirming the crusher as the bottleneck. The narrow ramp
(`ramp_closed` vs `baseline`) costs only −1.5 % when bypassed via the
secondary route. Upgrading the ramp on its own (`ramp_upgrade`) is essentially
a no-op (+0.5 %, CI overlaps baseline) — but combined with a 12-truck fleet
(`trucks_12_ramp_upgrade`) it delivers the run's best throughput at 1 619 tph.

---

## 9. Answers to the operational decision questions

Each subsection answers one of the six required questions in `prompt.md`,
citing mean and 95% CI directly from `summary.json` so the answer is
auditable.

### 9.1 Q1 — Expected baseline throughput

> *What is the expected ore throughput to the crusher during the baseline
> 8-hour shift?*

**Answer.** **12 546.7 t per shift, 95% CI [12 491.4, 12 601.9]** —
equivalently **1 568.3 tph, 95% CI [1 561.4, 1 575.2]** (n=30 replications,
8 trucks, base ramp).

The CI is tight (≈ ±0.4 % of the mean) because the crusher is near saturation,
so per-replication variance is modest. The 95% CI for `total_tonnes` does not
overlap any of the six other scenarios, so every comparative answer below is
significant at the conventional 5 % level.

### 9.2 Q2 — Likely bottlenecks

> *What are the likely bottlenecks in the haulage system?*

**Answer.** Under the composite `utilisation × mean_queue_wait` ranking
(see `summary.json::scenarios.baseline.top_bottlenecks`), the bottlenecks in
baseline are, in order:

| Rank | Resource | Utilisation | Queue wait (min) | Composite score |
|---:|---|---:|---:|---:|
| 1 | **`D_CRUSH` (crusher)** | 0.912 | 3.28 | **2.99** |
| 2 | **`L_S` (south loader)** | 0.803 | 2.45 | **1.97** |
| 3 | `L_N` (north loader) | 0.602 | 2.62 | 1.58 |
| 4 | `E03_UP` (narrow ramp, up) | 0.053 | 10.89 | 0.57 |
| 5 | `E05_TO_CRUSH` | 0.421 | 0.15 | 0.06 |

Three takeaways:

1. **The crusher is the binding constraint** in every scenario where it isn't
   manually slowed. Its composite score is ≈ 50 % higher than the next
   resource, and it is the only resource > 90 % utilised.
2. **`E03_UP` has very low utilisation (5 %) but a high mean queue wait (10.9
   min)**. That looks paradoxical until you remember it is a capacity-1
   loaded-only ramp on a long route; trucks queue in clumps even though the
   resource itself is rarely held. Ranking by composite score (rather than
   either factor alone) keeps it on the radar, but it is not the binding
   constraint — the upgrade scenario confirms this (next question).
3. **Loader asymmetry**: `L_S` is 80 % utilised vs `L_N` at 60 %, despite both
   being capacity-1, because the dispatch rule pulls trucks to `L_S` for its
   shorter mean service time (4.5 vs 6.5 min). The fast loader is therefore
   the second bottleneck; equalising loader speeds would help on the margin.

### 9.3 Q3 — Does adding more trucks materially improve throughput?

> *Does adding more trucks materially improve throughput, or does the system
> saturate?*

**Answer.** Adding trucks helps **only up to fleet size 8**; beyond that the
system saturates on the crusher.

| Fleet | tph mean | 95% CI | Δ vs prev step | Cycle time (min) | Crusher util |
|---:|---:|---|---:|---:|---:|
| 4 | 956.25 | [951.39, 961.11] | — | 24.42 | 0.557 |
| 8 | 1568.33 | [1561.43, 1575.24] | **+64.0 %** | 29.66 | 0.912 |
| 12 | 1613.33 | [1603.31, 1623.36] | **+2.9 %** | 42.68 | 0.937 |

Going from 4 → 8 trucks delivers a **+64 % uplift** (CIs are
non-overlapping by ≈ 600 tph, p « 0.05). Going from 8 → 12 delivers only
**+2.9 %** (45 tph, CIs barely separated) while cycle time *worsens* by
+44 % (29.7 → 42.7 min) and the crusher queue wait **quadruples** (3.3 →
14.2 min). In other words, the extra four trucks spend most of their time
queueing at the crusher — they convert tonnes-per-hour gains into
tonnes-of-trucks-stuck-in-line.

**Operational implication.** Sticking with 8 trucks is the right call unless
a crusher upgrade is also on the table. If both trucks and crusher are
upgraded, fleet size 12 makes sense; otherwise the marginal four trucks are
wasted.

### 9.4 Q4 — Would improving the narrow ramp materially improve throughput?

> *Would improving the narrow ramp materially improve throughput?*

**Answer. No, not on its own.** `ramp_upgrade` (which raises ramp capacity
from 1 to 2 and `max_speed_kph`) yields **1 575.8 tph, 95% CI
[1 568.2, 1 583.5]**. The baseline is **1 568.3 tph, 95% CI
[1 561.4, 1 575.2]**. The 95% CIs **overlap** by 7 tph; the point-estimate
gain is just **+0.48 %** (≈ 60 tonnes across an 8-hour shift) and is
statistically borderline.

The reason is mechanical: the crusher is already 91 % utilised in baseline.
Removing a non-binding constraint (the ramp's queue wait drops, but its
`utilisation × qwait` was already 0.57 — small) just shifts the queue
elsewhere. The crusher utilisation moves from 0.912 to 0.916; throughput is
unchanged within noise.

**However** — the ramp upgrade *does* matter when paired with a fleet
expansion. The combo scenario `trucks_12_ramp_upgrade` produces **1 619.2 tph,
95% CI [1 608.7, 1 629.6]**, which is +3.2 % over baseline and +0.4 % over
`trucks_12` alone (and outside the `trucks_12` CI's upper bound by ≈ 6 tph).
The ramp upgrade is therefore a **complement** to a fleet expansion, not a
substitute.

**Operational implication.** Don't fund the ramp upgrade in isolation. Bundle
it with the trucks-12 decision or invest the capital in crusher capacity
instead.

### 9.5 Q5 — How sensitive is throughput to crusher service time?

> *How sensitive is throughput to crusher service time?*

**Answer. Highly sensitive — roughly linear in the inverse service rate.**
The `crusher_slowdown` scenario approximately **doubles** the crusher mean
service time (3.5 → 6.5 min, see `data/scenarios/crusher_slowdown.yaml`).
Throughput collapses to **814.2 tph, 95% CI [807.0, 821.3]** — a **−48.1 %**
drop versus baseline.

Mechanistically:

- Crusher utilisation rises from 0.912 → **0.948** (close to its theoretical
  ceiling at 100 %).
- Crusher queue wait inflates from 3.28 min → **26.57 min** (an 8× increase).
- Average truck cycle time inflates from 29.66 → **55.49 min** (almost 2×).
- Loader queues *empty out*: `loader_queue_min` drops from 2.51 → 0.64
  because trucks are now stuck downstream at the crusher rather than
  recycling fast enough to queue at loaders.

The scenario evidences **classic single-bottleneck dynamics**: when the
constraint slows down, every other resource un-saturates and queueing
concentrates entirely at the constraint. A 1 % slowdown in crusher service
roughly costs ≈ 1 % of shift throughput in this regime.

**Operational implication.** Crusher uptime and feed-rate consistency are the
single highest-leverage operational concern. A 30-minute crusher stoppage,
linearly extrapolated, would cost ≈ 800 t.

### 9.6 Q6 — What is the operational impact of losing the main ramp route?

> *What is the operational impact of losing the main ramp route?*

**Answer. Surprisingly small — about −1.5 % throughput.** `ramp_closed`
delivers **1 545.4 tph, 95% CI [1 537.2, 1 553.6]** vs baseline **1 568.3 tph
[1 561.4, 1 575.2]**. The CIs **do not overlap** (gap ≈ 8 tph at the
nearest edges), so the loss is statistically real, but it is operationally
modest — the equivalent of about 183 tonnes lost across an 8-hour shift.

Why is the impact so contained?

1. **The bypass route exists and is reachable.** Closing `E03_UP` removes
   the loaded-direction ramp; routing now sends loaded trucks via the longer
   `J5/J6 → CRUSH` path. The reachability self-check passes for all four
   required OD pairs, so the simulation runs to completion (rather than
   failing loudly).
2. **Cycle time inflates only modestly** (29.66 → 30.11 min, +1.5 %) because
   the bypass adds a few hundred metres rather than a kilometre.
3. **Loader load redistributes**: with the direct route gone, the dispatch
   rule re-balances toward `L_N` (utilisation 0.60 → 0.66) while `L_S` drops
   (0.80 → 0.74). The new bottleneck is the loader, not the route — the
   `top_bottlenecks` ranking now puts **`L_N` first** (composite score 3.21,
   above `D_CRUSH` at 2.88), the only scenario where the crusher is not #1.

**Operational implication.** The mine has genuine route redundancy. Losing
the main ramp is a tolerable disruption rather than a shift-stopping one.
However, the new binding constraint is `L_N`, so a *coincident* `L_N`
breakdown during a `ramp_closed` event would be much more damaging than
either alone — a useful contingency-planning insight.

### 9.7 Combo scenario (proposed seventh) — `trucks_12_ramp_upgrade`

We proposed and ran this combo to disambiguate Q3 and Q4: does the ramp
investment only pay off after the fleet is expanded?

**Answer. Yes, weakly.** `trucks_12_ramp_upgrade` produces **1 619.2 tph,
95% CI [1 608.7, 1 629.6]**, the highest of any scenario. That is:

- **+3.2 %** over baseline (CIs do not overlap).
- **+0.4 %** over `trucks_12` alone (CIs marginally overlap; gain is small
  but consistent across replications).
- Top bottleneck remains `D_CRUSH` (composite 13.45, vs 13.34 for
  `trucks_12`).

**Operational implication.** Even with both interventions, the system is
still crusher-bound. The combo confirms that further capital should target
the crusher (not trucks, not roads) if 1 619 tph is unsatisfactory.

---

## 10. Likely bottlenecks (cross-scenario)

Aggregating across all seven scenarios, the persistent bottleneck pattern is:

1. **`D_CRUSH` is the binding constraint** in 6 of 7 scenarios. Its
   utilisation is > 0.90 in every scenario except `trucks_4` (0.56, the only
   under-fleeted case). Its composite score is the highest in 6 scenarios.
2. **`L_S` is the secondary bottleneck** whenever the crusher is not slowed.
   The dispatch rule pulls trucks toward the faster loader (4.5-min mean vs
   6.5-min for `L_N`), so `L_S` saturates before `L_N`. Equalising loader
   speeds would reduce `L_S` queue wait by ≈ 30–40 % at no fleet cost.
3. **`L_N` becomes the #1 bottleneck under `ramp_closed`** (composite 3.21,
   above the crusher at 2.88) because the closure forces more traffic through
   the north loop. This is the single scenario where the crusher is not the
   binding resource.
4. **`E03_UP` (narrow ramp) has high queue-wait but low utilisation** in
   every scenario where it is not closed. It is a *latent* constraint —
   periodic clustering of loaded trucks creates short bursts of queueing
   without ever holding the resource for very long. Removing it (ramp
   upgrade) yields negligible throughput gain because it was never the
   binding constraint.

The cross-scenario evidence is consistent with single-server-system
intuition: throw capital at the crusher first, the dispatch rule second
(equalise loader pull), and only then at routes.

---

## 11. Limitations of the model

The full list lives in [`conceptual_model.md`](./conceptual_model.md) §7;
the most consequential ones for interpreting §9 are:

1. **Static per-scenario routing.** Trucks do not re-plan during a
   replication. A real dispatcher might divert to the bypass route once
   `E03_UP` shows a long queue. We trade a small amount of realism for
   reproducibility and clean bottleneck attribution.
2. **No operator events.** No shift change, no crib break, no refuelling,
   no maintenance windows. Throughput is therefore an *upper bound* on what
   an operator would actually see in steady-state production.
3. **Edge resources are one-per-direction.** `E03_UP` and `E03_DOWN` are
   independent SimPy resources. If the physical narrow ramp is a single
   shared lane, real congestion is *worse* than modelled (especially in
   `trucks_12`).
4. **Stochastic inputs are independent across draws.** No autocorrelation
   in load times, no correlated loader breakdowns, no operator skill
   effects. The CIs reflect *modelled* variance, not real-world variance,
   which is typically larger.
5. **Hard cut at t = 480.** In-flight loads / dumps at the cut are
   discarded. The "actual" tonnes in the bin at the moment the whistle blows
   are slightly below the simulation's reported figure for any scenario where
   the cut interrupts a dump.
6. **`WASTE` and `MAINT` excluded.** These nodes exist in the topology but
   are never visited. Real operational throughput must share haul capacity
   with waste removal and maintenance trips.

The CIs in §9 are **statistical**, not **epistemic** — they capture
replication-to-replication variance under the model's assumptions. The
operational implications stand for a relative comparison of scenarios; the
absolute throughput numbers should be treated as a model-internal benchmark,
not a production forecast.

---

## 12. Suggested further work

If a follow-on study is in scope, the highest-leverage extensions (in
priority order) are:

1. **Crusher capacity scenarios.** `crusher_speedup` (mean 2.5 min) and
   `crusher_capacity_2` (two parallel crushers) — directly quantify the
   value of the binding-constraint upgrade. Expected to produce the largest
   throughput uplift of any single intervention.
2. **Equal-speed-loaders scenario.** Set both loaders to mean 5.5 min (the
   weighted average) to test whether dispatching imbalance is costing
   throughput. Cheap to run; the answer informs dispatcher policy without
   any capital expense.
3. **Dynamic re-routing.** Allow trucks to re-plan at junctions when
   downstream queues exceed a threshold. Requires a real-time queue lookup
   and adds a re-route policy parameter; expected to soften the
   `ramp_closed` impact further.
4. **Operator events and breaks.** Add a 30-min crib break at t=240 and a
   shift-change handover at t=0/480 to bring throughput in line with a real
   shift. Worth ≈ −5–10 % on the headline figure.
5. **Correlated stochasticity.** Replace the per-draw-independent lognormal
   travel multiplier with an autocorrelated process (e.g. day-of-week
   weather effects). Likely to widen CIs by 2–3×.
6. **Coincident-failure scenarios.** `loader_LN_outage` paired with
   `ramp_closed` (the §9.6 contingency case), `crusher_slowdown` paired with
   `trucks_12` (worst-case capital-intensive saturation), etc. These inform
   resilience planning rather than steady-state throughput.

---
