# Template: Technical Tutorial Post

## Best subreddits
- `r/Python`, `r/learnpython`, `r/simpy`, `r/datascience`

## Best rhetoric devices
- **Tricolon** for listing steps or concepts
- **Asyndeton** for punchy instruction sequences
- **Litotes** for understated observations about complexity

## What needs to be in the post

A technical tutorial needs these ingredients, but NOT in any fixed order, and not all of them every time:

- **The thing you did or discovered**: what's the actual technique/trick/approach?
- **Working code**: real, runnable code that someone can copy. Not pseudocode.
- **Why it matters**: what problem does this solve? What was the alternative?
- **Something you didn't expect**: a gotcha, a surprise, a thing that confused you
- **Specifics**: numbers, version numbers, timings, line counts. Vague is suspicious.

Optional (include when natural, skip when not):
- TL;DR, one sentence, only for longer posts
- Link to full code/repo
- What you'd do differently next time

## Structural approaches

**Do NOT follow any of these as a fill-in-the-blanks template. They're starting points. Vary the structure each time.**

### Approach 1: Lead with the code

Jump straight into the code snippet after 1-2 sentences of context. Explain what it does *after* showing it. This is how people actually share things in Slack or Discord. "Hey look at this" first, explanation second.

### Approach 2: Tell the story

Write it like you're telling a colleague what happened. No headers. Just paragraphs. "I was trying to do X, tried Y, that didn't work because Z, then I found this..." Let the code appear naturally in the narrative where it makes sense.

### Approach 3: Problem-embedded

State what you were stuck on, show the code that fixed it, then scatter the insights throughout instead of collecting them into a tidy "What I Learned" section. Mention the gotchas inline, as they come up.

## Example

**Title:** SimPy trick: using Store instead of Resource when your queue items aren't identical

**Body:**
```
I spent weeks modelling a warehouse with SimPy using `Resource` for
everything. Picking stations, packing lines, dispatch bays. It worked
fine until the client asked "Can we prioritise express orders?"

`Resource` doesn't care what's in the queue. First-come, first-served.
Full stop.

Turns out `simpy.FilterStore` exists for exactly this:

```python
import simpy

def warehouse(env):
    dispatch = simpy.FilterStore(env, capacity=50)

    yield dispatch.put({"order": "A1", "priority": "express"})
    yield dispatch.put({"order": "A2", "priority": "standard"})

    # grab only express orders
    item = yield dispatch.get(lambda x: x["priority"] == "express")
```

Three lines changed from my original `Resource` version. The entire
priority system just fell out naturally from that.

The thing that annoys me is that the SimPy docs do mention this.
Briefly. On one page. I'd been using the library for months.

Quick mental model if it helps:
- `Resource` = identical items competing for capacity
- `Store` = items you need to inspect or filter
- `FilterStore` = Store but with a lambda so you can grab specific ones

TL;DR: use FilterStore not Resource if your queue items aren't identical
```

## Anti-patterns (what NOT to do)

These are the AI tells specific to technical tutorials:

- **The Problem / The Solution / What I Learned structure.** This is the single biggest AI fingerprint for technical posts. Real people don't organise their thoughts into these exact three buckets. Avoid these exact headers.

- **Three insights, all the same length, all in bullet points.** If you have observations, vary how you present them. Some inline, some as asides, some as bullets. Don't make them symmetrical.

- **"Here's what I learned" as a standalone section.** Insights land better when they're woven into the narrative. "I didn't realise until later that..." mid-paragraph is more human than a tidy list at the end.

- **The crafted TL;DR.** "TL;DR: SimPy's FilterStore provides a flexible mechanism for priority-based queue management, enabling lambda-based filtering that...". nobody writes a TL;DR like that. One casual sentence.

- **Closing with "Anyone else discovered X?"**: works once in a while, but if every tutorial ends with a discussion question, it's a pattern. Sometimes just end with the last piece of information.

- **Uniform code explanation.** Don't explain every line of code. Explain the surprising bits. Skip the obvious ones. "The `yield` stuff is standard SimPy, the interesting bit is the lambda on line 8."

## Voice notes for technical tutorials

- Show working code, not pseudocode. Reddit will try to run it
- Admit what confused you. "I was stuck on this for hours" builds credibility
- Include the version numbers (Python 3.11, SimPy 4.1.1)
- If there's a better way, acknowledge it. Reddit will tell you anyway
- Specifics beat generalities: "50 lines" not "a few lines", "3 hours" not "a while"
- Imperfection is a feature. A slightly disorganised post with genuine insight beats a perfectly structured post every time.
- Vary your register, go from technical to casual within the same paragraph
