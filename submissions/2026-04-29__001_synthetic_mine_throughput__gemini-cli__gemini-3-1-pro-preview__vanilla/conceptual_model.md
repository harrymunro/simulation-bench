# Conceptual Model

## System Boundary
The simulation models the haulage system of a synthetic mine. It includes trucks, loaders (North and South pits), the primary crusher, and the road network (represented as a directed graph). The simulation tracks operations over an 8-hour shift, beginning with trucks at the parking area. Waste haulage, maintenance events, and loader/truck breakdowns (availability < 1.0) are excluded or considered out of scope unless explicitly requested, focusing solely on ore throughput.

## Entities
- **Trucks**: The active entities moving through the system. Trucks have properties like payload capacity (100 tonnes), empty speed factor, and loaded speed factor.

## Resources
- **Loaders**: `L_N` (capacity 1) and `L_S` (capacity 1). These constrain the loading process. Trucks queue if the loader is busy.
- **Crusher**: `D_CRUSH` (capacity 1). Constrains the dumping process.
- **Constrained Road Segments**: Edges with `capacity` constraints (e.g., `E03_UP` with capacity 1). These are modeled as shared resources. A truck must acquire the edge resource before it can commence travel on that segment and releases it upon arrival at the next node. For simplicity, opposite direction edges (e.g., `E03_UP` and `E03_DOWN`) are treated as independent resources as per the dataset metadata.

## Events
- **Simulation Start**: Trucks are instantiated and dispatched from the `PARK` node.
- **Travel to Loader**: Truck requests constrained edges sequentially based on the shortest path.
- **Join Loader Queue**: Truck arrives at `LOAD_N` or `LOAD_S` and requests the loader resource.
- **Loading**: Truck captures the loader. Loading takes a stochastic amount of time.
- **Travel to Crusher**: Truck leaves the loader, payload is set to 100 tonnes, and it routes to the `CRUSH` node, acquiring constrained edges along the route.
- **Join Crusher Queue**: Truck arrives at `CRUSH` and requests the crusher resource.
- **Dumping**: Truck captures the crusher. Dumping takes a stochastic amount of time. Ore throughput is recorded.
- **Return Travel**: Truck becomes empty and returns to a loader.

## State Variables
- Total tonnes delivered.
- Truck state (current location, loaded/empty).
- Queues at loaders, crusher, and constrained edges.
- Resource utilizations (busy time for loaders and crusher).
- Cycle times (from leaving the crusher/park to completing the next dump).

## Assumptions
- **Routing**: Trucks route dynamically using Dijkstra's shortest path based on expected travel time. Travel time is calculated as $Distance / (SpeedLimit \times SpeedFactor)$. If an edge is closed, its weight is set to infinity.
- **Dispatching**: When a truck is empty (either at start or after dumping), it selects the loader that provides the shortest expected time to load. The expected time includes travel time to the loader + (current loader queue length $\times$ mean load time) + mean load time.
- **Independence of directional capacities**: As stated in the edge metadata, narrow roads are simplified as separate directional edges. We assume they operate as independent queues, so a truck going up does not block a truck going down.
- **No shift transitions**: The simulation runs exactly for the shift length (8 hours) and abruptly stops or only counts completed dumps within the time window.

## Performance Measures
- **Expected Ore Throughput**: Total tonnes dumped at the crusher over the shift.
- **Tonnes per Hour**: Total tonnes / Shift hours.
- **Cycle Time**: Average time to complete a full load-and-dump cycle.
- **Utilizations**: Percentage of shift time the crusher and loaders were actively processing trucks.
- **Wait Times**: Average time spent queuing at loaders and the crusher.
