---
name: landing-page-design
description: Create visual wireframe designs for landing pages. Produces design specs that developers can implement. Use when asked to design a landing page, create a wireframe, plan page layout, or structure a web page. Triggers on "landing page design", "wireframe", "page layout", "design a page".
---

# Landing Page Design

Create visual wireframe designs for landing pages as markdown specifications. This skill produces **design documents**, not copy - use `/copywrite` for the actual text content.

## When to Use This Skill

| Task | Skill |
|------|-------|
| Design page structure and layout | `/landing-page-design` (this skill) |
| Write compelling copy for sections | `/copywrite --type website_landing` |
| Both design and copy | This skill first, then `/copywrite` |

## Design Process

```
Design Request
      ↓
Select Template (product-launch, lead-magnet, waitlist)
      ↓
Define Sections & Order
      ↓
Create Wireframes (visual notation)
      ↓
Add Design Notes
      ↓
Save to posts/general/website/{slug}-design.md
```

## Automatic Steps

### 1. Clarify Requirements

Before designing, establish:
- **Page goal**: Conversion, awareness, or waitlist capture?
- **Target audience**: Who is this page for?
- **Primary action**: What should visitors do?
- **Key objections**: What hesitations must we address?

### 2. Select Template

| Template | Use For |
|----------|---------|
| `product-launch` | Course launches, bootcamps, paid products |
| `lead-magnet` | Free ebook, guide, or resource downloads |
| `waitlist` | Pre-launch interest capture |

### 3. Create Wireframe Document

Use the visual notation conventions below to create a clear design spec.

## Section Types

### Hero Section
First impression. Must answer: "What is this and why should I care?"

```
┌─────────────────────────────────────────────────────────┐
│                     [HERO SECTION]                      │
│                                                         │
│  ┌─────────────────────────┐  ┌──────────────────────┐  │
│  │   HEADLINE              │  │                      │  │
│  │   Supporting text       │  │      [IMAGE/         │  │
│  │                         │  │       VIDEO]         │  │
│  │   [PRIMARY CTA]         │  │                      │  │
│  └─────────────────────────┘  └──────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Benefits Section
Answer: "What's in it for me?" Focus on outcomes, not features.

```
┌─────────────────────────────────────────────────────────┐
│                   [BENEFITS SECTION]                    │
│                                                         │
│                  Section Headline                       │
│                                                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │   [ICON]    │  │   [ICON]    │  │   [ICON]    │     │
│  │  Benefit 1  │  │  Benefit 2  │  │  Benefit 3  │     │
│  │  Description│  │  Description│  │  Description│     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
```

### Features Section
Detailed breakdown of what's included.

```
┌─────────────────────────────────────────────────────────┐
│                   [FEATURES SECTION]                    │
│                                                         │
│  ┌───────────────────────┐  ┌────────────────────────┐  │
│  │   Feature 1           │  │                        │  │
│  │   • Detail            │  │      [SCREENSHOT/      │  │
│  │   • Detail            │  │       MOCKUP]          │  │
│  │   • Detail            │  │                        │  │
│  └───────────────────────┘  └────────────────────────┘  │
│                                                         │
│  ┌────────────────────────┐  ┌───────────────────────┐  │
│  │                        │  │   Feature 2           │  │
│  │      [SCREENSHOT/      │  │   • Detail            │  │
│  │       MOCKUP]          │  │   • Detail            │  │
│  │                        │  │   • Detail            │  │
│  └────────────────────────┘  └───────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Social Proof Section
Build trust through others' experiences.

```
┌─────────────────────────────────────────────────────────┐
│                 [SOCIAL PROOF SECTION]                  │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  "Testimonial quote..."                         │    │
│  │                                                 │    │
│  │  [AVATAR]  Name, Title, Company                 │    │
│  └─────────────────────────────────────────────────┘    │
│                                                         │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐    │
│  │ [LOGO]  │  │ [LOGO]  │  │ [LOGO]  │  │ [LOGO]  │    │
│  └─────────┘  └─────────┘  └─────────┘  └─────────┘    │
└─────────────────────────────────────────────────────────┘
```

### FAQ Section
Address objections before they become blockers.

```
┌─────────────────────────────────────────────────────────┐
│                    [FAQ SECTION]                        │
│                                                         │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ▸ Question 1?                                  │    │
│  │    Answer (collapsed by default)               │    │
│  └─────────────────────────────────────────────────┘    │
│  ┌─────────────────────────────────────────────────┐    │
│  │  ▸ Question 2?                                  │    │
│  │    Answer                                       │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

### CTA Section
Final conversion push. Remove all friction.

```
┌─────────────────────────────────────────────────────────┐
│                    [CTA SECTION]                        │
│                                                         │
│                 Compelling headline                     │
│                 Supporting urgency text                 │
│                                                         │
│                 ┌─────────────────┐                     │
│                 │  [PRIMARY CTA]  │                     │
│                 └─────────────────┘                     │
│                                                         │
│                 Risk reversal text                      │
└─────────────────────────────────────────────────────────┘
```

## Wireframe Notation Conventions

### Layout Elements

| Notation | Meaning |
|----------|---------|
| `┌───┐` | Section or element boundary |
| `[IMAGE]` | Placeholder for image |
| `[VIDEO]` | Placeholder for video |
| `[ICON]` | Placeholder for icon |
| `[LOGO]` | Placeholder for company logo |
| `[CTA]` | Call-to-action button |
| `[FORM]` | Input form |
| `▸` | Expandable/accordion element |

### Design Notes

Use callout blocks to explain design decisions:

```markdown
> **Design note**: [Explanation of why this design choice]
```

Use requirement callouts for must-haves:

```markdown
> **Required**: [Something that must be included]
```

Use warning callouts for common mistakes:

```markdown
> **Avoid**: [Common mistake to prevent]
```

## Output Format

Save designs to: `posts/general/website/{page-slug}-design.md`

### Frontmatter

```yaml
---
type: website-design
subtype: landing-page
status: draft | ready | approved
created: YYYY-MM-DD
page_name: Brief description
target_audience: Who this page is for
primary_goal: conversion | awareness | waitlist
template: product-launch | lead-magnet | waitlist
sections: [hero, benefits, features, social-proof, faq, cta]
---
```

## Quality Checklist

Before finalising any design:

- [ ] Clear page goal established
- [ ] Target audience defined
- [ ] Sections follow logical narrative arc
- [ ] Each section has design notes explaining purpose
- [ ] Mobile considerations mentioned
- [ ] CTA is prominent and repeated appropriately
- [ ] Objections addressed (FAQ or inline)
- [ ] Social proof included
- [ ] File saved with complete frontmatter

## Integration with Other Skills

**Workflow for complete landing pages:**

1. **`/landing-page-design`** - Create the visual structure (this skill)
2. **`/copywrite --type website_landing`** - Generate copy for each section
3. Hand both documents to developer for implementation

## Templates

See the templates directory for starting points:

- [Product Launch](templates/product-launch.md) - Course/product launch pages
- [Lead Magnet](templates/lead-magnet.md) - Free resource download pages
- [Waitlist](templates/waitlist.md) - Pre-launch waitlist capture

## Key Resources

- Voice guide: [VOICE_GUIDE.md](../shared/VOICE_GUIDE.md)
- Business context: [BUSINESS_CONTEXT.md](../shared/BUSINESS_CONTEXT.md)
- Copywriting skill: [/copywrite](../copywrite/SKILL.md)
