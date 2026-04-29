# Template: Blog Technical Article

For tutorials, deep-dives, how-to guides, and technical comparisons.

**Do NOT follow this as a fill-in-the-blanks template.** These are loose approaches and examples. Pick elements that fit, ignore what doesn't, and let the piece find its own shape. If your article looks like any of the structures below with the brackets filled in, you've done it wrong.

## Best rhetoric devices

- **Tricolon** for listing steps, features, or concepts
- **Asyndeton** for punchy instruction sequences
- **Anaphora** for emphasising repeated patterns or steps

Use at most 1-2. They must be invisible. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md).

## Approaches

Technical blog posts can be more structured than thought pieces, readers expect sections, steps, and code blocks. But the structure should emerge from the content, not from an outline you wrote before you started.

The key: **mix narrative with technical content**. Tell the story of solving the problem while teaching. "I tried X, it broke because Y, so I did Z" is more engaging than "Step 1: Do X. Step 2: Do Y."

### Approach 1: The problem-solving narrative

Write it as a story. You had a problem, you tried things, some failed, you eventually figured it out. Weave the technical teaching into the narrative. Sections don't need to be labelled "Step 1". they can be "The first thing I tried" or "Where it all went wrong" or just a header that describes what you're about to show.

This works well for: debugging stories, performance optimisation, migration guides, "how I built X" posts.

### Approach 2: The reference with personality

Sometimes people just need the information, how to set up X, how to use Y, what Z does. That's fine. Write a reference. But inject personality into the explanations, add warnings from experience, note the gotchas you actually hit. Headers can be more descriptive here, but don't make them form a perfect essay outline.

This works well for: setup guides, API explanations, "how to do X in SimPy" posts.

### Approach 3: The comparison that picks a side

Don't write balanced comparisons where everything gets equal treatment. You have an opinion. Lead with it. Explain both options, but make it clear which one you'd pick and why. Spend more time on the one you prefer. Be honest about where your pick falls short, that builds more credibility than fake balance.

This works well for: X vs Y posts, tool comparisons, "should you use X?" posts.

## Anti-patterns

- **Headers that form a perfect essay outline**: "Introduction" -> "The Problem" -> "The Solution" -> "Conclusion" is AI structure. Mix descriptive headers with quirky ones. Skip headers entirely for some sections if they're short.
- **Uniform section lengths**: If every section is 3-4 paragraphs, it reads as generated. Some sections should be one sentence. Others should be long.
- **Step-by-step without story**: "Step 1... Step 2... Step 3..." with no narrative, no false starts, no "actually wait, do this first". that's a recipe, not an article.
- **The perfect before/after**: AI loves symmetric before/after comparisons with matching bullet points. Real before/after is messy, you improved three things and made one thing slightly worse, or the numbers are better but setup is more annoying now.
- **Explaining things the audience already knows**: If you're writing for SimPy users, don't explain what SimPy is. Technical audiences smell padding instantly.

## Example

```markdown
# How I Cut My SimPy Model Runtime by 80%

Last week, my simulation took 47 minutes to run.

Today it does the same thing in 9. I didn't buy faster hardware. I didn't
rewrite the hot loops in C (though I thought about it, briefly, at 2am
on a Tuesday). I just stopped making three mistakes.

The annoying part? They were all obvious in hindsight.

---

## The resource creation thing

I was creating `simpy.Resource` objects inside my process functions.
Every time a customer arrived, new resource. Sounds reasonable.
it wasn't.

[Code example showing the problem]

[Code example showing the fix]

The fix took about four minutes. The speedup was 3x. I wish I could
say I found it through careful profiling, but actually my colleague
looked at the code and said "why are you doing that?"

---

## Queues (or: why Python lists will betray you)

This one I did find through profiling, at least.

[Technical explanation with code]

I should mention, this only matters if your queues get long. If
your simulation has queues of 5-10 items, you won't notice. Mine
had queues of 50,000+ because I was modelling a distribution centre
on Black Friday. At that scale, the difference between a list and
a deque is the difference between lunch and dinner.

---

## The obvious one I should have done from the start

[Explanation about not running full simulations during development]

---

## So where did that leave me?

Runtime went from 47 to 9 minutes. Memory dropped too, from about
2.3GB to 400MB, though I'm less sure how much of that was the
resource fix and how much was the queue fix.

The patience improvement is harder to quantify but it's real.

I'd bet at least one of these applies to your models. Try the
resource one first, it's the quickest fix and usually has the
biggest impact.
```

Note how the example mixes technical content with narrative, uses inconsistent header styles, includes a tangent about the colleague, and doesn't end with a tidy summary of all three points.

## Variations

These are starting points, not structures to fill in. Deviate freely.

### Tutorial-ish

Start with what you'll build, then tell the story of building it. Include false starts and wrong turns, a tutorial where everything works first time doesn't teach debugging. Put the complete working code at the end, but don't just list steps to get there. You can use numbered steps for the actual "type this" parts, but wrap them in narrative.

### Comparison

Pick your winner early. Don't maintain suspense about which option is better, the reader came for your opinion. Be generous to the option you don't prefer (acknowledge where it wins) but be clear about your recommendation. Spend more words on the one you recommend.

### Deep-dive

Start with why anyone should care about this concept, then go as deep as needed. You can start simple and go deeper, but you can also start with the confusing bit and work backwards to the explanation. Include the misconceptions you personally held, not just generic "common misconceptions."

## SEO Checklist

- [ ] Primary keyword in title
- [ ] Primary keyword in first 100 words
- [ ] Keywords in at least 2 H2 headers
- [ ] Meta description includes primary keyword
- [ ] Meta description is 150-160 characters
- [ ] Alt text for any images
- [ ] Internal links to related content
