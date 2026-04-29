# Synthetic Mine Throughput Simulation

This project contains a discrete-event simulation built with Python and **SimPy** to model and estimate ore throughput to a primary crusher in a synthetic mine operation over an 8-hour shift.

## Requirements and Installation

The simulation depends on a standard Python 3 environment.

Install the required dependencies using `pip`:

```bash
pip install simpy pandas numpy networkx scipy pyyaml
```

## Running the Simulation

Execute the simulation script from the root directory:

```bash
python3 simulation.py
```

This will automatically:
1. Load all data from the `data/` directory.
2. Run all required scenarios (30 replications each).
3. Generate the outputs: `results.csv`, `summary.json`, and `event_log.csv`.

## Conceptual Model

The simulation is built using a discrete-event approach with `simpy`.
A complete description of the system boundary, entities, resources, and state variables is available in [conceptual_model.md](conceptual_model.md).

Key concepts:
- **Active Entities**: Trucks.
- **Constrained Resources**: Loaders, Dump Points (Crusher), and single-lane road segments (edges with `capacity=1`).
- **Graph-based Routing**: `networkx` is used to represent the mine topology.

## Main Assumptions

1. **Wait locations**: Trucks wait at the start node of a constrained edge until it is entirely clear before entering.
2. **Dispatching**: Trucks use a dynamic "shortest expected cycle time" heuristic. They compute the empty travel time to each loader plus the expected wait time (based on trucks currently en route and trucks already in the queue).
3. **No interruptions**: Operator breaks, shift handover delays, and maintenance breakdowns within the 8-hour shift are excluded.
4. **Stochastic distributions**: Load, dump, and travel times follow truncated normal distributions.

## Routing and Dispatching Logic

- **Routing**: Static shortest-path weights are precalculated for empty and loaded trucks based on edge distances and specific speed limits (in `networkx`).
- **Dispatching**: When a truck is empty (either starting at PARK or returning from the CRUSH dump point), it dynamically evaluates all reachable loaders. It selects the loader that minimizes: `travel_time + (queue_length + active_count + trucks_en_route) * mean_load_time`. This actively prevents all trucks from flocking to a single loader simultaneously.

## Operational Decision Questions

### 1. Expected ore throughput
The baseline expected ore throughput is **~12,650 tonnes** over the 8-hour shift, equating to roughly **1,580 tonnes per hour (tph)**.

### 2. Likely bottlenecks
The primary bottleneck in the haulage system is the **Primary Crusher**. In the baseline scenario, its utilization is consistently around **92%**, indicating it is operating near maximum practical capacity given the stochastic arrival of trucks.

### 3. Adding more trucks (Fleet sizing)
Adding more trucks (`trucks_12` scenario) results in a system saturation point. Throughput marginally increases from ~12,650t to ~13,023t, but crusher utilization maxes out at **95%**, and average queue times at the crusher explode from **~3 minutes to over 14 minutes**. Adding trucks yields heavily diminishing returns because the crusher cannot process the ore fast enough. Conversely, reducing to 4 trucks (`trucks_4`) drops throughput significantly to ~7,580t, leaving the crusher underutilized (~56%).

### 4. Improving the narrow ramp
Upgrading the narrow main ramp (`ramp_upgrade` scenario) does **not** materially improve throughput (resulting in ~12,580t, within the margin of error of the baseline). This is because the narrow ramp is not the bottleneck; the crusher is. Upgrading the ramp only causes trucks to reach the heavily-utilized crusher faster, where they end up waiting anyway.

### 5. Sensitivity to crusher service time
The system is highly sensitive to the crusher's service time. In the `crusher_slowdown` scenario (mean dump time increased to 7.0 min), total throughput drops catastrophically to **~6,450 tonnes**. Crusher queue times skyrocket to over **27 minutes** per truck, causing widespread starvation at the loaders (loader utilization drops below 40%).

### 6. Operational impact of losing the main ramp
Losing the main ramp (`ramp_closed` scenario) has **virtually zero impact** on overall steady-state throughput. Trucks simply detour via the bypass route (`J7` -> `J8`). Because the system throughput is bounded by the crusher, adding a couple of minutes to the travel time for the initial trip from `PARK` to the loaders has no long-term effect on the 8-hour shift's total delivered ore.

## Limitations and Future Improvements
- **Model Limitations**: Continuous spatial physics (acceleration curves, tight cornering slowdowns, vehicle passing) are abstracted into discrete time delays.
- **Suggested Improvements**: The crusher could be modeled dynamically with a finite holding bin capacity and a continuous processing rate, allowing trucks to dump immediately if the bin is not full, rather than waiting for discrete dumping operations to finish sequentially. An alternative stockpile dump point could also be added to keep trucks moving if the primary crusher is full.
