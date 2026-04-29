# Template: Blog Thought Piece

For opinion articles, industry analysis, predictions, and contrarian takes.

**Do NOT follow this as a fill-in-the-blanks template.** Thought pieces are the highest risk for AI detection. The balanced-argument essay structure ("here's what people think, here's why they're wrong, here's the counterargument I'll graciously acknowledge, here's my conclusion") is the most recognisable AI pattern in long-form content. These are loose approaches. Your piece should feel like someone with strong opinions sat down and wrote what they think.

## Best rhetoric devices

- **Antithesis** for contrasting conventional wisdom vs reality
- **Chiasmus** for memorable, quotable conclusions

Use at most 1-2. They must be invisible. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md). Thought pieces are where rhetorical devices are most likely to get spotted, because the writing is already more stylised. Less is more.

## Approaches

The through-line: **have a strong opinion and don't apologise for it.** Real thought pieces are unbalanced. They lean into one side. They spend five paragraphs on the argument and one sentence on the counterargument, or they don't address the counterargument at all. The reader is here for your take, not a Wikipedia summary of both sides.

### Approach 1: The opinion with receipts

You believe something. You have evidence, personal experience, data, specific examples. Write it. Start with the opinion, then back it up. Don't build to your thesis like an essay, state it, then prove it. Go on tangents when they're interesting. Acknowledge where you might be wrong, but don't give the opposing view equal treatment. You're not a judge, you're an essayist.

This works well for: contrarian takes, "X is overrated/underrated", industry critique.

### Approach 2: The thing that happened and what it means

Something happened, to you, in the industry, in a project. You're going to tell the reader about it and then explain why it matters more broadly. The narrative carries the piece. The opinion emerges from the story rather than being stated upfront. This is lower risk for AI detection because narrative structure is harder to fake.

This works well for: personal experience pieces, "what I learned from X", industry event responses.

### Approach 3: The prediction or analysis

You've noticed something, a trend, a pattern, a shift. You're going to describe what you see and where you think it's going. Be specific about your prediction. Be honest about your uncertainty. Include what would prove you wrong. This is where the "I might be wrong" isn't a polite hedge, it's genuinely interesting to explore the failure mode of your own argument.

This works well for: industry predictions, trend analysis, "the future of X" pieces.

## Anti-patterns

- **The balanced essay**: This is the big one. AI writes "on one hand... on the other hand" pieces where every claim gets a caveat. Real people with opinions lean into them. If you're writing a thought piece, you should spend at least 3x more words on your position than on the counterargument.
- **Steel-manning before you've even argued**: Don't open with "let's be fair to the other side." You haven't made your case yet. Make it first. Acknowledge the counterargument later, briefly, if at all.
- **The tidy thesis statement**: "In this piece, I'll argue that X" is an essay, not a blog post. Just start arguing.
- **Symmetric structure**: "The Conventional Wisdom" -> "Why I Disagree" -> "The Evidence" -> "The Counterargument" -> "What This Means" is an AI outline. Real thought pieces don't have this symmetry. One section might be huge, another might be two sentences.
- **Hedging everything**: "I think" / "perhaps" / "it could be argued" sprinkled everywhere. Pick your moments to hedge. The rest of the time, just say what you mean.
- **The manufactured uncertainty close**: "Only time will tell" or "The truth probably lies somewhere in the middle." If you wrote a thought piece to conclude with "it's complicated," you wasted everyone's time.

## Example

```markdown
# Stop Teaching Simulation Theory First

Every simulation course I've seen makes the same mistake.

They start with theory. Queuing formulas. Probability distributions.
Markov chains. Weeks of mathematics before anyone writes a line of code.

I taught this way for years. I was wrong.

---

## The thing about theory-first

Universities love it because it feels rigorous. It mirrors how physics
is taught, how maths is taught, how engineering is taught. And I get
the logic, you need foundations before you build.

Except in simulation, the foundations aren't the theory. The foundations
are seeing a model run and thinking "huh, that's not what I expected."

---

## What actually happens

Students who struggled with probability distributions, genuinely smart
students, engineers with years of experience, would come alive the
moment you showed them code. A queue isn't complicated when you can
print() what's happening at each step. An exponential distribution
makes sense when you can plot 10,000 samples and see the shape.

The abstraction was the barrier. Not the concept.

(I suspect this is true for a lot of engineering education, but that's
a rant for another day.)

---

## I ran a loose experiment

Not a proper study. I don't have ethics board approval or a control
group or any of the things that would make this publishable. But I
had two cohorts, one semester apart. First cohort: theory first.
Second cohort: code first, theory when they asked for it.

The second cohort built better models. Not marginally, noticeably.
And nobody dropped out in week two, which had been a persistent
problem.

---

## The objection I hear constantly

"But they need the fundamentals."

Yes. Eventually.

But timing matters. Theory after you've built something gives you a
framework to hang knowledge on. Theory before you've built something
gives you a framework for... what, exactly? You're memorising
relationships between concepts you've never seen in action.

---

## What I do now

Code first. Break things. Fix things. Introduce theory when someone
asks "why does this work?"

The questions come naturally. The theory clicks faster. And I've
stopped losing students before they build anything.

If you're teaching simulation, or learning it, try flipping the
order. The theory will make more sense when you need it.
```

Note how this example doesn't give balanced treatment. The "theory first" position gets acknowledged briefly but the piece clearly leans toward one side. The "experiment" is described honestly as imperfect. The piece includes a parenthetical tangent. The ending doesn't summarise, it just makes a suggestion and stops.

## Variations

These are starting points. Deviate.

### Contrarian take

Lead with the belief you're challenging. Then explain why you disagree. You can acknowledge where the conventional wisdom is right, but only after you've made your case, and briefly. End with genuine uncertainty if you feel it, or with conviction if you don't. "I might be wrong about this" is fine when it's honest. It's not fine as a polite formula.

### Industry analysis

Start with what you've noticed. Describe the pattern. Explain where you think it's going. Be specific, name companies, tools, trends. Vague industry analysis ("the landscape is shifting") is useless and reads as AI. If you're going to analyse, analyse something concrete.

### Prediction

Make the prediction early. Then spend the piece supporting it. Include what would prove you wrong, this is the interesting part. If your prediction turns out to be wrong, what does that tell us? End with what to do regardless of whether you're right.

## Persuasion Checklist

- [ ] Your position is clear and stated early (not built to like an essay)
- [ ] The piece is unbalanced . your argument gets significantly more space than the counterargument
- [ ] Personal experience or specific examples are included (not just abstract reasoning)
- [ ] Tangents or asides exist . it's not a perfectly structured argument
- [ ] Tone is confident but admits genuine uncertainty where it exists
- [ ] Ending adds something or just stops . it doesn't summarise
- [ ] Could NOT be outlined as "Thesis -> Arguments -> Counterargument -> Conclusion"
