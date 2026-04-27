---
name: evaluate-submission
description: Run the Simulation Bench automated harness against a submission folder under /submissions and produce an evaluation_report.json plus a concise summary. Use this skill whenever the user asks to evaluate, score, grade, run the harness on, or check a submission to the Simulation Bench — phrasings like "evaluate submission X", "run the harness on Y", "score the latest run", "did model Z pass?", "check submissions/<folder>" should all trigger it. Also use when the user mentions a submission folder name that follows the date__benchmark__harness__model taxonomy, even if they don't say the word "evaluate".
---

# Evaluate a Simulation Bench submission

Use this skill to run `harness/evaluate_submission.py` against a submission and report results clearly. The skill must reflect the full protocol in `RUN_PROTOCOL.md` and the rubric in `SCORING_GUIDE.md` — both the automated layer and the human qualitative layer.

## What this skill does

1. Resolves the submission folder under `submissions/`.
2. Decodes the folder name to extract benchmark id, harness, model, date, and any run tag.
3. Locates the artefacts (either under `outputs/` or at the submission root).
4. Optionally records runtime by invoking `harness/measure_run.py` when missing.
5. Validates `token_usage.json` shape if present.
6. Invokes `harness/evaluate_submission.py` with all the right paths.
7. Reads the resulting `evaluation_report.json` and summarises it for the user, including the human-review next steps and intervention log.

## Submission folder layout

Submissions live in `submissions/<folder>` where the folder name follows the taxonomy:

```
<YYYY-MM-DD>__<benchmark_id>__<harness>__<model>[__<run_tag>]
```

Per `RUN_PROTOCOL.md` §3 the **required deliverables** are:

```text
conceptual_model.md
README.md
results.csv
summary.json
event_log.csv
```

Optional deliverables: `topology.png`, `animation.gif`, `animation.mp4`, `additional_scenarios/`.

Other files the harness consumes when present:

- `run_metrics.json` — produced by `harness/measure_run.py`.
- `token_usage.json` — per `RUN_PROTOCOL.md` §5 schema.
- `results/evaluation_report.json` — produced by this skill.
- `interventions.md` (or notes in `README.md`) — per `RUN_PROTOCOL.md` §8.

If the submission folder does not yet exist, ask the user where the submission lives or whether they would like to create it via the `create-submission` skill.

## Step 1 — Decode the folder name

Split the folder name on `__`. You should get four or five segments:

| Index | Meaning      |
| ----- | ------------ |
| 0     | run date     |
| 1     | benchmark id |
| 2     | harness      |
| 3     | model        |
| 4     | run tag (optional) |

The benchmark id maps to a folder under `benchmarks/`. If the folder is missing or the segment is malformed, stop and tell the user — do not guess.

## Step 2 — Locate the artefacts (outputs-dir resolution)

Required deliverables may live in either of two layouts:

1. **Nested**: `submissions/<folder>/outputs/{results.csv, summary.json, event_log.csv, conceptual_model.md, README.md}`
2. **Flat**: those same files directly under `submissions/<folder>/`

Check for `summary.json` and `results.csv` to decide:

- If `submissions/<folder>/outputs/summary.json` exists → use `--outputs-dir submissions/<folder>/outputs`.
- Else if `submissions/<folder>/summary.json` exists → use `--outputs-dir submissions/<folder>` (per `RUN_PROTOCOL.md` §6 fallback).
- Else stop: the submission has not produced artefacts.

## Step 3 — Decide whether to measure runtime

If `submissions/<folder>/run_metrics.json` is missing **and** the submission has an executable entrypoint (`run_experiment.py`, `sim.py`, or whatever the submission's own README declares), ask the user whether to time it. If yes, run from the project root:

```bash
python harness/measure_run.py \
  --submission-dir submissions/<folder> \
  --command "<entrypoint command>" \
  --metrics-out submissions/<folder>/run_metrics.json
```

Do not invent an entrypoint. If you cannot find one, skip and tell the user runtime metrics will be absent. Note that `measure_run.py` enforces a default 2700s (45 min) timeout consistent with `RUN_PROTOCOL.md` §2 `max_wall_clock_minutes: 45`.

## Step 4 — Validate token usage shape (required, soft-fail)

Per `RUN_PROTOCOL.md` §5, every submission MUST contain a `token_usage.json` and a `run_metrics.json`. Schema for `token_usage.json`:

```json
{
  "input_tokens": 0,
  "output_tokens": 0,
  "total_tokens": 0,
  "token_count_method": "exact",
  "estimated_cost_usd": null
}
```

Soft-fail behaviour (do not abort):

- If `token_usage.json` is missing → print a loud warning telling the operator to generate the file (the dashboard treats it as `unrecorded`).
- If `run_metrics.json` is missing → print a loud warning and suggest `harness/measure_run.py`.
- If `token_count_method == "unknown"` → flag it explicitly in the summary so reviewers know the row will show `—` on the leaderboard.

Surface `token_count_method` (`"exact"`, `"reported"`, `"estimated"`, or `"unknown"`) in the report summary regardless.

## Step 5 — Run the evaluator

From the project root:

```bash
python harness/evaluate_submission.py \
  --benchmark-dir benchmarks/<benchmark_id> \
  --submission-dir submissions/<folder> \
  --outputs-dir <resolved outputs path from Step 2> \
  --run-metrics submissions/<folder>/run_metrics.json \
  --token-usage submissions/<folder>/token_usage.json \
  --report-out submissions/<folder>/results/evaluation_report.json
```

Omit `--run-metrics` and `--token-usage` if those files do not exist. The harness exits 0 when every automated check passes and 1 otherwise — a non-zero exit is informational, not a skill failure.

## Step 6 — Summarise the report

Read `submissions/<folder>/results/evaluation_report.json` and present:

- **Header** — folder name decoded into date, benchmark, harness, model, run tag.
- **Required deliverables** — confirm all five from `RUN_PROTOCOL.md` §3 are present; flag any missing.
- **Required scenarios** — the six benchmark scenarios (`baseline`, `trucks_4`, `trucks_12`, `ramp_upgrade`, `crusher_slowdown`, `ramp_closed`) — flag any absent from `summary.json`.
- **Automated checks** — passed/total and pass rate; list failed checks with their messages.
- **Scenario means** — `scenario_total_tonnes_means` as a small table.
- **Behavioural checks** — call out any failures and remind the user that per `SCORING_GUIDE.md` a failure may indicate a model bug, a scenario not applied correctly, or a legitimate modelling choice that needs human review — *not* an automatic disqualification.
- **Quantitative metrics** — runtime seconds, return code, timed_out flag, LOC, file count, token usage with `token_count_method` (note when any are `null`).
- **Intervention status** — read `submission.yaml.intervention.category`. Surface one of: `autonomous`, `hints`, `manual_repair`, `failed`, `unrecorded`. If the field is missing or unrecognised, prompt the operator to fill it in (per `RUN_PROTOCOL.md` §8); the dashboard will render `?` until they do.
- **Human review pointer** — remind the user that `SCORING_GUIDE.md` defines the 100-point rubric:

  | Category | Points |
  | --- | ---: |
  | Conceptual modelling | 20 |
  | Data and topology handling | 15 |
  | Simulation correctness | 20 |
  | Experimental design | 15 |
  | Results and interpretation | 15 |
  | Code quality and reproducibility | 10 |
  | Traceability and auditability | 5 |

  Point to `benchmarks/<benchmark_id>/templates/reviewer_form.md` as the form to fill in. Make clear that **`Final score = Human quality score + automated bonus/penalty context`** — the harness output is context, not a final score.

Keep the summary tight. The full JSON is on disk; do not paste it in full unless the user asks.

## Edge cases

- **No artefacts at all** — the submission has not produced outputs. Stop and tell the user.
- **Folder name does not match the taxonomy** — surface the mismatch, suggest the canonical form, and ask whether to proceed anyway with explicit `--benchmark-dir`.
- **Multiple submissions matching a partial name** — list the matches and ask which one. Do not pick silently.
- **Benchmark id not in `benchmarks/`** — stop. The harness will fail and the user needs to know.
- **`token_usage.json` missing required fields** — flag the deviation from `RUN_PROTOCOL.md` §5 schema; still run the evaluator (the harness tolerates partial token data).
- **Behavioural checks failing despite plausible code** — do not call the run "broken." Per `SCORING_GUIDE.md`, treat failing checks as evidence to investigate during human review.

## Why this exists

The harness is several flags long, the paths repeat, submission layouts vary (root vs `outputs/`), and the human-review rubric needs to be surfaced explicitly so reviewers do not mistake the automated pass rate for the final score. Wrapping it as a skill keeps invocations consistent, produces the same report shape every time, and reminds the user of every step in `RUN_PROTOCOL.md` and every category in `SCORING_GUIDE.md`.
