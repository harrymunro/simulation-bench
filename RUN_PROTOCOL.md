# Run Protocol

This protocol is intended to make agent runs comparable.

## 1. Prepare a clean task context

Give the agent:

- `benchmarks/001_synthetic_mine_throughput/prompt.md`
- the full `data/` folder
- any project-level constraints you want to enforce, such as no internet access

Do not give the agent:

- private expected behaviour notes
- scoring rules, unless you intentionally want the agent to see the scoring rubric
- another agent's solution
- human hints from previous runs

## 2. Standard constraints

Recommended V1 constraints:

```yaml
internet_access: false
max_wall_clock_minutes: 45
human_interventions_allowed: 0
python_version: "3.11+"
allowed_packages:
  - simpy
  - numpy
  - pandas
  - scipy
  - matplotlib
  - networkx
  - pyyaml
```

## 3. Required agent deliverables

The submission should include:

```text
conceptual_model.md
README.md
results.csv
summary.json
event_log.csv
```

The solution may also include:

```text
topology.png
animation.gif
animation.mp4
additional_scenarios/
```

## 4. Quantitative measurement

If possible, run the final solution through:

```bash
python harness/measure_run.py \
  --submission-dir path/to/submission \
  --command "python run_experiment.py" \
  --metrics-out path/to/submission/run_metrics.json
```

This records:

- command
- start time
- end time
- runtime seconds
- return code
- stdout/stderr tails
- Python LOC
- file counts

## 5. Token usage

Exact token usage is platform-dependent. If the platform exposes token usage, save it as:

```text
token_usage.json
```

Suggested schema:

```json
{
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "token_count_method": "exact",
  "estimated_cost_usd": null
}
```

If exact token usage is unavailable, use:

```json
{
  "input_tokens": null,
  "output_tokens": null,
  "total_tokens": null,
  "token_count_method": "unknown",
  "estimated_cost_usd": null
}
```

Do not mix exact and estimated token counts without labelling them.

## 6. Automated evaluation

After the run, execute:

```bash
python harness/evaluate_submission.py \
  --benchmark-dir benchmarks/001_synthetic_mine_throughput \
  --submission-dir path/to/submission \
  --outputs-dir path/to/submission/outputs \
  --run-metrics path/to/submission/run_metrics.json \
  --token-usage path/to/submission/token_usage.json \
  --report-out results/evaluation_report.json
```

If outputs are written directly to the submission root, pass:

```bash
--outputs-dir path/to/submission
```

## 7. Human scoring

Use `SCORING_GUIDE.md` and the reviewer form in:

```text
benchmarks/001_synthetic_mine_throughput/templates/reviewer_form.md
```

## 8. Recording interventions

Record every human nudge, clarification, manual fix, or rerun.

A good benchmark result should distinguish:

- fully autonomous success
- success after one or more hints
- success after manual repair
- failed run

