# Conceptual Model

## System Boundary

The model covers one 8-hour ore haulage shift from truck dispatch through loading, loaded travel, crusher dumping, and empty return/re-dispatch to an ore loader. It includes the directed mine road topology, ore loaders, the primary crusher dump point, truck payloads, stochastic service times, stochastic travel-time variation, and finite-capacity road segments.

The model excludes truck breakdowns, refuelling, operator breaks, maintenance dispatch, blasting delays, stockpile blending, downstream plant availability, and detailed traffic rules such as priority control or passing bays.

## Entities

- Trucks are active SimPy processes.
- Ore payloads are represented as a truck state and payload tonnage, not as separate entities.

Each truck has a payload capacity, empty speed factor, loaded speed factor, start node, current route, and cycle-time history.

## Resources

- Loaders at `LOAD_N` and `LOAD_S`, using capacities and service-time parameters from `data/loaders.csv`.
- Primary crusher dump resource `D_CRUSH`, using capacity and dump-time parameters from `data/dump_points.csv`.
- Road segments with capacity below `999`, represented as shared SimPy resources. Opposite directed edges with the same two endpoint nodes share one physical road resource, so traffic in both directions competes for a single-lane segment.

Roads with capacity `999` are treated as unconstrained but still have time-consuming travel.

## Events

The main truck cycle is:

1. Truck dispatched from its current node.
2. Loader selected by dispatch policy.
3. Truck travels empty over the directed topology to the selected loader.
4. Truck queues for the loader.
5. Loading starts and ends.
6. Truck travels loaded to the crusher.
7. Truck queues for the crusher.
8. Dumping starts and ends.
9. Completed dump contributes payload tonnes to shift throughput.
10. Truck is re-dispatched empty from the crusher while the shift is still active.

For constrained road resources, the event log also records road queue and road entry events.

## State Variables

The simulation tracks:

- simulation clock time in minutes
- truck loaded/empty status
- truck current node during dispatch and movement
- selected loader and route
- tonnes delivered to the crusher
- completed truck cycle times
- loader, crusher, and constrained-road queue waits
- loader, crusher, and constrained-road busy time
- truck productive time spent travelling, loading, or dumping

## Assumptions Derived From Data

- The primary production objective is ore delivery from `LOAD_N` and `LOAD_S` to `CRUSH`.
- Trucks carry 100 tonnes per completed dump.
- Node and dump/loader service-time means and standard deviations define loading and dumping duration.
- Edge distance and maximum speed define mean travel time.
- Edges marked closed are unavailable for routing.
- Scenario YAML files override the baseline scenario data.

## Introduced Assumptions

- Loading and dumping durations are positive truncated normal samples.
- Travel time uses a lognormal multiplier with the configured coefficient of variation.
- Routing uses shortest expected travel time on currently open directed edges.
- Dispatch chooses the loader with the lowest estimated empty travel time, current loader queue workload, mean load time, and loaded travel time to the crusher.
- Trucks are continuously dispatched while the 8-hour shift is active.
- Throughput is counted only for dumping completions before the shift cutoff.
- Truck utilisation in `results.csv` is productive utilisation: the fraction of shift time spent travelling, loading, or dumping, excluding resource queue waits.

## Limitations

- The dispatch policy is heuristic and myopic; it does not globally optimise fleet assignment.
- Road resources are first-come, first-served and do not model traffic direction control or passing bays.
- The narrow main ramp primarily affects startup access from parking in this topology; after trucks enter the upper network, the crusher-to-loader loop usually does not use it.
- Resource service times are independent and identically distributed; temporal correlation from weather, shift conditions, or operator effects is not modelled.
- Unfinished truck cycles at the shift cutoff do not count toward delivered tonnes.

## Performance Measures

The experiment reports, by scenario and replication:

- total tonnes delivered to the crusher
- tonnes per hour
- average completed truck cycle time
- average productive truck utilisation
- crusher utilisation
- average loader queue time
- average crusher queue time
- loader-specific utilisation and queue waits
- constrained-road utilisation and queue waits

Scenario summaries report means and 95% confidence intervals for throughput metrics across 30 replications.
