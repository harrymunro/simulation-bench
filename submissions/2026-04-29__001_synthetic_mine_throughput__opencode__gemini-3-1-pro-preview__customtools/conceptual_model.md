# Conceptual Model

## System boundary
The model includes the active hauling operations of a synthetic mine. It covers truck movements from parking to loading faces, hauling to the primary crusher, dumping, and returning. It excludes detailed mechanical breakdowns (except optional maintenance routes), blasting, operator shift changes, and detailed spatial physics of truck interactions (e.g., passing, acceleration curves). Roads, loaders, and the crusher are modelled as resources.

## Entities
- **Trucks**: Active entities that cycle through the mine (Park -> Loader -> Crusher -> Loader...). They carry state variables like current location, load status, and accumulated payload.
- **Ore Payload**: Implicitly carried by trucks. Recorded in tonnes upon dumping at the crusher.

## Resources
- **Loaders**: Modelled as discrete resources with capacity 1 at specific pit face nodes (LOAD_N, LOAD_S).
- **Primary Crusher**: Modelled as a discrete resource with capacity 1 at the CRUSH node.
- **Constrained Road Segments**: Edges with capacity=1 (e.g., narrow ramps, single-lane pit accesses). Directions sharing the same physical road (e.g., E03_UP and E03_DOWN) are modelled as a single shared resource to prevent simultaneous traversal in opposing directions.

## Events
The simulation records key events in an event log:
- **travel_start / travel_end**: Truck begins and ends traversal of a road segment.
- **queue_start / queue_end**: Truck joins or leaves a queue for a loader, crusher, or constrained road segment.
- **load_start / load_end**: Truck begins and ends loading ore at a face.
- **dump_start / dump_end**: Truck begins and ends dumping ore at the primary crusher.

## State variables
- **Truck State**: Location (node), loaded/empty status, payload (tonnes).
- **System State**: Queue lengths at loaders, crushers, and roads; resource utilization times; total tonnes delivered; cumulative truck cycle times.

## Assumptions
- **Derived from data**: Trucks have varying speeds when empty vs loaded. Some routes are strictly single-lane and act as bottlenecks. Load and dump times follow normal distributions truncated at >0.
- **Introduced assumptions**: 
  1. Trucks queue at the entrance to constrained road segments and do not enter until the segment is clear.
  2. Trucks are dispatched dynamically based on a "shortest expected cycle time" heuristic, evaluating travel time + expected loader wait time.
  3. No truck breakdowns or shift delays occur within the 8-hour window (warmup=0).
- **Limitations**: The model assumes instantaneous acceleration/deceleration at nodes. Continuous traffic dynamics like bunching on unconstrained roads are not explicitly captured, though travel time noise (CV=0.10) approximates traffic variability.

## Performance measures
- **Total Tonnes Delivered**: Cumulative ore dumped at the crusher.
- **Tonnes per Hour (tph)**: Total tonnes / 8 hours.
- **Average Truck Cycle Time**: Time from leaving the crusher (or parking) to next dump completion.
- **Utilisation**: Percentage of total time trucks are actively moving/loading/dumping, and percentage of time loaders/crusher are actively servicing trucks.
- **Queue Times**: Average waiting time at loaders and the crusher.
