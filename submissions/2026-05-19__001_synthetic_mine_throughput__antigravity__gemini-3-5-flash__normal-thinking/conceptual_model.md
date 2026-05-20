# Conceptual Model Design — Synthetic Mine Throughput Simulation

This document outlines the conceptual design of our discrete-event simulation (DES) model of the synthetic mine haulage network, built using Python and SimPy.

---

## 1. System Boundary

### Included in the Model
- **Active Fleet**: 4, 8, or 12 trucks (configured by scenario) starting from `PARK` at $t=0$, hauling ore between active pit faces and the primary crusher.
- **Physical Nodes**: Starting parking location, intersections/junctions, load nodes (`LOAD_N`, `LOAD_S`), and dump location (`CRUSH`).
- **Directed Graph Topology**: Edge connections with physical distances and max speed limits.
- **Constrained Road Segments**: Single-lane roads and ramps with capacity = 1 (where only one truck can occupy the road segment in a given direction at a time).
- **Constrained Material Facilities**: Loaders at each face and the primary crusher hopper, all modeled as single-capacity queueing servers.
- **Stochastic Travel Times**: Dynamic travel durations along edges subject to lognormal noise (CV = 0.10).
- **Stochastic Service Times**: Loader cycle times and crusher dumping times subject to truncated normal distributions.
- **Dynamic Dispatcher**: Multi-factor decision policy assigning trucks to loaders to minimize expected completion times.

### Excluded from the Model
- **Waste & Maintenance Routing**: Transporting overburden to `WASTE` and truck routing to `MAINT` are excluded based on the operational decision boundaries.
- **Equipment Breakdowns**: Truck and loader mechanical failures, scheduled maintenance, or refueling delays.
- **Shift Handover Delay**: Shifts are cut off cleanly at exactly 480 minutes without shift-change ramping down.
- **Hopper Stockpile Level Constraints**: Crusher throughput is based strictly on dump events, assuming infinite crusher hopper space and downstream processing capacity.

---

## 2. Active Entities

- **Truck**: The primary dynamic entity moving through the system. Each truck has:
  - `truck_id`: Unique identifier (e.g., `T01`).
  - `payload_tonnes`: Static hauling capacity of 100.0 tonnes (from `trucks.csv`).
  - `empty_speed_factor`: 1.00 when empty (from `trucks.csv`).
  - `loaded_speed_factor`: 0.85 when loaded (from `trucks.csv`).
  - `state`: Current active operational state (e.g., loading, traveling, queueing).

---

## 3. Constrained Resources

1. **Loaders** (`L_N` at node `LOAD_N`, `L_S` at node `LOAD_S`):
   - Capacity = 1.
   - Serve one truck at a time.
   - Manage queues in first-in-first-out (FIFO) order.
2. **Primary Crusher** (`D_CRUSH` at node `CRUSH`):
   - Capacity = 1.
   - Dumps one truck at a time.
   - Manages queue in FIFO order.
3. **Single-Lane Roads & Ramps** (edges with capacity = 1):
   - Capacity = 1.
   - Only one truck can traverse the directed segment at any time.
   - Waiting trucks queue at the upstream junction node before entering.

---

## 4. Chronological Events

For each truck cycle, the following events occur in chronological order:

1. **Truck Dispatched**: Truck is assigned to a loader face $L \in \{\text{LOAD\_N}, \text{LOAD\_S}\}$.
2. **Travel Empty**: Truck moves along the shortest-time path from its current position (`PARK` or `CRUSH`) to $L$.
3. **Edge Queue Start** *(conditional)*: Arrives at a capacity-1 edge along the path and must wait if occupied.
4. **Edge Enter / Leave** *(conditional)*: Enters the capacity-1 edge, traverses it, and releases the edge.
5. **Loader Queue Start**: Arrives at loader node $L$ and joins the loader queue.
6. **Loading Start**: Reaches front of queue and loader begins service.
7. **Loading End**: Loading service completes; truck payload is set to 100 tonnes.
8. **Travel Loaded**: Truck travels along the shortest-time path from $L$ to `CRUSH`.
9. **Crusher Queue Start**: Arrives at the primary crusher junction and joins the dump queue.
10. **Dumping Start**: Reaches front of queue and crusher hopper begins receiving ore.
11. **Dumping End**: Dumping service completes; truck payload is reset to 0, total throughput is incremented, and a haul cycle is recorded.

---

## 5. State Variables

- **Simulation Time** ($t$): Current clock minutes in SimPy, running from $t = 0.0$ to $t = 480.0$.
- **Cumulative Throughput**: Total tonnes of ore dumped at the primary crusher during the shift.
- **Resource Queue State** ($Q(res)$): Number of trucks waiting in queue for resource `res` (loaders, crusher, or capacity-1 edges).
- **Resource Active State** ($C(res)$): Current occupancy count of resource `res` (0 or 1).
- **Truck State Vector**: For each truck $T$, the exact minutes spent in each state:
  - $T_{\text{TRAVEL\_EMPTY}}$: Empty travel time.
  - $T_{\text{TRAVEL\_LOADED}}$: Loaded travel time.
  - $T_{\text{LOADING}}$: Active loading time.
  - $T_{\text{DUMPING}}$: Active dumping time.
  - $T_{\text{QUEUE\_LOADER}}$: Waiting time in loader queues.
  - $T_{\text{QUEUE\_CRUSHER}}$: Waiting time in crusher queue.
  - $T_{\text{QUEUE\_EDGE}}$: Waiting time at capacity-1 road segment entrances.

---

## 6. Modeling Assumptions

### Assumptions Derived From Data
- **Loader Services**: Slower loading at North Pit ($\mu = 6.5 \text{ min}$, $\sigma = 1.2 \text{ min}$) vs. faster loading at South Pit ($\mu = 4.5 \text{ min}$, $\sigma = 1.0 \text{ min}$).
- **Crusher Services**: Crusher dump service time is $\mu = 3.5 \text{ min}$, $\sigma = 0.8 \text{ min}$.
- **Truck Speed Scaling**: Truck empty speed factor is 1.0, and loaded speed factor is 0.85, meaning loaded trucks travel 15% slower than empty trucks.

### Assumptions We Introduced
- **Stochastic Travel Noise**: Edge travel times are modeled using lognormal noise with a coefficient of variation of 0.10. This accounts for minor traffic delays, road surface conditions, and driver variation.
- **Stochastic Truncation**: Normal service distributions are truncated at a minimum of 0.1 minutes to prevent non-physical negative durations:
  $$T_{\text{service}} = \max(0.1, \mathcal{N}(\mu, \sigma^2))$$
- **Dynamic Dispatch Heuristic**: Trucks are assigned to the loader that minimizes their total expected cycle completion time (travel time + queue delay + service time):
  $$\text{Score}(L) = T_{\text{travel}}(\text{current}, L) + (Q(L) \times \mu_{\text{load}, L}) + \mu_{\text{load}, L}$$
  where $Q(L)$ is the current number of trucks in queue and in service at loader $L$.

### Model Limitations
- No physical overtaking model on multi-lane (capacity=999) edges; speed is independent of local density on those edges.
- No stockpile levels or plant processing constraints downstream of the crusher.
- Excludes waste and maintenance routing.

---

## 7. Performance Measures

1. **Total Tonnes Delivered** ($T_{\text{tot}}$): Cumulative tonnes received at the crusher.
2. **Tonnes per Hour** ($TPH$): $T_{\text{tot}} / 8.0$.
3. **Average Truck Cycle Time** ($\bar{C}$): Average minutes to complete a full haul cycle (from dispatch to dump completion).
4. **Average Truck Utilisation** ($\bar{U}_{\text{truck}}$): Fraction of shift spent in productive work:
   $$U_{\text{truck}} = \frac{T_{\text{TRAVEL\_EMPTY}} + T_{\text{TRAVEL\_LOADED}} + T_{\text{LOADING}} + T_{\text{DUMPING}}}{480.0}$$
5. **Resource Utilisation** ($U_{\text{res}}$): Total active busy time divided by shift length (480 min).
6. **Average Queue Time** ($\bar{W}_{\text{res}}$): Average wait time of all trucks that queued at resource `res`.
7. **Composite Bottleneck Rank**: Ranked score for each resource evaluated as:
   $$\text{Bottleneck Score} = \text{Utilisation} \times \text{Mean Queue Wait}$$
