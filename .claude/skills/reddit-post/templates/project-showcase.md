# Template: Project Showcase Post

## Best subreddits
- `r/Python`, `r/SideProject`, `r/programming`, `r/simpy`, `r/datascience`

## Best rhetoric devices
- **Antithesis** for before/after or problem/solution
- **Tricolon** for feature lists
- **Anadiplosis** for building narrative momentum

## What needs to be in the post

A project showcase needs to answer a few questions, but how you organise the answers is up to you:

- **What you built**: in one or two sentences, what is it?
- **Why it exists**: what problem were you solving? (can be implicit, don't need a whole section)
- **Working code**: a key snippet, the interesting bit, not the boilerplate
- **Results or proof it works**: numbers, benchmarks, output, screenshots
- **Honesty about what's rough**: limitations, things you'd change, known issues

Optional:
- Links to repo/demo (if open source or public)
- What feedback you're looking for (be specific)
- Tech stack details (if interesting, not just a laundry list)

## Structural approaches

**Do NOT follow any of these as a fill-in-the-blanks template. Vary the structure each time.**

### Approach 1: Lead with results

Open with the numbers or the output. "After 100 replications, my SimPy model matched Arena's results within 5%." Then explain what the thing is and how you built it. People care about results first, the backstory can come after.

### Approach 2: Embed the code early

One or two sentences of context, then drop the core code snippet. Let the code do the talking. Explain what's interesting about it after. Fill in the "why I built this" context later in the post, or just let people infer it.

### Approach 3: Just tell the story

No headers. Write it as a narrative. "I had this problem, I tried this, it didn't work, I tried something else, here's where I landed." Let the code and results appear naturally where they fit in the story. This reads the most human but works best when the story is genuinely interesting.

## Example

**Title:** I built a hospital A&E simulator in SimPy. 200 lines that replaced a £15k Arena model

**Body:**
```
After years of Arena for healthcare simulation, I wanted to see if SimPy
could handle a real-world A&E patient flow model. Short answer: yes.

A local NHS trust needed ambulance arrivals, walk-ins, triage, treatment,
discharge modelled. Previous quote from a consultancy: £15,000 + licence
costs. My approach: two weekends and a lot of coffee.

The core of the model is honestly not that complicated:

```python
def patient(env, name, priority, hospital):
    arrival = env.now
    with hospital.triage.request(priority=priority) as req:
        yield req
        yield env.timeout(np.random.exponential(triage_time))

    with hospital.treatment.request(priority=priority) as req:
        yield req
        yield env.timeout(np.random.exponential(treat_time[priority]))

    hospital.log_patient(name, arrival, env.now)
```

Priority queuing came free with `PriorityResource`. Didn't have to
build it myself, which was a nice surprise.

After 100 replications:
- Mean wait: 47 mins (vs 52 from Arena)
- 4-hour breach rate: 8.3% (vs 8.1%)
- Runtime: 2.3 seconds for 100 reps. Arena took 4 minutes.

Close enough for decision-making. Fast enough that I could actually
run sensitivity analysis without going to make tea.

Things I'd do differently. I'd use `FilterStore` instead of
`PriorityResource` (more flexible), and I should've written tests
from the start instead of bolting them on after. The plotting code
is also messier than the simulation code but that's always the way.

Full code on GitHub: [link]. Not polished, not production-ready,
but it works and it's free.

edit: should mention it does patient arrivals as a Poisson process,
triage with priority-based queuing, treatment rooms as shared resources
with capacity constraints. Tracks wait times, utilisation, breach rates.
```

## Anti-patterns (what NOT to do)

These are the AI tells specific to project showcases:

- **The six-section template.** "Why I Built This" -> "What It Does" -> "How It Works" -> "Results" -> "What I'd Do Differently" -> "Links" is instantly recognisable as generated. You can cover all these things, but don't put them in labelled sections like a product spec.

- **Feature bullet lists that read like marketing copy.** "Models patient arrivals (Poisson process, configurable rates)" with consistent formatting for 5 items is an AI pattern. Mention features as they come up in the narrative, or if you do list them, make the list messy.

- **The perfectly self-aware "What I'd Do Differently" section.** Some self-awareness is good, but a tidy section with three bullet points of equal length is suspicious. Scatter your self-criticism through the post, or mention it casually at the end.

- **"Looking for feedback on X" as a closer.** Specific feedback requests are fine in moderation, but "Looking for feedback on the modelling approach, especially from anyone who's done healthcare simulation. What am I oversimplifying?" reads like a crafted engagement hook. Sometimes just post the thing and let people respond to whatever catches their eye.

- **The "Not polished, not production-ready, but it works" disclaimer.** This exact phrase pattern (three parallel clauses) is becoming an AI fingerprint. Be honest about limitations but vary how you express it.

- **Separate "Links" section at the end.** Just drop the GitHub link inline wherever it fits naturally. A standalone "Links" section with formatted bullet points is unnecessarily structured.

## Voice notes for project showcases

- Lead with what's interesting, not with backstory, nobody cares about your tool until they're intrigued
- Include actual numbers, lines of code, runtime, cost savings, accuracy comparisons
- Show real code, not marketing screenshots
- Be honest about limitations, but scatter the honesty, don't collect it into a confessional section
- Disclose if it's your product/business: "Full disclosure: I built this and I teach simulation"
- Open source it if you can. Reddit strongly prefers this
- Imperfection is a feature. A post where you circle back to add something you forgot ("edit: should mention it also does X") reads as more human than one where everything is covered perfectly the first time.
- Let some rough edges show in the writing itself, not just in your description of the project
