# Submissions

Each submission lives in its own folder under this directory and is identified by a structured name that captures the four facts needed to compare runs on the leaderboard.

## Folder taxonomy

```
submissions/<YYYY-MM-DD>__<benchmark_id>__<harness>__<model>[__<run_tag>]/
```

| Segment        | Required | Description                                                                 | Example                          |
| -------------- | -------- | --------------------------------------------------------------------------- | -------------------------------- |
| `YYYY-MM-DD`   | yes      | Date the run was started, ISO-8601 (UTC).                                   | `2026-04-25`                     |
| `benchmark_id` | yes      | Numeric prefix and slug of the benchmark, matching `benchmarks/<id>`.       | `001_synthetic_mine_throughput`  |
| `harness`      | yes      | Agent runtime / scaffolding used to drive the model. `kebab-case`.          | `claude-code`, `cursor`, `aider` |
| `model`        | yes      | Model identifier the harness invoked. `kebab-case`, no spaces.              | `claude-opus-4-7`, `gpt-5`       |
| `run_tag`      | no       | Optional disambiguator for repeat runs (attempt number, variant, reviewer). | `attempt-2`, `tools-off`         |

Separator is double underscore `__` between segments and single dash inside segments. The optional `run_tag` lets you record multiple runs of the same model on the same date without overwriting each other.

### Examples

```
2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7
2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__attempt-2
2026-05-02__001_synthetic_mine_throughput__cursor__gpt-5
2026-05-02__001_synthetic_mine_throughput__aider__claude-sonnet-4-6__tools-off
```

## Required contents

Each submission folder should contain everything needed for the harness to evaluate it independently:

- `conceptual_model.md` — the agent's written model
- `README.md` — how to install and run the submission
- `run_experiment.py` (or equivalent entrypoint named in the submission's README)
- `outputs/` directory containing:
  - `results.csv`
  - `summary.json`
  - `event_log.csv`
  - any optional artifacts (visualisations, additional scenarios)
- `run_metrics.json` — produced by `harness/measure_run.py`
- `token_usage.json` — optional, supplied by the runner if available
- `results/evaluation_report.json` — produced by `harness/evaluate_submission.py`

## Running the evaluation

Use the `evaluate-submission` skill, or invoke the harness directly:

```bash
python harness/evaluate_submission.py \
  --benchmark-dir benchmarks/<benchmark_id> \
  --submission-dir submissions/<folder> \
  --outputs-dir submissions/<folder>/outputs \
  --run-metrics submissions/<folder>/run_metrics.json \
  --token-usage submissions/<folder>/token_usage.json \
  --report-out submissions/<folder>/results/evaluation_report.json
```
