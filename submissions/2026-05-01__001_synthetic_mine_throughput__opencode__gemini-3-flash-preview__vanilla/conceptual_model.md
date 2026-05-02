# Conceptual Model: Synthetic Mine Throughput Simulation

## System Boundary

### Included
- Truck cycle: travel empty, loading, travel loaded, dumping.
- Stochastic service times at loaders and crusher.
- Stochastic travel times.
- Resource constraints at loaders and crusher (queueing).
- Capacity constraints on specific road segments (edges).
- Routing based on shortest time in the provided graph.
- Multiple replications (30+) for statistical significance.

### Excluded
- Truck breakdowns/maintenance (availability is fixed at 1.0 in dataset, but could be added if needed; current focus is on operational throughput).
- Shift changes or operator breaks.
- Detailed engine performance modelling (represented by speed factors).
- Fuel consumption.
- Multiple types of material (only ore to crusher is primary goal).

## Entities

- **Trucks**: The primary active agents that move between loading points and the crusher.
- **Ore Payloads**: Moved by trucks from sources to the destination.

## Resources

- **Loaders**: Constrained resources at `LOAD_N` and `LOAD_S`.
- **Crusher**: Constrained resource at `CRUSH`.
- **Constrained Road Segments**: Edges with `capacity < 999` limit the number of trucks that can be on that segment simultaneously.

## Events

1. **Simulation Start**: Trucks are initialized at their `start_node`.
2. **Dispatch**: Truck is assigned a loading point.
3. **Travel Empty**: Truck moves from current location to the assigned loader.
4. **Arrive at Loader**: Truck joins the queue.
5. **Loading Starts**: Loader becomes available and starts serving the truck.
6. **Loading Ends**: Truck is now loaded; loader is released.
7. **Travel Loaded**: Truck moves from loader to the crusher.
8. **Arrive at Crusher**: Truck joins the crusher queue.
9. **Dumping Starts**: Crusher becomes available and starts serving the truck.
10. **Dumping Ends**: Truck is empty; crusher is released; tonnes are recorded.
11. **Return/Cycle Repeat**: Truck is dispatched again.

## State Variables

- **Simulation Clock**: Current time in minutes.
- **Resource States**: Number of trucks currently using loaders, crusher, and road segments.
- **Queue States**: Number of trucks waiting at each resource.
- **Truck State**: Location, loaded status, current destination.
- **Cumulative Production**: Total tonnes delivered to the crusher.
- **Cycle Metrics**: Individual truck cycle times, wait times, and travel times.

## Assumptions

### Data-Derived Assumptions
- Travel time is calculated as `distance / (speed * speed_factor)`.
- Speeds are affected by `empty_speed_factor` or `loaded_speed_factor`.
- Stochastic service times follow a truncated normal distribution (to avoid negative times).

### Introduced Assumptions
- Trucks always take the shortest time path based on the current graph state (static routing unless roads are closed).
- No overtaking on narrow roads (handled by capacity constraint).
- Dispatching follows "nearest available loader" logic: if multiple are available, pick one; if none are available, pick the one with the shortest expected queue time.

### Limitations
- The model does not account for complex traffic interactions beyond road capacity.
- Elevation changes are implicitly handled by the provided distances and road types, but not explicitly modeled with physics.

## Performance Measures

- **Total Tonnes Delivered**: Cumulative ore delivered in 8 hours.
- **Tonnes Per Hour (TPH)**: Throughput rate.
- **Truck Utilisation**: Percentage of time trucks are moving or being served (vs waiting in queues).
- **Resource Utilisation**: Percentage of time loaders and the crusher are busy.
- **Queue Times**: Average time spent waiting at loaders and the crusher.
- **Cycle Time**: Time taken for a full load-haul-dump-return cycle.
