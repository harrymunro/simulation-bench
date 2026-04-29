# Synthetic Mine Throughput Simulation

This project implements a discrete-event simulation of a mine haulage network using SimPy and NetworkX. It estimates ore throughput to a primary crusher over an 8-hour shift under various operational scenarios.

## Installation & Requirements

Ensure you have Python 3.8+ installed. The simulation requires the following dependencies:

```bash
pip install simpy networkx pandas numpy scipy pyyaml
```

## Running the Simulation

Execute the main simulation script, which runs 30 replications for all 6 required scenarios:

```bash
python3 sim.py
```

This will generate:
- `results.csv`: Replication-level detailed results.
- `summary.json`: Aggregated scenario metrics and confidence intervals.
- `event_log.csv`: A complete discrete-event trace for all replications.

## Conceptual Model & Assumptions

Please refer to [`conceptual_model.md`](conceptual_model.md) for details on system boundaries, entities, state variables, and resource definitions.

### Routing and Dispatching Logic
- **Routing**: Shortest-path routing using Dijkstra's algorithm. Edge weights are defined as the expected travel time `(distance / max_speed)`. Empty and loaded speeds are handled by dynamically calculating path times.
- **Dispatching**: Dynamic nearest-available loader assignment. After dumping, a truck chooses a loader by minimizing the sum of expected travel time and expected queue waiting time. 

## Operational Decision Questions

### 1. What is the expected ore throughput to the crusher during the baseline 8-hour shift?
The baseline configuration delivers approximately **12,416 tonnes per shift** (1,552 tonnes per hour) with a 95% confidence interval of roughly [12,341, 12,491]. 

### 2. What are the likely bottlenecks in the haulage system?
In the baseline, the **Crusher** operates at around 90-91% utilisation, while trucks experience minor queuing at the loaders. As the fleet grows, the Crusher becomes the absolute constraint, generating long queues. 

### 3. Does adding more trucks materially improve throughput, or does the system saturate?
The system **saturates**. Increasing the fleet from 8 to 12 trucks yields negligible additional throughput (rising slightly to 12,666 tonnes), but crusher queues skyrocket to 14.9 minutes. Decreasing the fleet to 4 trucks severely drops throughput (to 8,126 tonnes). The baseline 8-truck fleet is optimal for this crusher capacity.

### 4. Would improving the narrow ramp materially improve throughput?
**No.** The ramp upgrade scenario delivers ~12,440 tonnes, practically indistinguishable from the baseline. This is because trucks only traverse the ramp once during the initial dispatch from parking. Subsequent cycles occur entirely in the upper network. 

### 5. How sensitive is throughput to crusher service time?
**Extremely sensitive.** The `crusher_slowdown` scenario cuts throughput by nearly half (to 6,440 tonnes). Crusher queues explode to 28 minutes, bottlenecking the entire cycle. Since the crusher operates continuously near 90%+ utilisation in baseline, any degradation immediately impacts production.

### 6. What is the operational impact of losing the main ramp route?
**Negligible to zero.** In the `ramp_closed` scenario, throughput remains at ~12,416 tonnes. Trucks simply take the western bypass from `PARK` to the loaders. Since this detour is only taken once at the beginning of the shift, the 8-hour steady-state throughput is completely unaffected. 

## Limitations
- No breakdowns or shift changes are modeled.
- Traffic dynamics on wide roads (passing, acceleration, deceleration) are not explicitly simulated, potentially underestimating travel times when the network is busy.
