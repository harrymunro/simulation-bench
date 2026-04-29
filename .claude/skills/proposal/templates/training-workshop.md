# Template: Training & Workshop Proposal

For delivering simulation training, Python workshops, AI/ML upskilling, or technical workshops to client teams through Aspegio.

**Do NOT follow this as a fill-in-the-blanks template.** Training proposals need to feel tailored to the client's team and context, not like a course catalogue entry with their name on it. Read [ANTI_AI_DETECTION.md](../../shared/ANTI_AI_DETECTION.md) first.

## Best rhetoric devices

- **Litotes** for understated credibility ("Aspegio is not unfamiliar with teams who have never touched Python")
- **Antithesis** for before/after the training, or contrasting their current approach with where they could be
- **Tricolon** for learning outcomes or session summaries (but break the symmetry)

Use at most 1-2. Invisible, as always. All training proposals must use formal, third-person voice. No first person ("I", "my", "me"). Use "Aspegio" or impersonal constructions.

## How training proposals differ from project proposals

Training proposals sell a transformation, not a deliverable. The client is not buying a model or a report. They are investing in the belief that their team will be more capable afterwards. That means:

- **The situation understanding** focuses on the team's current skill level and what's blocking them
- **The approach** describes the learning experience, not just the syllabus
- **The deliverables** include what participants leave with (code, templates, confidence) not just "training delivered"
- **Credibility** comes from teaching experience specifically, not just domain expertise

## Loose Structure

```
# [Training Title - descriptive, for this team specifically]

## [Their situation]
[What's the team's current level? What are they trying to do
that they can't do yet? Why now? Reference specifics from
the conversation about their team, their tools, their gaps.]

## [What the training covers]
[Not a syllabus. A description of what they'll learn and why
it matters for their work. Organised by capability, not by
day. "By the end, your team will be able to..." is fine as
a framing device but don't make every item start the same way.]

## [How it works]
[Format, duration, hands-on vs lecture ratio, exercises.
Be specific about the teaching approach. "Exercises will use
the client's actual data" is worth more than "interactive
workshop format."]

## [What they'll leave with]
[Concrete things: working code, templates, reference materials.
Things that outlast the training itself. Not "comprehensive
training materials" but "a working simulation template based
on your production line that they can extend."]

## [Logistics]
[Duration, location, group size, prerequisites. What you
need from them beforehand.]

## [Investment]
[Pricing. Note what's included (materials, follow-up support
if offered). Day rate or fixed price.]

## [Next steps]
[Simple.]
```

## Anti-patterns

- **The generic syllabus.** "Day 1: Introduction to Python. Day 2: Data structures." This is a course catalogue, not a proposal. Frame what they'll learn around what they need to do, not around Python's feature set.
- **Promising transformation without specifics.** "Your team will be empowered to leverage simulation for strategic decision-making." What does that actually mean? Be concrete. "Your planning team will be able to build and run a simulation model of your warehouse without calling IT."
- **The uniform learning outcomes list.** "Participants will be able to: [verb] [noun]. Participants will be able to: [verb] [noun]." Break the pattern. Some outcomes are a sentence, some need a paragraph of context.
- **Overselling interactivity.** "Hands-on, interactive, engaging workshop experience." Describe what participants will actually do. "Participants will build a working model of the process on day one" says more than any amount of adjectives.
- **Ignoring prerequisites honestly.** If the team needs basic Python before this training will work, state so clearly. Suggesting a pre-work module is more honest than implying everyone will keep up regardless.

## Variations

### Half-day workshop

Focused and sharp. One topic, one capability. No syllabus, just "in 4 hours, your team will go from X to Y." These proposals can be very short. A page is fine.

### Multi-day programme

Needs more structure. Break it into modules or days, but frame each one around a capability they'll gain, not a topic you'll cover. Include how the days build on each other.

### Ongoing coaching

For teams that need support over months rather than a one-off event. Focus on availability, format (weekly calls, code reviews, office hours), and what success looks like after 3-6 months.

## Example excerpt

```
# Simulation with Python: Workshop for the Planning Team

## Current Team Position

Based on the discussion with Sarah, the planning team comprises strong
analysts whose primary tool is Excel. The team has received simulation
outputs from external consultants (including, it was noted, some
questionable Arena models), but no one on the team can build or modify
a simulation model independently. When assumptions require updating,
the team must wait for the consultant.

That is the dependency this workshop is designed to break.

## Workshop Content

The programme spans two days. By the end, participants will be able to
build a basic simulation of the packing line in Python, run scenarios,
and interpret the results without external assistance.

Day one establishes the foundational mental model. How discrete-event
simulation works, why it differs from the spreadsheet models the team
currently relies upon, and developing fluency with Python and SimPy.
Participants will build a simple model of a single-server queue. Not
the most compelling exercise, but it is the foundation upon which
everything else is constructed.

Day two applies the concepts directly to the client's operations.
Using actual packing line data, the group will build a model
collaboratively. By the afternoon, participants will be running
scenarios: the effect of adding a second packing station, the impact
of a 20% increase in order volumes, the consequences of altering the
shift pattern.

The workshop will not cover optimisation, statistical analysis of
outputs, or advanced Python. These are all valuable topics, but they
belong to a second week of training. Attempting to compress them into
two days would result in broad exposure but poor retention.

## What Participants Will Receive

- A working simulation model of the packing line (built by the
  participants, not provided by Aspegio)
- A SimPy reference guide compiled from over a decade of practical
  application
- All exercise files and data sets from the workshop
- Sufficient confidence to modify the model as operational conditions
  change

## Logistics

Two consecutive days, delivered on-site at the Coventry facility.
Requirements include a room with a projector and adequate desk space
for laptops. Maximum group size is 12 participants; the 8 Sarah
identified would be ideal.

All participants will need a laptop with Python installed. Setup
instructions will be provided two weeks in advance. Should IT
provisioning prove difficult, Aspegio can supply pre-configured USB
drives.

## Investment

£[X] for the two-day workshop, including all materials and one month
of email support for follow-up questions.
```

Note how the example references the specific client contact by name, acknowledges what the team has tried before, is honest about what will not be covered and why, and maintains a formal third-person register throughout. It reads as an authoritative professional document, not informal correspondence.
