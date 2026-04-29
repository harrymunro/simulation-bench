# Template: Nurture Email Sequence

## Purpose
Build relationship with new subscribers over time. Establish trust before asking for anything.

**Do NOT follow this as a fill-in-the-blanks template.** A nurture sequence is a series of emails, not a series of identical structures with different content pasted in. The biggest AI tell in nurture sequences is every email following the same micro-structure, same length opening, same kind of body, same style of sign-off. Each email should feel like it was written on a different day (because it should be). Read [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md) first.

## Best rhetoric devices
- **Anadiplosis** for narrative flow
- **Litotes** for humble, relatable tone
- **Epistrophe** for memorable closes

Use sparingly and invisibly. Don't use the same device in consecutive emails.

## Sequence Overview (7 emails over 3 weeks)

| Day | Email | Purpose | CTA |
|-----|-------|---------|-----|
| 0 | Welcome | Set expectations, deliver lead magnet | None |
| 2 | Quick win | Immediate value, build credibility | Reply |
| 5 | Story | Personal connection, relatability | None |
| 8 | Deep value | Substantial teaching | Free resource |
| 12 | Philosophy | Your worldview, differentiation | None |
| 16 | Soft pitch | Introduce paid offering | Learn more |
| 21 | Transition | Move to regular newsletter | Choose frequency |

## The Most Important Rule: Deliberate Variation

Each email in the sequence must feel different from the ones before and after it. Vary these deliberately:

- **Length**: Email 1 might be 150 words. Email 4 might be 400. Email 7 might be 60.
- **Structure**: One email is mostly a story. The next is a code walkthrough. The next is three paragraphs and a question.
- **Tone**: The welcome is warm and straightforward. The story email is reflective. The philosophy email is opinionated. The transition is brief and practical.
- **Sign-off style**: "Harry" / "- H" / "Harry" / just the name / "- Harry" / "H" / "Harry". don't use the same one twice in a row.
- **Opening style**: Don't start three consecutive emails with a declarative statement. Mix it up: a question, a scene, a fact, a code snippet, a one-word sentence.
- **CTA presence**: Some emails have no CTA at all. Some end with "hit reply." Some have a link. The variation is the point.

If someone reads all 7 emails back-to-back (they won't, but still), they should not be able to identify a repeated micro-structure.

---

## Email 1: Welcome (Day 0)

Short. Deliver the thing they signed up for. Set expectations. Don't oversell yourself.

```
Subject: Your [lead magnet] is ready

Here it is: [LINK]

I'm Harry. I teach engineers how to build simulation
models using Python and SimPy.

Quick background: I spent ten years building simulations
for clients in manufacturing, logistics, and operations.
Now I teach others to do the same.

What you can expect from these emails:

- Practical SimPy tips you can use immediately
- Honest takes on the simulation industry
- Occasional stories of things going wrong (there are many)

I send roughly one email per week. You can unsubscribe
anytime - no hard feelings.

For now, enjoy the [lead magnet]. If you have questions,
hit reply. I read every response.

Harry
```

---

## Email 2: Quick Win (Day 2)

Give them something they can use right now. Code is good here. Keep the framing minimal, let the tip do the work.

```
Subject: The first thing I build in every simulation

Before I model anything complex, I build this:

A single entity going through a single process with a
single resource.

Every time. No matter how complex the final model will be.

Here's why:

If this simple case doesn't work, nothing will.

    import simpy

    def simple_process(env, resource):
        with resource.request() as req:
            yield req
            yield env.timeout(5)
            print(f"Done at {env.now}")

    env = simpy.Environment()
    resource = simpy.Resource(env, capacity=1)
    env.process(simple_process(env, resource))
    env.run()

That's it. 10 lines. One entity. One resource.

From here, I add complexity piece by piece. Each addition
either works or breaks something. When it breaks, I know
exactly what caused it.

The engineers who struggle most are the ones who try to
build the whole model at once.

Start simple. Verify as you go.

Does this match how you approach new models?
Hit reply - I'm curious about your process.

Harry
```

---

## Email 3: Story (Day 5)

This one should feel different from emails 1 and 2. No code. No tips. Just a story that reveals something about how you think. Let the lesson be implicit, don't spell it out with a "The lesson I learned was..." paragraph.

```
Subject: The model that almost got me fired

True story.

Early in my career, I built a simulation for a warehouse
operations team.

They wanted to know how many pickers they needed for
peak season. Simple enough, right?

I built the model. Ran the experiments. Delivered the
recommendation: they needed 40% more staff.

The operations manager went pale. That wasn't in budget.
That would need director approval. That would make him
look like he hadn't planned properly.

He asked me to "re-run the numbers."

I understood what he meant: find a different answer.

I didn't. The model was right.

What I did wrong was surprising him. I'd delivered truth
without preparing him for it. I'd made his problem worse,
not better.

Now I start every project with: "What result would be
difficult for you to act on?"

Better to know the constraints before you model.

- H

P.S. The warehouse did hire more pickers. Three months
after peak season destroyed their SLAs. Sometimes being
right just means waiting.
```

---

## Email 4: Deep Value (Day 8)

The meatiest email. Teach something substantial. This is where a code pattern, a longer walkthrough, or a detailed explanation earns its place. It should feel like a mini blog post that landed in their inbox.

```
Subject: The SimPy pattern that changed everything for me

There's a pattern I use in almost every simulation now.

It's not in most tutorials. I figured it out after years
of hitting the same problems.

I call it the "Event Collector" pattern.

The problem: SimPy runs, but you can't easily see what
happened. Print statements get messy. Logs become walls
of text.

The solution: A simple collector that captures events
as they happen, ready for analysis afterward.

    from dataclasses import dataclass
    from typing import List

    @dataclass
    class Event:
        time: float
        entity: str
        action: str
        details: dict

    class EventCollector:
        def __init__(self):
            self.events: List[Event] = []

        def record(self, time, entity, action, **details):
            self.events.append(Event(time, entity, action, details))

        def to_dataframe(self):
            import pandas as pd
            return pd.DataFrame([vars(e) for e in self.events])

Now in your processes:

    collector.record(env.now, "Patient-1", "arrived", priority=2)
    collector.record(env.now, "Patient-1", "started_treatment")

After the run:

    df = collector.to_dataframe()
    # Full event history, ready for analysis

This single pattern made my simulations 10x easier to
debug and analyse.

I wrote a full guide on this with more examples:
[LINK TO FREE RESOURCE]

Harry
```

---

## Email 5: Philosophy (Day 12)

Opinionated. This is where you differentiate yourself. Take a stance. Don't hedge. The tone should be noticeably different from the teaching emails, more reflective, more personal conviction.

```
Subject: Why I teach SimPy (not Arena, Simul8, or FlexSim)

People sometimes ask why I focus on SimPy.

Commercial tools have better UIs. Bigger companies behind
them. More "enterprise" credibility.

Here's my honest answer:

I've used those tools. I've paid for those licences. I've
sat through those vendor trainings.

And I've watched engineers become dependent on tools they
don't control.

When the licence expires, the model stops running.
When the vendor changes the format, old work breaks.
When you need something custom, you're stuck.

SimPy is different.

It's free. It's Python. It's yours.

You control your code. You own your models. You decide
what's possible.

Is it harder to learn? At first, maybe. But you're learning
Python - a skill that transfers everywhere.

Is the UI less pretty? There's no UI. You build what you
need.

Does it have less features? No. It has fewer buttons.
The features come from the Python ecosystem.

I teach SimPy because I believe engineers should own their
tools, not rent them.

That might not be the right choice for everyone.
But it's why I'm here.

Harry
```

---

## Email 6: Soft Pitch (Day 16)

Brief. Honest. Low pressure. This should be noticeably shorter than the emails before it. Don't re-sell them on your expertise, you've been demonstrating it for two weeks.

```
Subject: If you want to go further

For the past two weeks, I've been sharing SimPy tips
and stories.

If you've found them useful, there's more where that
came from.

The Simulation Bootcamp is my complete programme for
engineers who want to master SimPy.

Structured learning. Real projects. Direct support.

Not for everyone - it requires time and focus.

But if you're serious about becoming the simulation
expert on your team, it's the fastest path I know.

You can see what's inside here: [LINK]

No pressure. These emails will keep coming either way.

But I wanted you to know it exists.

- H
```

---

## Email 7: Transition (Day 21)

The shortest email in the sequence. Practical, not sentimental. Just tell them what happens next.

```
Subject: What happens next

You've been getting these "welcome" emails for three weeks.

Starting now, you'll get my regular newsletter instead.
Same voice, same mix of tips and stories. Just less
frequent, usually once a week.

If that's too much, you can switch to monthly or
unsubscribe entirely: [LINK]

No hard feelings either way. Your inbox, your rules.

Harry

P.S. If you ever have a simulation question, just reply.
I read every response.
```

---

## Anti-Patterns

Things that make nurture sequences smell like AI:

- **Every email follows the same micro-structure.** If all 7 emails are: opening hook -> body content -> lesson -> sign-off, the sequence reads as generated. Deliberately break the pattern. Some emails should be mostly story. Some mostly code. Some just a few sentences.
- **Uniform length.** If every email is 150-200 words, that's suspicious. A welcome email might be 120 words. The deep value email might be 350. The transition email might be 60.
- **Same sign-off every time.** Alternate between "Harry", "- H", "- Harry", just the name.
- **Parallel subject line style.** Don't make every subject line follow the same formula. Mix declarative statements, questions, fragments, and casual phrases.
- **The predictable CTA escalation.** Yes, the sequence should build from no-CTA to soft-CTA to pitch. But it shouldn't feel like a ramp. Some emails after email 2 can have no CTA at all. The pitch in email 6 should feel spontaneous, not inevitable.
- **Every email starting the same way.** Don't start three consecutive emails with a first-person declarative sentence. Vary your openings: a question, a scene, a fact, a code snippet.
- **Wrapping every story with "The lesson I learned was..."** Let some lessons be implicit. Trust the reader.

## Voice notes for nurture sequences
- Build trust slowly - no selling until email 6
- More personal, less polished than other content
- Stories > tips in early emails
- Ask for replies, not clicks
- Acknowledge that you're in their inbox by invitation
- Each email should feel like it was written on a different day, because it should have been
