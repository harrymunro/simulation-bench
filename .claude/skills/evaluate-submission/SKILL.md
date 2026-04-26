---
name: evaluate-submission
description: Run the Simulation Bench automated harness against a submission folder under /submissions and produce an evaluation_report.json plus a concise summary. Use this skill whenever the user asks to evaluate, score, grade, run the harness on, or check a submission to the Simulation Bench — phrasings like "evaluate submission X", "run the harness on Y", "score the latest run", "did model Z pass?", "check submissions/<folder>" should all trigger it. Also use when the user mentions a submission folder name that follows the date__benchmark__harness__model taxonomy, even if they don't say the word "evaluate".
---

# Evaluate a Simulation Bench submission

Use this skill to run `harness/evaluate_submission.py` against a submission and report results clearly.

## What this skill does

1. Resolves the submission folder under `submissions/`.
2. Decodes the folder name to extract benchmark id, harness, model, date, and any run tag.
3. Optionally records runtime by invoking `harness/measure_run.py` (only when the submission has not been run yet).
4. Invokes `harness/evaluate_submission.py` with all the right paths.
5. Reads the resulting `evaluation_report.json` and summarises it for the user.

## Submission folder layout

Submissions live in `submissions/<folder>` where the folder name follows the taxonomy:

```
<YYYY-MM-DD>__<benchmark_id>__<harness>__<model>[__<run_tag>]
```

For example:

```
submissions/2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7
```

A submission folder is expected to contain:

- `outputs/` with `results.csv`, `summary.json`, `event_log.csv`
- `run_metrics.json` (produced by `harness/measure_run.py`)
- `token_usage.json` (optional)
- `results/evaluation_report.json` after evaluation

If the submission folder does not yet exist, ask the user where the submission lives or whether they would like to create the folder using the documented taxonomy.

## Step 1 — Decode the folder name

Split the folder name on `__`. You should get four or five segments:

| Segment index | Meaning      |
| ------------- | ------------ |
| 0             | run date     |
| 1             | benchmark id |
| 2             | harness      |
| 3             | model        |
| 4 (optional)  | run tag      |

The benchmark id maps directly to a folder under `benchmarks/`. If the folder is missing or the segment is malformed, stop and tell the user — do not guess.

## Step 2 — Decide whether to measure runtime

If `submissions/<folder>/run_metrics.json` is missing **and** the submission has an executable entrypoint (`run_experiment.py` or whatever the submission's own README declares), ask the user whether to time it. If yes, run:

```bash
python harness/measure_run.py \
  --submission-dir submissions/<folder> \
  --command "<entrypoint command>" \
  --metrics-out submissions/<folder>/run_metrics.json
```

Do not invent an entrypoint. If you cannot find one, skip this step and tell the user the runtime metrics will be absent.

## Step 3 — Run the evaluator

From the project root:

```bash
python harness/evaluate_submission.py \
  --benchmark-dir benchmarks/<benchmark_id> \
  --submission-dir submissions/<folder> \
  --outputs-dir submissions/<folder>/outputs \
  --run-metrics submissions/<folder>/run_metrics.json \
  --token-usage submissions/<folder>/token_usage.json \
  --report-out submissions/<folder>/results/evaluation_report.json
```

Omit `--run-metrics` and `--token-usage` if those files do not exist. The harness exits 0 when every automated check passes and 1 otherwise — a non-zero exit is informational, not a failure of the skill itself.

## Step 4 — Summarise the report

Read `submissions/<folder>/results/evaluation_report.json` and present:

- **Header** — folder name, decoded into date, benchmark, harness, model, run tag.
- **Automated checks** — passed/total and pass rate. List any failed checks with their messages.
- **Scenario means** — `scenario_total_tonnes_means` as a small table.
- **Quantitative metrics** — runtime seconds, return code, LOC, files, token usage (note when any are `null`).
- **Next steps** — remind the user that the SCORING_GUIDE rubric is still required for the human portion.

Keep the summary tight. The full JSON is on disk, so do not paste it in full unless the user asks.

## Edge cases

- **No `outputs/` folder yet** — the submission has not produced artifacts. Stop and tell the user; do not run the evaluator on an empty directory.
- **Folder name does not match the taxonomy** — surface the mismatch, suggest the canonical form, and ask whether to proceed anyway with explicit `--benchmark-dir`.
- **Multiple submissions matching a partial name** — if the user gave only a date or a model, list the matches and ask which one. Do not pick silently.
- **Benchmark id not in `benchmarks/`** — stop. The harness will fail and the user needs to know.

## Why this exists

The harness is several flags long, the paths repeat, and submission folders follow a specific taxonomy that is easy to mistype. Wrapping it as a skill keeps invocations consistent and produces the same evaluation report shape every time, which is what the leaderboard depends on.
