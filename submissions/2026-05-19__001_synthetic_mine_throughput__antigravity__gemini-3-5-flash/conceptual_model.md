# Conceptual Model - Synthetic Mine Throughput Simulation

This document outlines the conceptual design of the discrete-event simulation model developed for the synthetic mine haulage operations.

## System Boundary

### Included in the Model:
- **Haul Road Network**: All nodes (junctions, parking, crusher, loading points) and directed edges (haul roads, bypasses, ramps).
- **Truck Fleet**: Active truck entities with defined load capacities, empty and loaded speeds, and start locations.
- **Loader Stations**: Constrained loader resources at `LOAD_N` and `LOAD_S` with stochastic loading times.
- **Dumping Station**: Constrained primary crusher resource at `CRUSH` with stochastic dumping times.
- **Capacity-Constrained Roads**: Road segments with a capacity of 1 (such as the main ramp `E03_UP`/`E03_DOWN` and pit approaches) modeled as queuing resources.
- **Stochastic Travel Times**: Travel time variation along each edge due to congestion, road conditions, or grader activity.

### Excluded from the Model:
- **Waste Dumping**: The waste dump `WASTE` and its associated routing (as the operational objective is strictly to maximize ore to crusher).
- **Maintenance Bay**: Maintenance routing and refuelling events at `MAINT` (since truck availability in the baseline dataset is 1.00 and no breakdown data is configured).
- **Shift Breaks**: Crib breaks, pre-start checks, or operator changeovers.

---

## Entities

- **Truck**: The primary active entity in the simulation. It moves through the road network, transports ore payloads (100 tonnes), requests loading and dumping resources, and makes local dispatching decisions.

---

## Resources

- **Loaders (`L_N` and `L_S`)**: Located at nodes `LOAD_N` and `LOAD_S` respectively. Each has a capacity of 1, meaning only one truck can be loaded at a time.
- **Crusher (`D_CRUSH`)**: Located at node `CRUSH` with a capacity of 1. Only one truck can dump at a time.
- **Constrained Road Segments**: Directed edges with a capacity of 1 (`E03_UP`, `E03_DOWN`, `E05_TO_CRUSH`, `E05_FROM_CRUSH`, `E07_TO_LOAD_N`, `E07_FROM_LOAD_N`, `E09_TO_LOAD_S`, `E09_FROM_LOAD_S`). Only one truck can traverse each directed segment at any moment.

---

## Events

The simulation is driven by the following chronological event transitions for each truck cycle:

1. **Truck Dispatched**: Truck selects a loader using the dispatching policy.
2. **Road Segment Request**: Truck requests entry to a capacity-constrained edge (if applicable).
3. **Road Segment Entry**: Truck begins traversing the edge.
4. **Road Segment Exit**: Truck completes traversing the edge and releases the road resource.
5. **Loader Arrival**: Truck arrives at the selected loader and joins its queue.
6. **Loading Start**: Loader resource is acquired, and loading begins.
7. **Loading End**: Loading completes, loader resource is released, truck state becomes `loaded`.
8. **Crusher Arrival**: Truck arrives at the crusher and joins its queue.
9. **Dumping Start**: Crusher resource is acquired, and dumping begins.
10. **Dumping End**: Dumping completes, crusher resource is released, tonnage is recorded, truck state becomes `empty`.

---

## State Variables

The simulation engine monitors and updates the following state variables:
- `env.now`: Current simulation time (in minutes).
- `truck.location`: Current node of each truck.
- `truck.state`: Current state of each truck (e.g., `TRAVELLING_EMPTY`, `QUEUEING_LOADER`, `LOADING`, `TRAVELLING_LOADED`, `QUEUEING_CRUSHER`, `DUMPING`).
- `resource.queue`: Queue lengths of loaders, crusher, and capacity-constrained roads.
- `resource.count`: Current number of active users for each resource.
- `total_tonnes_delivered`: Total completed ore tonnage dumped at the crusher.
- `resource.busy_time`: Cumulative busy time of loaders, crusher, and road resources for utilization calculations.
- `truck.cycle_times`: A log of completed round-trip durations for each truck.

---

## Assumptions

### Derived from the Data:
- Nodes and edges CSV files accurately represent the physical coordinate geography and speed limits.
- Trucks travel at the maximum speed limit of each edge, adjusted by their empty speed factor (1.00) or loaded speed factor (0.85).

### Introduced Assumptions:
- **Travel Time Noise**: Modeled using a **lognormal distribution** with a Coefficient of Variation (CV) of 10% ($\text{CV} = 0.10$). Lognormal distribution prevents non-physical negative travel times.
- **Loading and Dumping Truncation**: Sampled from a normal distribution and truncated using $\max(0.1\text{ min}, \text{sample})$ to avoid non-positive times.
- **Dispatching Heuristic**: Trucks are dispatched at `t = 0` simultaneously from `PARK`. For each subsequent cycle, empty trucks at `CRUSH` are dynamically dispatched based on the minimum expected completion time of loading:
  $$\text{score}_L = T_{\text{current} \to L} + (Q_L + A_L) \times T_{\text{load}, L} + T_{\text{load}, L}$$

### Model Limitations:
- Mutual exclusion of opposite-direction single-lane roads (e.g. `E03_UP` and `E03_DOWN`) is simplified such that they are modeled as separate independent resources, meaning they do not block each other.
- No dynamic traffic congestion is modeled other than the queuing at capacity-constrained edges.

---

## Performance Measures

- **Total Ore Throughput (tonnes)**: Total ore tonnes dumped at `CRUSH` before $t = 480$ minutes.
- **Hourly Throughput (tonnes/hour)**: Total tonnes delivered divided by 8 hours.
- **Average Truck Cycle Time (min)**: Average duration of a completed truck cycle (from dispatch to completion of dump).
- **Average Truck Utilization (%)**: Fraction of shift time spent in productive states (`TRAVELLING_EMPTY`, `LOADING`, `TRAVELLING_LOADED`, `DUMPING`).
- **Resource Utilization (%)**: Fraction of shift time spent servicing trucks for loaders and crusher.
- **Average Queue Times (min)**: Average time spent waiting in queue for loaders and crusher.
- **Resource Bottleneck Index**: Defined as $\text{Utilization} \times \text{Mean Queue Wait Time}$.
