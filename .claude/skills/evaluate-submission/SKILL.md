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
7. Reads the resulting `evaluation_report.json` and summarises it for the user, including the intervention log.
8. Performs the **human qualitative review** against the 7-category rubric in `SCORING_GUIDE.md` and reports a 0–100 score with per-category notes.
9. Drafts a `scores/seed_scores.json` entry and (with explicit user confirmation) appends it and refreshes the public leaderboard.

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
- **Human review pointer** — note that the qualitative 0–100 review follows in Step 7. The harness output is *context*, not a final score: per `SCORING_GUIDE.md`, **`Final score = Human quality score + automated bonus/penalty context`**.

Keep the summary tight. The full JSON is on disk; do not paste it in full unless the user asks.

## Step 7 — Human qualitative review (mandatory, do not skip)

Per `SCORING_GUIDE.md` the 100-point rubric is:

| Category | Max | What to assess |
| --- | ---: | --- |
| Conceptual modelling | 20 | system boundary, entities, resources, events, state variables, assumptions, limitations, performance measures; data-derived facts vs. introduced assumptions clearly separated |
| Data and topology handling | 15 | reads input files; uses nodes/edges meaningfully; routes from graph; handles constrained segments; reacts correctly to scenario perturbations; no hard-coded answers |
| Simulation correctness | 20 | proper SimPy use; trucks as active entities; loaders/crusher/constrained roads as resources; load–haul–dump–return cycle coherent; tonnes recorded on completed dump events; queueing plausible |
| Experimental design | 15 | required scenarios run; ≥30 replications; controlled seeds; reported uncertainty; sensible stochasticity; warmup choice explained; reproducible |
| Results and interpretation | 15 | answers the decision questions; identifies bottlenecks plausibly; operational implications; avoids overclaiming; clear results; throughput improvement discussion |
| Code quality and reproducibility | 10 | structure; readability; dependency management; no hardcoded local paths; configurable parameters; clean run instructions; file organisation |
| Traceability and auditability | 5 | `event_log.csv` is useful; truck movements auditable; state transitions visible; queueing inspectable; visualisations derived from sim/event log |

### Inputs to read before scoring

You **must** read these files end-to-end before assigning scores. Do not score from filenames or summaries alone:

1. `submissions/<folder>/conceptual_model.md` — for category 1.
2. `submissions/<folder>/README.md` — decision-question answers (cat. 5), run instructions (cat. 6).
3. The submission's source code (`sim.py`, `sim_core.py`, or whatever the runner declares) — categories 2, 3, 6.
4. `summary.json` and a few rows of `results.csv` — categories 4 and 5.
5. The first 50–100 rows of `event_log.csv` — category 7.
6. `submissions/<folder>/results/evaluation_report.json` (already produced) for the automated context block.
7. `benchmarks/<benchmark_id>/data/scenarios/*.yaml` if you need to verify a scenario perturbation was applied as the benchmark intended.

If the submission is large, read source files in full where they are <500 lines; sample longer files but always read the truck process / event-recording function in full. Do not delegate this to a subagent without then re-reading the high-stakes sections yourself.

### How to score each category

For each of the seven categories:

1. State 2–4 specific observations as **strengths** with file:line citations where possible.
2. State 1–4 specific observations as **weaknesses** with file:line citations where possible.
3. Assign an integer score within `[0, max]`. Calibration anchors:
   - **Max** = excellent on every sub-criterion; reviewer would adopt this approach as a template.
   - **~75% of max** = solid coverage with one or two real concerns; trustworthy as a first pass.
   - **~50% of max** = meets the surface checks but has structural problems a reviewer must work around.
   - **<25% of max** = the category is substantially missing or wrong.
4. Avoid scoring the same defect twice across categories. Pick the most relevant category and mention it once.

Sum the seven category scores into the **total /100**. Do not round, weight, or combine with the automated pass rate — `SCORING_GUIDE.md` is explicit that automation is context, not a multiplier.

### Failure modes checklist

Tick any of the failure modes from `benchmarks/<benchmark_id>/templates/reviewer_form.md` that apply (e.g. "Static calculation rather than DES", "No multiple replications", "Hard-coded outputs"). A submission that triggers one of these caps the total at the category-derived score — do not award points back via interpretation.

### Final judgement

End the human review with a single line answering "Would you trust this model as a first-pass decision-support artefact?" — choose **Yes / Partially / No** with one sentence of justification. This is what the `recommendation` field on the leaderboard records.

### Output format

Present the human review immediately after the automated summary, in this order:

1. One-paragraph automated context recap (runtime, automated checks, token method).
2. Per-category table with `Category | Max | Score | Notes`.
3. Failure modes ticked (omit the section if none).
4. Final judgement line.

Keep notes terse — one or two sentences per category. The full reasoning is for the rubric, not the leaderboard.

## Step 8 — Update and deploy the leaderboard (gated on user confirmation)

The public dashboard at <https://simulation-bench.fly.dev/> reads from `scores/seed_scores.json`. After the human review is complete, **draft** the leaderboard entry, **show it to the user**, and only proceed when they explicitly confirm. The two sub-steps each require their own confirmation, because writing to `seed_scores.json` is a content change and `make deploy` is a production deployment.

### 8a. Draft the leaderboard entry

Construct the JSON object that would be appended to `scores/seed_scores.json` and present it to the user **before writing**. Use this exact shape (match the existing entries):

```json
{
  "submission_id": "<folder name>",
  "reviewer": "<your reviewer label, e.g. opus-subagent or claude-code>",
  "review_date": "<YYYY-MM-DD>",
  "conceptual_modelling": <int 0-20>,
  "data_topology": <int 0-15>,
  "simulation_correctness": <int 0-20>,
  "experimental_design": <int 0-15>,
  "results_interpretation": <int 0-15>,
  "code_quality": <int 0-10>,
  "traceability": <int 0-5>,
  "automated_checks_passed": <int>,
  "automated_checks_total": <int>,
  "behavioural_checks_passed": <int>,
  "recommendation": "<short phrase, e.g. 'Strong submission' / 'Partially trustworthy' / 'Reject'>",
  "notes": "<one sentence covering the most important strength or concern>"
}
```

Field-mapping rules:

- Use the score from Step 7 verbatim — do not silently adjust to make the leaderboard look smoother.
- `automated_checks_passed` / `automated_checks_total` come from `evaluation_report.json` → `automated_checks.passed` / `.total`.
- `behavioural_checks_passed` is the count of checks under `automated_checks.checks` whose `name` is one of `trucks_12_gt_trucks_4`, `baseline_gt_trucks_4`, `ramp_upgrade_ge_baseline`, `crusher_slowdown_lt_baseline`, `ramp_closed_le_baseline`, `truck_count_saturation_plausible`, and that have `passed: true`.
- `submission_id` is the folder name verbatim (no leading `submissions/`).
- `review_date` is **today's** date in `YYYY-MM-DD`.

Then ask the user one clear question: **"Append this entry to `scores/seed_scores.json`? (y/n)"** Wait for an affirmative before writing.

If an entry for the same `submission_id` already exists in the file, surface that **before** drafting and ask whether to (a) replace in place, (b) append a re-review (multiple entries per submission are valid in `seed_scores.json`), or (c) skip. Do not silently duplicate or silently overwrite.

When writing: read the full file, append (or replace) the object inside the JSON array, and write it back. Preserve trailing-newline / indentation conventions of the existing file.

### 8b. Deploy (separate confirmation)

`make deploy` runs `make ingest` → `harness/build_dashboard.py` → `npm run build` → `flyctl deploy --remote-only`. The last step ships a Caddy container to the production fly.io app **simulation-bench**, which is publicly visible.

This is a production deployment. Do **not** run `make deploy` automatically. Ask the user explicitly: **"Run `make deploy` to ship to <https://simulation-bench.fly.dev/>? (y/n)"** Even if the user already authorised the deploy earlier in the same session for a *different* submission, ask again — authorisation does not span submissions.

If the user declines, suggest `make preview` (local-only, no deploy) and stop. Do not nag.

If the user confirms:

- Run `make deploy` from the project root.
- If `flyctl` is missing or not authenticated, surface that immediately rather than failing mid-pipeline; suggest `flyctl auth login`.
- If `npm install` or `npm run build` fails, do **not** retry with `--force` or `--legacy-peer-deps`; show the error and stop. The dashboard build is an integrity check.
- After deploy, confirm the row shows up on the live leaderboard. If `dashboard/src/data/leaderboard.json` has the row but the live site does not, wait ~30s and retry once before flagging an issue.

### 8c. If the user did not ask for an evaluation-and-deploy

If the user's original request was just "evaluate" (not "evaluate and deploy"), make Step 8 *opt-in*: produce the draft entry, show it, and ask whether they want to persist it. Default to no. The skill should never deploy as a side-effect of a plain evaluation request.

## Edge cases

- **No artefacts at all** — the submission has not produced outputs. Stop and tell the user.
- **Folder name does not match the taxonomy** — surface the mismatch, suggest the canonical form, and ask whether to proceed anyway with explicit `--benchmark-dir`.
- **Multiple submissions matching a partial name** — list the matches and ask which one. Do not pick silently.
- **Benchmark id not in `benchmarks/`** — stop. The harness will fail and the user needs to know.
- **`token_usage.json` missing required fields** — flag the deviation from `RUN_PROTOCOL.md` §5 schema; still run the evaluator (the harness tolerates partial token data).
- **Behavioural checks failing despite plausible code** — do not call the run "broken." Per `SCORING_GUIDE.md`, treat failing checks as evidence to investigate during human review.

## Why this exists

The harness is several flags long, the paths repeat, submission layouts vary (root vs `outputs/`), and the human-review rubric needs to be surfaced explicitly so reviewers do not mistake the automated pass rate for the final score. Wrapping it as a skill keeps invocations consistent, produces the same report shape every time, and reminds the user of every step in `RUN_PROTOCOL.md` and every category in `SCORING_GUIDE.md`.
