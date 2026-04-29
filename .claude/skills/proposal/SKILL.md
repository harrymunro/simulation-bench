---
name: proposal
description: Write consulting proposals for Aspegio simulation and AI engagements. Use when asked to write a proposal, pitch, statement of work, or consulting engagement document. Triggers on "proposal", "pitch", "statement of work", "SOW", "consulting proposal".
---

# Proposal Writer

Write consulting proposals for **Aspegio** engagements. Simulation, AI, data science, technical advisory.

## Important: Aspegio, not the education business

Proposals come from Aspegio, the consulting company. The shared `BUSINESS_CONTEXT.md` covers the education business. For proposals:
- The sender is Aspegio (the company), not an individual
- Use third person throughout. "Aspegio will build..." or "The proposed approach involves..." Never "I'll build..." or "I'd recommend..."
- The tone is formal and professional, conveying authority and credibility
- You're writing to a specific client contact, not a broad audience
- The anti-AI detection rules still apply (they're universal)
- The voice guide applies in spirit (British spellings, no corporate jargon) but proposals are more formal than other content types

## Core Writing Engine

This skill uses `/copywrite` as its core writing engine. The copywrite skill handles voice, rhetoric, and anti-AI detection. This skill adds **proposal-specific guidance** on top of that foundation.

## Before Writing

1. **Gather client context**: What's the client's name? What problem did they describe? Who's the contact? What's their industry? What did they say in the initial conversation? The more specific context you have, the less generic the proposal reads.

2. **Run the rhetoric selector**:
   ```bash
   uv run python .claude/skills/shared/rhetoric_selector.py --type proposal_direct
   ```

3. **Review shared guides**:
   - [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md) for tone (calibrated for proposals below)
   - [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) (critical for proposals, see notes below)

## Proposal Anatomy

These are the building blocks. Not every proposal needs all of them, and they don't need to appear in this order. A short engagement might skip the credentials section entirely. A follow-up proposal to an existing client might skip the situation understanding. Use what fits.

### Opening

Demonstrate you understood their problem. Not a generic "Thank you for the opportunity" intro. Reference something specific from the conversation. Show you were listening.

Bad: "Thank you for considering Aspegio for this engagement."
Better: "During our initial discussion, a familiar pattern emerged: a warehouse model that takes 6 hours to run and produces outputs that lack stakeholder confidence."

### Situation understanding

Reflect back what they told you, in your own framing. This is where you prove you understood the real problem, not just the surface request. Often the client asked for one thing but actually needs something adjacent.

### Proposed approach

Concrete activities, not vague methodology. "Aspegio will build a discrete-event simulation of the fulfilment centre" beats "We'll apply simulation methodology to optimise your operations." Avoid consultant-speak. State the work in plain language, but maintain a formal register.

### Deliverables

Concrete, specific, not padded. A list of actual things they'll receive. If it's a model, say what it models. If it's a report, say what questions it answers. Don't pad with "project documentation" and "knowledge transfer sessions" unless those genuinely matter.

### Timeline and logistics

When things happen, roughly. Don't over-specify. "4-6 weeks" is honest. "Exactly 23 working days" is fiction. Note any dependencies on client access, data, or stakeholder availability.

### About / credentials

Understated. Relevant experience only. Don't list every project you've ever done. Pick the 2-3 that are most relevant to this client's situation. Litotes is your friend here. "Not unfamiliar with pharmaceutical manufacturing" is more credible from a British consultant than "extensive experience across the pharmaceutical sector."

### Investment

Pricing. Or a placeholder if pricing comes later. Be direct about what it costs. If there are options (phases, tiers), present them clearly.

### Next steps

What happens if they say yes. Keep it simple. "Subject to agreement, Aspegio can commence the week of [date]. Access to [specific thing] will be required."

## Voice Calibration for Proposals

Proposals represent Aspegio as a professional consultancy. The tone should be formal, authoritative, and measured. Direct without being casual. Precise without being stiff. The register is that of a senior technical document, not informal correspondence.

**Prioritise:**
- Formal, third-person voice throughout ("Aspegio will...", "The proposed approach...", "This engagement...")
- Professional authority (understated, not boastful)
- Precision and specificity (exact deliverables, clear timelines)
- Litotes and understatement ("not unfamiliar with" rather than "expert in")
- Logical flow between sections

**Avoid:**
- First person ("I", "my", "me"). Use "Aspegio", passive voice, or impersonal constructions
- Casual asides, parenthetical tangents, or conversational tone
- Humour beyond the very occasional dry observation
- Self-deprecation of any kind
- Contractions (use "will not" rather than "won't", "does not" rather than "doesn't")

**Retain:**
- Directness (still no corporate fluff or consultant-speak)
- British spellings
- Specificity over vagueness
- Clear recommendations ("Aspegio recommends X over Y because...")

## Anti-AI Detection: Critical for Proposals

A proposal that reads as AI-generated destroys trust instantly. The client is evaluating whether to give you money. If the document you send them to earn that trust was clearly generated by a language model, you've lost before you started.

Read [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md). All the rules apply. Plus these proposal-specific risks:

- **The symmetric structure.** AI proposals follow a rigid section order with uniform section lengths. Real proposals have sections of wildly different lengths. The "About" section might be two sentences. The "Approach" section might be a full page.
- **Consultant-speak.** "Leverage our expertise to drive value across your operations." This is the AI default for proposals. Write in plain English. Say what you'll do.
- **The perfect problem-solution symmetry.** AI maps every problem point to a matching solution point. Real proposals sometimes solve problems the client didn't mention and don't address every point they raised (because some aren't actually problems).
- **Padded deliverables.** "Comprehensive documentation", "Knowledge transfer workshop", "Executive summary report." If these aren't genuinely valuable, cut them. A shorter deliverables list is more credible.
- **The confident-yet-humble tone.** AI proposals have a specific register where they sound confident about everything while occasionally hedging with "we understand that." Pick a lane. Be confident where you're confident. Be honest where you're uncertain.

## Templates

See templates folder:
- [Consulting Project](templates/consulting-project.md) for simulation/AI consulting engagements
- [Training Workshop](templates/training-workshop.md) for delivering training to client teams

## Quality Checklist

Before finalising:

- [ ] **AI detection pass**: Does this read like a generated proposal? If you've seen this structure from ChatGPT before, rewrite.
- [ ] **Client specificity**: Could this proposal only have been written for this client? If you could swap the company name and it still works, it's too generic.
- [ ] **No consultant-speak**: No "leverage", "synergy", "holistic approach", "drive value", "best-in-class"
- [ ] **No banned phrases** from [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md)
- [ ] **Deliverables are concrete**: Each deliverable is a specific thing, not a category of things
- [ ] **No first person**: No "I", "my", or "me". Use "Aspegio", passive voice, or impersonal constructions
- [ ] **Voice is right**: Formal, authoritative, measured. Direct, understated, credible.
- [ ] **Section lengths vary**: Not every section is the same length
- [ ] **Rhetoric is invisible**: Devices are working but not identifiable
- [ ] **British spellings** throughout
- [ ] **Saved** to `posts/proposals/{client-slug}.md` with complete frontmatter

## Example Proposal Excerpt

```
# Fulfilment Centre Simulation Model

## Situation Understanding

The Coventry DC currently processes approximately 40,000 orders per day, with
projections indicating 60,000 by Q3. The existing layout was designed for a
throughput of 25,000. The addition of a night shift provided some relief, but
queue times at the packing stations suggest the bottleneck has migrated
downstream.

The board requires a business case for a layout redesign before committing
capital. A static spreadsheet analysis, however, will not capture the queuing
dynamics at the root of the problem. This is precisely where discrete-event
simulation provides the greatest value.

## Proposed Approach

Aspegio will build a discrete-event simulation of the DC, from goods-in
through to dispatch. The model will represent:

- Current picking routes and station allocations
- Order arrival patterns (derived from actual order data, not assumptions)
- Staff scheduling across all three shifts
- The proposed layout changes the operations team has already developed

The model will not attempt to represent every conveyor belt and scanner. That
level of detail incurs cost without improving the quality of the decision.
The appropriate level of fidelity is one that reveals where queues form and
how they respond to layout changes. No more.

The principal output will be a comparison of 3-4 layout scenarios, each run
across a range of demand levels (40k, 50k, 60k orders/day), showing
throughput, queue times at each station, and staff utilisation. Figures
suitable for board-level decision-making.

## Timeline

Approximately 4 weeks from receipt of order data.

- Week 1: Data analysis, model structure, assumptions document
- Weeks 2-3: Model build and validation
- Week 4: Scenario runs, results, recommendations

This engagement requires access to 3-6 months of order history and a
half-day walkthrough of the DC. A 30-minute session with whoever designed
the proposed layouts will also be necessary, to ensure the model does not
explore options that have already been ruled out.

## Investment

£[X] for the full engagement, invoiced in two stages: 50% at kick-off,
50% on delivery of the final report.

This includes one round of revisions to the scenarios. Additional layouts
beyond the initial set can be explored at a day rate of £[Y].
```

Note how the example uses specifics from the client conversation, varies section lengths, avoids consultant-speak, and maintains a formal third-person voice throughout. The scoping paragraph ("The model will not attempt to represent every conveyor belt") demonstrates honest scoping that builds trust without resorting to casual tone.

## Key Resources

- **Anti-AI detection**: [ANTI_AI_DETECTION.md](../shared/ANTI_AI_DETECTION.md) (READ THIS FIRST)
- Voice guide: [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md)
- Rhetorical devices: [RHETORICAL_DEVICES.md](../shared/RHETORICAL_DEVICES.md)
