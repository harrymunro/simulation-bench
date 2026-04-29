# Task: Synthetic Mine Throughput Simulation

You are given a synthetic mine topology dataset containing nodes, edges, trucks, loaders, dump points, and scenario configuration files.

Your task is to build a discrete-event simulation in Python using **SimPy** to estimate ore throughput to the primary crusher over an 8-hour shift.

The goal is not only to produce working code, but to produce a clear, reproducible, interpretable modelling-and-simulation analysis.

---

## Operational decision questions

Your analysis should answer the following questions:

1. What is the expected ore throughput to the crusher during the baseline 8-hour shift?
2. What are the likely bottlenecks in the haulage system?
3. Does adding more trucks materially improve throughput, or does the system saturate?
4. Would improving the narrow ramp materially improve throughput?
5. How sensitive is throughput to crusher service time?
6. What is the operational impact of losing the main ramp route?

You may propose one additional scenario if you believe it would help the mine operator make a better decision. This is optional.

---

## Input data

You are provided with the following input files:

```text
data/
├── nodes.csv
├── edges.csv
├── trucks.csv
├── loaders.csv
├── dump_points.csv
└── scenarios/
    ├── baseline.yaml
    ├── trucks_4.yaml
    ├── trucks_12.yaml
    ├── ramp_upgrade.yaml
    ├── crusher_slowdown.yaml
    └── ramp_closed.yaml
```

The mine topology is represented as a directed graph.

### Nodes

Each node has metadata such as:

- `node_id`
- `node_name`
- `node_type`
- `x_m`
- `y_m`
- `z_m`
- optional capacity and service-time metadata

Node types may include:

- loading locations
- crusher / dump locations
- junctions
- parking
- maintenance or service locations

### Edges

Each edge represents a road segment and includes metadata such as:

- `edge_id`
- `from_node`
- `to_node`
- `distance_m`
- `max_speed_kph`
- `road_type`
- `capacity`
- optional metadata

Some road segments are capacity-constrained and should be treated as shared resources if appropriate.

---

## Required modelling approach

Your solution must be a genuine discrete-event simulation using **SimPy**.

The model should represent:

- trucks as active entities
- loaders as constrained resources
- the crusher / dump point as a constrained resource
- capacity-constrained road segments as resources where appropriate
- travel along the mine topology as time-consuming events
- loading, hauling, dumping, and return travel as part of each truck cycle

The simulation should use the topology data to calculate routes and travel times.

A static calculation or simple deterministic spreadsheet-style model is not sufficient.

---

## Conceptual model design

Provide a concise conceptual model design in:

```text
conceptual_model.md
```

Your conceptual model should describe:

### System boundary

What is included in the model, and what is excluded?

### Entities

What moves through the system?

For example:

- trucks
- ore payloads, if modelled separately

### Resources

What constrains the system?

For example:

- loaders
- crusher
- constrained road segments

### Events

What events occur during the simulation?

For example:

- truck dispatched
- truck arrives at loader
- truck joins loader queue
- loading starts
- loading ends
- truck travels loaded to crusher
- truck joins crusher queue
- dumping starts
- dumping ends
- truck returns empty

### State variables

What state is tracked?

For example:

- truck location
- truck loaded / empty status
- queue lengths
- resource busy time
- tonnes delivered
- cycle times

### Assumptions

Where data is missing, make reasonable assumptions and document them clearly.

Separate:

- assumptions derived from the data
- assumptions you introduced
- limitations of the model

### Performance measures

Define the outputs you calculate and how they are measured.

---

## Required scenarios

You should run the provided scenarios and use them to answer the operational decision questions:

| Scenario | Purpose |
|---|---|
| `baseline` | Expected performance under the base 8-truck configuration |
| `trucks_4` | Lower fleet size |
| `trucks_12` | Higher fleet size |
| `ramp_upgrade` | Improved main ramp capacity and speed |
| `crusher_slowdown` | Slower crusher service |
| `ramp_closed` | Main ramp unavailable, requiring rerouting if possible |

You may add one additional scenario if it helps your analysis, but the six scenarios above should be included.

---

## Experimental requirements

Your solution must:

1. Simulate an 8-hour shift.
2. Run at least 30 replications for each required scenario.
3. Use random seed control so results are reproducible.
4. Include stochastic loading, dumping, and/or travel times where appropriate.
5. Report uncertainty around key outputs, such as 95% confidence intervals.
6. Produce machine-readable output files.
7. Include clear instructions for running the model.

---

## Routing and dispatching

You may choose your own routing and dispatching logic, but you must explain it.

For example, you may use:

- shortest-distance routing
- shortest-time routing
- nearest available loader
- fixed assignment of trucks to loading points
- dynamic assignment based on queues or expected cycle time

Your chosen approach should be reasonable and documented.

If a route is impossible because of the topology, the model should fail clearly rather than silently producing misleading results.

---

## Required outputs

Your solution should produce the following files:

```text
conceptual_model.md
results.csv
summary.json
event_log.csv
README.md
```

You may also include additional files such as:

```text
topology.png
animation.gif
animation.mp4
```

Animation is optional and should not come at the expense of model correctness, reproducibility, or interpretability.

---

## `results.csv`

The `results.csv` file should contain scenario-level and replication-level results.

It should include, where applicable:

- `scenario_id`
- `replication`
- `random_seed`
- `total_tonnes_delivered`
- `tonnes_per_hour`
- `average_truck_cycle_time_min`
- `average_truck_utilisation`
- `crusher_utilisation`
- `average_loader_queue_time_min`
- `average_crusher_queue_time_min`

You may include additional columns for loader-specific, road-specific, or bottleneck metrics.

---

## `summary.json`

The `summary.json` file should contain summary-level results suitable for automated checking.

Recommended schema:

```json
{
  "benchmark_id": "001_synthetic_mine_throughput",
  "scenarios": {
    "baseline": {
      "replications": 30,
      "shift_length_hours": 8,
      "total_tonnes_mean": 0,
      "total_tonnes_ci95_low": 0,
      "total_tonnes_ci95_high": 0,
      "tonnes_per_hour_mean": 0,
      "tonnes_per_hour_ci95_low": 0,
      "tonnes_per_hour_ci95_high": 0,
      "average_cycle_time_min": 0,
      "truck_utilisation_mean": 0,
      "loader_utilisation": {},
      "crusher_utilisation": 0,
      "average_loader_queue_time_min": 0,
      "average_crusher_queue_time_min": 0,
      "top_bottlenecks": []
    }
  },
  "key_assumptions": [],
  "model_limitations": [],
  "additional_scenarios_proposed": []
}
```

Use meaningful values rather than zeros.

If you choose a different schema, document it clearly.

---

## `event_log.csv`

The `event_log.csv` file should provide a trace of important simulation events.

It should include columns such as:

```text
time_min
replication
scenario_id
truck_id
event_type
from_node
to_node
location
loaded
payload_tonnes
resource_id
queue_length
```

The event log should make it possible to inspect whether trucks moved through valid routes and whether queueing behaviour occurred at constrained resources.

---

## `README.md`

The README should explain:

1. How to install dependencies.
2. How to run the simulation.
3. How to reproduce the required scenario results.
4. The conceptual model.
5. The main assumptions.
6. The routing and dispatching logic.
7. The key results.
8. The answers to the operational decision questions.
9. The likely bottlenecks.
10. The limitations of the model.
11. Any suggested improvements or further scenarios.

---

## Optional visualisation

You may include a static topology visualisation, such as `topology.png`, showing:

- nodes
- edges
- node types
- loading points
- crusher
- constrained road segments

You may also include a simple animation of truck movements if useful.

Any visualisation or animation should be generated from the model data or simulation event log, not manually fabricated.

---

## Constraints

Use Python.

You may use common packages such as:

```text
simpy
numpy
pandas
scipy
matplotlib
networkx
pyyaml
```

Avoid unnecessary dependencies.

The model should run from a clean environment using the instructions you provide.

---

## Evaluation criteria

Your solution will be evaluated on:

### 1. Conceptual modelling

- clear system boundary
- sensible entity, resource, event, and state definitions
- appropriate assumptions
- clear limitations
- suitable performance measures

### 2. Data and topology handling

- reads the provided input files
- uses the topology meaningfully
- calculates routes and travel times from the graph
- handles constrained road segments appropriately
- avoids hard-coded answers

### 3. Simulation correctness

- uses SimPy properly
- models truck cycles coherently
- models loading, hauling, dumping, and return travel
- represents queues and constrained resources correctly
- records throughput based on completed dump events

### 4. Experimental design

- uses multiple replications
- controls random seeds
- reports uncertainty
- produces reproducible outputs
- handles stochastic behaviour appropriately

### 5. Results and interpretation

- reports the required metrics
- answers the operational decision questions
- identifies likely bottlenecks
- explains operational implications
- avoids overclaiming beyond the model assumptions

### 6. Code quality

- clear structure
- readable code
- configurable parameters
- reasonable separation of model, experiment, analysis, and reporting
- simple dependency management

### 7. Traceability and auditability

- produces a useful event log
- allows inspection of truck movements and state transitions
- supports validation of queueing and resource behaviour

### 8. Efficiency

- reasonable runtime
- reasonable code size
- reasonable token and tool usage, where measurable

---

## Important note

Correctness, reproducibility, and interpretability are more important than visual polish.

A simple, well-explained simulation with defensible assumptions is better than a polished animation attached to a weak model.

