---
name: marketing-email
description: Create marketing emails and newsletters. Use when asked to write emails, newsletters, launch announcements, email sequences, nurture emails, or promotional content for email. Triggers on "email", "newsletter", "email sequence", "nurture".
---

# Marketing Email Creator

Create compelling marketing emails in Harry's authentic, witty voice.

## Core Writing Engine

This skill uses `/copywrite` as its core writing engine. The copywrite skill handles:
- Voice and tone application
- Rhetorical device selection and integration
- British spelling and language patterns

This skill adds **email-specific guidance** on top of that foundation: subject lines, CTAs, preview text, and email type structures.

## Before Writing

1. **Identify the email type**:
   - Newsletter (regular value delivery)
   - Launch announcement (course/product promotion)
   - Nurture sequence (relationship building)

2. **Run the rhetoric selector**:
   ```bash
   uv run python .claude/skills/shared/rhetoric_selector.py --type email_newsletter
   # or --type email_launch
   # or --type email_nurture
   ```

3. **Review context** (or use copywrite's built-in checklist):
   - [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md)
   - [BUSINESS_CONTEXT.md](../shared/BUSINESS_CONTEXT.md)
   - [CONTENT_PILLARS.md](../shared/CONTENT_PILLARS.md)

## Email Anatomy

### Subject Line
- 4-7 words ideal
- Create curiosity or promise value
- Avoid spam triggers (FREE, URGENT, !!!)
- Test with: "Would I open this?"

**Warning**: The "subject line formulas" below are also AI's favourite patterns. AI-generated subject lines have recognisable tells, the curiosity-gap formula ("The thing nobody tells you about X"), the numbered benefit ("How to achieve X in Y"), the dramatic near-miss ("I almost X until..."). These are fine formulas, but if you use them exactly as written, they'll sound generated.

**The best subject lines break the formulas.** Write the subject line you'd actually type to a friend: "you won't believe what SimPy can do with 5 lines" or just "quick SimPy thing". Avoid subject lines that are too perfectly crafted, a slightly rough subject line gets opened because it feels real.

**Subject line formulas** (use as starting points, not fill-in-the-blanks):
- Curiosity: "The thing nobody tells you about [X]"
- Benefit: "How to [achieve X] in [timeframe]"
- Story: "I almost [dramatic thing] until..."
- Direct: "[Specific thing] that changed my [result]"
- Antithesis: "[Old way] vs [new way]"

### Preview Text
- First 40-90 characters visible in inbox
- Complements (doesn't repeat) subject line
- Often the first sentence of your email

### Opening
- Don't waste the first line on "Hi [Name]"
- Start with something interesting
- Hook them immediately - they're deciding whether to keep reading

### Body
- Short paragraphs (2-3 sentences max)
- One idea per paragraph
- Use rhetorical devices for flow and emphasis
- Personal stories are your secret weapon
- Specifics > generalities (numbers, examples, real situations)

### CTA (Call to Action)
- ONE clear CTA per email
- Button or link, not both
- Action-oriented text ("Join the masterclass" not "Click here")
- Earned, not forced - comes after providing value

### Sign-off
- Keep it simple: "Harry" or "- Harry"
- P.S. lines work for secondary CTAs or personal notes

## Templates

See templates folder:
- [Newsletter](templates/newsletter.md)
- [Launch Announcement](templates/launch-announcement.md)
- [Nurture Sequence](templates/nurture-sequence.md)

## Voice Reminders

From [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md):

### Do
- Write like you're emailing one person
- Write like you're dashing off an email, not crafting one
- Share real stories and real numbers
- Be genuinely helpful before asking for anything
- Use "you" more than "I"
- British spellings throughout

### Don't
- Start with "I hope this email finds you well"
- Use "we" when you mean "I"
- Include multiple CTAs competing for attention
- Write walls of text without line breaks
- Sound like a marketing department

## Email Types Explained

### Newsletter
**Purpose**: Regular value delivery, staying top of mind
**Frequency**: Weekly or bi-weekly
**Mix**: Technical tip + industry observation + personal note
**CTA**: Soft (reply, share, optional course mention)

### Launch Announcement
**Purpose**: Promote a specific offering
**Frequency**: During launch windows only
**Structure**: Generally problem → solution → proof → offer, but vary the order and don't hit every beat every time. This exact sequence is a known copywriting formula and also an AI favourite, rearrange it, skip a section, or lead with proof instead of problem.
**CTA**: Direct (join, enrol, sign up)

### Nurture Sequence
**Purpose**: Build relationship over time with new subscribers
**Length**: 5-7 emails over 2-3 weeks
**Arc**: Welcome → Value → Story → More value → Soft pitch
**CTA**: Graduated (reply → free resource → masterclass → course)

## Anti-AI Detection

Read the shared [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) guide before writing. The rules there apply to all content.

Email is the most forgiving format, people expect conversational tone, and nobody is inspecting your newsletter for AI patterns the way they would a Reddit post. But there are still risks:

- **Subject lines are the highest risk.** AI-generated subject lines have recognisable patterns: the curiosity-gap formula, the numbered benefit, the dramatic near-miss. These are the first thing a reader sees and the easiest to pattern-match. Write the subject line last, and write it like you'd type it to a colleague.
- **The "Problem -> Solution -> Proof -> Offer -> Urgency" launch structure** is a known copywriting formula but also an AI favourite. Don't follow it in order every time. Lead with the offer sometimes. Skip the urgency if it's not real. Start with a story instead of the problem.
- **P.S. lines are naturally human**: use them freely. AI rarely generates them unprompted, so they actually help.
- **Emails should feel dashed off, not composed.** A newsletter that reads like it was written in 5 minutes between meetings is more trustworthy than one that reads like it was polished for a week.
- **The newsletter tip-story-CTA structure is fine** but shouldn't be identical every time. Sometimes it's just a tip. Sometimes it's just a story. Sometimes there's no CTA at all. Vary it.

## Example Emails

### Newsletter Example
```
Subject: The 30-second SimPy trick that took me years to find

Three years of using SimPy and I only just discovered this.

You can monitor resources without writing custom code.

I'd been building elaborate tracking systems. Logging
every request. Counting every release. Feeling clever
about my monitoring infrastructure.

Turns out SimPy has resource.count and resource.queue
built in.

    print(f"In use: {machine.count}")
    print(f"Waiting: {len(machine.queue)}")

Two lines. Same information. No cleverness required.

The best code is often the code you don't write.

---

What's your favourite "I can't believe I didn't know this"
moment? Hit reply - I read every response.

- H

P.S. Just remembered, if you're getting started with SimPy,
my free masterclass covers the fundamentals in 45 minutes.
Might save you some of the embarrassment I went through:
[link]
```

### Launch Example
```
Subject: The Simulation Bootcamp opens Monday

In three months, you could be building simulation models
that actually get used.

Not theoretical exercises. Not academic projects, real
models that influence real decisions.

That's what the Simulation Bootcamp delivers.

I've spent ten years building simulations for clients
who needed answers yesterday. This course is everything
I wish someone had taught me when I started.

Here's what's inside:
• Complete SimPy mastery (from basics to advanced)
• Real-world project work (not toy examples)
• Code templates you can adapt for your work
• Direct access to ask me anything

The uncomfortable truth about simulation skills:
most engineers learn by struggling alone for years.
This is the shortcut I never had.

Doors open Monday at 9am UK time.

Get on the waitlist here: [link]

Harry
```

## Quality Checklist

Before sending, verify:
- [ ] AI detection pass: Does the subject line sound generated? Rewrite if yes.
- [ ] No banned phrases from [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)
- [ ] Subject line creates curiosity or promises clear value
- [ ] Opening line is interesting (not "Hi, I hope...")
- [ ] Paragraphs are short and scannable
- [ ] Voice is authentically Harry (check against guide)
- [ ] Rhetorical devices (if used) are invisible
- [ ] ONE clear CTA (or none if pure value email)
- [ ] CTA is earned (value delivered first)
- [ ] No spelling errors (especially British vs American)
- [ ] Read aloud - does it sound like a person?
