#!/usr/bin/env python3
"""
Mozart-Inspired Rhetorical Device Selector

Like Mozart's "Musikalisches Würfelspiel" (Musical Dice Game), this script uses
probability distributions to select rhetorical devices, creating natural variety
while maintaining elegance.

Usage:
    python rhetoric_selector.py --type linkedin_technical
    python rhetoric_selector.py --type linkedin_provocative --count 3
    python rhetoric_selector.py --type email_nurture
"""

import argparse
import random
from dataclasses import dataclass
from typing import Optional
import numpy as np

@dataclass
class RhetoricalDevice:
    name: str
    definition: str
    example: str
    placement: str  # hook, body, closing, any

DEVICES = {
    "tricolon": RhetoricalDevice(
        name="Tricolon",
        definition="Three parallel elements of similar length and structure",
        example="Learn it. Build it. Ship it.",
        placement="any"
    ),
    "antithesis": RhetoricalDevice(
        name="Antithesis",
        definition="Placing opposing ideas in parallel structure",
        example="Commercial software costs thousands; SimPy costs nothing.",
        placement="hook"
    ),
    "anaphora": RhetoricalDevice(
        name="Anaphora",
        definition="Beginning successive phrases with the same words",
        example="You don't need a consultant. You don't need a training budget. You don't need permission.",
        placement="body"
    ),
    "epistrophe": RhetoricalDevice(
        name="Epistrophe",
        definition="Ending successive phrases with the same words",
        example="They said it couldn't be done in Python. I did it in Python.",
        placement="closing"
    ),
    "anadiplosis": RhetoricalDevice(
        name="Anadiplosis",
        definition="The last word of one phrase becomes the first of the next",
        example="Understanding leads to confidence. Confidence leads to action.",
        placement="body"
    ),
    "hyperbaton": RhetoricalDevice(
        name="Hyperbaton",
        definition="Deliberately unusual word order for emphasis",
        example="Wrong, I was. Completely wrong.",
        placement="hook"
    ),
    "chiasmus": RhetoricalDevice(
        name="Chiasmus",
        definition="Reversing structure of two parallel phrases (AB-BA)",
        example="Don't learn to use the tool - use the tool to learn.",
        placement="closing"
    ),
    "polyptoton": RhetoricalDevice(
        name="Polyptoton",
        definition="Repeating words from the same root in different forms",
        example="Teaching teaches the teacher.",
        placement="any"
    ),
    "asyndeton": RhetoricalDevice(
        name="Asyndeton",
        definition="Omitting conjunctions for speed and impact",
        example="Install Python. Import SimPy. Build your first model.",
        placement="hook"
    ),
    "polysyndeton": RhetoricalDevice(
        name="Polysyndeton",
        definition="Extra conjunctions for accumulation effect",
        example="And then you export. And then you clean. And then you wait.",
        placement="body"
    ),
    "hyperbole": RhetoricalDevice(
        name="Hyperbole",
        definition="Deliberate exaggeration for emphasis",
        example="I've spent roughly a thousand hours fighting software licences.",
        placement="any"
    ),
    "litotes": RhetoricalDevice(
        name="Litotes",
        definition="Understatement by denying the opposite (very British)",
        example="The results were not entirely disappointing.",
        placement="any"
    ),
}

# Content type probability profiles
# Higher weight = more likely to be selected
PROFILES = {
    "linkedin_technical": {
        "tricolon": 0.20,       # Lists work well for tips
        "antithesis": 0.15,    # Contrasting old vs new way
        "anaphora": 0.10,      # Good for emphasis
        "asyndeton": 0.18,     # Quick, punchy for technical content
        "litotes": 0.12,       # Understated British humour
        "hyperbole": 0.08,     # Occasional exaggeration
        "anadiplosis": 0.05,
        "epistrophe": 0.05,
        "hyperbaton": 0.03,
        "chiasmus": 0.02,
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "linkedin_provocative": {
        "antithesis": 0.25,    # Challenging conventional wisdom
        "hyperbaton": 0.15,    # Unexpected catches attention
        "anaphora": 0.15,      # Builds momentum for argument
        "litotes": 0.12,       # Dry understatement
        "tricolon": 0.10,
        "hyperbole": 0.08,
        "chiasmus": 0.05,
        "epistrophe": 0.04,
        "asyndeton": 0.03,
        "anadiplosis": 0.02,
        "polyptoton": 0.01,
        "polysyndeton": 0.00,
    },
    "linkedin_personal": {
        "anadiplosis": 0.18,   # Creates narrative flow
        "litotes": 0.15,       # Humble, British understatement
        "hyperbaton": 0.12,    # Reflective, unusual phrasing
        "antithesis": 0.12,    # Then vs now contrasts
        "tricolon": 0.10,
        "anaphora": 0.10,
        "epistrophe": 0.08,
        "hyperbole": 0.05,
        "chiasmus": 0.05,
        "polyptoton": 0.03,
        "asyndeton": 0.02,
        "polysyndeton": 0.00,
    },
    "email_newsletter": {
        "tricolon": 0.18,
        "anaphora": 0.15,      # Good for email structure
        "anadiplosis": 0.12,   # Flow between paragraphs
        "litotes": 0.12,
        "antithesis": 0.10,
        "epistrophe": 0.10,
        "asyndeton": 0.08,
        "hyperbole": 0.05,
        "chiasmus": 0.04,
        "hyperbaton": 0.03,
        "polyptoton": 0.02,
        "polysyndeton": 0.01,
    },
    "email_launch": {
        "antithesis": 0.20,    # Before/after, with/without
        "tricolon": 0.18,      # Features, benefits
        "anaphora": 0.15,      # Building excitement
        "asyndeton": 0.12,     # Urgency
        "hyperbole": 0.10,     # Big claims (tastefully)
        "epistrophe": 0.08,
        "anadiplosis": 0.05,
        "litotes": 0.05,
        "chiasmus": 0.04,
        "hyperbaton": 0.02,
        "polyptoton": 0.01,
        "polysyndeton": 0.00,
    },
    "email_nurture": {
        "anadiplosis": 0.20,   # Flow and connection
        "litotes": 0.18,       # Modest, trust-building
        "tricolon": 0.15,
        "anaphora": 0.12,
        "epistrophe": 0.10,
        "antithesis": 0.08,
        "hyperbaton": 0.05,
        "chiasmus": 0.05,
        "asyndeton": 0.03,
        "hyperbole": 0.02,
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "generic": {
        # Balanced profile for general prose
        "tricolon": 0.15,
        "antithesis": 0.12,
        "anaphora": 0.12,
        "litotes": 0.12,
        "anadiplosis": 0.10,
        "asyndeton": 0.08,
        "epistrophe": 0.08,
        "hyperbole": 0.06,
        "chiasmus": 0.06,
        "hyperbaton": 0.05,
        "polyptoton": 0.03,
        "polysyndeton": 0.03,
    },
    "website_landing": {
        # Landing page copy - punchy, benefit-focused
        "tricolon": 0.22,      # Benefit lists, features
        "antithesis": 0.20,    # Before/after, with/without
        "asyndeton": 0.15,     # Speed, urgency
        "anaphora": 0.12,      # Building momentum
        "hyperbole": 0.08,     # Bold claims (tastefully)
        "epistrophe": 0.06,
        "anadiplosis": 0.05,
        "litotes": 0.05,
        "chiasmus": 0.04,
        "hyperbaton": 0.02,
        "polyptoton": 0.01,
        "polysyndeton": 0.00,
    },
    "ad_copy": {
        # Short-form ads - maximum impact, minimum words
        "antithesis": 0.25,    # Strong contrast
        "asyndeton": 0.22,     # Speed and punch
        "tricolon": 0.18,      # Memorable three-part
        "hyperbole": 0.10,     # Attention-grabbing
        "anaphora": 0.08,
        "litotes": 0.06,
        "epistrophe": 0.05,
        "chiasmus": 0.03,
        "hyperbaton": 0.02,
        "anadiplosis": 0.01,
        "polyptoton": 0.00,
        "polysyndeton": 0.00,
    },
    "course_description": {
        # Product/course descriptions - value-building
        "tricolon": 0.20,      # What you'll learn lists
        "anaphora": 0.18,      # Building value ("You'll...")
        "anadiplosis": 0.15,   # Connecting benefits
        "antithesis": 0.12,    # Before/after transformation
        "asyndeton": 0.10,     # Quick benefit lists
        "litotes": 0.08,       # Understated credibility
        "epistrophe": 0.06,
        "hyperbole": 0.04,
        "chiasmus": 0.04,
        "hyperbaton": 0.02,
        "polyptoton": 0.01,
        "polysyndeton": 0.00,
    },
    "article_technical": {
        # Technical tutorials, deep-dives, how-to guides
        "tricolon": 0.20,      # Steps, features, lists
        "asyndeton": 0.18,     # Punchy instruction sequences
        "anaphora": 0.15,      # Emphasising patterns
        "anadiplosis": 0.12,   # Connecting concepts
        "antithesis": 0.10,    # Before/after, old/new way
        "litotes": 0.08,       # Understated British observations
        "epistrophe": 0.05,
        "hyperbole": 0.04,
        "chiasmus": 0.03,
        "hyperbaton": 0.03,
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "article_thought": {
        # Thought pieces, opinion, industry analysis
        "antithesis": 0.22,    # Challenging conventional wisdom
        "anaphora": 0.18,      # Building persuasive momentum
        "chiasmus": 0.12,      # Memorable, quotable conclusions
        "anadiplosis": 0.10,   # Narrative flow
        "tricolon": 0.10,      # Structured arguments
        "litotes": 0.08,       # Understated confidence
        "hyperbaton": 0.06,    # Emphasis through unusual order
        "epistrophe": 0.05,
        "hyperbole": 0.04,
        "asyndeton": 0.03,
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "article_linkedin": {
        # LinkedIn long-form articles - blend of technical and provocative
        "antithesis": 0.18,    # Attention-grabbing contrasts
        "anaphora": 0.16,      # Building emotional momentum
        "anadiplosis": 0.14,   # Narrative flow between sections
        "tricolon": 0.12,      # Structured takeaways
        "litotes": 0.10,       # British understatement
        "chiasmus": 0.08,      # Quotable endings
        "asyndeton": 0.06,     # Punchy lists
        "hyperbaton": 0.05,
        "epistrophe": 0.04,
        "hyperbole": 0.04,
        "polyptoton": 0.02,
        "polysyndeton": 0.01,
    },
    "reddit_technical": {
        # Reddit technical tutorials - depth, code-first, understated
        "tricolon": 0.18,      # Listing steps, features, learnings
        "asyndeton": 0.16,     # Punchy technical sequences
        "litotes": 0.16,       # Understated British humour lands well on Reddit
        "antithesis": 0.12,    # Before/after, old way/new way
        "anadiplosis": 0.10,   # Connecting concepts in tutorials
        "anaphora": 0.08,      # Emphasis without feeling salesy
        "epistrophe": 0.06,
        "hyperbaton": 0.05,
        "chiasmus": 0.04,
        "hyperbole": 0.03,     # Low - Reddit distrusts exaggeration
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "reddit_discussion": {
        # Reddit discussion starters - provocative but genuine, debate-friendly
        "antithesis": 0.22,    # Framing debates, contrasting positions
        "anaphora": 0.16,      # Building arguments with repetition
        "litotes": 0.14,       # Dry understatement, very Reddit-compatible
        "tricolon": 0.12,      # Structured argument points
        "anadiplosis": 0.08,   # Connecting ideas in longer posts
        "chiasmus": 0.08,      # Memorable, quotable conclusions
        "hyperbaton": 0.06,    # Unusual phrasing grabs attention
        "epistrophe": 0.05,
        "asyndeton": 0.04,
        "hyperbole": 0.03,     # Low - sincerity over exaggeration
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "reddit_showcase": {
        # Reddit project showcases - show don't tell, honest, technical
        "antithesis": 0.20,    # Problem/solution, before/after, cost comparison
        "tricolon": 0.18,      # Feature lists, results summaries
        "anadiplosis": 0.14,   # Building narrative momentum
        "litotes": 0.12,       # Self-deprecating honesty
        "asyndeton": 0.10,     # Quick feature/result lists
        "anaphora": 0.08,      # Emphasis in results sections
        "epistrophe": 0.06,
        "chiasmus": 0.04,
        "hyperbaton": 0.04,
        "hyperbole": 0.02,     # Very low - let numbers speak
        "polyptoton": 0.01,
        "polysyndeton": 0.01,
    },
    "proposal_direct": {
        # Consulting proposals - understated credibility, logical flow
        "litotes": 0.22,       # Understated credibility, very British
        "antithesis": 0.20,    # Current state vs proposed, problem vs solution
        "anadiplosis": 0.14,   # Logical flow between sections
        "tricolon": 0.12,      # Deliverables, benefits, approach steps
        "asyndeton": 0.12,     # Punchy capability lists without brochure feel
        "anaphora": 0.06,
        "epistrophe": 0.05,
        "chiasmus": 0.04,
        "hyperbaton": 0.03,
        "hyperbole": 0.02,     # Very low - credibility, not hype
        "polyptoton": 0.00,
        "polysyndeton": 0.00,  # Too slow for proposals
    },
    "medium_technical": {
        # Medium technical prose - all concepts explained in flowing narrative, no code/tables
        # Audio-optimised: favour devices that land when heard, not seen
        "anaphora": 0.20,      # Repetitive starts build rhythm when listened to
        "anadiplosis": 0.18,   # Chain-linking concepts flows naturally as speech
        "antithesis": 0.14,    # Contrasts are clear and powerful in audio
        "polysyndeton": 0.12,  # Extra conjunctions create natural spoken cadence
        "tricolon": 0.10,      # Rule of three works in speech but can feel like a list
        "litotes": 0.08,       # Understatement lands well when heard
        "epistrophe": 0.06,    # End repetition works as audio emphasis
        "hyperbole": 0.04,
        "chiasmus": 0.03,      # Harder to catch when listening
        "asyndeton": 0.02,     # Omitting conjunctions can feel choppy in audio
        "hyperbaton": 0.02,    # Unusual word order can confuse listeners
        "polyptoton": 0.01,
    },
    "medium_story": {
        # Medium personal narrative - spoken storytelling, emotional flow
        # Audio-optimised: devices that build narrative momentum when heard
        "anadiplosis": 0.22,   # Chain-linking creates irresistible narrative pull
        "polysyndeton": 0.16,  # "And then... and then..." is natural storytelling
        "anaphora": 0.14,      # Repetitive starts build emotional momentum
        "litotes": 0.12,       # Understated moments are powerful in personal stories
        "antithesis": 0.10,    # Then vs now, expected vs reality
        "epistrophe": 0.08,    # End repetition for emotional landing
        "tricolon": 0.06,      # Occasional, not dominant in narrative
        "hyperbole": 0.04,     # Casual exaggeration feels natural in stories
        "chiasmus": 0.03,
        "hyperbaton": 0.02,
        "asyndeton": 0.02,     # Low - stories need conjunctions for flow
        "polyptoton": 0.01,
    },
    "medium_analysis": {
        # Medium industry analysis/opinion - persuasive prose for audio consumption
        # Audio-optimised: devices that build argument when heard
        "antithesis": 0.20,    # Contrasting positions is the core of analysis
        "anaphora": 0.18,      # Building persuasive cadence
        "anadiplosis": 0.14,   # Connecting argument threads naturally
        "polysyndeton": 0.10,  # Accumulation of evidence feels weighty when heard
        "litotes": 0.10,       # Understated confidence, very British
        "tricolon": 0.08,      # Structured argument points
        "epistrophe": 0.06,    # Reinforcing conclusions
        "chiasmus": 0.05,      # Memorable reversals for key points
        "hyperbole": 0.04,
        "hyperbaton": 0.03,
        "asyndeton": 0.01,     # Very low - analysis needs smooth flow
        "polyptoton": 0.01,
    },
}

# Transition compatibility matrix
# Some devices pair well together, others don't
TRANSITIONS = {
    "tricolon": ["antithesis", "epistrophe", "litotes"],
    "antithesis": ["tricolon", "chiasmus", "anaphora"],
    "anaphora": ["epistrophe", "tricolon", "anadiplosis"],
    "epistrophe": ["anaphora", "chiasmus", "tricolon"],
    "anadiplosis": ["anaphora", "tricolon", "litotes"],
    "hyperbaton": ["litotes", "antithesis", "tricolon"],
    "chiasmus": ["antithesis", "epistrophe", "litotes"],
    "polyptoton": ["tricolon", "anaphora", "anadiplosis"],
    "asyndeton": ["tricolon", "anaphora", "hyperbaton"],
    "polysyndeton": ["anadiplosis", "anaphora", "epistrophe"],
    "hyperbole": ["litotes", "antithesis", "tricolon"],
    "litotes": ["hyperbole", "antithesis", "chiasmus"],
}


def sample_devices(
    content_type: str,
    count: int = 3,
    recent_devices: Optional[list[str]] = None,
    seed: Optional[int] = None
) -> list[dict]:
    """
    Sample rhetorical devices using probability distributions.

    Uses Dirichlet-modified weights to encourage variety when recent
    devices are provided.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)

    if content_type not in PROFILES:
        raise ValueError(f"Unknown content type: {content_type}. "
                        f"Available: {list(PROFILES.keys())}")

    profile = PROFILES[content_type].copy()

    # Apply Dirichlet-style penalty for recently used devices
    if recent_devices:
        for device in recent_devices:
            if device in profile:
                profile[device] *= 0.3  # Reduce probability of recent devices

    # Normalise weights to sum to 1
    total = sum(profile.values())
    weights = [profile[d] / total for d in DEVICES.keys()]
    device_names = list(DEVICES.keys())

    # Sample first device
    selected = []
    first_device = np.random.choice(device_names, p=weights)
    selected.append(first_device)

    # Sample remaining devices considering transitions
    for _ in range(count - 1):
        last_device = selected[-1]
        compatible = TRANSITIONS.get(last_device, device_names)

        # Boost compatible devices
        adjusted_weights = []
        for i, name in enumerate(device_names):
            if name in selected:
                adjusted_weights.append(0)  # Don't repeat
            elif name in compatible:
                adjusted_weights.append(weights[i] * 1.5)  # Boost compatible
            else:
                adjusted_weights.append(weights[i])

        # Normalise
        total = sum(adjusted_weights)
        if total == 0:
            break
        adjusted_weights = [w / total for w in adjusted_weights]

        next_device = np.random.choice(device_names, p=adjusted_weights)
        selected.append(next_device)

    # Build output
    results = []
    for device_name in selected:
        device = DEVICES[device_name]
        results.append({
            "device": device.name,
            "definition": device.definition,
            "example": device.example,
            "suggested_placement": device.placement,
        })

    return results


def format_output(devices: list[dict], content_type: str) -> str:
    """Format the selected devices for display."""
    lines = [
        f"# Rhetorical Recipe for {content_type.replace('_', ' ').title()}",
        "",
        f"Selected {len(devices)} devices for your content:",
        ""
    ]

    for i, d in enumerate(devices, 1):
        lines.extend([
            f"## {i}. {d['device']}",
            f"**What it is**: {d['definition']}",
            f"**Example**: \"{d['example']}\"",
            f"**Use in**: {d['suggested_placement']}",
            ""
        ])

    lines.extend([
        "---",
        "Remember: Use these naturally. If a device doesn't fit, skip it.",
        "The goal is elegance, not forced cleverness."
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Mozart-inspired rhetorical device selector"
    )
    parser.add_argument(
        "--type", "-t",
        choices=list(PROFILES.keys()),
        help="Content type to generate devices for"
    )
    parser.add_argument(
        "--count", "-c",
        type=int,
        default=3,
        help="Number of devices to select (default: 3)"
    )
    parser.add_argument(
        "--recent", "-r",
        nargs="*",
        default=[],
        help="Recently used devices to avoid (for variety)"
    )
    parser.add_argument(
        "--seed", "-s",
        type=int,
        default=None,
        help="Random seed for reproducibility"
    )
    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List available content types"
    )

    args = parser.parse_args()

    if args.list_types:
        print("Available content types:")
        for t in PROFILES.keys():
            print(f"  - {t}")
        return

    if not args.type:
        parser.error("the following arguments are required: --type/-t")

    devices = sample_devices(
        content_type=args.type,
        count=args.count,
        recent_devices=args.recent,
        seed=args.seed
    )

    print(format_output(devices, args.type))


if __name__ == "__main__":
    main()
