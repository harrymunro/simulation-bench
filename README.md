# Synthetic Mine Throughput Simulation

This project implements a discrete-event simulation using SimPy and NetworkX to model and estimate ore throughput in a synthetic mine under various scenarios.

## Installation and Execution

To run the simulation, follow these steps:

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Run the simulation experiment runner:
   ```bash
   python -m mine_simulation.runner
   ```

The runner will execute multiple scenarios (baseline, different truck counts, ramp variations, etc.) and output the results to the current directory:
- `results.csv`
- `event_log.csv`
- `summary.json`

## Summary of Results and Bottlenecks

Based on the initial scenario runs (30 replications per scenario):

- **Throughput:** The baseline scenario achieves an average of **12,400 tonnes** per 8-hour shift (1,550 tonnes/hour). Lowering the fleet size to 4 trucks (`trucks_4` scenario) reduces throughput to **8,400 tonnes** per shift.
- **Crusher Bottleneck:** The primary bottleneck in the system is the crusher. In the baseline and most other scenarios, crusher utilization is very high (around **91.5%**).
- **Queuing:** When the fleet size is increased to 12 trucks (`trucks_12`), throughput does not increase above 12,400 tonnes, indicating the system is completely saturated. This is confirmed by a massive spike in the average crusher queue time, jumping from ~5.3 minutes (baseline) to **~17.3 minutes**.
- **Loader Utilization:** There is an imbalance between the loaders. `LOAD_S` is highly utilized (~82-83%) across full-fleet scenarios, while `LOAD_N` sees much less utilization (~55-58%).

For more details on the conceptual model and assumptions, see [conceptual_model.md](conceptual_model.md).
