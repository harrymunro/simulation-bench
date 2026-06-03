# Task: Asia–Europe Container Shipping Throughput

You advise a liner shipping operator that moves containers from Asia to Europe.
Build a **discrete-event simulation in Python using SimPy** to estimate how many
containers (TEU) the service delivers to its primary European port over a 180-day
planning horizon, and use it to answer the operator's decision questions below.

This is a modelling task, not a coding exercise. The value is in a defensible model,
honest experiments, and a clear, decision-useful interpretation. **You decide how to
model the system, what to measure, and how to structure your outputs.** Where this
brief is silent, make a reasonable choice and justify it.

## Operational decision questions

1. What container throughput (TEU) does the service deliver to the primary port over
   the baseline horizon, and with what uncertainty?
2. Where is the binding constraint in this system? Justify your answer with evidence
   from the model, not from how the inputs are labelled.
3. Does adding ships materially increase delivered throughput, or does the system
   saturate? What happens to ships and cycle time as the fleet grows?
4. Would expanding the canal (more transit slots, faster transit) materially improve
   throughput? Explain *why* or why not.
5. How sensitive is throughput to discharge productivity at the destination port?
6. What is the operational impact of losing the canal route entirely?
7. Given everything above, what single intervention would you recommend to raise
   delivered throughput, and what is your evidence?

You may add **one** additional scenario of your own if it strengthens your advice.

## Input data

The `data/` directory contains the network and fleet. The column headers are
self-describing; part of the task is deciding which fields matter and which do not.

```
data/
├── nodes.csv          # ports and maritime waypoints (a directed graph)
├── sea_legs.csv       # directed sea legs: distance, speed limit, type, capacity, closed
├── vessels.csv        # the vessel pool and its attributes
├── berths.csv         # berth / crane capacity at each port
└── scenarios/         # the experiments to run (below)
```

The network is a **directed graph**. Some legs are capacity-constrained; treat them
as shared resources if your model justifies it. Routes and travel times should be
derived from the graph, not assumed. If a required route is impossible (for example
because a leg is closed), the model must **fail clearly** rather than silently
producing misleading results.

## Required experiments

Run every scenario in `data/scenarios/` and use them to answer the decision
questions. The scenarios inherit from `baseline.yaml` and override specific fields:

| Scenario | What it changes |
|---|---|
| `baseline` | The base service configuration |
| `fleet_small` | Fewer vessels |
| `fleet_large` | More vessels |
| `canal_upgrade` | More canal slots and faster transit |
| `port_slowdown` | Slower cranes at the destination port |
| `canal_closed` | The canal is unavailable |

## Experimental requirements

Your solution must:

1. Be a genuine SimPy discrete-event simulation (not a spreadsheet-style calculation).
2. Simulate the full planning horizon defined in the scenario files.
3. Run at least **30 replications** per scenario.
4. Control random seeds so results are reproducible.
5. Include stochastic variation where appropriate (e.g. transit and handling times).
6. Report uncertainty around key outputs (e.g. 95% confidence intervals).
7. Address any start-of-horizon transient appropriately, and say what you did.

## Required deliverables

Produce these files. **Their internal structure is your choice** — there is no fixed
schema — but you must document whatever schema you adopt in `README.md`.

```
conceptual_model.md   # system boundary, entities, resources, events, state,
                      # assumptions (separate data-derived from introduced), limitations
results.csv           # per-replication results (machine-readable)
summary.json          # scenario-level summary suitable for automated reading
event_log.csv         # a trace of important events, enough to audit vessel movements
                      # and to reconstruct delivered throughput
README.md             # how to install and run; your routing/dispatching logic;
                      # the key results; answers to the decision questions; the
                      # bottleneck; limitations; and the schema of your output files
```

Make the machine-readable files genuinely machine-readable: a third party should be
able to locate per-scenario throughput and per-replication results from clear,
conventional column and field names without a bespoke key, and should be able to
reconstruct delivered throughput from the event log. Document your names in `README.md`.

Optional: a topology figure or animation derived from the model or event log. Do not
let visual polish substitute for a correct, well-explained model.

## Constraints

Use Python and common scientific packages (`simpy`, `numpy`, `pandas`, `scipy`,
`matplotlib`, `networkx`, `pyyaml`). Avoid unnecessary dependencies. The model must
run from a clean environment using the instructions you provide.

Correctness, reproducibility, and interpretability matter more than presentation. A
simple, well-explained simulation with defensible assumptions and a correctly
identified bottleneck beats an elaborate one that is confidently wrong.
