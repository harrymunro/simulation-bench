# Template: Medium Analysis

For industry opinion, trend analysis, predictions, and contrarian takes. Written entirely in prose. No code, no tables, no lists.

**Do NOT follow this as a fill-in-the-blanks template.** Analysis pieces on Medium should read like a smart person thinking through a problem in public. Not a report, not a whitepaper, not a balanced survey. You have a point of view. State it. Back it up. Admit where you're uncertain.

## Why analysis works as prose

Analysis pieces are the ones most likely to default to structured formatting: comparison tables, pro/con lists, feature matrices. Resist this completely. When you're forced to describe comparisons and trade-offs in prose, you're forced to think about them more carefully. You can't hide behind a tidy grid. You have to actually argue for your position, which produces better analysis.

For listeners, this is especially important. An analysis delivered as prose sounds like an informed opinion. An analysis delivered as a table sounds like nothing at all, because the text-to-speech engine will butcher it.

## Best rhetoric devices

- **Antithesis** for contrasting what people believe with what's actually true
- **Anaphora** for building a persuasive cadence when making your case

Use at most 1-2. They must be invisible. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md).

## Approaches

### Approach 1: The opinion with evidence

You think something is true about the simulation industry, about Python, about how engineers learn, about commercial software pricing. State it plainly in the first few paragraphs. Then spend the rest of the article backing it up with specific experiences, data points, conversations, and observed patterns.

Don't save your opinion for the end. Don't build toward it like a legal argument. Put it out there and then defend it. Readers who disagree will keep reading to see if you can change their mind. Readers who agree will keep reading because it feels good to have your position articulated well.

This works well for: industry critique, contrarian takes, "everyone is doing X wrong" pieces.

### Approach 2: The pattern described

You've noticed something happening across your clients, your students, the industry. You're going to describe the pattern and explain what you think it means. This is less opinionated than Approach 1. You're more of a reporter here, albeit one with strong observational instincts.

The key is specificity. "The industry is changing" means nothing. "Three of my clients this year have abandoned their Arena licences and two more are thinking about it" is a pattern worth discussing. Name the pattern, describe the evidence, speculate on causes, and say what you think happens next.

This works well for: trend analysis, market observations, "what I'm seeing" pieces.

### Approach 3: The prediction with stakes

You're going to predict something. Make it specific enough that you could be proven wrong. "AI will change simulation" is unfalsifiable. "Within two years, the major commercial simulation vendors will offer AI-assisted model building, and it will be mediocre" is a prediction with teeth.

Spend most of the article explaining why you believe this. Include what would prove you wrong, not as a polite disclaimer, but as a genuine exploration of the alternative. If your prediction is wrong, what does that tell us about the world? That question is often more interesting than the prediction itself.

This works well for: industry predictions, technology forecasts, "where this is heading" pieces.

## Anti-patterns

- **The balanced assessment**: Giving equal weight to all sides. If you're writing analysis, you have a view. The piece should be obviously weighted toward your position. Acknowledging counterarguments is fine. Treating them as equally valid is not analysis, it's a Wikipedia article.
- **The framework introduced**: "I use a three-part framework for evaluating..." This screams AI and also screams consultant. If you have a way of thinking about something, weave it into your analysis. Don't name it and present it as a framework.
- **Vague industry commentary**: "The landscape is shifting" or "disruption is accelerating." These mean nothing. Every sentence in an analysis piece should contain either a specific observation or a specific claim. If you can't point to evidence, don't make the claim.
- **The safe prediction**: Predicting something that's already happening or that everyone agrees on is not interesting. Good predictions are the ones where you could be embarrassingly wrong. That's what makes them worth reading.
- **The symmetric structure**: Three trends, each with a paragraph of description and a paragraph of analysis, followed by a conclusion that ties them together. This is AI's favourite analysis format. Real analysis is messy. One trend might get five paragraphs because it's complicated. Another might get two sentences because it's simple but important.

## Example

```markdown
# Commercial Simulation Software Has a Pricing Problem It Can't Solve

Arena, Simul8, FlexSim, and AnyLogic all charge thousands of pounds per
year for a single licence. Some of them charge tens of thousands. This
has been true for decades, and for most of those decades it was fine
because there was no serious alternative.

There is now, and the vendors know it. What I don't think they've figured
out is that they can't solve this with pricing alone.

I've watched three clients leave commercial software for Python and
SimPy in the past eighteen months. In each case, the conversation
followed the same pattern. The licence renewal email arrived. Someone
with budget authority asked, for the first time in years, whether they
actually needed to renew. Someone else mentioned that they'd heard you
could do simulation in Python. A few weeks later, I got a phone call.

The interesting thing is that none of these clients left because of
features. SimPy doesn't have a visual editor. It doesn't have built-in
animation. It doesn't have a library of pre-built components. By any
feature comparison, the commercial tools win. They left because of
money and control.

Money is obvious. When you're paying five or eight thousand pounds a
year and someone shows you a free alternative that does eighty percent
of what you need, the conversation becomes "is that remaining twenty
percent worth five thousand pounds?" For a lot of teams, the honest
answer is no.

Control is subtler but, I think, more important in the long run. When
your simulation model lives in a proprietary format that only one
vendor's software can open, you're locked in. You can't share models
freely. You can't version-control them properly. You can't extend them
with custom code without hitting the limits of whatever scripting
language the vendor bolted on as an afterthought. With Python, the
model is just code. You own it completely.

The vendors could drop their prices. Some of them probably will. But
the control problem doesn't have a pricing solution. You can't sell
freedom as a feature of a proprietary product. That's the contradiction
they're stuck with, and I genuinely don't know how they resolve it.

Maybe they don't need to. There are plenty of organisations that
will always prefer a graphical, supported, enterprise-grade tool
over writing code. That market is real and probably stable. But it's
shrinking, and the people leaving it aren't coming back.
```

Notice: the piece has a clear opinion stated early. The evidence is specific (three clients, eighteen months, the exact conversation pattern). The ending doesn't resolve neatly. It acknowledges a counterargument (some orgs will always prefer commercial tools) without treating it as equally important. The final sentence is confident but not grandiose.

## Variations

### The industry autopsy

Something failed, or is failing, or is about to fail. Examine why. Be specific about the causes and honest about whether you saw it coming. Don't write from hindsight as if you always knew. If you were surprised, say so. That's more interesting.

### The uncomfortable comparison

Compare two things that aren't usually compared. "Simulation licensing works exactly like gym memberships" or "Teaching engineers Python feels like teaching my kids to ride bikes." The unexpected comparison forces fresh thinking and is inherently engaging as audio because listeners want to see if the comparison holds up.

### The "what nobody says"

There's something everyone in the industry knows but nobody writes about. Price gouging. The fact that most simulation models never get used. The dirty secret that half the time a spreadsheet would have been fine. Writing about unspoken truths is the most reliable way to get engagement on Medium because readers feel like they're being let in on something.
