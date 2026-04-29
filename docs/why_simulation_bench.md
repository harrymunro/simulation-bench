# Why Simulation Bench

## Why I created this

With so many harnesses out there, so many different models, and so many different
techniques, I really had a hard time figuring out just what is better — or best —
for doing modelling and simulation work in SimPy.

I wanted a real answer, not a vibe. So I built my own benchmark to help me think
through it: a single, substantial discrete-event simulation problem (synthetic
open-pit mine haulage), a fixed set of decision questions, and an evaluation
harness that captures both the cheap quantitative signals (runtime, tokens, LOC,
schema and behavioural checks) and the things that actually matter for modelling
work (conceptual model quality, defensible assumptions, useful bottleneck
interpretation).

The bet: if I run the same problem through many harness × model × technique
combinations under the same protocol, I will start to see which ones are
genuinely good at modelling work — and which ones just look fast on a leaderboard.

## What I want this document to do

- Make the motivation explicit, so future readers (and future me) understand
  why the benchmark is shaped the way it is.
- Record the design choices that are easy to lose track of once the leaderboard
  exists, especially the ones that look arbitrary but aren't.
- Give a place to write down what I've learned from running it, separate from
  the operational `README.md` / `RUN_PROTOCOL.md` / `SCORING_GUIDE.md`.

## Design choices

A few decisions shaped V1, and most of them were deliberate trade-offs against
what a typical coding benchmark looks like.

### One substantial task, not many toy problems

Most coding benchmarks lean on dozens of small, self-contained problems with
unit-test pass/fail signals. That works for "can the model write a function",
but it does not tell me anything about modelling work. Modelling is the act of
deciding *what to model*, *what to leave out*, and *how to defend those
choices* — and a 50-line toy problem cannot expose any of that.

So V1 is one task: estimate ore throughput to a primary crusher over an 8-hour
shift, using a synthetic open-pit mine network with trucks, loaders, a
crusher, and constrained roads. It is big enough that the agent has to make
real modelling decisions, and small enough that a human reviewer can read the
whole submission in a sitting.

### Fixed decision questions, fixed required scenarios

The prompt pins six decision questions and a set of required scenarios
(baseline, more trucks, fewer trucks, ramp upgrade, crusher slowdown, ramp
closed). Without those anchors, every submission would answer a slightly
different question and nothing would be comparable.

The questions are written as decisions a mine operator might actually want —
"would improving the narrow ramp materially improve throughput?" — rather
than as software requirements. That keeps the focus on the modelling, not on
hitting an output schema.

### Room to choose, within those anchors

Within the fixed questions, the agent is free to choose routing logic,
dispatching policy, assumptions about loading and dumping behaviour, code
structure, and how to communicate uncertainty. That is on purpose. A
benchmark that prescribes the implementation only measures whether the agent
can follow instructions; this one is trying to measure whether the agent can
make defensible choices when the instructions stop short.

### No reference solution in the repo

There is no canonical implementation checked in alongside the prompt. If
there were, I could not trust the human scoring — reviewers would
unconsciously anchor to it, and any agent that had ever scraped this repo
would be reading from the answer key. The cost is that scoring is more
subjective; the benefit is that the benchmark is harder to game.

### Two scoring layers, weighted toward judgement

The evaluation has two layers:

- An **automated harness** that captures the cheap-to-measure things:
  runtime, return code, file presence, schema coverage, scenario coverage,
  basic behavioural sanity checks (more trucks should usually beat fewer,
  closing the ramp should usually hurt), LOC, file count, and token usage
  when the platform exposes it.
- A **human rubric** worth 100 points, weighted toward the things that
  actually determine whether the model is decision-useful: 20 points each
  for conceptual modelling and simulation correctness, 15 each for data and
  topology handling, experimental design, and results and interpretation,
  10 for code quality, and 5 for traceability.

The human layer dominates on purpose. A fast, cheap, wrong simulation is a
very small bonfire — and a leaderboard that rewards efficiency over
correctness would tell me the opposite of what I want to know.

### Intervention transparency

Every submission records whether the run was fully autonomous, succeeded
after hints, succeeded after manual repair, or failed. A leaderboard that
hides interventions overstates how good the underlying agent actually is, and
the whole point of this exercise is to see clearly.

## Outline (still to fill in)

1. The problem space — why modelling and simulation is a hard target for
   agentic coding tools.
2. What the harness can and can't measure — and why that gap is the whole point.
3. Early observations across harnesses, models, and techniques — what the
   submissions are telling me so far.
4. Where this goes next — additional benchmark tasks, scoring refinements,
   leaderboard methodology.
