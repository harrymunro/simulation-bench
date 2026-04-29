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

## Routing and Dispatching Logic

Trucks dynamically route themselves through the mine using the shortest path (based on baseline travel time) on the `MineTopology` graph. Dispatching operates on a `nearest_available_loader` heuristic. When a truck becomes empty at the crusher, it evaluates all ore sources:
1. It calculates the travel time to each loader.
2. It checks the current queue length at each loader.
3. If one or more loaders have no queue, the truck dispatches to the closest one (shortest travel time).
4. If all loaders have queues, the truck uses a tie-breaker score `(travel_time + expected_queue_time + mean_service_time)` to select the optimal destination.

## Summary of Results and Bottlenecks

Based on the scenario runs (30 replications per scenario):

1. **Throughput:** The baseline scenario achieves an average of **12,600 tonnes** per 8-hour shift (1,575 tonnes/hour). Lowering the fleet size to 4 trucks (`trucks_4` scenario) reduces throughput to **8,600 tonnes** per shift.
2. **Crusher Bottleneck:** The primary bottleneck in the system is the crusher. In the baseline and most other scenarios, crusher utilization is very high (around **91% - 93%**).
3. **Queuing:** When the fleet size is increased to 12 trucks (`trucks_12`), throughput barely increases (12,800 tonnes), indicating the system is completely saturated. This is confirmed by a massive spike in the average crusher queue time, jumping from ~5.1 minutes (baseline) to **~15.4 minutes**.
4. **Would improving the narrow ramp materially improve throughput?** No. The `ramp_upgrade` scenario only increases throughput marginally (to 12,700 tonnes). Because the crusher is the main bottleneck, faster travel times on the ramp simply result in trucks waiting slightly longer at the crusher queue (though the ramp itself clears faster).
5. **How sensitive is throughput to crusher service time?** Highly sensitive. In the `crusher_slowdown` scenario (increasing mean service time to 7.0 minutes), throughput plummets to **6,700 tonnes**. Average crusher queue time spikes to **~27.4 minutes**, completely starving the loaders of empty trucks.
6. **What is the operational impact of losing the main ramp route?** In the `ramp_closed` scenario, throughput remains at **12,600 tonnes**. Trucks successfully reroute via the bypass. Since the crusher was already the bottleneck, the extra travel time on the bypass merely absorbs time that would have otherwise been spent queuing at the crusher.

## Model Limitations

- **No Shift Changes or Breaks:** The model simulates 8 continuous hours without considering shift changeovers, operator breaks, or refueling (unless explicitly modeled as a maintenance trip, which is currently bypassed).
- **Constant Truck Payload:** The payload is assumed fixed per truck class, rather than a distribution based on loader efficiency or material density.
- **Instantaneous Dispatching:** Trucks make routing decisions instantly with perfect knowledge of the entire mine state, which does not account for communication delays or dispatch algorithm computation time in reality.

## Suggested Improvements and Further Scenarios

- **Dynamic Payload Modeling:** Incorporate variable payload distributions (e.g., normal distribution) depending on the loader type and material.
- **Maintenance and Break Events:** Schedule shift breaks or stochastic breakdown events for both trucks and fixed plant (crusher/loaders) to test robustness.
- **Additional Crusher Capacity:** Add a scenario where a secondary dump point or a higher capacity crusher is introduced to explicitly resolve the primary bottleneck.
- **Stochastic Routing Updates:** Have trucks periodically re-evaluate their destination while en-route rather than just once at the crusher.

For more details on the conceptual model and assumptions, see [conceptual_model.md](conceptual_model.md).
