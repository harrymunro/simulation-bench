# Red-Cell Review — HMS Vigilant

**Reviewer**: Red-Cell Navigator (HMS Vigilant)
**Date**: 2026-04-29
**Submission**: `2026-04-29__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__agent-teams-nelson-max-thinking`

---

## Overview

This review independently examines the SimPy mine simulation for correctness, schema conformance, and result plausibility. All six required scenarios are present with 30 replications each. The simulation runs reproducibly. The schema is fully compliant. Two medium-severity findings are identified; no critical or high-severity defects were found.

---

## CRITICAL Findings

None.

---

## HIGH Findings

None.

---

## MEDIUM Findings

### M1: E03_UP Ranked as Top Bottleneck — Startup Artifact, Not Steady-State

**Location**: `src/metrics.py:176-203`, `summary.json`, scenario `baseline`

**Observation**: In the baseline scenario, `E03_UP` (narrow ramp J2→J3) is ranked the top bottleneck with a mean queue wait of 6.03 min. However, inspection of the event log reveals that E03_UP is traversed **only during the initial truck dispatch from PARK** (approximately the first 18–20 simulation minutes). After trucks complete their first cycle and are at CRUSH, subsequent trips from CRUSH→LOAD_S go via CRUSH→J4→J6→LOAD_S (bypassing E03 entirely), and CRUSH→LOAD_N goes via CRUSH→J4→J3→J5→LOAD_N (using E04_FROM_CRUSH, not E03_UP).

**Impact**: The 6.03-min mean queue wait is an artifact of all 8 trucks queuing through the 1-truck-capacity E03_UP in the first ~20 minutes only. After that, E03_UP is never used again. This inflates E03_UP's apparent bottleneck ranking above D_CRUSH (crusher, 95% utilisation, 4.65 min mean queue), which is the true steady-state bottleneck. A mine operator reading the `top_bottlenecks` list would incorrectly prioritize ramp widening over crusher throughput improvement.

**Evidence**: `crusher_slowdown` (which runs half as many cycles per truck) produces **identical** E03_UP queue times and utilisation to `baseline` across all 30 replications — confirming the ramp is only contested at startup, not during steady-state operation.

**Recommended fix**: The bottleneck ranking would be more useful if restricted to steady-state (e.g., after the first 30 minutes), or if accompanied by a count of how many traversals contributed to the queue metric.

### M2: No Warmup Period Despite `warmup_minutes: 0` Config Key Present

**Location**: `data/scenarios/baseline.yaml`, `src/run_experiments.py:96-99`

**Observation**: The scenario YAML includes `warmup_minutes: 0` but the runner never reads or applies this field. All trucks start at PARK simultaneously at t=0 with no staggered entry. This causes an artificial startup surge through E03_UP (see M1) and means cycle-time and queue statistics for the first few cycles may overstate steady-state queue lengths for the ramp.

**Impact**: Low for throughput (which is robust to warmup effects), but meaningful for bottleneck identification and average queue metrics reported in summary.json. The model limitation is honestly documented ("All trucks start at PARK at t=0 with no warmup"), but the config key suggests warmup was intended and not implemented.

---

## LOW / Style Findings

### L1: Redundant `node_overrides` in `crusher_slowdown.yaml`

`crusher_slowdown.yaml` overrides both `dump_point_overrides.D_CRUSH.mean_dump_time_min` and `node_overrides.CRUSH.service_time_mean_min`. The simulation reads dump service time exclusively from `dump_points_df` via `_resolve_dump_params()`. The `node_overrides` entry is never read by the simulation and is harmless but misleading.

### L2: `_LOAD_NODE_TO_LOADER` Module-Level Dict Never Used

`simulation.py:19` declares `_LOAD_NODE_TO_LOADER: dict[str, str] = {}` and the comment says "populated per-run", but this dict is never written to or read anywhere in the codebase. Dead code.

### L3: `additional_scenarios_proposed` is Empty List

The spec says this field is optional but recommends at least considering additional scenarios. The field is present in `summary.json` but empty. This is acceptable per spec (prompt.md line 307) but represents a missed opportunity to answer the optional analysis question.

### L4: `shift_length_hours` Missing from `aggregate_replication` Return Dict

`metrics.py:aggregate_replication()` does not include `shift_length_hours` in its return dict. It is patched in by `run_experiments.py:111` (`rep_metrics["shift_length_hours"] = shift_hours`) before passing to `aggregate_scenario`. This works but is a slight inconsistency — the replication-level function should own all fields it computes.

---

## Schema Conformance Check

### `summary.json` (spec lines 281–309)

| Field | Status |
|---|---|
| `benchmark_id: "001_synthetic_mine_throughput"` | PASS |
| All 6 scenarios present | PASS |
| `replications: 30` per scenario | PASS |
| `shift_length_hours` | PASS |
| `total_tonnes_mean/ci95_low/ci95_high` | PASS |
| `tonnes_per_hour_mean/ci95_low/ci95_high` | PASS |
| `average_cycle_time_min` | PASS |
| `truck_utilisation_mean` | PASS |
| `loader_utilisation` (dict) | PASS |
| `crusher_utilisation` | PASS |
| `average_loader_queue_time_min` | PASS |
| `average_crusher_queue_time_min` | PASS |
| `top_bottlenecks` populated (5 entries each) | PASS |
| `key_assumptions` (8 entries) | PASS |
| `model_limitations` (7 entries) | PASS |

All required fields present. No schema violations.

### `results.csv` (spec lines 261–271)

All 10 required columns present: `scenario_id`, `replication`, `random_seed`, `total_tonnes_delivered`, `tonnes_per_hour`, `average_truck_cycle_time_min`, `average_truck_utilisation`, `crusher_utilisation`, `average_loader_queue_time_min`, `average_crusher_queue_time_min`.

Additional columns present (edge metrics, loader metrics, `completed_cycles`) — permitted by spec.

180 rows total (6 scenarios × 30 reps). **PASS**.

### `event_log.csv` (spec lines 318–336)

All 12 required columns present: `time_min`, `replication`, `scenario_id`, `truck_id`, `event_type`, `from_node`, `to_node`, `location`, `loaded`, `payload_tonnes`, `resource_id`, `queue_length`.

92,424 rows covering 5 replications × 6 scenarios. Event types include `dispatch`, `edge_enter`, `edge_exit`, `edge_request`, `arrive_loader`, `load_start`, `load_end`, `depart_loader`, `arrive_crusher`, `dump_start`, `dump_end`, `depart_crusher`. **PASS**.

---

## Reasonableness Check

| Check | Expected | Actual | Result |
|---|---|---|---|
| Baseline tonnes/h | ~1620 (crusher ~95% util at 3.5 min/dump → 1714 max) | 1620.0 | PASS |
| trucks_4 < baseline | Yes | 976.7 < 1620.0 | PASS |
| trucks_12 ≈ baseline (saturated) | Yes | 1624.6 ≈ 1620.0 (+0.3%) | PASS |
| ramp_closed > 0 (rerouting works) | Yes | 1610.4 t/h | PASS |
| crusher_slowdown < baseline | Yes | 820.0 << 1620.0 (−49%) | PASS |
| ramp_upgrade ≈ baseline (marginal gain) | Yes | 1629.2 vs 1620.0 (+0.6%) | PASS |
| CI widths sensible (≥30 reps, low variance) | Narrow | ~17 t/h width on baseline | PASS |
| Reproducibility (identical outputs, 2 runs) | Yes | Confirmed identical | PASS |
| t-distribution with df=n-1 for CI | Yes | `stats.t.interval(0.95, df=n-1)` | PASS |
| Crusher utilisation = busy_min/shift_min | Yes | Confirmed in `metrics.py:63-65` | PASS |
| Throughput = dumps with dump_start < shift_end | Yes | Confirmed in `metrics.py:44-46` | PASS |

### Additional routing checks

- **ramp_closed bypass**: Trucks from PARK route via J2→J7→J8→J6→LOAD_S and J2→J7→J5→LOAD_N, correctly avoiding closed E03_UP/E03_DOWN. No E03 events appear in ramp_closed event log. **PASS**.
- **Bypass connectivity**: LOAD_N→CRUSH and CRUSH→LOAD_N in ramp_closed use J5→J3→J4 and J4→J3→J5 respectively, which do not traverse E03_UP or E03_DOWN. The ramp bypass path (J2→J7→J8→J4) matches the spec description. **PASS**.
- **Seed control**: `seed = base_seed + replication_index` with `np.random.SeedSequence` producing independent per-truck RNG streams. Two sequential full runs produce byte-identical results. **PASS**.

---

## Simulation Correctness Assessment

| Component | Verdict |
|---|---|
| Truck cycle (dispatch→empty travel→load→loaded travel→dump→repeat) | CORRECT |
| Loaders as 1-capacity SimPy PriorityResources | CORRECT |
| Crusher as 1-capacity SimPy Resource | CORRECT |
| Capacity-constrained edges as Resources (E03_UP/DOWN, E05, E07, E09) | CORRECT |
| Ramp closure rerouting via bypass | CORRECT |
| Random seed control | CORRECT |
| Stochastic loading/dumping/travel times | CORRECT |
| 95% CI using t-distribution df=n-1 | CORRECT |
| crusher_utilisation = busy_time/shift_time | CORRECT |
| Throughput from dump_start < shift_end | CORRECT |
| 6 scenarios × 30 reps executed | CORRECT |
| Scenario inheritance (YAML deep merge) | CORRECT |
| Deterministic seeds (base_seed + replication) | CORRECT |
| All 3 output files written to spec | CORRECT |

---

## Recommendation

**PASS_WITH_FIXES**

The simulation is mechanically correct: truck cycles, resource constraints, routing, stochastic timing, seed control, and schema conformance all meet or exceed spec requirements. Reproducibility is confirmed. Reasonableness checks all pass.

The two medium findings (M1, M2) do not compromise the throughput estimates or output file compliance. However, M1 (E03_UP incorrectly ranked as top steady-state bottleneck) would mislead a mine operator reading the summary and warrants correction before the results are presented operationally. M2 (no warmup despite config key) is lower risk given the honest documentation in `model_limitations`.

The submission would **PASS** outright if M1 were addressed — for example, by adding a note to `top_bottlenecks` that E03_UP queue time reflects startup congestion only, or by filtering bottleneck metrics to exclude the first 30 minutes.
