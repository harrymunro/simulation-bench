---
name: copywrite
description: Core writing engine. Automatically deploys rhetorical devices and voice styling for any copywriting task. Use for any writing request including website copy, ads, course descriptions, or general prose. Triggers on "write", "draft", "create content", "help me write", "copywrite".
---

# Copywrite - Core Writing Engine

The central writing skill for all content. Applies voice guidelines, rhetorical devices, and anti-AI detection rules to create copy that sounds like a real person wrote it.

## How This Skill Works

All writing flows through this skill. Format-specific skills (`/linkedin-post`, `/reddit-post`, `/marketing-email`) delegate their core writing to this engine while adding format constraints.

```
Any Writing Request
        ↓
  /copywrite skill
        ↓
  Voice + Rhetoric Selection
        ↓
  Anti-AI Detection Pass   ← NEW: mandatory
        ↓
  Format Detection/Application
        ↓
     Final Content
```

## Automatic Steps

When this skill is invoked:

### 1. Detect Content Type

Map the request to a rhetoric profile:

| Request Type | Rhetoric Profile | Output Location |
|--------------|------------------|-----------------|
| LinkedIn post | `linkedin_technical`, `linkedin_provocative`, or `linkedin_personal` | `posts/linkedin/` |
| Reddit post | `reddit_technical`, `reddit_discussion`, or `reddit_showcase` | `posts/reddit/` |
| Newsletter | `email_newsletter` | `posts/emails/newsletter/` |
| Launch email | `email_launch` | `posts/emails/launch/` |
| Nurture email | `email_nurture` | `posts/emails/nurture/` |
| Landing page | `website_landing` | `posts/general/website/` |
| Ad copy | `ad_copy` | `posts/general/ads/` |
| Course description | `course_description` | `posts/general/website/` |
| Proposal | `proposal_direct` | `posts/proposals/` |
| General prose | `generic` | `posts/general/misc/` |

### 2. Run Rhetoric Selector

```bash
uv run python .claude/skills/shared/rhetoric_selector.py --type {profile}
```

The selector returns 3 devices. **Use at most 1-2.** Pick whichever fits most naturally. Drop the rest. Forcing all 3 into a piece is an AI fingerprint.

### 3. Apply Voice Guide

Reference [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md) for tone and style.

**Voice characteristics:**
- Witty and provocative, dry British humour
- Challenge conventional wisdom directly
- Authentically vulnerable, share failures openly
- Direct, no corporate fluff
- Use "I" not "we"

**Language patterns:**
- Contractions always (I'd, won't, it's, that's)
- British spellings: colour, optimise, modelling, centre
- Sentence fragments are fine. So are one-word paragraphs.
- Start sentences with And, But, So
- Parenthetical asides (because that's how people think)
- Self-corrections: "actually no. More like..."

**Do not use these phrases** (they are now AI fingerprints):
- "Here's the thing..."
- "Let's dive in"
- "It's worth noting"
- "Curious what others think"
- "The uncomfortable truth is..."
- "At the end of the day"
- See full list in [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)

### 4. Apply Anti-AI Detection Rules

**This step is mandatory.** Read [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) before writing.

Key rules:
- **Break structural symmetry**: if you list 3 things, make them different lengths. Never format all bullet points identically.
- **Vary paragraph length wildly**: a one-sentence paragraph, then a five-sentence one, then two sentences. Never write 5 consecutive paragraphs of similar length.
- **Don't use headers as an essay outline**: not every section needs one. Use them inconsistently, like a real person.
- **Lean into your opinions**: don't balance every argument. Have a point of view and commit to it.
- **Allow imperfection**: tangents, trailing thoughts, self-corrections, register shifts. These are human.
- **Skip the manufactured closer**: not every piece needs a question at the end. Just stopping is fine.
- **TL;DRs are terse**: one lazy sentence, not a crafted summary.
- **Rhetorical devices must be invisible**: if a reader could identify the device, it's too heavy.

### 5. Write the Content

With the voice, devices, and anti-AI rules in mind, write the content.

Rhetorical devices are word-level and sentence-level tools. They should never determine the structure of a piece. Don't map devices to sections (hook = antithesis, body = anaphora, closing = chiasmus). That creates an obviously composed structure. Instead, let a device appear wherever it fits, or nowhere, if nothing fits naturally.

### 6. Save with Frontmatter

All content must be saved to a markdown file with YAML frontmatter:

```yaml
---
type: linkedin | reddit | newsletter | launch | nurture | proposal | website | ad | course | generic
status: draft | ready | published
created: YYYY-MM-DD
topic: Brief description
rhetorical_devices: [device1, device2]
content_profile: The rhetoric profile used
---
```

## Rhetoric Profiles

### Generic
Balanced profile for general prose. Good for: blog posts, documentation, general writing.

### Website Landing
Optimised for landing page copy. Favours: Tricolon (benefit lists), Antithesis (before/after), Asyndeton (urgency).

### Ad Copy
Short-form ads and promotional snippets. Favours: Antithesis (contrast), Asyndeton (speed), Tricolon (memorable lists).

### Course Description
Product and course descriptions. Favours: Tricolon (what you'll learn), Anaphora (building value), Anadiplosis (connecting benefits).

## Quality Checklist

Before finalising any content, verify:

- [ ] **AI detection pass**: Could you identify this as AI-written? If yes, rewrite. (See [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md))
- [ ] **Structure is messy enough**: Paragraph lengths vary, bullet points aren't uniform, headers aren't an essay outline
- [ ] **No banned phrases**: None of the AI-associated phrases from the banned list appear
- [ ] **Rhetoric is invisible**: You can't point to a device and name it
- [ ] **Voice is authentically Harry**: Witty, direct, British, opinionated
- [ ] **British spellings** used throughout
- [ ] **No corporate jargon** or hollow phrases
- [ ] **Specific examples or numbers** included where relevant
- [ ] **Content saved** to correct location with complete frontmatter
- [ ] **Read aloud**: Does it sound like a person talking, or like a well-composed essay?

## Integration with Format Skills

This skill provides the core writing engine. Format-specific skills add:

- **`/linkedin-post`**: Character limits, hashtags, hook visibility, post structure
- **`/reddit-post`**: Subreddit targeting, code formatting, self-promotion rules, Reddit markdown
- **`/article`**: Long-form structure, SEO elements, article types
- **`/marketing-email`**: Subject lines, CTAs, email types, preview text

When using those skills, the voice, rhetoric, and anti-AI work happens here; they add format constraints.

## Key Resources

- **Anti-AI detection**: [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) (READ THIS FIRST)
- Voice guide: [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md)
- Business context: [BUSINESS_CONTEXT.md](../shared/BUSINESS_CONTEXT.md)
- Content pillars: [CONTENT_PILLARS.md](../shared/CONTENT_PILLARS.md)
- Rhetorical devices: [RHETORICAL_DEVICES.md](../shared/RHETORICAL_DEVICES.md)
