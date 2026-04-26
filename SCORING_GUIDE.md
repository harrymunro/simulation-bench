# Scoring Guide

The benchmark has an automated quantitative layer and a human qualitative layer.

## Recommended final score

```text
Final score = Human quality score + automated bonus/penalty context
```

For V1, do not let efficiency dominate. A fast, cheap, wrong simulation is a very small bonfire.

## Human quality score: 100 points

| Category | Points |
|---|---:|
| Conceptual modelling | 20 |
| Data and topology handling | 15 |
| Simulation correctness | 20 |
| Experimental design | 15 |
| Results and interpretation | 15 |
| Code quality and reproducibility | 10 |
| Traceability and auditability | 5 |

## 1. Conceptual modelling, 20 points

Assess whether the agent defines:

- system boundary
- entities
- resources
- events
- state variables
- assumptions
- limitations
- performance measures

High score: clear, concise, useful conceptual model that separates data-derived facts from introduced assumptions.

Low score: jumps straight into code or gives vague modelling waffle with no operational content.

## 2. Data and topology handling, 15 points

Assess whether the solution:

- reads the input files
- uses nodes and edges meaningfully
- calculates routes and travel times from the graph
- handles constrained road segments
- avoids hard-coded answers
- reacts correctly to scenario perturbations

## 3. Simulation correctness, 20 points

Assess whether the model:

- uses SimPy properly
- represents trucks as active entities
- represents loaders, crusher, and constrained roads as resources
- models loading, hauling, dumping, and return travel coherently
- records tonnes based on completed dump events
- handles queues and resource occupancy plausibly

## 4. Experimental design, 15 points

Assess whether the solution:

- runs required scenarios
- uses at least 30 replications
- controls random seeds
- reports uncertainty
- uses stochasticity sensibly
- explains warm-up choice or lack of warm-up
- supports reproducibility

## 5. Results and interpretation, 15 points

Assess whether the agent:

- answers the decision questions
- identifies bottlenecks plausibly
- explains operational implications
- avoids overclaiming
- presents clear results
- discusses what would improve throughput

## 6. Code quality and reproducibility, 10 points

Assess:

- structure
- readability
- simple dependency management
- no hard-coded local paths
- configurable parameters
- clean run instructions
- reasonable file organisation

## 7. Traceability and auditability, 5 points

Assess whether:

- `event_log.csv` is useful
- truck movements can be audited
- state transitions are visible
- queueing/resource behaviour can be inspected
- visualisation, if present, is derived from the simulation or event log

## Automated quantitative metrics

The evaluator reports, but does not fully judge:

- runtime seconds
- return code
- Python LOC
- file counts
- output files present
- schema coverage
- scenario coverage
- behavioural sanity checks
- token usage if supplied

## Suggested interpretation of automated behavioural checks

Treat behavioural checks as evidence, not as absolute truth.

For example:

- `trucks_12` should usually produce higher throughput than `trucks_4`
- `ramp_upgrade` should usually improve or maintain throughput versus baseline
- `crusher_slowdown` should usually reduce throughput
- `ramp_closed` should usually reduce throughput or force rerouting

A failing behavioural check may reveal:

- a model bug
- a scenario not applied correctly
- a legitimate modelling choice that should be reviewed manually

