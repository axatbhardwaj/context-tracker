#!/usr/bin/env python3
"""Wiki parser for context-tracker plugin.

Extracts structured sections from wiki-format context.md files.
"""

import re
from typing import List
from dataclasses import dataclass, field

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WikiKnowledge:
    """Structured wiki knowledge base.

    Provides type-safe contract between parser and merger (IDE autocomplete, clear interface).
    All section fields use empty lists (never None) to simplify merge logic.
    """
    architecture: str = ""
    decisions: List[str] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    key_symbols: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    recent_work: List[str] = field(default_factory=list)


def parse(content: str) -> WikiKnowledge:
    """Parse wiki markdown into WikiKnowledge.

    Regex pattern `## SectionName` is reliable for wiki format; full markdown
    parser (mistune, markdown-it) would be overkill for 5 known sections.

    Args:
        content: Markdown content with ## Section headers

    Returns:
        WikiKnowledge with extracted sections
    """
    try:
        wiki = WikiKnowledge()

        # Extract Architecture section (text block, not list)
        # Anchored with ^ to avoid matching ### headers (e.g. ### Architecture in legacy files)
        arch_match = re.search(
            r'^## Architecture[^\n]*\n(.*?)(?=\n## |\Z)',
            content,
            re.DOTALL | re.MULTILINE
        )
        if arch_match:
            wiki.architecture = arch_match.group(1).strip()

        # Extract list sections
        wiki.decisions = _extract_list_items(content, 'Decisions')
        wiki.patterns = _extract_list_items(content, 'Patterns')
        wiki.key_symbols = _extract_list_items(content, 'Key Symbols')
        wiki.issues = _extract_list_items(content, 'Issues')
        wiki.recent_work = _extract_list_items(content, 'Recent Work')

        return wiki

    except Exception as e:
        # Wiki parse failure preserved via fallback; user can manually fix structure
        logger.warning(f"Wiki parse failed: {e}")
        return WikiKnowledge()


def _extract_list_items(content: str, section_name: str) -> List[str]:
    """Extract bullet list items from section.

    Handles both - and * bullet styles. Whitespace normalized.

    Args:
        content: Markdown content
        section_name: Section header (without ##)

    Returns:
        List of item strings
    """
    # Anchored with ^ to avoid matching ### headers (e.g. ### Decisions in legacy files)
    pattern = rf'^## {section_name}[^\n]*\n(.*?)(?=\n## |\Z)'
    match = re.search(pattern, content, re.DOTALL | re.MULTILINE)

    if not match:
        return []

    section_content = match.group(1)

    # Extract lines starting with - or *
    items = re.findall(r'^[\-\*]\s+(.+)$', section_content, re.MULTILINE)

    return [item.strip() for item in items]


def has_empty_sections(wiki: WikiKnowledge) -> bool:
    """Check if wiki has empty Architecture, Patterns, or Key Symbols sections.

    Returns True when any enrichable section contains only placeholder text
    or is empty. Enables short-circuit enrichment: skip LLM calls if all
    sections are already user-populated.

    Args:
        wiki: WikiKnowledge instance to check

    Returns:
        True if any of Architecture, Patterns, or Key Symbols is empty
    """
    placeholder_pattern = r'_No .* yet\._'

    if not wiki.architecture or re.search(placeholder_pattern, wiki.architecture):
        return True

    if not wiki.patterns or not wiki.key_symbols:
        return True

    return False
