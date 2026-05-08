# Quarterdeck Report — Checkpoint 1

## Status
- **Completed:** 5 / 7 tasks (data + scenarios + topology, routing + dispatch, SimPy engine, experiment runner + stats, visualisation).
- **In progress:** none.
- **Pending:** 2 (documentation, final validation + metadata).
- **Hull:** Green across the squadron (single-session admiral).
- **Budget burn:** light — full 7 × 30 rep run completed in 1.2 s.

## Verification evidence
- All 7 scenarios pass reachability self-check (loud failure path tested implicitly by closures).
- `results.csv` has 210 data rows (7 × 30 reps).
- `summary.json` carries non-zero, plausible values across all scenarios.
- `event_log.csv` contains 36,503 events spanning 9 distinct event types including the required `enter_edge`/`leave_edge` for capacity-1 segments and full cycle events.
- `topology.png` renders correctly with capacity-1 edges highlighted in red.
- `animation.gif` (594 KB) generated from event log of baseline rep 0.

## Key findings (preview)
- Baseline: ~12,500 t / 8h shift, 1,562 t/h, cycle 29.8 min, crusher util 91 %.
- The crusher is the dominant bottleneck (composite score 3.05 baseline → 25 under crusher_slowdown).
- The narrow ramp E03 is essentially bypassed in steady-state cycles (utilisation ≈ 5 %); ramp_upgrade adds < 1 % throughput, ramp_closed costs ~ 1 %.
- Throughput saturates between 8 and 12 trucks (12,503 → 12,897 = +3 %), with diminishing per-truck returns (truck util drops 77 % → 55 %).

## Decisions
- Single-session mode confirmed: linear dependency chain, heavy same-file Python work — no captains spawned.
- Skipped the Estimate phase: design choices pinned by the interview-decisions memory.

## Next
- Write `conceptual_model.md` and `README.md` with the operational answers.
- Update `submission.yaml` to `status: complete`.
- Stand down with captain's log.

## Standing-orders scan
- `admiral-at-the-helm`: not applicable in single-session mode.
- `drifting-anchorage`: scope held to `prompt.md` + memory; no new env vars or parallel implementations introduced.
- All other orders trigger only with crew or subagents — none deployed.
