# Synthetic Mine Throughput Simulation Design

## 1. System Boundary and Conceptual Model

The simulation bounds include the physical road network (topology), the truck fleet, the ore loading faces, and the primary crusher. The simulation models a single 8-hour shift.

### Entities
*   **Trucks:** Active agents moving through the system. Trucks carry a `payload_tonnes` value and exist in either a loaded or empty state.

### Resources
*   **Loaders:** Capacity-constrained resources (capacity 1). Time to load is a truncated normal distribution.
*   **Crusher:** Capacity-constrained resource (capacity 1). Time to dump is a truncated normal distribution.
*   **Constrained Edges:** Any road segment with a defined `capacity` < 999 (e.g., the narrow ramp) acts as a capacity-constrained resource. Trucks must acquire the edge resource to travel on it and release it once traversed.

### Events
*   `dispatch_empty`: Truck calculates route to loader and begins travel.
*   `arrive_loader`: Truck arrives at loading node and joins queue (or begins loading).
*   `finish_loading`: Loading completes. Truck changes state to 'loaded'.
*   `dispatch_loaded`: Truck calculates route to crusher and begins travel.
*   `arrive_crusher`: Truck arrives at crusher node and joins queue (or begins dumping).
*   `finish_dumping`: Dumping completes. Ore is recorded. Truck changes state to 'empty'.
*   `enter_edge` / `exit_edge`: Occurs iteratively during travel for capacity-constrained segments.

### State Variables
*   **Truck:** Current location, loaded/empty status, cycle start time.
*   **System Metrics:** Total tonnes delivered, resource queue lengths, resource utilization time.

---

## 2. Architecture and Data Flow

### 2.1 Graph Topology (NetworkX)
The mine topology is built as a `networkx.DiGraph`.
*   **Nodes:** Contain spatial coordinates and metadata. If a node is a loader or crusher, it is associated with a SimPy Resource.
*   **Edges:** Contain distance, speed limit, and capacity. The base travel time is `distance_m / (max_speed_kph * 1000 / 60)` (converted to minutes).
*   **Edge Resources:** When the simulation initializes, edges with finite capacities are assigned a SimPy Resource.

### 2.2 Pathfinding and Dispatching
We utilize a Segment-by-Segment process model.
1.  **Loaded Truck:** Queries `networkx.shortest_path(weight='travel_time')` from current node to `CRUSH`.
2.  **Empty Truck:** We evaluate all available loaders. For each loader:
    *   Compute expected travel time via shortest path.
    *   Add expected queue wait time: `(current_queue_length + 1) * expected_load_time`.
    *   Select the loader with the minimum total expected time.

### 2.3 Stochasticity
*   **Travel Times:** Actual travel time on a segment is sampled from `normal(mean=base_time, std=base_time * travel_time_noise_cv)`.
*   **Service Times:** Loading and dumping times are sampled from `truncated_normal(mean, std, min=0)`.

---

## 3. Implementation Modules

*   `main.py`: Entry point. Parses arguments and runs scenarios.
*   `config.py`: Reads scenario YAMLs and dataset CSVs.
*   `topology.py`: Builds the NetworkX graph and handles pathfinding lookups.
*   `simulation.py`: The core SimPy environment. Houses the `MineSimulation` class, `Truck` processes, and Resources.
*   `metrics.py`: Classes to collect event logs, track KPIs, and calculate utilizations.
*   `output.py`: Writes `results.csv`, `summary.json`, and `event_log.csv`. Calculates confidence intervals.

---

## 4. Execution and Replications

For each scenario:
1.  Initialize metrics collection.
2.  Loop `replications` times (e.g., 30):
    *   Set `random.seed(base_seed + rep_number)`.
    *   Initialize SimPy env and Topology.
    *   Create Truck processes.
    *   Run for `shift_length_hours * 60` minutes.
    *   Compile replication results.
3.  Aggregate results across replications to produce CI bounds and output files.
