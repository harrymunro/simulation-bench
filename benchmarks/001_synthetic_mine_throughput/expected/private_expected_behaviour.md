# Private Expected Behaviour Notes

These notes are intended for evaluator calibration. Do not provide them to agents during a run.

## Baseline

The baseline has:

- 8 trucks
- 2 ore loading points
- 1 crusher
- capacity-constrained narrow ramp
- capacity-constrained crusher approach
- optional bypass

Expected bottleneck candidates:

- `E03_UP` / `E03_DOWN` narrow ramp
- `E05_TO_CRUSH` / crusher approach
- `CRUSH` / `D_CRUSH`
- potentially `L_N` depending on dispatch logic

## Truck-count sensitivity

Expected broad relationship:

```text
trucks_4 < baseline < trucks_12
```

However, the increase from 8 to 12 trucks should usually be smaller than the increase from 4 to 8 trucks if bottlenecks are modelled.

## Ramp upgrade

Expected:

- throughput improves or remains close to baseline
- queueing on the narrow ramp decreases
- bottleneck may shift to crusher, crusher approach, or loaders

## Crusher slowdown

Expected:

- throughput falls
- crusher queue time rises
- crusher utilisation should be high

## Ramp closure

Expected:

- the model should reroute via the bypass if routing is implemented
- throughput should fall or cycle time should rise
- if no route is possible, the model should fail clearly and document the failure

## Notes

These are behavioural expectations, not exact numeric answer keys.

