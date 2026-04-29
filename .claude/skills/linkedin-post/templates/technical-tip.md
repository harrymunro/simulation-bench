# Template: Technical Tip Post

## Best rhetoric devices
- **Tricolon** for listing steps or features (but make elements uneven lengths)
- **Asyndeton** for punchy instruction sequences
- **Litotes** for understated observations

## Approach. NOT a fill-in-the-blanks template

Do NOT follow this as a rigid structure. These are loose shapes a technical tip post can take. Pick one, then let the writing find its own shape. If the final post neatly maps back to one of these outlines, it's too structured.

### Shape 1: The "I struggled so you don't have to" post
Start with the confusion or the mistake. Spend time there, that's where the reader connects. The actual tip emerges from the story, almost as an aside. Don't label it "THE TIP" in your head or it'll read like a tutorial.

### Shape 2: The code-first post
Start with code or a specific technical detail. No hook, no setup, just drop them into the middle of something. Then zoom out to explain why it matters. This works when the tip is genuinely surprising and the code speaks for itself.

### Shape 3: The short one
One insight. Maybe four or five lines total. A sentence of context, the tip, a sentence of why it matters. Not everything needs to be a mini-essay. Some of the best technical LinkedIn posts are short enough that there's no "see more" fold at all.

## Example

```
yield env.all_of([event1, event2, event3])

That one line replaced about thirty lines of spaghetti in a
model I'd been fighting with for weeks. I had separate
processes, separate waits, separate timeouts, the kind of
code that makes you mass-close browser tabs when someone
asks for a screen share.

SimPy's AnyOf and AllOf let you yield multiple events at
once. The documentation mentions it, briefly, buried
somewhere around page 47. I found it by accident while
looking for something else entirely.

Three lines became one. Debugging went from "why is this
process stuck" to actually productive. Sometimes the best
features are the ones nobody bothers to mention in the
getting-started guide.

#SimPy #Python #Simulation #CodingTips
```

## Anti-patterns to avoid

These are the AI tells most common in technical tip posts:

- **The "Here's what nobody tells you" opener**: it's been done to death. If your post starts with a variation of "here's a secret," rewrite the opening.
- **Numbered steps with identical formatting**: `1. Do this thing. 2. Do this other thing. 3. Do this final thing.` each with the same sentence length. If you use steps, make them messy. One might need a paragraph of explanation. Another might be three words.
- **The neat before/after**: "Before: 30 lines of code. After: 3 lines of code. Result: 10x faster." This is real information delivered in an AI-shaped package. Embed the comparison in prose instead of displaying it symmetrically.
- **Starting with "Here's a SimPy trick..."**: functional but generic. Start with the code, start with the problem, start mid-frustration. Anything more specific than a label.
- **Ending with "What's your favourite [X]?"**: specific questions work ("Has anyone benchmarked FilterStore vs PriorityResource?") but generic engagement prompts don't. It's fine to just end.

## Voice notes for technical posts

- Teaching voice but still opinionated, you have views on the right way to do things
- Share real code, real numbers, real filenames if relevant
- Self-deprecation about past confusion is more relatable than expertise
- If you found something by accident, say so, it's more human than "I discovered"
- Technical posts can be funny. A dry observation about documentation quality or API design lands well.
