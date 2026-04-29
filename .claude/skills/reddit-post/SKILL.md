---
name: reddit-post
description: Create Reddit posts. Use when asked to write a Reddit post, Reddit content, or community discussion content about simulation, Python, SimPy, engineering, or related topics. Triggers on "reddit", "subreddit", "r/".
---

# Reddit Post Creator

Create engaging Reddit posts in Harry's witty, knowledgeable voice, adapted for Reddit's culture of authenticity, technical depth, and zero tolerance for marketing fluff.

## Core Writing Engine

This skill uses `/copywrite` as its core writing engine. The copywrite skill handles:
- Voice and tone application
- Rhetorical device selection and integration
- British spelling and language patterns

This skill adds **Reddit-specific constraints** on top of that foundation.

## Reddit vs LinkedIn: Key Differences

Reddit requires a fundamentally different approach:

| Aspect | LinkedIn | Reddit |
|--------|----------|--------|
| Self-promotion | Soft CTAs acceptable | Instant downvotes, earn trust first |
| Tone | Professional polish | Raw, conversational, peer-to-peer |
| Formatting | Short paragraphs, line breaks | Markdown-rich, code blocks, headers |
| Credibility | Job titles, authority | Show your work, share your code |
| Engagement | Questions drive comments | Genuine value drives upvotes |
| Length | Short (1,000-1,300 chars) | Varies wildly, as long as needed |

**The golden rule on Reddit: Give first, always. Promote never (or almost never).**

## Anti-AI Detection (Critical for Reddit)

**Read [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) before writing any Reddit post. Those rules override the templates below.**

Reddit is the most hostile platform for AI-generated content. Users actively hunt for it, downvote it, and call it out publicly. A post flagged as AI is dead, and may get you banned from the subreddit.

### Reddit-specific anti-AI rules

These go beyond the shared guide. On Reddit specifically:

- **Posts should read like forum comments, not essays.** If your post could be submitted as a university assignment, it's too polished. It should read like someone typing their experience into a text box.

- **Headers are optional even on long posts.** Plenty of good Reddit posts are just flowing paragraphs of text. Don't default to adding `##` headers, use them only when the post genuinely needs them for navigation.

- **Perfect structure is the #1 giveaway.** Real Reddit posts meander. They go on tangents. They circle back to something mentioned three paragraphs ago. They include details that aren't strictly relevant but are interesting.

- **TL;DRs are one lazy sentence, not crafted summaries.** "TL;DR simpy does most of what Arena does and it's free". that's it. No semicolons, no careful phrasing. Just the gist.

- **Don't end every post with an engagement question.** Sometimes you just... stop. When you're done saying what you wanted to say, stop saying it. If you do ask a question, make it specific and genuinely something you want answered, not "What do you think?"

- **Code and numbers are your credibility, not prose quality.** A badly written post with real benchmarks beats a beautifully written post with vague claims. Every time.

- **Roughness IS the authenticity signal.** A slightly disorganised post with genuine insight reads as human. A perfectly structured post with decent insight reads as AI. Reddit will take the messy one every time.

## Before Writing

1. **Run the rhetoric selector** to get your rhetorical devices:
   ```bash
   uv run python .claude/skills/shared/rhetoric_selector.py --type reddit_technical
   # or --type reddit_discussion
   # or --type reddit_showcase
   ```

2. **Review the voice guide**: See [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md) (or use copywrite's built-in checklist)

3. **Check content pillars**: See [CONTENT_PILLARS.md](../shared/CONTENT_PILLARS.md)

4. **Identify target subreddit(s)**: tone and depth vary by community:
   - `r/Python`, technical, code-focused, moderate length
   - `r/simpy`, niche, deep technical, beginner-friendly tone
   - `r/learnpython`, teaching-focused, patient, step-by-step
   - `r/datascience`, analytical, methodology-focused
   - `r/OperationsResearch`, academic, rigorous, theory + practice
   - `r/engineering`, practical, industry-focused, real-world examples
   - `r/SideProject` / `r/programming`, project showcases, broader audience

## Post Types

### Text Post (Self Post)
The primary format. Has a title and body.

### Link Post
Shares a URL (blog post, tutorial, tool). Title is everything, body is auto-generated from the link.

### Comment / Discussion Reply
Contributing to existing threads. Often where the real value is on Reddit.

## Post Structure

### The Title
- **Most important element**: determines whether anyone reads the body
- Be specific and descriptive, not clickbaity
- Good: "How I replaced Arena with 50 lines of SimPy for a hospital queue model"
- Bad: "This Python library changed everything!!"
- Include the key technical terms people search for
- Questions make excellent titles for discussion posts

### The Body

#### Opening (2-3 sentences)
- State the problem, context, or question directly
- No preamble or throat-clearing, get to the point
- Reddit readers decide in the first sentence whether to keep reading

#### Content (as long as needed)
- Use Reddit markdown: `**bold**`, `*italic*`, headers, bullet lists
- Code blocks are essential for technical posts, use triple backticks
- Headers are optional, use them when they help, skip them when they don't
- Include numbers, benchmarks, and specifics
- Show your actual code, not pseudocode

#### Closing
- Sometimes you just stop when you've said what you wanted to say
- If you ask a question, make it specific: "Has anyone benchmarked X against Y?" not "What do you think?"
- **No CTAs** unless you're sharing a genuinely free resource (and even then, tread carefully)

## Formatting Rules

- **Length**: No hard limit, but respect the reader's time. Technical tutorials can be long; discussion starters should be concise
- **Code blocks**: Use fenced code blocks with language hints (```python)
- **Headers**: Optional. Use `##` for sections in longer posts when they genuinely help readability. Many great Reddit posts use none.
- **Lists**: Bullet points for features/steps, numbered for sequences
- **Links**: Inline links `[text](url)`, never bare URLs
- **TL;DR**: One lazy sentence at the bottom for posts over ~300 words. Not a mini-essay.
- **No hashtags**: Reddit doesn't use them
- **No emojis** (or extremely sparingly), they read as unserious on most subreddits

## Templates by Content Type

See templates folder:
- [Technical Tutorial](templates/technical-tutorial.md)
- [Discussion Starter](templates/discussion-starter.md)
- [Project Showcase](templates/project-showcase.md)

## Voice Reminders (Reddit-Adapted)

From [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md), with Reddit adjustments:

**Keep from the core voice:**
- Witty, dry British humour. Reddit loves this
- Challenge conventional wisdom with evidence
- Share failures openly. Reddit respects honesty
- Use "I". personal experience is currency on Reddit
- British spellings (colour, optimise, modelling)
- Specific numbers and real examples

**Dial up for Reddit:**
- Technical depth, show your working
- Self-deprecation. Reddit rewards humility
- Genuine curiosity, ask real questions you want answers to
- Code examples, always show, don't just tell
- Roughness and imperfection, a post that's too clean is suspicious

**Dial down for Reddit:**
- Marketing language, zero tolerance
- Authority claims, let the work speak
- CTAs, earn the right over time, don't ask in posts
- Polish, roughness reads as authentic
- Structure, don't outline your post like an essay

### Phrases that work on Reddit
- "TIL..." (Today I Learned)
- "Genuine question:"
- "I might be wrong about this, but..."
- "edit: forgot to mention..."
- "obligatory 'it depends' but..."
- "I've been doing this for X years and only just realised..."
- "Roast my approach:" (inviting constructive criticism)
- Sentence fragments. Just a few words sometimes.
- Self-corrections: "took about 30 seconds, actually more like a minute once I added the warm-up"

### Avoid on Reddit
- "Check out my course/product/newsletter"
- "10x your productivity"
- Anything that sounds like a LinkedIn post
- "Upvote if you agree"
- Excessive self-promotion in any form
- "Here's the thing..." (ChatGPT's favourite opener)
- "Let's dive in" / "Let's dive into"
- "It's worth noting that..."
- "At the end of the day"
- "Curious what others think" (manufactured engagement)
- "What are your thoughts?" / "What's your take?" (generic engagement closers)
- "The key takeaway is..."
- "Let me break this down"
- Any phrase from the banned list in [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)

## Example Posts

### Technical Tutorial (r/Python)

**Title:** How I model hospital queues with SimPy in ~50 lines of Python

**Body:**
```
I keep seeing questions about discrete-event simulation libraries in Python,
and most answers point to heavy frameworks. For 90% of queuing problems,
SimPy is all you need.

I needed to model patient flow through A&E, arrival rates, triage,
treatment, discharge. The commercial quotes came in at £15k+. Which
seemed a bit much for what's essentially a glorified queue.

```python
import simpy

def patient(env, name, hospital):
    arrival = env.now
    with hospital.request() as req:
        yield req
        yield env.timeout(treatment_time())
    wait = env.now - arrival
    wait_times.append(wait)
```

That's the core of it. Everything else is configuration.

Few things I didn't expect:
- SimPy's `Resource` handles queuing logic automatically, you don't
  build any of that yourself
- `env.timeout()` with a distribution function gives you stochastic
  behaviour, which is most of what simulation actually is
- 50 lines got me 80% of what the £15k software would have done

The full model with plotting is about 120 lines. Happy to share
if there's interest.

TL;DR: SimPy + basic Python replaces expensive simulation software
for most queuing models.
```

### Discussion Starter (r/OperationsResearch)

**Title:** Genuine question: why is discrete-event simulation still dominated by proprietary tools?

**Body:**
```
I've been building simulation models for about 8 years now. Started with
Arena, moved to Simul8, and three years ago switched entirely to Python/SimPy.

The thing I can't figure out: why does the industry still default to
proprietary tools?

The arguments I hear:
- "Enterprise support", fair, but Stack Overflow has never let me down
- "Visual interface", Matplotlib and Plotly exist
- "Validation/verification", you can unit test SimPy models. Try that in Arena.

The arguments I don't hear but suspect:
- Procurement teams understand software licences, not open-source
- Consultancies sell the tool, not the solution
- "Nobody got fired for buying Arena" (the IBM effect)

I'm not saying commercial tools are useless. But the gap has narrowed to
the point where the default should probably be reversed.
```

## Self-Promotion Guidelines

Reddit has strict self-promotion rules. Follow the **10:1 rule**:
- For every self-promotional post, contribute 10 genuine value posts/comments
- Never post the same content across multiple subreddits simultaneously
- If sharing your own content (blog, tool), disclose it: "I wrote this" / "I built this"
- The post must stand on its own, the link should be supplementary, not required

## Quality Checklist

Before posting, verify:
- [ ] Title is specific, descriptive, and not clickbaity
- [ ] Voice is authentic (would a real person write this in a comment?)
- [ ] Anti-AI detection: would you flag this as AI-written? If yes, rewrite
- [ ] Structure is messy enough . not an essay outline
- [ ] No banned AI phrases (see [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md))
- [ ] Ending is natural . not a manufactured engagement question
- [ ] No marketing language or CTAs
- [ ] Code examples included where relevant (with proper formatting)
- [ ] Subreddit rules checked (many have specific posting guidelines)
- [ ] Provides genuine value . would you upvote this if someone else posted it?
- [ ] TL;DR is one lazy sentence (not a crafted summary) for longer posts
- [ ] Self-promotion guidelines followed (if linking own content)
- [ ] British spellings used throughout
