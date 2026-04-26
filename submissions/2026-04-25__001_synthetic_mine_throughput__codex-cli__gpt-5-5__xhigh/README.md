# Synthetic Mine Throughput Simulation

This submission implements a SimPy discrete-event simulation for the synthetic mine haulage benchmark. It reads the provided topology and scenario files, applies scenario overrides, runs 30 replications per required scenario, and writes reproducible machine-readable outputs.

## Install

Use Python 3 and install the listed dependencies:

```bash
python3 -m pip install -r requirements.txt
```

The tested local environment already had `simpy`, `pandas`, `numpy`, `networkx`, `pyyaml`, and `scipy` available.

## Run

Run all required scenarios from this folder:

```bash
python3 simulate.py
```

This writes:

- `results.csv`: one row per scenario replication
- `summary.json`: scenario-level means, 95% confidence intervals, assumptions, limitations, and bottleneck summaries
- `event_log.csv`: event trace for truck dispatch, road movement, loading, and dumping

To run a subset:

```bash
python3 simulate.py --scenarios baseline trucks_12
```

## Model Summary

Trucks are SimPy processes. Loaders, the crusher, and finite-capacity road segments are SimPy resources. Travel uses shortest expected time routes over the directed graph, then applies stochastic travel variation. Loading and dumping times are positive truncated normal samples. Roads with capacity below `999` are constrained resources; opposite directed edges with the same endpoints share one physical road resource.

Dispatch selects the loader with the lowest estimated empty travel time, current loader workload, mean loading time, and loaded travel time to the crusher. Trucks continue cycling while the shift clock is active. Ore throughput is counted only when a dump completes before the 480-minute cutoff.

See `conceptual_model.md` for the full conceptual model, assumptions, state variables, and limitations.

## Key Results

All values below are means across 30 replications of an 8-hour shift.

| Scenario | Mean tonnes | 95% CI tonnes | t/h | Avg cycle min | Crusher util. | Crusher queue min |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 12,130 | 12,076 to 12,184 | 1,516 | 30.64 | 0.889 | 2.35 |
| trucks_4 | 7,847 | 7,812 to 7,882 | 981 | 23.87 | 0.574 | 0.27 |
| trucks_12 | 12,757 | 12,684 to 12,829 | 1,595 | 43.13 | 0.933 | 11.60 |
| ramp_upgrade | 12,163 | 12,112 to 12,215 | 1,520 | 30.59 | 0.890 | 2.46 |
| crusher_slowdown | 6,447 | 6,379 to 6,514 | 806 | 56.12 | 0.953 | 27.67 |
| ramp_closed | 11,987 | 11,941 to 12,032 | 1,498 | 31.04 | 0.881 | 2.54 |

## Operational Questions

1. Baseline expected throughput is about 12,130 tonnes per 8-hour shift, or 1,516 tonnes per hour.

2. The likely steady-state bottlenecks are the crusher, the south loader `L_S`, the single-lane south face access road `road:J6-LOAD_S`, and the crusher approach `road:CRUSH-J4`. In the baseline, crusher utilisation is 0.889 and `L_S` utilisation is 0.874.

3. Adding trucks helps but saturates. Reducing to 4 trucks lowers throughput to about 7,847 tonnes. Increasing from 8 to 12 trucks raises throughput only to about 12,757 tonnes, a gain of about 5.2%, while average cycle time rises from 30.64 to 43.13 minutes and crusher queue time rises to 11.60 minutes.

4. Improving the narrow main ramp does not materially improve shift throughput in this topology. The ramp upgrade case increases mean throughput by only about 33 tonnes, or 0.3%. The event log shows the main ramp creates startup queueing from parking, but the recurring pit-crusher loop mostly stays on the upper network.

5. Throughput is highly sensitive to crusher service time. Doubling mean crusher dump time from 3.5 to 7.0 minutes reduces throughput to about 6,447 tonnes, a drop of about 46.9%, and crusher queue time rises to 27.67 minutes.

6. Losing the main ramp has a small operational impact under this model because traffic can reroute through the bypass and the recurring production loop does not rely on the lower-to-upper ramp after startup. Mean throughput falls to about 11,987 tonnes, a drop of about 1.2%.

## Additional Scenario Suggested

A useful next scenario would test a second or faster south-pit loader. The current results suggest extra trucks quickly push queueing to the crusher and south-side loading path; a loader-side change would help determine whether the south loader or crusher is the better next capital target.

## Limitations

- No breakdowns, refuelling, operator breaks, blasting delays, or maintenance events are modelled.
- Dispatch is a simple queue-aware heuristic, not a global optimiser.
- Road capacity resources are first-come, first-served and do not include passing bays or directional control logic.
- The model counts only completed dumps by shift end; partially completed cycles do not contribute tonnes.
- The main ramp result depends on the supplied topology: pits and crusher are connected on the upper network, so the ramp is not a repeated haul-cycle link.
