# Benchmark 001: Synthetic Mine Throughput

This benchmark evaluates whether an agent can build a SimPy discrete-event simulation for a synthetic mine haulage system.

The agent is given topology and equipment data and must answer decision questions about throughput, bottlenecks, and scenario sensitivity.

## Agent-facing files

Give the agent:

```text
prompt.md
data/
```

## Private / evaluator-facing files

Do not give the agent these during a benchmark run:

```text
expected/
public_tests/
templates/
```

## Required scenarios

The agent should run:

- `baseline`
- `trucks_4`
- `trucks_12`
- `ramp_upgrade`
- `crusher_slowdown`
- `ramp_closed`

## Required outputs

The submission should include:

```text
conceptual_model.md
README.md
results.csv
summary.json
event_log.csv
```

The agent may include optional visualisations, but they are not required.

## Why this benchmark exists

The task is designed to test:

- conceptual modelling
- graph/topology handling
- SimPy implementation
- stochastic experimental design
- scenario analysis
- bottleneck interpretation
- traceability through event logs

