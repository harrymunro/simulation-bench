# Synthetic Mine Throughput Simulation

## Installation

Install required dependencies:

```bash
pip install simpy networkx pandas scipy pyyaml
```

## Running the Model

To run the simulation across all scenarios and generate the outputs:

```bash
python run_all.py --data-dir data --out-dir .
```

This will produce:
- `results.csv`
- `summary.json`
- `event_log.csv`

## Conceptual Model

See `conceptual_model.md` for the detailed conceptual model.

## Routing and Dispatching Logic

Trucks follow a dynamic dispatching logic:
When empty, trucks evaluate all available loaders. For each loader, they compute the expected travel time (using shortest path on the NetworkX graph) plus the expected queue wait time `(queue_length + 1) * mean_service_time`. They dispatch to the loader with the lowest total expected time.

When loaded, trucks travel via the shortest path to the primary crusher. Constrained road segments (like narrow ramps) are modeled as SimPy resources. Trucks must request and acquire these resources before entering the segment and release them upon exiting.

## Assumptions
- Trucks always choose the loader with the minimum expected time (travel + queue).
- Stochasticity follows a truncated normal distribution.
- Crusher and loader service times are normally distributed.

## Limitations
- Breakdowns and maintenance are not explicitly modeled in cycles.
- Traffic congestion beyond capacity limits (speed reduction) is not modeled dynamically.

## Key Results
The `summary.json` file contains the detailed breakdown of the total tonnes and tonners per hour for each scenario, including the baseline, lower/higher fleet size configurations, and ramp constraints.
