# Template: Newsletter Email

## Purpose
Regular value delivery. Stay top of mind. Build trust.

**Do NOT follow this as a fill-in-the-blanks template.** This is loose guidance. Every newsletter should feel like a quick personal email you dashed off because something was on your mind, not a structured content piece assembled from components.

## Best rhetoric devices
- **Tricolon** for listing insights
- **Anadiplosis** for flowing narratives
- **Litotes** for understated observations

But keep them invisible. If someone could circle the device, you've overcranked it. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md).

## Loose Structure

The general idea is: share something useful or interesting, maybe ask for a reply. That's it.

Some ways this plays out:

- **Tip + story**: You learned something, here's the context, here's the thing. Probably the most common shape.
- **Just a tip**: Three sentences. A code snippet. Done. Not everything needs a narrative arc.
- **Just a story**: Something happened on a project. You're telling someone about it. The lesson is implicit, you don't need to spell it out.
- **A question**: You're genuinely wondering something. You ask your list. That's the whole email.
- **A ramble**: You started writing about one thing and ended up somewhere else. This is fine. Possibly the most human format there is.

Don't force every newsletter into the same shape. If the last three emails were tip-story-CTA, the next one should be something different.

```
Subject: [Something you'd actually type, not a formula]

[Start with whatever's interesting. A story, a fact, a question,
a line of code. No preamble.]

[The main thing you want to say. Could be one paragraph,
could be five. Let it be as long or short as it needs to be.]

[Maybe a code example if relevant]

[Maybe a takeaway. Or maybe you just stop here.]

---

[Optional: a question, reply invitation, or soft pointer to something.
Or nothing, not every email needs a CTA.]

Harry (or - H, or just your name, vary it)

P.S. [Optional, afterthoughts, secondary links, personal asides.
These feel human. Use them when something genuinely occurs to you.]
```

## Subject Line Examples
- "The 30-second SimPy trick that took me years to find"
- "Why your simulation is lying to you"
- "I deleted 500 lines of code yesterday"
- "The question that changed how I model"
- "What I got wrong about [topic]"
- "quick SimPy thing"
- "this broke my model for a week"

Remember: the best subject lines don't follow a formula. Write it like you'd type it to a colleague. See the subject line warnings in [SKILL.md](../SKILL.md).

## Example Newsletter

```
Subject: The simulation that made me look stupid

Last month, I presented a model to a client.

Twenty minutes of polished slides. Beautiful visualisations.
Confident recommendations.

Then someone asked: "What happens if the arrival rate
doubles during the lunch rush?"

I didn't know.

I'd modelled steady-state. Constant arrival rates. Nice,
neat, mathematically convenient assumptions.

Real systems don't work that way.

The fix was simple - a time-dependent arrival function.
Maybe 20 lines of code:

    def arrival_rate(time):
        hour = (time // 60) % 24
        if 11 <= hour <= 14:  # Lunch rush
            return 2.0
        return 1.0

But I'd missed it because I was optimising for "elegant"
instead of "realistic."

Now I start every model with one question:

When does this system NOT behave normally?

The edge cases are where reality lives.

---

What assumptions have bitten you lately?
Hit reply - I read every response.

- H

P.S. Time-dependent arrivals are covered in Module 4 of
the Simulation Bootcamp, if you're curious: [link]
```

## Anti-Patterns

Things that make newsletters smell like AI:

- **Identical structure every time.** If every newsletter is hook-tip-code-lesson-CTA, readers (and spam filters) notice the pattern. Mix it up.
- **The manufactured sign-off question.** "What do you think? I'd love to hear your perspective!". this is generic. Either ask something specific or don't ask at all.
- **Perfectly parallel bullet points.** If you list three things, make them different lengths and structures. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md).
- **Subject lines that sound like copywriting formulas.** "The 3-step framework that transformed my...". nobody talks like this in real emails.
- **Always having a lesson.** Sometimes a story is just a story. Not everything needs a neat takeaway paragraph at the end.
- **Consistent sign-offs.** Vary between "Harry", "- H", "- Harry", just your name. Real people aren't consistent about this.

## Variations

### "Lesson learned" newsletter
```
[What happened]
[What I learned]
[How you can apply this]
```

### "Quick tips" newsletter
```
Three things I learned this week:

1. [Tip with brief explanation]

2. [Tip with brief explanation]

3. [Tip with brief explanation]

Which one's most useful for you?
```

### "Behind the scenes" newsletter
```
[What I'm working on]
[Why it matters]
[What's next]
[Invitation to follow along]
```

### "Just one thing" newsletter
```
[A single observation or tip. Three paragraphs max.
No CTA. No elaborate framing. Just the thing.]
```

### "Question" newsletter
```
[Context for the question, a paragraph or two]
[The actual question]
[Hit reply.]
```

## Voice notes
- Conversational, not formal
- Share genuine insights, not filler
- Stories from real projects (anonymised if needed)
- Okay to admit uncertainty or mistakes
- End with engagement prompt (question or reply invitation), but not every time
