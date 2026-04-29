---
type: article
subtype: linkedin
status: draft
created: 2026-04-29
topic: Why I built Simulation Bench and what the first runs taught me
rhetorical_devices: [antithesis, litotes]
content_profile: article_linkedin
---

# Every AI agent passes the automated checks. That's exactly why I built this benchmark.

I had a question I couldn't answer.

There are dozens of AI coding setups now. Claude Code, Codex CLI, opencode, gsd2, pi-agent. Each runs against multiple models. Each has its own techniques: vanilla, max thinking, custom skills, whatever the latest thing is. Multiply it all out and you've got a matrix big enough to hide in.

For ordinary coding tasks you can just look at the leaderboards. SWE-bench, HumanEval, all of those. They tell you something. But I don't write web CRUD apps. I build discrete-event simulation models for a living, and nothing on those leaderboards looks anything like the work I actually do.

So I built my own benchmark. One substantial task: synthetic open-pit mine haulage in SimPy, eight-hour shift, six required scenarios, six decision questions a real mine operator might actually want answered. Big enough to need real modelling choices. Small enough that a human can read the whole submission in a sitting.

Then I started running things through it.

## The first surprise

Every submission passed every automated check. 53 out of 53. 57 out of 57. All six behavioural sanity checks fired correctly every single time. Claude Opus, Sonnet, GPT-5.5, Gemini 3.1 Pro Preview, whatever I threw at it.

That isn't because the benchmark is too easy. It's because the *automated* part of the benchmark is too easy. Frontier agents can write a SimPy model that runs, produces CSVs, and behaves roughly correctly when you change the inputs. That's table stakes now.

The leaderboard would be flat and uninformative if it stopped there.

## Where the variance actually lives

There's a 100-point human rubric on top of the automated layer. Twenty points for conceptual modelling, twenty for simulation correctness, fifteen each for data and topology handling, experimental design, and results interpretation, ten for code quality, five for traceability.

The human layer is where the agents diverge.

Conceptual modelling scores ranged from 14/20 to 19/20. Results interpretation ranged from 6/15 to 14/15. The same task, the same prompt, the same scenarios produced submissions that ranged from "decision-useful analysis with honest disclosures" to "correct DES with the bottleneck section left as placeholders".

The agents that score well treat the task as a modelling exercise. The ones that score poorly treat it as a coding exercise that happens to use SimPy. That distinction is everything.

## The bit that actually surprised me

I expected the model to dominate. Bigger model, better submission. Simple.

It's not that simple.

The two strongest submissions are both Claude Opus 4.7. One in vanilla Claude Code with max thinking (97/100). One in Claude Code with the superpowers skills enabled and max thinking (94/100). Reasonable. Top model, top scores.

But Sonnet 4.6 in vanilla Claude Code lands at 85/100, with strong conceptual modelling and weaker correctness. And Opus-class effort through other tools lands lower than Opus through Claude Code's native flow.

Same model, different runner, materially different output. That's one data point and I won't claim it's a trend yet. But the early signal is not entirely encouraging if you think the model name is what matters. It suggests the surrounding tooling and the prompting technique aren't just overhead. They shape what the model does on a modelling task.

## The failure modes are weirdly consistent

Across seven submissions, the same mistakes keep showing up.

Numbers that look reasonable but aren't actually derived from the topology. One submission claimed truncated-normal sampling and implemented Gaussian-clip. Looks fine until you read the code.

Silent scenario no-ops. The "ramp closed" scenario passed the behavioural sanity check by accident, because the agent's baseline routing already avoided the ramp. Nobody noticed. Including, presumably, the agent.

Decision questions left half-answered. The simulation runs, the CSVs are produced, the README never quite gets round to answering "would improving the narrow ramp materially improve throughput?". Which was, you know, the entire point.

Utilisation reported without definition. Cycle-time-based numbers labelled "utilisation" with no distinction between queue time and productive time. A mine planner reading that in a real review would ask awkward questions and get awkward silences back.

These are exactly the things automated checks can't catch. They're also exactly the things that matter.

## Why no reference solution

I deliberately didn't check a canonical implementation into the repo.

If I had, I couldn't trust the human scoring. Reviewers would unconsciously anchor to it. And any agent that had ever scraped this repo would be reading from the answer key. The cost is that scoring is more subjective. The benefit is that the benchmark is harder to game and the runs say something real.

Every submission also records whether the run was fully autonomous, succeeded after hints, succeeded after manual repair, or failed. A leaderboard that hides interventions overstates how good the underlying agent is, and the whole point is to see clearly.

## What this is for

I built it for myself. Not as a campaign, not as a service, not as a research programme. I add submissions when I have a real reason to want the answer. There's no plan to systematically cover the matrix. Each new tool/model/technique combination gets added when I would have run it anyway to decide what to use for my own modelling work.

That's deliberate. The runs that show up are the runs I actually wanted to do. If a combination never appears, it's probably because I never had a reason to try it.

The thing the benchmark keeps telling me is that picking the right tool matters less than picking the right way to use the tool. Frontier agents can absolutely build a simulation model. Whether they can do *modelling work* is a different question, and the answer depends on the surrounding setup, the prompting technique, and a lot of small choices most benchmarks don't try to measure.

If you're choosing an AI setup for serious simulation work, don't just pick the model. Pick the whole stack. Then read the output yourself before trusting it.

The repo is at github.com/harrymunro/simulation-bench if anyone wants to poke at it.
