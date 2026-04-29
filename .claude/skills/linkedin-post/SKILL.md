---
name: linkedin-post
description: Create LinkedIn posts. Use when asked to write a LinkedIn post, social media content, or professional social content about simulation, Python, SimPy, engineering, or related topics. Triggers on "linkedin", "post", "social media".
---

# LinkedIn Post Creator

Create engaging LinkedIn posts in Harry's witty, provocative British voice.

## Core Writing Engine

This skill uses `/copywrite` as its core writing engine. The copywrite skill handles:
- Voice and tone application
- Rhetorical device selection and integration
- British spelling and language patterns

This skill adds **LinkedIn-specific constraints** on top of that foundation.

## Before Writing

1. **Run the rhetoric selector** to get your rhetorical devices:
   ```bash
   uv run python .claude/skills/shared/rhetoric_selector.py --type linkedin_technical
   # or --type linkedin_provocative
   # or --type linkedin_personal
   ```

2. **Review the voice guide**: See [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md) (or use copywrite's built-in checklist)

3. **Check content pillars**: See [CONTENT_PILLARS.md](../shared/CONTENT_PILLARS.md)

4. **Read the anti-AI detection guide**: See [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) (this overrides the templates)

## Post Structure

### The Hook (First 2-3 lines)
- This is what shows before "...see more"
- Must stop the scroll
- Use a provocative statement, surprising fact, or bold claim
- Don't always open the same way, vary between statements, questions, numbers, mid-thought starts

### The Body
- Vary paragraph lengths, some short, some longer, not a uniform rhythm
- Include specifics: numbers, real examples, code snippets if relevant
- Build your argument or tell your story
- Not every sentence needs its own line. Sometimes running two or three together in a paragraph reads more naturally.

### The Closing
- End with a question, takeaway, or strong statement, vary which one you use
- Questions drive comments, but not every post needs one
- A strong declarative ending often lands harder than a question
- ONE CTA maximum (if any)

## Formatting Rules

- **Optimal length**: 1,000-1,300 characters
- **Maximum**: 3,000 characters (but shorter is usually better)
- **Line breaks**: Don't mechanically break after every 1-2 sentences. Vary it. Some paragraphs can be 3-4 sentences. Some can be one word.
- **Emojis**: Use sparingly if at all (max 1-2, and only if natural)
- **Hashtags**: 3-5 at the end, relevant to topic

### Hashtag suggestions
- #SimPy #Python #Simulation #DiscreteEventSimulation
- #Engineering #DataScience #OpenSource
- #ProcessImprovement #OperationsResearch

## Anti-AI Detection

**Read [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) before writing. Those rules override everything below.**

LinkedIn is more forgiving of polish than Reddit, but the patterns still get people called out. Here are the LinkedIn-specific traps:

### The "LinkedIn AI Post" fingerprint
- Hook line, then line break, then short paragraphs of 1-2 sentences each, then question at the end. This structure is fine *conceptually* but when every paragraph is the same length and every post ends with a question, it screams AI. Vary the execution.
- Don't always follow hook-body-CTA in that order. Sometimes start with the conclusion. Sometimes the hook IS the body. Sometimes skip the CTA entirely.

### Line break addiction
- The "short paragraphs with line breaks after every 1-2 sentences" pattern has become an AI fingerprint on LinkedIn specifically. Break it. Let some paragraphs breathe. Run a few sentences together. Not every thought needs its own line.

### The balanced take
- Your opinion should clearly lean one way. LinkedIn rewards conviction. A "both sides have merit" post reads as if a language model was trying not to offend anyone. Pick a side. Commit.

### The closing question trap
- Don't always end with a question. "What do you think?" and its variants are the most common AI tell on LinkedIn. Sometimes a strong declarative statement is a better ending. Sometimes just stopping is the best ending.

### Perfect parallel structures
- Three lines starting with the same word, each the same length, building to a crescendo, this is textbook AI rhetoric. If you're using repetition, break the pattern. Make one element longer, change the structure of one, or just cut it to two.

## Templates by Content Type

See templates folder:
- [Technical Tip](templates/technical-tip.md)
- [Industry Take](templates/industry-take.md)
- [Personal Story](templates/personal-story.md)

## Voice Reminders

From [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md):
- Witty and provocative, dry British humour
- Challenge conventional wisdom directly
- Share failures openly - they teach more than wins
- Use "I" not "we"
- British spellings (colour, optimise, modelling)

### Phrases that work
- "Look," (to start a provocative point)
- "Nobody talks about this, but..."
- "I was wrong about..."
- "Right, so." (casual lead-in)
- "Actually, no, wait." (self-correction)

### Avoid
- "Here's the thing..." (ChatGPT's favourite opener)
- "The uncomfortable truth is..." (AI signature phrase)
- "Excited to announce..."
- "Game-changer" / "Revolutionary"
- "Thought leader"
- Corporate jargon
- Everything on the banned list in [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)

## Example Posts

### Technical (with subtle tricolon and litotes)
```
SimPy queues tripped me up for months.

I kept thinking there was some deep simulation theory I was
missing. Some secret mechanism. Turns out a SimPy queue is
basically a Python list wearing a trench coat and pretending
to be sophisticated.

Once I stopped overthinking it and just learned three things.
Environment (your clock), Process (things that happen), and
Resource (things that get used up), the rest fell into place
embarrassingly fast.

The documentation isn't exactly a quick read. But it doesn't
need to be. Those three concepts are the foundation of every
model I've built for paying clients.

If you're struggling with SimPy, you probably know more
than you think you do.

#SimPy #Python #Simulation
```

### Provocative (with antithesis, anaphora broken up)
```
Last year, I paid £8,000 for simulation software.

This year, I paid £0.

Same models. Same results. The client couldn't tell the
difference, and honestly neither could I, once I got past
the sunk cost guilt.

You don't need Arena to model a queue. You probably don't
need Simul8 for that warehouse simulation either. And the
idea that you need FlexSim to optimise a production line is
mostly a story FlexSim's sales team tells.

Python. SimPy. Maybe two weeks of actual learning. That's
the real stack.

Most commercial simulation software exists to solve problems
Python solved years ago. The vendors just have better
marketing than the open-source community.

#SimPy #Python #OpenSource #Simulation
```

## Quality Checklist

Before posting, verify:
- [ ] AI detection pass: Could someone identify this as AI-written? If yes, rewrite.
- [ ] No banned phrases from [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)
- [ ] Structure isn't too neat . paragraph lengths vary, not every line break is after 1-2 sentences
- [ ] Hook stops the scroll (would YOU click "see more"?)
- [ ] Voice is authentically Harry (witty, direct, British)
- [ ] Rhetorical devices (if used) are invisible . reader shouldn't be able to identify them
- [ ] Specific examples or numbers included
- [ ] No corporate jargon
- [ ] Under 1,500 characters (ideally)
- [ ] CTA is soft and earned (if present)
- [ ] 3-5 relevant hashtags
