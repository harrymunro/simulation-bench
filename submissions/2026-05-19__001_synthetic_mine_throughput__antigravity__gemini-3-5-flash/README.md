# Discrete-Event Simulation: Synthetic Mine Throughput Analysis

This repository contains a genuine discrete-event simulation built in Python using **SimPy** to model and optimize haulage operations in a synthetic open-pit mine. The analysis estimates ore throughput to the primary crusher over an 8-hour shift under several operational and design scenarios.

![Mine Network Topology Map](/Users/harry/Workspace/simulation-bench/submissions/2026-05-19__001_synthetic_mine_throughput__antigravity__gemini-3-5-flash/topology.png)

![Live Simulation Animation](/Users/harry/Workspace/simulation-bench/submissions/2026-05-19__001_synthetic_mine_throughput__antigravity__gemini-3-5-flash/animation.gif)

---

## 1. Quick Start & Execution

### Installation of Dependencies
The simulation runs in Python 3. To install the required common dependencies:
```bash
pip install simpy numpy pandas scipy matplotlib networkx pyyaml
```

### Running the Experiments
All code is packaged within `src/mine_sim`. You can run the entire simulation suite (reproducing all 30 replications for all 7 scenarios) and generate the results with:
```bash
PYTHONPATH=src python3 -m mine_sim --run-all
```
This will automatically execute the simulations and produce the output files (`results.csv`, `summary.json`, and `event_log.csv`) in the submission folder.

To run a single specific scenario (e.g. `baseline`) and print a detailed summary in your console:
```bash
PYTHONPATH=src python3 -m mine_sim --scenario baseline
```

---

## 2. Answers to Operational Decision Questions

Based on running 30 replications for each scenario (using random seed control), here are the statistical answers to the mine operator's decision questions:

### Q1: What is the expected ore throughput to the crusher during the baseline 8-hour shift?
- **Answer**: The expected throughput is **12,473.3 tonnes** (95% Confidence Interval: **12,427.4 to 12,519.3 tonnes**), representing an average hourly crusher rate of **1,559.2 tonnes/hour**.

### Q2: What are the likely bottlenecks in the haulage system?
- **Answer**: The absolute primary bottleneck is the **Primary Crusher (`D_CRUSH`)** itself, which is heavily saturated with a mean utilization of **91.1%** and an average truck queue wait time of **3.45 minutes**. The secondary bottleneck is the **South Pit Loader (`L_S`)** with **79.8%** utilization and an average queue wait of **2.50 minutes**.

### Q3: Does adding more trucks materially improve throughput, or does the system saturate?
- **Answer**: **The system completely saturates.**
  - Reducing the fleet to **4 trucks** (`trucks_4`) drops throughput to **7,693.3 tonnes** (a 38.3% drop) because the system becomes "truck-starved" (crusher utilization falls to 56.0%).
  - However, adding more trucks to **12 trucks** (`trucks_12`) only increases throughput by a tiny **3.4%** (to **12,903.3 tonnes**) while average crusher queue wait times skyrocket from 3.45 min to **14.21 minutes**, and truck utilization plummets from 77.1% to **54.7%**. This proves the system is bottlenecked by the crusher, and adding trucks only increases congestion.

### Q4: Would improving the narrow ramp materially improve throughput?
- **Answer**: **No.** Upgrading the narrow ramp (`ramp_upgrade` scenario with infinite capacity and 28 kph speed limits) only increases throughput by **1.04%** to **12,603.3 tonnes**. Since the ramp is not the system's primary bottleneck, speeding up travel along it merely causes empty/loaded trucks to arrive at the crusher slightly faster, doing nothing to solve the crusher's processing rate limit.

### Q5: How sensitive is throughput to crusher service time?
- **Answer**: **Extremely sensitive.** Doubling the crusher service time to 7.0 minutes (`crusher_slowdown`) cuts the mine throughput almost in half, dropping it by **47.7%** to **6,526.7 tonnes**. Average crusher queue times skyrocket to **26.43 minutes** and truck utilization drops to **48.8%** as trucks spend a massive portion of the shift queuing.

### Q6: What is the operational impact of losing the main ramp route?
- **Answer**: **Negligible.** When the narrow ramp is closed (`ramp_closed`), forcing all trucks to detour via the western/eastern bypass network, the throughput only drops by **1.6%** to **12,273.3 tonnes**. This demonstrates that the bypass network is highly effective and has excellent spare capacity to absorb the detoured haulage traffic.

---

## 3. Comparative Scenario Summary

Below is the summary of key metrics averaged across the 30 replications (each replication runs with a unique seed `base_random_seed + replication_idx` to guarantee reproducibility):

| Scenario | Fleet Size | Mean Throughput (tonnes) | 95% Confidence Interval (tonnes) | Crusher Util (%) | Avg Crusher Queue (min) | Avg Truck Util (%) | Top Bottleneck |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `trucks_4` | 4 | 7,693.3 | [7,655.4, 7,731.2] | 56.0% | 0.64 | 93.2% | `D_CRUSH` |
| `baseline` | 8 | 12,473.3 | [12,427.4, 12,519.3] | 91.1% | 3.45 | 77.1% | `D_CRUSH` |
| `ramp_upgrade` | 8 | 12,603.3 | [12,532.3, 12,674.4] | 91.7% | 3.22 | 77.6% | `D_CRUSH` |
| `ramp_closed` | 8 | 12,273.3 | [12,209.1, 12,337.6] | 90.0% | 3.50 | 76.2% | `D_CRUSH` |
| `trucks_12` | 12 | 12,903.3 | [12,798.9, 13,007.8] | 93.8% | 14.21 | 54.7% | `D_CRUSH` |
| `crusher_slowdown`| 8 | 6,526.7 | [6,464.7, 6,588.6] | 94.7% | 26.43 | 48.8% | `D_CRUSH` |
| **`trucks_12_ramp_upgrade` (Combo)** | 12 | **12,906.7** | [12,804.3, 13,009.0] | 94.3% | 14.69 | 54.3% | `D_CRUSH` |

---

## 4. Modeling & Simulation Methodology

The model represents a robust, highly detailed digital twin of the mine:

### Conceptual Design
- **System Boundary**: Contains loading faces, crusher, and capacity-constrained roads. Omits waste and maintenance loops as they do not affect ore crusher throughput.
- **Entities**: Trucks represent active agents with state transitions (e.g. `TRAVELLING_EMPTY`, `QUEUEING_LOADER`, `LOADING`, `TRAVELLING_LOADED`, `QUEUEING_CRUSHER`, `DUMPING`).
- **Resources**: Loaders, Crusher, and capacity-constrained segments (capacity = 1) modeled as `simpy.Resource` queues.

### Routing & Dispatching Logic
- **Routing**: Static shortest-time paths computed via **Dijkstra's Algorithm** based on free-flow speeds and truck speed factors (empty = 1.00, loaded = 0.85). Re-calculated for each scenario to handle overrides (e.g., closed edges).
- **Dispatching Heuristic**: Dynamic empty truck dispatching based on a min expected completion score:
  $$\text{score}_L = T_{\text{current} \to L} + (Q_L + A_L) \times T_{\text{load}, L} + T_{\text{load}, L}$$
  where $T_{\text{current} \to L}$ is travel time to loader $L$, $Q_L$ is current queue length, $A_L$ is the count of trucks currently loading, and $T_{\text{load}, L}$ is mean load time.

### Stochastic Representation
- **Travel Times**: Travel time noise is represented as a **lognormal distribution** with a 10% Coefficient of Variation (CV = 0.10) to reflect minor road-surface and traffic disturbances while ensuring strictly positive times.
- **Loading & Dumping Service Times**: Modeled as normal distributions truncated with a physical minimum of 0.1 minutes using $\max(0.1, \text{sample})$.

---

## 5. Key Assumptions & Model Limitations

### Key Assumptions
1. Free-flow travel speeds represent baseline driver performance.
2. Truck payloads are fixed at 100 tonnes per cycle.
3. Trucks have instant access to loader and crusher queue states during dispatch decisions.

### Limitations
1. Opposing-traffic single-lane road segments (like uphill and downhill ramps) are modeled as independent separate resources, meaning they do not block each other.
2. No breakdown, fueling, crib-breaks, or weather delays are included.

---

## 6. Recommended Operational Actions

1. **Do Not Purchase Additional Trucks**: Increasing the fleet size beyond 8-9 trucks adds severe congestion at the crusher queue without increasing throughput.
2. **Prioritize Crusher De-bottlenecking**: The primary crusher is the system's hard constraint. Operational improvements that reduce dumping time or increase crusher processing speed (e.g., secondary crushing, feeder optimization, or faster tipping mechanisms) will yield the largest throughput gains.
3. **De-prioritize Ramp Upgrades**: Speeding up the ramp does not lead to significant throughput improvements and should be postponed in favor of crusher upgrades.
4. **Maintain Bypass Integrity**: The bypass network is a highly effective, low-impact alternative routing choice, allowing operations to continue with negligible throughput drops even during complete ramp shutdowns.
