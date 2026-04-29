# Conceptual Model Design

## System Boundary
The simulation models the active haulage operations over an 8-hour shift. It includes:
- Truck movements between loaders, the primary crusher, and parking.
- Queueing at loaders and the primary crusher.
- Constrained road segments (e.g., single-lane approach roads).
It excludes:
- Breakdowns, refueling, or maintenance delays.
- Shift changes or meal breaks.
- Explicit modeling of unconstrained road segment traffic dynamics (passing, acceleration).
- Ore grade blending or material properties.

## Entities
The primary active entities moving through the system are **Trucks**. Each truck cycle consists of:
1. Routing from its current location to an available loader.
2. Traveling empty to the loader queue.
3. Loading an ore payload.
4. Routing from the loader to the primary crusher.
5. Traveling loaded to the crusher queue.
6. Dumping the payload.
7. Repeating the process.

## Resources
The system is constrained by:
- **Loaders**: `LOAD_N` (capacity 1) and `LOAD_S` (capacity 1).
- **Crusher**: `CRUSH` (capacity 1).
- **Road Segments**: Edges with a capacity less than 999 are modeled as single-lane resources that trucks must acquire before entering and release upon exiting.

## Events
Key discrete events tracked in the simulation include:
- `travel_start`: Truck enters a road segment.
- `travel_end`: Truck exits a road segment.
- `queue_start`: Truck arrives at a resource (loader, crusher) and waits.
- `load_start` / `load_end`: Ore loading process.
- `dump_start` / `dump_end`: Ore dumping process at the crusher.

## State Variables
Tracked state includes:
- Truck status (location, loaded/empty).
- Resource states (busy/idle, queue lengths).
- Accumulators (total tonnes delivered, total truck active time, total crusher busy time).

## Assumptions
- **Derived from data**: 
  - Stochastic activity times (loading, dumping, travel) follow a truncated normal distribution to prevent negative durations.
  - The road network allows shortest-path calculations based on expected travel time.
- **Introduced**: 
  - The dispatch policy assigns an empty truck to the loader that minimizes expected turnaround time (travel time plus expected queue waiting time).
  - Trucks evaluate loader choices immediately upon finishing a dump.
- **Limitations**:
  - Unconstrained roads assume no traffic interference. Trucks travel at their maximum achievable speed modified by their loaded/empty factor.
  - The dispatch decision does not account for the travel time of other trucks currently heading to the same loader, which might lead to temporary clustering.

## Performance Measures
- **Throughput**: Total tonnes delivered and tonnes per hour.
- **Cycle Time**: Average duration from one dump completion to the next.
- **Utilisation**: Percentage of time trucks and the crusher are actively engaged in operations.
- **Bottleneck indicators**: Average queue times at loaders and the crusher.
