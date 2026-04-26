# Simulation Bench

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

