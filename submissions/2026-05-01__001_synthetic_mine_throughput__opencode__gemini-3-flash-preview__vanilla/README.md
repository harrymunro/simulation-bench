# Synthetic Mine Throughput Simulation

This project implements a discrete-event simulation of a synthetic mine haulage system using **SimPy**.

## Installation

To install the required dependencies, run:

```bash
pip install -r requirements.txt
```

## Running the Simulation

To run the simulation and generate all results:

```bash
python simulation.py
```

This will run 30 replications of 6 scenarios and produce the following files:
- `results.csv`: Detailed results for each replication.
- `summary.json`: Summary statistics and bottleneck identification.
- `event_log.csv`: A trace of simulation events (first replication of each scenario).
- `conceptual_model.md`: Documentation of the modeling approach.

## Conceptual Model

The simulation models trucks as active entities moving between loading points and a primary crusher.
Key features:
- **Shortest-time routing**: Trucks dynamically calculate the fastest path using Dijkstra's algorithm.
- **Resource constraints**: Loaders, the crusher, and narrow road segments are modeled as constrained resources with queues.
- **Stochasticity**: Loading times, dumping times, and travel times include random variations.
- **Scenario Analysis**: Evaluates the impact of fleet size, infrastructure upgrades, and operational disruptions.

## Routing and Dispatching Logic

- **Routing**: Shortest-time path calculation on the mine topology graph.
- **Dispatching**: Trucks use a "nearest available loader" policy. If multiple loaders are available, they choose based on travel time. If none are available, they choose the one with the shortest expected arrival-to-load-start time (travel time + expected queue time).

## Key Results and Operational Answers

### 1. Expected Throughput
Under the **baseline** 8-truck configuration, the expected throughput is approximately **1544 tonnes per hour (TPH)**, delivering ~12,350 tonnes per 8-hour shift.

### 2. Bottlenecks
The primary bottleneck in the baseline system is the **Crusher Capacity**. The crusher maintains over 90% utilization, and average queue times remain significant. While loading points have some queueing, the crusher is the ultimate constraint on system throughput.

### 3. Impact of Fleet Size
- **4 Trucks**: Throughput drops to ~950 TPH. The system is fleet-constrained (92% truck utilization).
- **12 Trucks**: Throughput increases only marginally to ~1587 TPH (+3%). The system saturates as crusher queue times jump from 3.5 min to 14.4 min. Adding more trucks beyond the baseline yields diminishing returns.

### 4. Narrow Ramp Upgrade
Improving the narrow ramp (speed and capacity) has a negligible impact on throughput (~+0.1%). This is because:
1. The baseline system already uses a slightly faster bypass route for the North pit.
2. The crusher bottleneck prevents any upstream improvements from translating into higher throughput.

### 5. Crusher Service Time Sensitivity
Throughput is **highly sensitive** to crusher performance. Doubling the crusher service time (**crusher_slowdown** scenario) halves the system throughput to ~800 TPH, with crusher queue times exceeding 26 minutes.

### 6. Impact of Losing the Main Ramp
Closing the main ramp (**ramp_closed**) has **no material impact** on throughput in this specific topology. Trucks seamlessly reroute to the western bypass, which is already competitive or faster for some routes.

## Limitations and Assumptions

- **Maintenance**: The model assumes 100% equipment availability. Real-world throughput would be lower due to unplanned breakdowns.
- **Traffic**: Interaction between trucks on wide roads is not modeled beyond basic travel time noise.
- **Uniform Payloads**: All trucks are assumed to carry their maximum nominal payload.
