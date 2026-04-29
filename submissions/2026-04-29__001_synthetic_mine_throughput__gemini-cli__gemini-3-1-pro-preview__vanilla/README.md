# Synthetic Mine Throughput Simulation

This repository contains a discrete-event simulation model written in Python using **SimPy**. The simulation estimates ore throughput to a primary crusher over an 8-hour shift for a synthetic mine.

## How to Install Dependencies

1. Create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
2. Install the requirements:
   ```bash
   pip install -r requirements.txt
   ```

## How to Run the Simulation

To execute the simulation and generate outputs:

```bash
source venv/bin/activate
python simulate.py
```

This will run all six predefined scenarios (30 replications each) and output:
- `results.csv`: Scenario and replication level metrics.
- `summary.json`: Aggregated statistics with confidence intervals.
- `event_log.csv`: Trace of simulation events.

## Conceptual Model & Assumptions

The model tracks **trucks** as active entities navigating a directed graph of the mine topology. **Loaders** (`L_N`, `L_S`), the **Crusher** (`D_CRUSH`), and **constrained road segments** are modeled as shared resources with specific capacities.

### Routing and Dispatching Logic
- **Routing**: Shortest-time path using Dijkstra's algorithm. Edge weights are dynamically calculated as `Distance / (SpeedLimit * SpeedFactor)`. If an edge is closed, it is ignored by the graph builder.
- **Dispatching**: When a truck becomes empty, it evaluates both loaders. It selects the loader offering the minimum expected time, calculated as: `Travel_Time + (Queue_Length * Mean_Load_Time) + Mean_Load_Time`.
- **Road Resources**: Constrained directional single-lane segments (like `E03_UP`) require a truck to acquire a capacity token before entering and release it upon leaving. Separate edges (e.g., `E03_UP` and `E03_DOWN`) are treated as independent queues.

For more details, see [conceptual_model.md](conceptual_model.md).

## Operational Decision Questions

Based on the 30 replications per scenario with random seed control, here are the answers to the operational questions:

### 1. What is the expected ore throughput to the crusher during the baseline 8-hour shift?
The expected throughput is **12,603 tonnes** (95% CI: 12,548 - 12,658 tonnes), which equates to ~1,575 tonnes per hour.

### 2. What are the likely bottlenecks in the haulage system?
The **primary crusher** is the major bottleneck. In the baseline scenario, its utilization reaches **92.8%**. Trucks spend on average ~3.9 minutes queuing at the crusher. The loaders and road segments operate comfortably below their maximum capacities.

### 3. Does adding more trucks materially improve throughput, or does the system saturate?
The system is deeply saturated by the crusher. Adding more trucks (from 8 to 12) only marginally increases throughput to **12,823 tonnes** (a ~1.7% increase), while crusher queue wait times explode to over 15 minutes, and overall truck utilization plummets from 77.5% to 54.6%.

### 4. Would improving the narrow ramp materially improve throughput?
**No.** The `ramp_upgrade` scenario yields **12,623 tonnes**, statistically indistinguishable from the baseline. Because the crusher is the actual system constraint, widening the ramp merely delivers trucks to the crusher queue faster, where they end up waiting.

### 5. How sensitive is throughput to crusher service time?
**Highly sensitive.** The `crusher_slowdown` scenario (increasing mean dump time from 3.5 to 7.0 minutes) slashes throughput by nearly half to **6,483 tonnes**. Crusher utilization remains pinned at 95.5%, and average queue times skyrocket to ~28.8 minutes. 

### 6. What is the operational impact of losing the main ramp route?
**Minimal.** In the `ramp_closed` scenario, trucks reroute via the longer bypass network. The throughput drops slightly to **12,416 tonnes** (~1.5% decrease). Since the crusher is the limiting factor, the extra travel time mostly cuts into the time trucks would have spent idling in the crusher queue anyway, buffering the impact of the longer route.

## Limitations of the Model
- **Traffic independence**: Aside from specific constrained single-lane segments, trucks do not slow each other down on normal haul roads.
- **Breakdowns**: Unplanned maintenance and breakdowns (truck/loader availability) are excluded.
- **Shift changes**: The simulation assumes 100% operational efficiency right up to the exact 8-hour mark, without hot-seat changeover times or breaks.
