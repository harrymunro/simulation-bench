# Template: Medium Narrative

For personal stories, career journeys, lessons learned, and experience-driven pieces. Written entirely in prose. No code, no tables, no lists.

**Do NOT follow this as a fill-in-the-blanks template.** Narrative Medium articles are the closest thing to spoken storytelling. If you can imagine the author telling this story at a dinner party and it landing well, you're on the right track. If it sounds like a TED talk transcript, you've gone too far.

## Why narrative works on Medium

Medium's audience self-selects for people who want to read. Not skim, not scan, but actually sit with a piece for eight or ten minutes. Narrative rewards that investment. And because so many Medium readers listen via text-to-speech, narrative prose has a massive advantage: stories are the oldest form of audio content. They work when spoken. Bullet points don't.

## Best rhetoric devices

- **Anadiplosis** for narrative momentum, where the end of one thought becomes the start of the next
- **Polysyndeton** for accumulation and the feeling of events piling up

Use at most 1-2. They must be invisible. See [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md).

## Approaches

### Approach 1: The thing that happened

Start in the middle of the story, not the beginning. "I was sitting in a client meeting when the simulation crashed" is more engaging than "Last year, I decided to build a simulation for a client." Drop the reader into a moment, then fill in the context they need as you go.

The story doesn't need a neat lesson. If there is one, let it emerge. If the story is interesting on its own, that's enough. Not every experience needs to be packaged as a takeaway.

This works well for: project stories, career-defining moments, failures and recoveries, client interactions.

### Approach 2: The slow realisation

Something you believed turned out to be wrong. Or something you dismissed turned out to matter. This isn't a dramatic reveal. It's the gradual accumulation of evidence that shifted your thinking. Describe the shift as it actually happened, not as a clean before-and-after.

Include the resistance. The part where you saw the evidence and didn't change your mind. The moment where you probably should have acted but didn't. That's the honest part, and it's what separates a real narrative from a constructed one.

This works well for: changed opinions, professional growth, methodology shifts, learning journeys.

### Approach 3: The day in the life

Describe what your work actually looks like, not the polished version, but the messy reality. The five tabs you have open. The spreadsheet you keep meaning to clean up. The hacky workaround you've been using for months. This kind of specificity is deeply human and almost impossible for AI to generate convincingly.

The narrative thread is "here's what it's actually like" as opposed to what people imagine or what job descriptions say. The interest comes from the gap between expectation and reality.

This works well for: simulation consulting work, teaching, freelancing, engineering practice.

## Anti-patterns

- **The hero's journey**: Challenge, struggle, triumph, lesson. This is the most overused narrative structure in AI-generated content. Real stories have false endings, partial victories, and lessons that don't quite fit.
- **The retrospective wisdom**: Writing from a position of "I see now what I couldn't see then" throughout the entire piece. Real narrative includes moments of genuine confusion that aren't resolved for the reader any more neatly than they were resolved for the writer.
- **The perfectly illustrative anecdote**: Every detail supports the thesis. Real stories include irrelevant details that happened to be memorable. The client's terrible coffee. The fact that it was raining. These aren't literary devices. They're what you actually remember.
- **Uniform emotional register**: The whole piece is reflective, or the whole piece is dramatic. Real narratives shift. A tense moment followed by an almost bored observation followed by something genuinely funny.
- **The manufactured vulnerability**: "I'll be honest with you..." followed by something that makes the writer look good. Real vulnerability is admitting something that might actually make the reader think less of you. "I didn't understand what a random seed was until embarrassingly recently" is more vulnerable than "I had to work really hard to overcome impostor syndrome."

## Example

```markdown
# I Built the Wrong Model for Six Months

The client was a logistics company with a warehouse problem. Too many
orders backing up, not enough throughput, the usual. They wanted a
simulation to figure out where the bottleneck was.

I knew where the bottleneck was within two hours of visiting the
warehouse. It was the packing station. You could see it. Orders
stacking up on one side, finished packages trickling out the other.
A child could have spotted it.

But they weren't paying me to point at things. They were paying me
to build a model. So I built a model.

I modelled the receiving dock. I modelled the storage racks. I modelled
the pick paths, the conveyor system, the sorting stations. I spent
weeks calibrating arrival distributions from their order data. I got
the model to within three percent of their actual throughput numbers.
I was genuinely proud of it.

And then I showed them the results, which confirmed what everyone
already knew: the packing station was the bottleneck. The room went
quiet in the way that rooms go quiet when people are too polite to
say what they're thinking.

The operations manager, to his credit, asked a good question. "So
what should we do about it?" And I realised I'd spent six months
building an incredibly detailed model that told them something
obvious, without building the thing they actually needed, which was
a model that could test different solutions.

I rebuilt the model in two weeks. This time, I only modelled the parts
that mattered for testing interventions. The receiving dock was a
simple arrival process. The storage racks were a delay. The interesting
bit, the packing station and what happened when you added a second one
or changed the shift pattern or rerouted certain order types, that's
where all the detail went.

The second model was less impressive to look at. It also actually
helped them make a decision.

I think about this project whenever someone asks me how detailed their
simulation should be. The answer is almost always less detailed than
you think, but detailed in different places than you'd expect.
```

Notice: the story includes specific details (three percent accuracy, two-week rebuild) that make it feel real. The room going quiet is a sensory detail that works in audio. The "lesson" emerges from the story rather than being stated as a thesis. The ending doesn't wrap up neatly; it's a reflection that raises as many questions as it answers.

## Variations

### The failure without redemption

Sometimes you just got it wrong and there's no satisfying recovery arc. Describe what happened honestly. What you'd do differently. What you still aren't sure about. These are the most human stories because success stories are inherently suspect.

### The unexpected connection

Two things you didn't think were related turned out to be deeply connected. The narrative follows your realisation, not the logical connection itself. Start with one thing, introduce the other separately, and let the reader feel the connection click at roughly the same time you did.

### The long apprenticeship

Something you learned slowly, over years, that can't be compressed into a five-minute read. This is where Medium's long-form format shines. Take the reader through the timeline. Include the plateaus, the frustrations, the periods where nothing seemed to change. This mirrors how people actually learn things and is deeply satisfying to listen to.
