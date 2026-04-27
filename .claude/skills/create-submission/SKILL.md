---
name: create-submission
description: Scaffold a new submission folder under /submissions for a Simulation Bench run, named per the date__benchmark__harness__model[__run_tag] taxonomy, with the standard subdirectories and a starter metadata file. Use this skill whenever the user wants to create, set up, scaffold, prepare, register, or "make a folder for" a new submission, run, attempt, or benchmark trial — phrasings like "create a new submission folder for X harness using Y model", "set up a run for Opus 4.7 on the mine benchmark", "scaffold a vanilla Claude Code submission", "prep a folder for tomorrow's run" should all trigger it. Also trigger when the user describes a harness/model combo and clearly intends to record a run, even if they don't say the word "submission".
---

# Create a new submission folder

Use this skill to create a properly-named submission directory under `submissions/`, ready for an agent to populate with code and outputs.

## Folder taxonomy

```
submissions/<YYYY-MM-DD>__<benchmark_id>__<harness>__<model>[__<run_tag>]/
```

| Segment      | Source                                                                                            |
| ------------ | ------------------------------------------------------------------------------------------------- |
| date         | Today's date in `YYYY-MM-DD` (UTC) unless the user gave a different one                           |
| benchmark_id | Defaults to `001_synthetic_mine_throughput` (the only benchmark today). Pick from `benchmarks/`.  |
| harness      | The agent runtime (`claude-code`, `cursor`, `aider`, …). Lowercase kebab-case, no spaces.         |
| model        | The model the harness drove. Lowercase kebab-case, no spaces. Strip vendor prefixes if redundant. |
| run_tag      | Optional. Use when the user signals a variant or repeat (e.g. "no skills", "attempt 2").          |

### Normalisation rules

- Lowercase everything.
- Replace spaces with `-`. Replace `_` inside a segment with `-` (the separator between segments is `__`).
- Strip punctuation that is not `-` or alphanumeric.
- Common model normalisations: `Opus 4.7` → `claude-opus-4-7`, `Sonnet 4.6` → `claude-sonnet-4-6`, `GPT-5` → `gpt-5`, `Haiku 4.5` → `claude-haiku-4-5`. Apply the same vendor-prefixed shape the project's docs use.
- Common harness normalisations: `Claude Code` → `claude-code`, `vanilla claude code` → `claude-code` (the "vanilla" / "no skills" detail belongs in `run_tag`), `Cursor` → `cursor`, `Aider` → `aider`.
- Run tags should be short and meaningful: `no-skills`, `attempt-2`, `tools-off`, `with-mcp`. If the user said "vanilla, no skills loaded", use `no-skills`.

## Step 1 — Extract the four (or five) facts

From the user's request, identify:

1. **harness** — what is driving the model
2. **model** — which model is being driven
3. **benchmark_id** — default to `001_synthetic_mine_throughput` if unstated
4. **date** — default to today
5. **run_tag** — only if the user signalled a variant or it disambiguates from an existing folder

If any of (harness, model) is missing or ambiguous, ask one short clarifying question before creating the folder. Do not invent a model name.

If the user mentions an unreleased version, a TBC version, or "latest", record that in a metadata file rather than the folder name. Folder names should stay stable; freeform notes belong in `submission.yaml`.

## Step 2 — Resolve collisions

Before creating the folder, check whether one with the same name already exists. If it does:

- If the user did not specify a `run_tag`, suggest one (`attempt-2`, then `attempt-3`, etc.) and confirm.
- If they did, stop and tell them — do not overwrite.

## Step 3 — Create the directory and seed it with the task

Create the submission directory, then copy the agent-facing inputs in from the benchmark so the run is self-contained:

```
submissions/<folder>/
├── prompt.md           # copied from benchmarks/<benchmark_id>/prompt.md
├── data/               # copied from benchmarks/<benchmark_id>/data/
└── submission.yaml     # metadata about this run (written in the next step)
```

Use these commands from the project root:

```bash
mkdir -p submissions/<folder>
cp benchmarks/<benchmark_id>/prompt.md submissions/<folder>/prompt.md
cp -R benchmarks/<benchmark_id>/data submissions/<folder>/data
cat > submissions/<folder>/token_usage.json <<'JSON'
{
  "input_tokens": null,
  "output_tokens": null,
  "total_tokens": null,
  "token_count_method": "unknown",
  "estimated_cost_usd": null
}
JSON
cat > submissions/<folder>/run_metrics.json <<'JSON'
{
  "command": null,
  "runtime_seconds": null,
  "return_code": null,
  "timed_out": null,
  "note": "Populate via harness/measure_run.py once the run completes."
}
JSON
```

Do not copy `expected/`, `public_tests/`, or `templates/` — those are evaluator-side material the agent must not see. Do not create `outputs/`, `results/`, or a `run_experiment.py` stub; the agent will produce those itself when it runs.

If `prompt.md` or `data/` is missing from the benchmark folder, stop and tell the user — the benchmark is malformed and the run cannot start.

## Step 4 — Write `submission.yaml`

This file captures the structured facts behind the folder name plus any free-form context the folder name cannot hold.

```yaml
submission_id: <folder name>
date: <YYYY-MM-DD>
benchmark_id: <benchmark_id>
harness:
  name: <harness>
  version: <string or "tbc">
  notes: <free-form, e.g. "vanilla, no skills loaded">
model:
  name: <model>
  vendor: <anthropic | openai | google | …>
  notes: <free-form, e.g. "1M context, default thinking budget">
run_tag: <run_tag or null>
operator: <user's name or env, optional>
status: scaffolded     # scaffolded | running | complete | abandoned
intervention:
  category: unrecorded   # autonomous | hints | manual_repair | failed | unrecorded
  notes: ""
```

Leave `intervention.category` as `unrecorded` until the run completes; update it during evaluation per `RUN_PROTOCOL.md` §8.

Populate every field you have evidence for. Use `tbc` for things the user explicitly flagged as not yet known. Leave optional fields as `null` rather than guessing.

## Step 5 — Report what you did

Tell the user:

- The exact folder path you created.
- The decoded segments, so they can spot a typo.
- A reminder that the agent now reads `prompt.md` and `data/` from inside the submission folder, writes its solution there, and the user can then run the `evaluate-submission` skill.

Keep the report short — one block of facts, no preamble.

## Examples

**Example 1**

User: "Create a new submission folder for a vanilla claude code agent harness (no skills loaded) using claude code version tbc, using Opus 4.7."

Folder name:
```
2026-04-25__001_synthetic_mine_throughput__claude-code__claude-opus-4-7__no-skills
```

`submission.yaml` excerpt:
```yaml
harness:
  name: claude-code
  version: tbc
  notes: vanilla, no skills loaded
model:
  name: claude-opus-4-7
  vendor: anthropic
run_tag: no-skills
```

**Example 2**

User: "Set up a run for Cursor with GPT-5 on the mine benchmark, second attempt."

Folder name:
```
2026-04-25__001_synthetic_mine_throughput__cursor__gpt-5__attempt-2
```

**Example 3**

User: "Scaffold a Sonnet 4.6 run, claude code with full skills."

Folder name:
```
2026-04-25__001_synthetic_mine_throughput__claude-code__claude-sonnet-4-6__with-skills
```

## Edge cases

- **Benchmark folder does not exist** — stop and tell the user. The benchmark id must match a directory under `benchmarks/`.
- **User describes a harness/model that does not normalise cleanly** — propose a name, ask for confirmation, then proceed. The folder name is part of the leaderboard's key, so stability matters more than cleverness.
- **User wants to reuse an old folder** — do not. Create a new one with `attempt-N` so prior results are preserved.

## Why this exists

Submission folder names are the primary key on the leaderboard. Hand-typing them invites typos and inconsistent abbreviations across runs. Wrapping the operation as a skill makes every new run start from the same shape with the same metadata file.
