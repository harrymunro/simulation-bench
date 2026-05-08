# Battle Plan — Synthetic Mine Throughput Simulation

## Commander's Intent

Deliver a defensible, reproducible SimPy discrete-event simulation that quantifies ore throughput to the primary crusher across the six required scenarios plus one combined `trucks_12 + ramp_upgrade` scenario, and answers all six operational decision questions in a single readable report. The model must be visibly correct (event log shows valid routes and queueing), reproducible (per-replication seed = base + rep_idx), and interpretable (composite bottleneck rank surfaced in summary.json). Correctness, reproducibility, and interpretability dominate visual polish.

## Mission Mode

**single-session.** Heavy same-file editing on one Python package; linear dependencies; design decisions pinned by interview-decisions memory. Multi-agent integration friction is not warranted for a contained ~1.5k LOC build. Admiral builds, runs, validates, documents.

## Tasks

### T1 — Scaffolding & Data Loading
- **Deliverable:** `src/mine_sim/__init__.py`, `src/mine_sim/data.py`, `src/mine_sim/scenarios.py`, `src/mine_sim/topology.py`, `pyproject.toml`-style requirements (or plain `requirements.txt`).
- **Modification targets:** New package under `src/mine_sim/`. New `requirements.txt`. Reads existing `data/*.csv` and `data/scenarios/*.yaml`.
- **Acceptance:**
  - Loads nodes, edges, trucks, loaders, dump_points without error.
  - Resolves YAML scenario inheritance (`inherits: baseline` + per-key overrides for `edge_overrides`, `node_overrides`, `dump_point_overrides`, `fleet`, `simulation`).
  - `Topology` builds a directed `networkx.DiGraph` with edge attributes incl. distance, max_speed_kph, capacity, closed.
  - Free-flow traversal time = `distance_m / (max_speed_kph * 1000/60)` minutes (loaded uses `loaded_speed_factor`, empty uses `empty_speed_factor` applied to truck speed multiplier).
  - **Reachability self-check:** for each scenario, after applying closures, verify every truck start_node can reach `LOAD_N`, `LOAD_S` (or at least one ore source if scenario disables one), and `CRUSH`, AND that loaders can reach `CRUSH`. Raise loud error otherwise.
- **Station tier:** 2 (medium).

### T2 — Routing & Dispatch
- **Deliverable:** `src/mine_sim/routing.py`.
- **Modification targets:** New module within the package.
- **Acceptance:**
  - Static shortest-time Dijkstra between every (origin, destination) pair on the closure-applied graph, computed once per scenario; cached.
  - Edge weight = empty free-flow time for empty legs, loaded free-flow time for loaded legs (we precompute for both states).
  - Dispatch rule: when loader is free / truck is dispatched, choose loader minimizing `expected_travel_to_loader + queue_len * mean_load_time + own_load_time` (per memory: `min(travel + queue_len × mean_load + own_load)`).
  - Excludes `WASTE` and `MAINT` from any route used by ore haulage (per memory).
- **Station tier:** 2.

### T3 — SimPy Simulation Engine
- **Deliverable:** `src/mine_sim/simulation.py`.
- **Modification targets:** New module within the package.
- **Acceptance:**
  - One `simpy.Resource` per directed capacity-1 edge (mirrors CSV).
  - One `simpy.Resource` per loader (capacity from CSV).
  - One `simpy.Resource` for the crusher (capacity 1).
  - Truck process: dispatch → travel to chosen loader → request loader → load (normal-truncated, max(0.1, sample)) → travel loaded to crusher → request crusher → dump (normal-truncated, max(0.1, sample)) → travel back to next chosen loader → loop.
  - Edge traversal time noised by lognormal with cv=0.10 around free-flow.
  - Hard cut at shift_length_minutes (480 default): trucks stop accepting new dispatches after t≥shift; trucks finish their current dump if already in progress, then stop. Throughput counts dumps with completion time ≤ shift_length.
  - Simultaneous t=0 dispatch (all trucks start at t=0).
  - Per-rep seed = `base_random_seed + rep_idx`.
  - Truck utilisation = productive time only (loading + dumping + traveling laden or empty toward productive next step) / shift; queue/idle time excluded.
  - Event log entries for: dispatched, arrive_loader, load_start, load_end, depart_loader, arrive_crusher, dump_start, dump_end, depart_crusher, plus enter/leave for each capacity-1 edge.
- **Station tier:** 3 (high — model correctness is mission critical).

### T4 — Experiment Runner, Statistics & Outputs
- **Deliverable:** `src/mine_sim/experiment.py`, `src/mine_sim/stats.py`, `src/mine_sim/__main__.py`.
- **Modification targets:** New modules.
- **Acceptance:**
  - CLI: `python -m mine_sim run --scenarios all|<list> --output-dir .` runs scenarios.
  - Default runs all 7 scenarios. Writes `results.csv` (per-rep), `summary.json`, `event_log.csv` (long form, sample of reps to keep size manageable — e.g., reps 0,1,2 only).
  - Student-t n-1 95% CIs over reps.
  - Per scenario summary: tonnes mean+CI, t/h mean+CI, cycle time, truck utilisation, loader utilisation by id, crusher utilisation, loader/crusher queue waits, top_bottlenecks ranked by `util × mean_queue_wait` over loaders/crusher/cap-1 edges.
- **Station tier:** 2.

### T5 — Visualisation
- **Deliverable:** `src/mine_sim/visualise.py`. Outputs `topology.png` and `animation.gif`.
- **Modification targets:** New module.
- **Acceptance:**
  - `topology.png`: spring-or-coordinate-based plot of the graph with node types colored, capacity-1 edges highlighted, ore loaders + crusher labeled.
  - `animation.gif`: replay first replication of baseline at coarse temporal resolution (e.g., 5-minute steps) showing truck positions interpolated along edges. Generated from `event_log.csv`. Acceptable to be modest (small file, low FPS).
  - Animation generation must not block the experiment harness (separate CLI subcommand).
- **Station tier:** 1 (low — optional polish).

### T6 — Documentation
- **Deliverable:** `conceptual_model.md`, `README.md`.
- **Modification targets:** New top-level docs in submission folder.
- **Acceptance:**
  - `conceptual_model.md`: system boundary, entities, resources, events, state, assumptions (data-derived vs introduced), limitations, performance measures.
  - `README.md`: install, run instructions, reproduction notes, conceptual model summary, assumptions, routing/dispatch logic, **answers to all 6 operational decision questions with numerical evidence**, bottleneck identification, limitations, suggested improvements.
- **Station tier:** 2.

### T7 — Execute, Validate, Update Submission Metadata
- **Deliverable:** All artifacts produced; `submission.yaml` updated to `status: complete`.
- **Modification targets:** Generated outputs + edit `submission.yaml`.
- **Acceptance:**
  - All 7 scenarios run cleanly, 30+ reps each.
  - `summary.json` has non-zero meaningful values everywhere.
  - Total runtime reasonable (target < 5 min wall clock).
  - Event log inspection shows valid routes (no impossible edges) and queueing at expected resources.
  - Final `submission.yaml` records `status: complete`, `intervention: nelson-v2.2.2`.
- **Station tier:** 3 (mission-end gate).

## Coordination

T1 → T2 → T3 → T4 → T7 (linear chain). T5 can run after T3 has produced an event log. T6 runs after T7 to record real numbers. Admiral works tasks in order in single-session mode.

## Forces & Crew

Single-session: admiral implements all tasks directly, no captains, no crew, no marines. Red-cell discipline applied via self-review at task boundary (run, inspect event_log, eyeball metrics).

## Standing Order Check Answers

- **becalmed-fleet:** Single-session is correct: heavy same-file editing on one cohesive Python package, linear dependencies, design pinned by memory. Multi-agent would integrate-friction more than it would parallelise.
- **light-squadron:** N/A in single-session; tasks are split into 7 ordered units that match the natural dependency boundaries (data, routing, sim, experiment, viz, docs, validate).
- **split-keel:** Each task owns its own files; no overlapping ownership.
- **unclassified-engagement:** Every task has a station tier (1–3).
- **all-hands-on-deck:** No crew mustered (single-session).
- **skeleton-crew:** N/A (no crew).
- **crew-without-canvas:** N/A.
- **captain-at-the-capstan:** N/A.
- **press-ganged-navigator:** No red-cell navigator assigned (single-session); admiral applies self-review.
- **admiral-at-the-helm:** Admiral implementing is correct in single-session mode.
- **wrong-ensign:** Tools used will match single-session (no Agent dispatch, no TeamCreate, no SendMessage).
- **pulling-the-oar:** N/A (no subagents to fail).

## Out of Scope

- WASTE and MAINT routing (excluded per memory).
- Truck breakdowns / availability < 1.0 (no scenario uses it; trucks.csv has 1.0 across the board).
- Operator shift changes mid-run.
- Fuel/maintenance dynamics.
- A "polish" animation.gif beyond proof-of-life motion.
