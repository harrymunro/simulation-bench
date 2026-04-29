# Synthetic Mine Throughput Simulation - Conceptual Model

## 1. System Boundary and Topography
The system is modeled as a discrete-event simulation running a directed graph (NetworkX) to represent the `MineTopology`. 
The nodes represent locations (e.g., parking, loaders, crushers) and edges represent paths between locations.
Edges track distance, maximum speed, and a baseline calculated travel time (`distance / speed`). 

## 2. Entities
- **Active Entities:** 
  - **Trucks:** Operate in a continuous cycle over the shift length (`while True:`). Their cycle includes deciding on a destination, traveling, queuing, loading, traveling, queuing, and dumping.

## 3. Resources
- **Loaders:** Modeled as a single-capacity resource (`capacity=1`).
- **Crusher:** Modeled as a single-capacity resource (`capacity=1`).
- **Road Segments:** Constrained edges (like narrow ramps) are modeled as directional resources (`capacity=edge_capacity`). This means trucks traveling the same direction contend for capacity, but opposite directions do not block each other unless specifically modeled as shared.

## 4. State Variables
- **Truck State:** `current_node`, `loaded` (boolean), `payload` (tonnes).
- **System State:** `total_tonnes_delivered` (aggregated over the shift).

## 5. Events
The simulation captures key transitions (state changes) into an event log:
- `travel_start`: Truck departs a node.
- `queue_road_start`: Truck arrives at a constrained road segment and waits for capacity.
- `queue_load_start` / `queue_dump_start`: Truck arrives at a loader or crusher and waits in queue.
- `load_start` / `dump_start`: Truck begins the loading or dumping service.
- `load_end` / `dump_end`: Truck completes service.

## 6. Rules, Limits, and Assumptions
- **Travel Time Stochasticity:** Each travel edge duration adds stochastic noise to the deterministic baseline using a truncated normal distribution.
- **Service Times:** Loading and dumping times are sampled from a truncated normal distribution based on node parameters (`service_time_mean_min`, `service_time_sd_min`).
- **Dispatching Logic:** Trucks use a `nearest_available_loader` heuristic. "Nearest" means shortest travel time. "Available" means no queue. If multiple have no queue, the closest is picked. If all loaders have queues, trucks use a tie-breaker selecting the loader with the lowest `(expected_queue_time + travel_time)`.
- **Simplifications:** 
  - Constant truck payload per truck class (no partial loads).
  - Instantaneous dispatch routing calculation.
  - No shift change, maintenance, or breaks are modeled.
