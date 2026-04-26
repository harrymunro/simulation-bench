# Harness

The harness provides quantitative and structural checks. It is not a replacement for human review.

## `measure_run.py`

Runs a submission command and records runtime, return code, stdout/stderr tails, LOC, and file counts.

## `evaluate_submission.py`

Checks required files, CSV columns, `summary.json`, scenario coverage, behavioural sanity checks, LOC, and supplied token metrics.

## Token usage

The harness can report token usage only if it is supplied by the runner in `token_usage.json` or `run_metrics.json`.

