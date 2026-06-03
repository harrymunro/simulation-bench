# Benchmark 002: Asia–Europe Container Shipping Throughput

This benchmark evaluates whether an agent can build a SimPy discrete-event
simulation of a liner container service from two Asian export hubs (Shanghai,
Singapore) to a primary European import port (Rotterdam), via the Suez Canal with
a Cape of Good Hope reroute.

It is the **maximum-difficulty** member of the suite. Relative to 001 it:

- runs under **reduced hand-holding** — the agent-facing `prompt.md` gives the
  business questions and raw data but **not** the entity/resource/event checklist,
  the required output columns, or the `summary.json` schema; the agent must derive
  the conceptual model and decide its own output structure;
- contains **designed, verified traps** rather than monotonic scenarios (see
  `expected/private_expected_behaviour.md`); and
- is scored by a harness that **re-derives throughput from the event log** and
  cross-checks it against the submitted summary (see `expected/scoring_rules.yaml`).

## Agent-facing files

Give the agent only:

```text
prompt.md
data/
```

## Private / evaluator-facing files

Do **not** give the agent these during a run:

```text
expected/            # scoring_rules.yaml, summary_schema.json, private_expected_behaviour.md
public_tests/
templates/
```

`expected/reference_solution/` (a private oracle simulation used to verify the
traps and generate calibration numbers) is git-ignored and never shipped.

## Required scenarios

`baseline`, `fleet_small`, `fleet_large`, `canal_upgrade`, `port_slowdown`,
`canal_closed`. The agent may add one scenario of its own.

## Required outputs

```text
conceptual_model.md
README.md
results.csv
summary.json
event_log.csv
```

The internal structure of these files is the agent's choice; the harness locates
the throughput series tolerantly per `expected/scoring_rules.yaml`.

## How it is evaluated

```bash
python harness/evaluate_submission.py \
  --benchmark-dir benchmarks/002_container_shipping_throughput \
  --submission-dir submissions/<folder> \
  --outputs-dir submissions/<folder>/outputs \
  --report-out submissions/<folder>/results/evaluation_report.json
```

The harness is benchmark-aware: required files, scenarios, the primary metric, the
behavioural checks, and the event-log cross-check are all read from
`expected/scoring_rules.yaml`. Human qualitative review follows `SCORING_GUIDE.md`,
and the reviewing model + harness are recorded with every score.

## Why this benchmark exists

To test, under conditions where presentation alone cannot earn marks:

- conceptual modelling without a supplied template;
- meaningful directed-graph routing with a real reroute;
- correct representation of the *true* bottleneck versus the labelled one;
- recognising saturation and diminishing returns;
- honest, decision-useful interpretation and a non-obvious recommendation.
