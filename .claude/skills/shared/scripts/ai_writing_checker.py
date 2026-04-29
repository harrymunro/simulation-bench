#!/usr/bin/env python3
"""
AI Writing Checker

Scans markdown content for AI-tell patterns: banned vocabulary, banned phrases,
structural uniformity, em dashes, rule-of-three compulsions, negative parallelisms,
and formal transition density.

Usage:
    python ai_writing_checker.py <markdown_file>

Outputs JSON report to stdout.
"""

import json
import math
import re
import sys
from pathlib import Path
from typing import Any


def strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (between --- markers) from text."""
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    remainder = text[end + 3:]
    # Strip single leading newline that immediately follows the closing ---
    if remainder.startswith("\n"):
        remainder = remainder[1:]
    return remainder


def _word_count(text: str) -> int:
    """Count words in a string."""
    return len(text.split())


def _std_dev(values: list[float]) -> float:
    """Calculate population standard deviation."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((v - mean) ** 2 for v in values) / len(values)
    return math.sqrt(variance)


def _match_banned_word(token: str, all_banned: set[str]) -> str | None:
    """Return the canonical banned word if token is an inflected form, else None."""
    if token in all_banned:
        return token
    # Check common English inflections: -s, -es, -ed, -ing, -ly, -ness, -tion
    for banned in all_banned:
        if (
            token == banned + "s"
            or token == banned + "es"
            or token == banned + "d"
            or token == banned + "ed"
            or token == banned + "ing"
            or token == banned + "ly"
            or token == banned + "ness"
            or token == banned + "tion"
            or (banned.endswith("e") and token == banned[:-1] + "ing")
            or (banned.endswith("e") and token == banned[:-1] + "ed")
        ):
            return banned
    return None


def check_banned_vocabulary(
    lines: list[str], banned_words: dict[str, list[str]]
) -> list[dict[str, Any]]:
    """Check for AI-overused individual words. Returns findings list."""
    all_banned = set()
    for category_words in banned_words.values():
        all_banned.update(w.lower() for w in category_words)

    word_counts: dict[str, dict[str, Any]] = {}

    for line_num, line in enumerate(lines, start=1):
        words = re.findall(r"[a-zA-Z'-]+", line.lower())
        for word in words:
            stripped = word.strip("'-")
            canonical = _match_banned_word(stripped, all_banned)
            if canonical is not None:
                if canonical not in word_counts:
                    word_counts[canonical] = {"count": 0, "lines": []}
                word_counts[canonical]["count"] += 1
                if line_num not in word_counts[canonical]["lines"]:
                    word_counts[canonical]["lines"].append(line_num)

    findings = []
    for word, data in sorted(word_counts.items()):
        severity = "flag" if data["count"] >= 2 else "warning"
        findings.append({
            "word": word,
            "count": data["count"],
            "lines": data["lines"],
            "severity": severity,
        })

    return findings


def check_banned_phrases(
    lines: list[str], banned_phrases: list[str]
) -> list[dict[str, Any]]:
    """Check for multi-word AI-tell phrases. Returns findings list."""
    findings = []

    for line_num, line in enumerate(lines, start=1):
        line_lower = line.lower()
        for phrase in banned_phrases:
            if phrase.lower() in line_lower:
                findings.append({
                    "phrase": phrase.lower(),
                    "line": line_num,
                    "severity": "flag",
                })

    return findings


def check_structural_uniformity(text: str) -> dict[str, Any] | None:
    """Check paragraph length variance. Returns finding or None if OK."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    if len(paragraphs) < 3:
        return None

    lengths = [float(_word_count(p)) for p in paragraphs]
    sd = _std_dev(lengths)
    threshold = 5.0

    if sd < threshold:
        return {
            "check": "structural_uniformity",
            "severity": "flag",
            "detail": f"Paragraph length StdDev: {sd:.1f} words (threshold: {threshold})",
            "paragraph_lengths": [int(l) for l in lengths],
        }

    return None


def check_em_dashes(lines: list[str]) -> list[dict[str, Any]]:
    """Check for em dash characters. Returns findings list."""
    findings = []

    for line_num, line in enumerate(lines, start=1):
        if "\u2014" in line or " \u2013 " in line or " -- " in line or " \u2014 " in line:
            findings.append({
                "line": line_num,
                "severity": "flag",
                "snippet": line.strip()[:80],
            })

    return findings


def check_rule_of_three(text: str) -> list[dict[str, Any]]:
    """Heuristic detection of rule-of-three patterns. Returns findings list."""
    findings = []

    bullet_pattern = re.compile(r"^[\s]*[-*]\s+(.+)$", re.MULTILINE)
    lines = text.split("\n")

    bullet_groups: list[list[tuple[int, str]]] = []
    current_group: list[tuple[int, str]] = []

    for i, line in enumerate(lines):
        match = bullet_pattern.match(line)
        if match:
            current_group.append((i + 1, match.group(1)))
        else:
            if current_group:
                bullet_groups.append(current_group)
                current_group = []
    if current_group:
        bullet_groups.append(current_group)

    for group in bullet_groups:
        if len(group) == 3:
            lengths = [_word_count(item[1]) for item in group]
            if lengths[0] > 0:
                max_len = max(lengths)
                min_len = min(lengths)
                if max_len > 0 and (min_len / max_len) > 0.5:
                    findings.append({
                        "type": "three_similar_bullets",
                        "lines": [item[0] for item in group],
                        "severity": "info",
                        "detail": f"3 bullet points of similar length ({lengths})",
                    })

    # Match: word[s], word[s], and word[s] — limit each group to 1-2 words so
    # preceding context ("SimPy is") doesn't get absorbed into group 1.
    tricolon_pattern = re.compile(
        r"(\w+(?:\s+\w+){0,1}),\s+(\w+(?:\s+\w+){0,1}),\s+and\s+(\w+(?:\s+\w+){0,1})"
    )
    for i, line in enumerate(lines):
        for match in tricolon_pattern.finditer(line):
            parts = [match.group(1), match.group(2), match.group(3)]
            lengths = [_word_count(p) for p in parts]
            max_len = max(lengths)
            min_len = min(lengths)
            # Accept if all parts are short (1-2 words) or similarly sized (ratio > 0.5)
            all_short = all(ln <= 2 for ln in lengths)
            similar = max_len > 0 and (min_len / max_len) > 0.5
            if similar or all_short:
                findings.append({
                    "type": "tricolon_phrase",
                    "line": i + 1,
                    "severity": "info",
                    "detail": f"Tricolon: '{match.group(0)}'",
                })

    return findings


def check_negative_parallelism(lines: list[str]) -> list[dict[str, Any]]:
    """Check for 'not just X, but also Y' patterns. Returns findings list."""
    patterns = [
        re.compile(r"not\s+just\b.*?\bbut\s+also\b", re.IGNORECASE),
        re.compile(r"not\s+only\b.*?\bbut\b", re.IGNORECASE),
        re.compile(r"not\s+merely\b.*?\bbut\b", re.IGNORECASE),
        re.compile(r"not\s+simply\b.*?\bbut\b", re.IGNORECASE),
    ]

    findings = []
    for line_num, line in enumerate(lines, start=1):
        for pattern in patterns:
            if pattern.search(line):
                findings.append({
                    "line": line_num,
                    "severity": "flag",
                    "snippet": line.strip()[:80],
                })
                break

    return findings


def check_transition_density(
    lines: list[str],
    transition_words: list[str] | None = None,
) -> dict[str, Any] | None:
    """Check density of formal transition words at sentence starts."""
    if transition_words is None:
        transition_words = []

    prose_lines = [
        l for l in lines
        if l.strip()
        and not l.strip().startswith(("#", "-", "*", ">", "`", "|"))
    ]

    if len(prose_lines) < 5:
        return None

    transition_count = 0
    for line in prose_lines:
        line_lower = line.strip().lower()
        for tw in transition_words:
            if line_lower.startswith(tw.lower()):
                transition_count += 1
                break

    density = transition_count / len(prose_lines)
    threshold = 0.10

    if density > threshold:
        return {
            "check": "transition_density",
            "severity": "flag",
            "detail": (
                f"Transition word density: {density:.0%} "
                f"({transition_count}/{len(prose_lines)} prose lines, "
                f"threshold: {threshold:.0%})"
            ),
        }

    return None


def run_all_checks(
    raw_content: str,
    file_path: str,
    vocab_data: dict[str, Any],
) -> dict[str, Any]:
    """Run all 7 checks and return structured JSON report."""
    content = strip_frontmatter(raw_content)
    lines = content.split("\n")
    non_empty_lines = [l for l in lines if l.strip()]

    checks: list[dict[str, Any]] = []

    vocab_findings = check_banned_vocabulary(
        non_empty_lines, vocab_data["banned_words"]
    )
    if vocab_findings:
        checks.append({
            "check": "banned_vocabulary",
            "severity": max(
                (f["severity"] for f in vocab_findings),
                key=lambda s: {"flag": 2, "warning": 1, "info": 0}.get(s, 0),
            ),
            "findings": vocab_findings,
        })

    phrase_findings = check_banned_phrases(
        non_empty_lines, vocab_data["banned_phrases"]
    )
    if phrase_findings:
        checks.append({
            "check": "banned_phrases",
            "severity": "flag",
            "findings": phrase_findings,
        })

    structural = check_structural_uniformity(content)
    if structural:
        checks.append(structural)

    em_findings = check_em_dashes(non_empty_lines)
    if em_findings:
        checks.append({
            "check": "em_dashes",
            "severity": "flag",
            "findings": em_findings,
        })

    three_findings = check_rule_of_three(content)
    if three_findings:
        checks.append({
            "check": "rule_of_three",
            "severity": "info",
            "findings": three_findings,
        })

    parallel_findings = check_negative_parallelism(non_empty_lines)
    if parallel_findings:
        checks.append({
            "check": "negative_parallelism",
            "severity": "flag",
            "findings": parallel_findings,
        })

    transition_result = check_transition_density(
        non_empty_lines,
        transition_words=vocab_data.get("transition_words", []),
    )
    if transition_result:
        checks.append(transition_result)

    severity_weights = {"flag": 2, "warning": 1, "info": 0}
    score = 0
    flag_count = 0
    warning_count = 0
    info_count = 0

    for check in checks:
        sev = check.get("severity", "info")
        if "findings" in check:
            for finding in check["findings"]:
                f_sev = finding.get("severity", sev)
                score += severity_weights.get(f_sev, 0)
                if f_sev == "flag":
                    flag_count += 1
                elif f_sev == "warning":
                    warning_count += 1
                else:
                    info_count += 1
        else:
            score += severity_weights.get(sev, 0)
            if sev == "flag":
                flag_count += 1
            elif sev == "warning":
                warning_count += 1
            else:
                info_count += 1

    return {
        "file": file_path,
        "score": score,
        "checks": checks,
        "summary": f"{flag_count} flags, {warning_count} warnings, {info_count} info",
    }


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python ai_writing_checker.py <markdown_file>", file=sys.stderr)
        sys.exit(1)

    file_path = Path(sys.argv[1])
    if not file_path.exists():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        sys.exit(1)

    script_dir = Path(__file__).resolve().parent
    data_file = script_dir.parent / "data" / "ai_vocabulary.json"
    if not data_file.exists():
        print(f"Error: vocabulary data not found: {data_file}", file=sys.stderr)
        sys.exit(1)

    with open(data_file) as f:
        vocab_data = json.load(f)

    raw_content = file_path.read_text()
    result = run_all_checks(raw_content, str(file_path), vocab_data)

    print(json.dumps(result, indent=2))

    sys.exit(0 if result["score"] == 0 else 1)


if __name__ == "__main__":
    main()
