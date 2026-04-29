# Simulation Bench

Deployed here: https://simulation-bench.fly.dev/

A benchmark for evaluating agentic software development on modelling and simulation work, beginning with a synthetic open-pit mine haulage problem implemented in SimPy.

The benchmark asks an agent to build a discrete-event simulation from supplied topology data and decision questions. It evaluates not only whether the code runs, but whether the agent can produce a defensible conceptual model, use topology data meaningfully, run experiments, report uncertainty, and interpret bottlenecks.

## Current benchmark

```text
benchmarks/001_synthetic_mine_throughput
```

The task is to estimate ore throughput to a primary crusher over an 8-hour shift using a synthetic mine network.

## Key design choices

V1 deliberately includes:

- one substantial modelling task rather than many toy problems
- fixed decision questions and fixed required scenarios
- room for the agent to choose routing, dispatching, assumptions, and implementation design
- no reference solution in the agent-facing repository
- quantitative harness scripts for runtime, output schema, scenario coverage, LOC, files, and behavioural checks
- human review rubric for conceptual modelling and qualitative judgement

## What can be automated?

The harness can automatically capture or check:

- wall-clock runtime, if run through `harness/measure_run.py`
- process return code
- number of Python files
- lines of code
- required output files
- `summary.json` schema
- `results.csv` columns
- `event_log.csv` columns
- required scenario coverage
- basic behavioural sanity checks across scenarios
- file-size and manifest metadata
- token usage, if supplied by the runner in `token_usage.json` or `run_metrics.json`

The harness cannot reliably automate:

- whether the conceptual model is genuinely good
- whether assumptions are operationally reasonable
- whether bottleneck interpretation is decision-useful
- whether the code structure is elegant
- exact token usage when the agent platform does not expose it

Those are covered by the human scoring rubric in `SCORING_GUIDE.md`.

## Quick start

Install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run the benchmark manually by giving the agent:

```text
benchmarks/001_synthetic_mine_throughput/prompt.md
benchmarks/001_synthetic_mine_throughput/data/
```

After the agent creates a solution and output files, evaluate it:

```bash
python harness/evaluate_submission.py \
  --benchmark-dir benchmarks/001_synthetic_mine_throughput \
  --submission-dir path/to/submission \
  --outputs-dir path/to/submission/outputs \
  --report-out results/evaluation_report.json
```

To time a submission run:

```bash
python harness/measure_run.py \
  --submission-dir path/to/submission \
  --command "python run_experiment.py" \
  --metrics-out path/to/submission/run_metrics.json
```

## Suggested leaderboard columns

- final human score
- automated checks passed
- runtime seconds
- input tokens
- output tokens
- total tokens
- production LOC
- files created
- required scenarios completed
- behavioural checks passed
- human interventions

## Public dashboard

The leaderboard at <https://simulation-bench.fly.dev/> is built from this repository:

- `scores/seed_scores.json` — source of truth for human review scores.
- `submissions/<id>/token_usage.json` and `submissions/<id>/run_metrics.json` — per-run tokens and time.
- `SCORING_GUIDE.md` and `RUN_PROTOCOL.md` — methodology pages.

### Refreshing the dashboard after adding a submission or score

```bash
# 1. Add the new submission folder under submissions/ (use the create-submission skill)
# 2. Append the new review block to scores/seed_scores.json
# 3. Rebuild and deploy:
make deploy
```

`make deploy` runs:

1. `python harness/normalize_tokens.py` — ensures every submission has `token_usage.json` + `run_metrics.json`.
2. `python harness/record_score.py --from-json scores/seed_scores.json` — refreshes `scores/scores.db`.
3. `python harness/build_dashboard.py` — emits `dashboard/src/data/leaderboard.json` and per-submission `.md` files.
4. `cd dashboard && npm run build` — produces `dashboard/dist/`.
5. `flyctl deploy --remote-only` — ships the Caddy container to fly.io.

For a local preview before deploying: `make preview` (serves `dashboard/dist/` on `http://127.0.0.1:4321/`).
