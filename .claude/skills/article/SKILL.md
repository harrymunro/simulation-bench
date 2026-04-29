---
name: article
description: Create long-form articles (blog posts and LinkedIn articles). Use when asked to write articles, blog posts, tutorials, deep-dives, thought pieces, or long-form content. Triggers on "article", "blog post", "blog", "tutorial", "deep-dive", "thought piece", "long-form".
---

# Article Creator

Create long-form articles in Harry's witty, provocative British voice. Covers blog articles (technical tutorials, thought pieces) and LinkedIn articles.

## Core Writing Engine

This skill uses `/copywrite` as its core writing engine. The copywrite skill handles:
- Voice and tone application
- Rhetorical device selection and integration
- British spelling and language patterns

This skill adds **article-specific constraints** on top of that foundation.

## Before Writing

1. **Determine article type**:
   - **Technical** (tutorial, deep-dive, comparison): Use `article_technical` profile
   - **Thought piece** (opinion, industry analysis, prediction): Use `article_thought` profile
   - **LinkedIn article**: Use `article_linkedin` profile

2. **Run the rhetoric selector**:
   ```bash
   uv run python .claude/skills/shared/rhetoric_selector.py --type article_technical
   # or --type article_thought
   # or --type article_linkedin
   ```

3. **Review the voice guide**: See [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md)

4. **Check content pillars**: See [CONTENT_PILLARS.md](../shared/CONTENT_PILLARS.md)

5. **Read the anti-AI detection guide**: See [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) (this overrides templates)

## Article Types

### Blog Articles

**Length**: 800-2000+ words depending on topic depth

**SEO Elements** (for blog posts):
- **Title**: Clear, benefit-driven, include primary keyword
- **Meta description**: 150-160 characters, compelling summary
- **Headers**: Use H2/H3 hierarchy, include keywords naturally
- **Internal links**: Link to related content where relevant

**Output location**: `posts/articles/blog/{topic-slug}.md`

### LinkedIn Articles

**Length**: 800-1500 words (shorter than blog, optimised for platform)

**Platform considerations**:
- No SEO metadata needed
- Stronger hook required (competing with feed)
- More personal, conversational tone
- End with engagement prompt

**Output location**: `posts/articles/linkedin/{topic-slug}.md`

## Article Structure

Articles need a beginning, a middle, and an end. That's it. Don't follow percentage rules or rigid formulas.

### Opening

Start with something that earns the next sentence. A bold claim, a specific detail, something personal, a number that surprises. Don't write a three-part opening sequence of hook-context-promise, just get the reader's attention and make them want to continue.

The opening might be one sentence. It might be three paragraphs. It depends on the piece.

### Body

The middle of the article carries the argument, the story, the technical content, whatever the piece is actually about.

- **Break content into sections**: but the sections don't need to be uniform or follow a perfect outline
- **Concrete examples**: Real code, real numbers, real stories, these are what make articles worth reading
- **Sections can overlap**: revisiting an earlier point with new context is fine
- **Tangents are allowed**: if something interesting comes up, follow it for a paragraph before coming back
- **Go deep where it matters**: not every section needs equal weight. Some points deserve three paragraphs, others deserve one sentence
- **Don't force progressive build**: real arguments circle back, jump ahead, and sometimes contradict what you said two sections ago before resolving

### Closing

Either add something new (a twist, a caveat, a personal admission) or just stop. Don't summarise by restating the same points from the body, the reader just read them. A call to action is fine if it's earned, but not every piece needs one.

## Anti-AI Detection

**Read [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) before writing. Its rules override templates.**

Articles are the most forgiving format for structure, people expect headers, sections, and some organisation in long-form writing. But AI patterns still show up in specific ways:

- **Formulaic structure**: Real articles don't follow percentage breakdowns. The opening might be one line or half a page. The closing might be a single sentence. Don't plan an article like an essay outline.
- **Descriptive headers that form a perfect outline**: "Challenges Encountered" → "Solutions Implemented" → "Results Achieved" is AI structure. Real headers are inconsistent. "The bit where everything fell apart" next to "Performance results" next to a header that's actually a question.
- **No tangents or asides**: Real blog writing wanders. A parenthetical aside, a half-related anecdote, a "this reminds me of" moment, these are what make articles feel human. If every paragraph directly serves the thesis, it reads as generated.
- **Restating points in the conclusion**: Don't summarise the article at the end. The reader was there. Either add something new or just stop writing.
- **Narratively convenient anecdotes**: Personal stories should feel like they actually happened to you, not like they were constructed to perfectly illustrate the point. Real anecdotes have irrelevant details, don't land perfectly, and sometimes only sort of support what you're saying.

## Templates

See templates folder for loose guidance and approaches:
- [Blog Technical](templates/blog-technical.md) - Tutorials, deep-dives, comparisons
- [Blog Thought Piece](templates/blog-thought-piece.md) - Opinion, analysis, predictions
- [LinkedIn Article](templates/linkedin-article.md) - Long-form LinkedIn content

## Voice Reminders

From [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md):
- Witty and provocative, dry British humour
- Challenge conventional wisdom directly
- Share failures openly - they teach more than wins
- Use "I" not "we"
- British spellings (colour, optimise, modelling)

### Phrases that work in articles
- "Let me tell you what actually happened..."
- "I used to believe... Then I learned..."
- Self-corrections: "It took about 30 seconds. Actually no, more like a minute once I added the edge cases"
- Parenthetical asides: (because of course it did)
- Mid-thought register shifts: going from technical to "anyway, the point is"

### Avoid
- "In this article, I will..."
- "As we all know..."
- "It goes without saying..."
- "Here's the thing about..."
- "The uncomfortable truth is..."
- "Everyone says X. They're wrong."
- Corporate jargon and hollow phrases
- Any phrase on the banned list in [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)

## Frontmatter Format

All articles must include:

```yaml
---
type: article
subtype: blog-technical | blog-thought | linkedin
status: draft | ready | published
created: YYYY-MM-DD
topic: Brief description
meta_description: 150-160 char summary (blog only)
rhetorical_devices: [device1, device2]
content_profile: article_technical | article_thought | article_linkedin
---
```

## Quality Checklist

Before publishing, verify:

- [ ] AI detection pass: Could you identify this as AI-written? Rewrite if yes.
- [ ] No banned phrases from ANTI_AI_DETECTION.md
- [ ] Structure has tangents or asides . it's not a perfect essay outline
- [ ] Hook grabs attention in first 2-3 sentences
- [ ] Voice is authentically Harry (witty, direct, British)
- [ ] Rhetorical devices (if any) are invisible
- [ ] Concrete examples included (code, numbers, stories)
- [ ] British spellings used consistently
- [ ] No corporate jargon or hollow phrases
- [ ] CTA is relevant and earned (if included at all)
- [ ] Read aloud . does it sound like a person talking at a pub, or presenting at a conference?
- [ ] Meta description compelling (blog posts only)
- [ ] Saved to correct location with complete frontmatter

## Example Opening

```markdown
I spent £8,000 on simulation software last year.

This year? £0.

The models are better. The clients are happier. And I've stopped
dreading licence renewal season.
```

Note: This is one example, not a formula. The specific pattern of £X-then-£0 antithesis is effective but overused. Your opening might be a question, an anecdote, a single provocative sentence, or three paragraphs of context. Match the opening to the piece, not to a template.
