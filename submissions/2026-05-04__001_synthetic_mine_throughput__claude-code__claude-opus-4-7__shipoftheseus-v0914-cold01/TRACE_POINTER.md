# Trace Pointer & Reproducibility Notes

This file responds to the upstream maintainer's request for a standard trace
format ("prompt versions, tool calls, token/time, and what the human grader
saw") so others can replicate this submission.

## What is captured here (in this submission)

| Item | File | Notes |
|------|------|-------|
| Prompt actually used | `data/` directory + the upstream `benchmarks/001_synthetic_mine_throughput/prompt.md` (verified `data/nodes.csv` etc. byte-identical to upstream) | Cold mode — only this prompt + data was given to the agent |
| Final code | `mine_sim/`, `tests/`, `run_experiment.py`, `requirements.txt` | Single-process Python; no parallel workers |
| Outputs | `outputs/{results.csv, summary.json, event_log.csv}` + the in-outputs `README.md` and `conceptual_model.md` copies (per upstream evaluator convention) | Real SimPy execution; not synthesised |
| Wall-clock + LOC | `run_metrics.json` | Generated via `harness/measure_run.py`; runtime 4.6 s end-to-end |
| Token usage | `token_usage.json` | `token_count_method: unknown` — Claude Code's agentic session does not expose per-prompt token totals to the agent at submission time |
| Automated + behavioural checks | `results/evaluation_report.json` | 53/53 automated; 6/6 behavioural |
| Self-review scores | `../../scores/seed_scores.json` (entry tagged `reviewer: self-claude-code`) | Honest self-rating; independent reviewer is welcome to overwrite this entry |

## What lives outside this submission (in the producing repo)

The full 15-phase agentic trace — interview, plan, multiverse universe selection
(3 candidate universes scored head-to-head), tournament, sub-phase TDD log,
sprint-regression loop, quality gate evidence, analytical-bound cross-validation
— lives in the producing repo:

```
github.com/whyjp/ShipofTheseus
└── .ShipofTheseus/synthetic_mine_throughput_v0914_cold01/
    ├── timing/{start.json, end.json}
    ├── naming/00-naming.md
    ├── intent/{01-intent.md, 02-intent-review.md, 03-cold-read.md,
    │            04-questions.md, 04-answers.md, 04-autonomy.md,
    │            04-stack.md, 04-verification.md, 04-runtime-prereq.md,
    │            05-decisions.md}
    ├── plan/{06-plan.md, 07-plan-review.md, tournament.md,
    │          candidates/universe-{1,2,3}/{meta, 06-plan, 07-cold-read}.md}
    ├── impl/08-impl-log.md
    ├── quality/09-quality-gate.md
    ├── sprints/{01,02,03}/{inputs,report}.json
    ├── webview/{index, output-observability}.md
    └── handoff/14-handoff.md   ← also includes the bench-rubric self-estimate
                                   AND the analytical-bound vs simulated ratio
                                   per scenario
```

This trace was emitted as part of the autonomous run, not retroactively.

## Reproducing this submission from scratch

```bash
# 1. From this submission folder:
pip install -r requirements.txt
python run_experiment.py
python -m pytest tests/ -q

# 2. Re-evaluate via the upstream harness (from simulation-bench root):
python harness/measure_run.py \
    --submission-dir submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01 \
    --command "python run_experiment.py" \
    --metrics-out submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01/run_metrics.json

python harness/evaluate_submission.py \
    --benchmark-dir benchmarks/001_synthetic_mine_throughput \
    --submission-dir submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01 \
    --outputs-dir   submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01/outputs \
    --run-metrics   submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01/run_metrics.json \
    --token-usage   submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01/token_usage.json \
    --report-out    submissions/2026-05-04__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__shipoftheseus-v0914-cold01/results/evaluation_report.json
```

Per-(scenario, replication) seed = `12345 + 1000 × scenario_idx + replication_idx`.
Outputs are bit-stable for fixed inputs and seeds.

## Honesty notes (re: maintainer's safety / hallucination request)

Engineering recommendations in this submission's `README.md §8` are scored by the
producing agent against the analytical bound (independent of the simulation) —
see `outputs/README.md §8` and the `analytical_bound_ratio` rows in the producing
repo's `handoff/14-handoff.md`. We tag each recommendation by evidence grade:

- **A** (analytical+sim agreement): ramp non-binding finding, crusher binding,
  trucks-12 saturation.
- **B** (sim-only with stochastic confidence interval): ramp_closed magnitude
  (− 0.6 %) — small enough that a slightly different routing graph could move
  it, though direction is robust.
- **C** (assumption-derived, not directly validated): the proposed
  `trucks_10_ramp_upgrade` further-scenario suggestion — the agent has not run
  this scenario; it is a recommendation for the operator/maintainer.

The agent does not claim grade-A confidence on grade-B or grade-C statements.

## Cost ledger
- Claude Code session approximate wall clock: 18.5 minutes (full agentic run from
  prompt receipt through 5-deliverable handoff).
- `run_experiment.py` measured by `measure_run.py`: 4.6 seconds.
- Token totals: not captured (see `token_usage.json`).
- Human interventions: 0 (phase-04 answers were pre-baked by the caller spec; no
  ack required during the autonomous run).
