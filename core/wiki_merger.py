#!/usr/bin/env python3
"""Wiki merger for context-tracker plugin.

Merges session context into wiki knowledge base with deduplication and rotation.
"""

from datetime import datetime
from difflib import SequenceMatcher
from typing import List

from core.session_analyzer import SessionContext
from core.wiki_parser import WikiKnowledge
from utils.logger import get_logger

logger = get_logger(__name__)


def merge_session(
    wiki: WikiKnowledge, session: SessionContext, max_recent: int = 5
) -> WikiKnowledge:
    """Merge session context into wiki knowledge base.

    5 recent sessions before archiving balances context vs wiki length;
    provides ~1 week of history for active projects. Older sessions archived
    to git history.

    Args:
        wiki: Existing wiki knowledge
        session: Session context to merge
        max_recent: Maximum recent work entries (user-specified: 5)

    Returns:
        Updated WikiKnowledge
    """
    # 0.8 similarity threshold catches near-duplicate entries using string matching
    wiki.decisions = _deduplicate(
        existing=wiki.decisions, new_items=session.decisions_made, threshold=0.8
    )

    # Add problems to Issues section (deduplicated to prevent duplicate fixes)
    wiki.issues = _deduplicate(
        existing=wiki.issues, new_items=session.problems_solved, threshold=0.8
    )

    # Rotate recent work to keep only last 5 sessions (6th drops oldest)
    if session.summary:
        date_str = datetime.now().strftime("%Y-%m-%d")
        entry = f"[{date_str}] {session.summary}"
        wiki.recent_work = _rotate_recent(wiki.recent_work, entry, max_recent)

    return wiki


def _deduplicate(
    existing: List[str], new_items: List[str], threshold: float
) -> List[str]:
    """Deduplicate items using similarity threshold.

    0.8 threshold catches near-duplicate entries; uses SequenceMatcher for
    character-level comparison, not semantic similarity. Threshold tunable via config.

    Args:
        existing: Current items
        new_items: Items to add
        threshold: Similarity threshold (0.0-1.0, default 0.8)

    Returns:
        Deduplicated list (new items prepended)
    """
    result = [item for item in existing if isinstance(item, str) and item]

    for new_item in new_items:
        if not isinstance(new_item, str) or not new_item:
            continue

        is_duplicate = False
        for existing_item in result:
            if _similarity(new_item, existing_item) >= threshold:
                is_duplicate = True
                break

        if not is_duplicate:
            result.insert(0, new_item)

    return result


def _similarity(a: str, b: str) -> float:
    """Calculate similarity between two strings.

    SequenceMatcher from stdlib avoids ML dependencies; provides simple
    string comparison fallback when cosine similarity unavailable.

    Args:
        a: First string
        b: Second string

    Returns:
        Similarity score (0.0-1.0)
    """
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _rotate_recent(recent: List[str], new_entry: str, max_size: int) -> List[str]:
    """Rotate recent work list to maintain max size.

    Max 5 sessions provides ~1 week of history for active projects; 6th session
    drops oldest entry. Older sessions archived to git history.

    Args:
        recent: Existing recent work entries
        new_entry: New entry to add
        max_size: Maximum list size (user-specified: 5)

    Returns:
        Rotated list with new entry prepended

    Raises:
        ValueError: If max_size is not positive
    """
    if max_size <= 0:
        raise ValueError(f"max_size must be positive, got {max_size}")
    result = [new_entry] + recent
    # Slice to max_size ensures list never exceeds limit
    return result[:max_size]
