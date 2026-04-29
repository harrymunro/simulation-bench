# Template: Medium Technical Prose

For explaining concepts, methodologies, tools, and how things work. Written entirely in prose. No code, no tables, no lists.

**Do NOT follow this as a fill-in-the-blanks template.** Technical Medium articles should read like a knowledgeable friend explaining something over a long coffee. The reader (or listener) should follow the logic through narrative, not through formatted structures.

## The challenge

Technical content is where the prose-only constraint is hardest. The instinct is to show code, to build a table, to make a numbered list of steps. Resist all of it. If you can't explain something without visual formatting, you don't understand it well enough to write about it. That's not a criticism. It's a genuinely useful forcing function.

When you describe what code does instead of showing it, you're forced to understand the why, not just the what. "This function iterates over arrivals and calculates the mean inter-arrival time" is less useful than "The idea is surprisingly simple: look at when each customer walked through the door, measure the gaps between arrivals, and average those gaps. That average tells you how frequently customers show up, which turns out to be the single most important input to your entire simulation."

## Best rhetoric devices

- **Anadiplosis** for building chains of explanation where one concept leads to the next
- **Anaphora** for emphasising patterns or repeated structures in an argument

Use at most 1-2. They must be invisible. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md).

## Approaches

### Approach 1: The concept unwrapped

You're explaining something that sounds complicated but has a simple core idea. Start with why anyone should care. Then peel back the layers, starting from the simplest version and adding complexity only when the reader is ready. Don't build toward a reveal. State the simple version early and then deepen it.

The key is to use concrete scenarios throughout. Don't say "a process enters a queue." Say "a patient arrives at A&E and joins the queue for triage." Every abstraction should have a corresponding real-world image the listener can hold in their head.

This works well for: SimPy concepts, simulation methodology, statistical ideas, programming paradigms.

### Approach 2: The comparison in motion

You're comparing two approaches, tools, or methodologies. Instead of a side-by-side table, tell the story of using both. Describe the experience of each. Where one frustrated you. Where the other surprised you. Let the comparison emerge from lived experience rather than feature checklists.

The danger here is false balance. If you genuinely think one approach is better, say so early and then use the comparison to explain why. Readers respect opinions. They distrust neutral surveys.

This works well for: SimPy vs commercial software, Python vs other languages, different simulation approaches, competing methodologies.

### Approach 3: The method walked through

You're explaining how to do something. Instead of numbered steps, narrate the process as a journey. "The first thing you'll want to do is..." followed by "Once that's in place, the next question is..." followed by "This is where it gets interesting, because...". The reader follows a path rather than checking off a list.

Include the false starts and dead ends. "My first instinct was to model this as a simple queue, but that fell apart when I realised that patients don't actually wait in order. They get triaged by severity." That narrative of failed-then-corrected approach teaches more than the correct approach alone.

This works well for: tutorials, how-to guides, process explanations, getting-started guides.

## Anti-patterns

- **The textbook explanation**: Defining terms, stating properties, listing applications. This is what Wikipedia does. Medium articles should feel like discovery, not reference material.
- **The step-by-step without story**: "First, install Python. Then, import SimPy. Then, define your process." Even when narrated in prose, if the structure is obviously a disguised numbered list, it reads as AI-generated.
- **Abstract throughout**: Never grounding the explanation in a specific, tangible scenario. If you're explaining probability distributions, don't just describe what an exponential distribution is. Describe the specific moment when you realised your simulation was wrong because you'd used a normal distribution for arrival times and the results looked nothing like reality.
- **Equal depth everywhere**: Not everything needs the same level of explanation. Spend three paragraphs on the concept that's actually confusing and one sentence on the bit that's straightforward.
- **The disclaimered expertise**: "I'm no expert, but..." or "This is just my understanding..." at the start of a technical article. If you're writing about it, own your knowledge. Caveat specific claims where appropriate, not the entire piece.

## Example

```markdown
# Why Your Simulation Results Look Wrong (and What To Do About It)

## It's probably the warm-up period

I wasted three months of my career before someone told me about warm-up
periods.

I was building factory simulations, running them for what I thought was
long enough, and getting results that never quite matched reality. The
utilisation numbers were always slightly off. The queue lengths didn't
match what the factory floor managers were seeing. I assumed I was
modelling something wrong. I rebuilt the logic twice.

The problem was simpler and more embarrassing than that. When a
simulation starts, everything is empty. No queues, no work in progress,
no parts moving through the system. The simulation has to fill up before
it reaches a state that looks anything like the real system. Those first
few hundred time steps are essentially fiction, and I was averaging them
into my results.

The fix is to throw away the beginning. Run the simulation, ignore the
first chunk of time until the system reaches a steady state, and only
start collecting statistics after that point. In the simulation world,
this is called the warm-up period, and once you know about it, you
see it everywhere.

## How long is long enough?

This is where it gets genuinely tricky. There's no universal answer.
A simple queue model might settle down in a few hundred time steps.
A complex factory with recirculating flows might take thousands. I've
seen models that needed tens of thousands of steps before the transient
effects washed out.

The method I use, and I should say upfront that this is one of several
valid approaches, is Welch's method. The idea is to run the simulation
multiple times, average the output across those runs, and then apply a
moving average to smooth the result. You look at the smoothed curve and
find where it flattens out. That's roughly where your warm-up period
ends.

It sounds precise. It isn't, really. You're eyeballing a curve and
making a judgement call. But it's a much better judgement call than
guessing, which is what I was doing before.
```

Notice: the explanation of a technical concept (warm-up periods) is entirely in prose. No code, no formulas, no diagrams. The reader follows through narrative and specific experience. The second section admits uncertainty honestly rather than presenting the method as definitive.

## Variations

### The misconception corrected

Start with what people typically get wrong. Explain why it's wrong through a specific experience. Then explain what's actually going on. This works because listeners naturally lean in when they think they might be wrong about something.

### The evolution of understanding

Describe how your understanding of a concept changed over time. First you thought X. Then you learned Y. Now you think Z, but you're not entirely sure about one part of it. This mirrors how people actually learn and is almost impossible to fake with AI.

### The practical consequence

Focus less on how something works and more on what happens when you ignore it. Describe the failure mode in vivid detail. Then explain the concept as the solution to that specific failure. The concept becomes the answer to a question the reader is already asking.
