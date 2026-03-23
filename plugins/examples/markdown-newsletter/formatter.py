"""
Markdown Newsletter Formatter — Content Format Plugin

Converts intelligence findings into a clean weekly newsletter format.
Outputs Markdown suitable for email platforms (Buttondown, ConvertKit, etc.)
or direct publishing.

Config:
  newsletter_name: str (default "Intelligence Briefing")
  max_items: int (default 20)
  include_metadata: bool (default False)
  sections: list[str] (default [] = all categories)
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone


def _categorize_findings(findings: list[dict]) -> dict[str, list[dict]]:
    """Group findings by category."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for f in findings:
        category = f.get("category", "general")
        groups[category].append(f)
    return dict(groups)


def _priority_score(finding: dict) -> float:
    """Score a finding for newsletter ordering. Higher = more important."""
    score = 0.0
    # Boost findings with high relevance/confidence
    meta = finding.get("metadata", {})
    score += meta.get("relevance", 0.5) * 2
    score += meta.get("confidence", 0.5)
    # Boost findings with clear summaries
    if len(finding.get("summary", "")) > 50:
        score += 0.5
    # Boost price drops and stock events (actionable)
    event = meta.get("event", "")
    if event in ("price_change", "out_of_stock", "back_in_stock"):
        score += 1.0
    return score


def _section_title(category: str) -> str:
    """Convert a category slug to a readable section title."""
    titles = {
        "regulatory": "Regulatory Updates",
        "ecommerce": "E-Commerce Watch",
        "news": "Industry News",
        "academic": "Research & Studies",
        "community": "Community Buzz",
        "competitors": "Competitor Moves",
        "general": "Notable Findings",
        "plugin": "Plugin Findings",
    }
    return titles.get(category, category.replace("-", " ").replace("_", " ").title())


def _section_emoji(category: str) -> str:
    """Return a thematic section divider character (not emoji in body text)."""
    dividers = {
        "regulatory": "---",
        "ecommerce": "---",
        "news": "---",
        "academic": "---",
        "community": "---",
        "competitors": "---",
    }
    return dividers.get(category, "---")


def format(findings: list[dict], config: dict) -> str:
    """
    Format intelligence findings into a weekly newsletter.

    Args:
        findings: List of finding dicts from the intelligence pipeline
        config: Plugin configuration

    Returns:
        Formatted Markdown string
    """
    name = config.get("newsletter_name", "Intelligence Briefing")
    max_items = config.get("max_items", 20)
    include_metadata = config.get("include_metadata", False)
    allowed_sections = config.get("sections", [])

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%B %d, %Y")

    # Sort by priority and limit
    sorted_findings = sorted(findings, key=_priority_score, reverse=True)[:max_items]

    # Group by category
    grouped = _categorize_findings(sorted_findings)

    # Filter sections if specified
    if allowed_sections:
        grouped = {k: v for k, v in grouped.items() if k in allowed_sections}

    # Build newsletter
    lines = []

    # Header
    lines.append(f"# {name}")
    lines.append("")
    lines.append(f"*Week of {date_str}*")
    lines.append("")
    lines.append(f"> {len(sorted_findings)} findings from {len(grouped)} categories this week.")
    lines.append("")

    # Table of contents
    if len(grouped) > 1:
        lines.append("## In This Issue")
        lines.append("")
        for category in grouped:
            title = _section_title(category)
            count = len(grouped[category])
            anchor = category.lower().replace(" ", "-")
            lines.append(f"- [{title}](#{anchor}) ({count})")
        lines.append("")

    # Sections
    for category, items in grouped.items():
        title = _section_title(category)
        lines.append("---")
        lines.append("")
        lines.append(f"## {title}")
        lines.append("")

        for item in items:
            item_title = item.get("title", "Untitled")
            summary = item.get("summary", "")
            url = item.get("url", "")
            source = item.get("source", "")

            # Item title with link
            if url:
                lines.append(f"### [{item_title}]({url})")
            else:
                lines.append(f"### {item_title}")
            lines.append("")

            # Summary
            if summary:
                lines.append(summary)
                lines.append("")

            # Source attribution
            if source:
                source_label = source.replace("plugin:", "").replace("-", " ").title()
                lines.append(f"*Source: {source_label}*")
                lines.append("")

            # Optional metadata
            if include_metadata and item.get("metadata"):
                meta = item["metadata"]
                meta_items = []
                for k, v in meta.items():
                    if k not in ("event",):
                        meta_items.append(f"**{k}**: {v}")
                if meta_items:
                    lines.append(f"<details><summary>Details</summary>")
                    lines.append("")
                    lines.append(" | ".join(meta_items))
                    lines.append("")
                    lines.append("</details>")
                    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append(f"*Generated by OpenClaw Intelligence on {now.strftime('%Y-%m-%d %H:%M UTC')}*")
    lines.append("")
    lines.append("To configure this newsletter, edit `config.json` in the markdown-newsletter plugin directory.")
    lines.append("")

    return "\n".join(lines)
