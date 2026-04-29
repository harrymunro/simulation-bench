# Synthetic Mine Throughput Simulation - Design Specification

## 1. Architecture & Topology Graph

We will parse the CSV data into a `MineTopology` class wrapping a `networkx.DiGraph`. 
- **Nodes** will store location and type metadata.
- **Edges** will store distance, speed limits, and calculate a deterministic baseline `travel_time_min` (distance / speed).
- We'll pre-calculate the all-pairs shortest paths (using Dijkstra, weighted by travel time) so trucks can instantly request the path and ETA between any two nodes. 
- If an edge is closed (`closed == True`), we remove it from the graph before running the shortest path algorithm. If a route is impossible, `networkx.NetworkXNoPath` will be caught and the model will cleanly abort.

## 2. Entities & The Simulation Environment

- **Simulation Environment:** We will wrap `simpy.Environment` in a `MineSimulation` class. This class will parse the scenario config, hold the `MineTopology`, and set up resources.
- **Resources:** 
  - Each loader and the crusher will be a `simpy.Resource(capacity=1)`.
  - Constrained roads (like the ramp `E03_UP` and `E03_DOWN`) will be separate directional `simpy.Resource(capacity=edge_capacity)` attached to their respective edges, meaning traffic travelling up does not contend with traffic travelling down, but multiple trucks travelling up contend with each other.
- **Trucks (Active Entities):** A `Truck` class will take the `env`. Its `run()` method will be a `while True:` loop executing the cycle:
  1. Determine next destination (loader or crusher).
  2. Travel: Request road resources node-by-node. Add stochastic noise to the baseline travel time for each edge.
  3. Queue & Serve: Request loader/crusher resource, wait, yield `env.timeout` for service time (drawn from truncated normal, truncated at > 0).
  4. Log: Append row to `event_log` list at every state transition.

## 3. Metrics, Dispatching, & Experiment Runner

- **Dispatch Logic:** `nearest_available_loader` with `shortest_expected_cycle_time` tie-breaker. When a truck leaves the crusher, it queries the loaders. "Nearest" means shortest travel time. "Available" means no queue. If multiple have no queue, it picks the closest. If all have queues, it falls back to the tie-breaker: picking the loader with the lowest `(expected_queue_time + travel_time + service_time)`.
- **Metrics Collection:** We'll track total tonnes delivered at the crusher. The `event_log` will capture start/end of queues, allowing us to compute average queue times and utilizations post-simulation.
- **Experiment Runner:** A script will iterate over all 6 scenario YAML files. For each, it will instantiate `MineSimulation` 30 times (replications), using seeds `base_random_seed + rep_idx`. It will aggregate the results (mean, 95% CI) and dump `summary.json`, `results.csv`, and `event_log.csv`.

## 4. Required Outputs
- `conceptual_model.md`: A concise markdown explanation of the system boundary, entities, resources, events, state variables, assumptions, and performance measures.
- `results.csv`: Row per replication per scenario with key metrics.
- `summary.json`: Aggregated metrics with 95% CIs.
- `event_log.csv`: Raw trace of all truck state transitions.
- `README.md`: Instructions to run.
