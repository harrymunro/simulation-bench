# Reviewer Form: Asia–Europe Container Shipping (002)

Submission:

Reviewer model:        <!-- e.g. claude-opus-4-8 -->
Reviewer harness:      <!-- e.g. claude-code -->
Date:

## Automated report

- Automated report file:
- Runtime seconds:
- Python LOC:
- Required scenarios present:
- Behavioural checks passed:
- Event-log cross-check (summary vs trace):
- Token usage method:

## Human quality score

| Category | Max | Score | Notes |
|---|---:|---:|---|
| Conceptual modelling | 20 |  |  |
| Data and topology handling | 15 |  |  |
| Simulation correctness | 20 |  |  |
| Experimental design | 15 |  |  |
| Results and interpretation | 15 |  |  |
| Code quality and reproducibility | 10 |  |  |
| Traceability and auditability | 5 |  |  |
| **Total** | **100** |  |  |

> Reweighting note: at maximum difficulty, presentation alone earns little. Award
> the top of each band only for substantive correctness — especially a correctly
> *diagnosed* bottleneck and the trap scorecard below. Do not award points back for
> tidy formatting that masks a wrong conclusion.

## Trap diagnosis scorecard (the discriminators)

Tick what the submission actually demonstrates (see `expected/private_expected_behaviour.md`).
These feed Data/topology (cat 2), Simulation correctness (cat 3), and Results (cat 5).

- [ ] Identifies the **Rotterdam discharge berth** as the binding constraint (with evidence, e.g. utilisation), not the canal
- [ ] **Trap A:** explains `canal_upgrade` is a near-no-op *because* the berth binds / the canal has slack
- [ ] **Trap B:** identifies saturation / diminishing returns under `fleet_large` and the anchorage-queue blow-up
- [ ] **Trap C:** reroutes `canal_closed` via the Cape (or fails loudly), and reports the longer cycle / lower throughput
- [ ] Recommends the **non-obvious** intervention: more Rotterdam discharge capacity (not more ships, not the canal)
- [ ] Handles the start-of-horizon **transient / warm-up** and justifies it
- [ ] Avoids the **distractors**: does not count Hamburg as delivered throughput; does not invent a binding draft constraint

## Key observations

### Strengths

-

### Weaknesses

-

### Failure modes observed

Tick any that apply.

- [ ] Did not use SimPy / static calculation rather than DES
- [ ] Used topology cosmetically but not meaningfully (no graph routing)
- [ ] Named the canal as the bottleneck without checking utilisation
- [ ] Reported `canal_upgrade` no-op without explaining why
- [ ] Claimed "more ships = more throughput" and missed saturation
- [ ] `canal_closed` did not reroute (errored silently / teleported / no cost)
- [ ] Invented a Panama or other impossible reroute
- [ ] Recommended canal or fleet investment as the primary lever
- [ ] No multiple replications / no seed control / no uncertainty reporting
- [ ] Ignored the start-of-horizon transient
- [ ] summary.json throughput not supported by the event log (failed cross-check)
- [ ] Hard-coded outputs
- [ ] Over-polished visualisation, weak model
- [ ] Failed to answer the decision questions

## Final judgement

Would you trust this model as a first-pass decision-support artefact?

- [ ] Yes
- [ ] Partially
- [ ] No

Notes:
