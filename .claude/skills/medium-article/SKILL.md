---
name: medium-article
description: Create long-form Medium articles written entirely in prose. Medium articles are frequently consumed via audio (text-to-speech), so this skill produces flowing, narrative prose with no code blocks, no tables, no bullet lists, and no formatting that breaks when read aloud. Use this skill whenever the user mentions "Medium", "Medium article", "Medium post", "medium.com", or wants prose-only long-form content, an audio-friendly article, or a listicle-free essay. Also triggers on "write an essay", "long read", or "prose piece" when the context suggests Medium publishing.
---

# Medium Article Creator

Create long-form articles for Medium in Harry's witty, provocative British voice. Every article is written as continuous prose because Medium readers frequently listen to articles via text-to-speech. Content that relies on visual formatting (code blocks, tables, bullet points, numbered lists) falls apart in audio. Prose doesn't.

## Core Writing Engine

This skill uses `/copywrite` as its core writing engine. The copywrite skill handles voice, tone, rhetorical devices, and British spelling. This skill adds **Medium-specific constraints** on top of that foundation.

## The Prose-Only Rule

This is the defining constraint. Everything in the article must be written as flowing paragraphs. No exceptions.

**What this means in practice:**

Instead of a code snippet, describe what the code does and why it matters. Walk the reader through the logic in sentences. If you're explaining a function that takes a list of arrival times and returns average wait, say that. Describe the inputs, the transformation, the output. A reader listening on their commute can follow a well-described algorithm. They cannot follow `def calculate_wait(arrivals: list[float]) -> float:`.

Instead of a table comparing features, weave the comparison into your narrative. "Arena charges upwards of five thousand pounds for a single licence, while SimPy costs nothing. But price is only part of the story. Arena gives you a drag-and-drop interface that means you're building models within hours. SimPy asks you to write Python, which means a steeper first week but a dramatically more flexible second month." That paragraph replaces a three-column comparison table and works perfectly when read aloud.

Instead of a bulleted list of benefits, fold them into the flow. Don't stack five short phrases vertically when you can build them into a sentence or two that carries the reader forward.

Headers are the one structural element that survives audio. Text-to-speech engines typically pause before headers, giving them a natural section-break quality. Use them, but not as an outline. Use them when you'd naturally take a breath and shift direction.

## Before Writing

1. **Determine article type**:
   - **Technical** (concept explanation, methodology, how-something-works): Use `medium_technical` profile
   - **Story** (personal narrative, journey, lesson learned): Use `medium_story` profile
   - **Analysis** (industry opinion, trend analysis, prediction): Use `medium_analysis` profile

2. **Run the rhetoric selector**:
   ```bash
   uv run python .claude/skills/shared/rhetoric_selector.py --type medium_technical
   # or --type medium_story
   # or --type medium_analysis
   ```

3. **Review the voice guide**: See [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md)

4. **Check content pillars**: See [CONTENT_PILLARS.md](../shared/CONTENT_PILLARS.md)

5. **Read the anti-AI detection guide**: See [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) (this overrides everything)

## Medium Platform Specifics

**Length**: 1,500 to 3,000+ words. Medium displays an estimated reading time, and articles between seven and twelve minutes tend to perform best. That's roughly 1,800 to 3,000 words. Go longer if the topic earns it, shorter if it doesn't. Don't pad.

**Title**: Clear, specific, and interesting. Medium titles compete in feeds and email digests. Avoid clickbait formulas ("You Won't Believe...") but also avoid academic dryness. The best Medium titles make a promise the article delivers on, or state something surprising enough to earn a click.

**Subtitle**: Medium prominently displays a subtitle beneath the title. Use it to add context, qualify the title, or create a one-two punch. The subtitle should complement the title, not repeat it.

**Opening paragraph**: Medium shows the first few lines as a preview in feeds. The opening must hook on its own, without the body. Write it as if most people will read only this paragraph and decide whether to continue.

**Section breaks**: Use horizontal rules or headers to create breathing room. A wall of unbroken prose is intimidating even when the writing is good. But don't over-section a short piece. Let the content dictate the rhythm.

**Kicker/closing**: Medium readers who finish an article are the most likely to clap and follow. The ending should feel earned. Don't trail off. Either land on something memorable or circle back to the opening in a way that reframes it.

## Article Structure

Medium articles need to flow like spoken narrative. Think of how you'd explain something at a pub, in a long conversation with someone genuinely interested.

### Opening

The opening does one job: make the reader stay. On Medium, this matters more than most platforms because the feed preview shows your first sentences. If those sentences are a throat-clearing preamble about the state of the industry, nobody clicks through.

Start with a specific detail, a surprising number, a personal moment, or a bold claim. The opening might be one paragraph or four. It depends on the piece. What it must never be is an abstract introduction that could apply to any article on the topic.

### Body

This is where the prose-only constraint earns its keep. Without the crutch of code blocks and bullet lists, the body has to carry the reader through explanation, argument, or narrative using nothing but well-crafted sentences and paragraphs.

Vary paragraph length aggressively. A single-sentence paragraph followed by a long, winding paragraph followed by a two-sentence paragraph creates a rhythm that keeps listeners engaged. Uniform paragraph length is both an AI tell and an audio monotony trap.

Sections don't need to be equal length. If one section is the heart of the piece, give it room. If another section is a brief aside, let it be brief. The structure should reflect what matters, not impose artificial balance.

When explaining something technical, use analogies and concrete scenarios rather than abstract descriptions. Instead of describing how a priority queue works in the abstract, describe what happens when three ambulances arrive at a hospital and the triage nurse has to decide who gets seen first. The concept lands harder and survives the transition to audio intact.

### Closing

Add something the reader didn't expect: a personal confession, a caveat that undermines your own argument slightly, a twist that reframes the whole piece. Or just stop. A strong final sentence is better than a paragraph of summary.

Never summarise what the reader just read. They were there. On Medium specifically, a weak ending kills engagement metrics because readers who feel let down don't clap or share.

## Audio-Friendliness Checklist

Because Medium articles are so frequently listened to, apply these checks:

Read the piece aloud (or imagine doing so). Does every sentence make sense when heard rather than seen? If a sentence requires re-reading to parse, it needs rewriting, because listeners can't re-read.

Check for ambiguous pronoun references. "It" and "this" and "that" are fine in written prose because the reader can glance back. In audio, they can cause confusion. When in doubt, repeat the noun.

Avoid dense parenthetical asides that interrupt the main sentence for too long. A short parenthetical works fine when spoken. A parenthetical that runs for fifteen words derails the listener's sense of where the sentence was going. (Short ones like this are fine.)

Numbers and statistics should be rounded and contextualised. "Roughly three thousand pounds a year" is better than "£2,847 annually" for audio. The precise number adds nothing when you can't see it.

Transitions between sections should be smooth enough that a listener doesn't lose their place. If two sections are about very different things, the first sentence of the new section should gently signal the shift rather than assuming the reader saw the header.

## Anti-AI Detection

**Read [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) before writing. Its rules override everything here.**

Medium is a high-scrutiny platform for AI detection. Readers and editors actively look for AI-generated content. The prose-only format actually helps here because AI-generated articles tend to lean on lists and structured formatting. But AI patterns still show up in prose:

**The essay-shaped article**: Introduction with thesis, three body sections of equal weight, conclusion that restates the thesis. This is the most common AI structure in long-form content. Real articles meander, go deep on one point and skim another, include tangents that are interesting but not strictly necessary.

**Uniformly smooth prose**: Every paragraph transitions neatly into the next. Every sentence is the same register. No rough edges, no sudden shifts in tone. Real prose has texture. A paragraph of careful analysis followed by "Anyway, the point is..." followed by a paragraph of personal anecdote. That's human.

**Hedged everything**: "It could be argued that", "One might suggest", "It's worth considering". AI hedges constantly. Have opinions. State them. Hedge only when you genuinely aren't sure, and say so plainly: "I don't know if this is right."

**The inspirational close**: Medium AI articles almost always end with an uplifting, forward-looking final paragraph. "The future is bright for those who..." Just stop when the piece is done.

## Templates

See templates folder for loose guidance on approaches:
- [Medium Technical Prose](templates/medium-technical-prose.md) - Explaining concepts, methods, how things work
- [Medium Narrative](templates/medium-narrative.md) - Personal stories, journeys, lessons
- [Medium Analysis](templates/medium-analysis.md) - Industry opinion, trends, predictions

## Voice Reminders

From [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md):
- Witty and provocative, dry British humour
- Challenge conventional wisdom directly
- Share failures openly
- Use "I" not "we"
- British spellings (colour, optimise, modelling)

### Phrases that work in Medium prose
- Self-corrections mid-paragraph: "It took about a week. Actually, closer to three weeks once I stopped lying to myself about it."
- Honest asides: "I should mention that I had no idea what I was doing at this point."
- Register shifts: from careful technical explanation to "Look, the maths isn't the hard part."
- Conversational connectors: "So here's the thing I didn't expect." (but don't overuse "here's the thing")

### Avoid
- "In this article, I will..."
- "Let's dive in"
- "Here's the thing about..."
- "The uncomfortable truth is..."
- Any phrase on the banned list in [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)
- Em dashes (use periods, commas, or restructure)
- Code blocks, tables, bullet points, numbered lists

## Frontmatter Format

All Medium articles must include:

```yaml
---
type: article
subtype: medium-technical | medium-story | medium-analysis
platform: medium
status: draft | ready | published
created: YYYY-MM-DD
topic: Brief description
subtitle: Medium subtitle text
reading_time_minutes: estimated reading time
rhetorical_devices: [device1, device2]
content_profile: medium_technical | medium_story | medium_analysis
---
```

## Output Location

Save to: `posts/articles/medium/{topic-slug}.md`

## Quality Checklist

Before publishing, verify:

- [ ] **Prose-only**: Zero code blocks, zero tables, zero bullet lists, zero numbered lists
- [ ] **Audio test**: Read aloud. Every sentence makes sense when heard, not just seen
- [ ] **AI detection pass**: Could you identify this as AI-written? Rewrite if yes
- [ ] **No banned phrases** from ANTI_AI_DETECTION.md
- [ ] **Structure has asymmetry**: Sections are different lengths, tangents exist, it's not a perfect outline
- [ ] **Hook works in preview**: First paragraph stands alone as a feed preview
- [ ] **Subtitle complements title**: Not a repetition, adds context or punch
- [ ] **Voice is authentically Harry**: Witty, direct, British, opinionated
- [ ] **Rhetorical devices are invisible**: If you can spot them, they're too heavy
- [ ] **Concrete examples**: Real scenarios, real numbers, real stories (described in prose)
- [ ] **British spellings** used consistently
- [ ] **No corporate jargon** or hollow phrases
- [ ] **Closing earns its place**: Adds something new or stops cleanly
- [ ] **Paragraph length varies**: Not all the same size
- [ ] **Transitions work for listeners**: Section shifts are signalled in prose, not just by headers
- [ ] **Saved to correct location** with complete frontmatter
- [ ] **Run the AI writing checker**: `uv run python .claude/skills/shared/scripts/ai_writing_checker.py <file_path>` — target score: 0

## Example Opening

The following is one example of how a Medium article might begin. It is not a formula.

```markdown
I spent six months building a simulation model in Arena. The client loved it.
Then they asked me to change one thing, a single routing rule, and I spent
two more weeks untangling the spaghetti of drag-and-drop logic I'd created
to find where that rule lived.

That was the project that made me learn Python.

Not because Python is perfect. It isn't. The learning curve is real, and
the first month felt like I'd traded a comfortable prison for a terrifying
wilderness. But somewhere around week six, something clicked. I could read
my own model. Not interpret a visual flowchart that kind of represented my
model if I squinted. Actually read it, line by line, and understand exactly
what was happening and why.

I want to explain what that shift felt like, because I think it matters
more than any technical comparison I could give you.
```

Notice: no code shown, even though the topic is programming. The experience of coding is described in prose. The reader (or listener) follows the story without needing to see a screen. The second paragraph is a single sentence. The third is long. The fourth is short again. That rhythm is deliberate.
