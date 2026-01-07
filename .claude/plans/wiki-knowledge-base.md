# Wiki-Style Knowledge Base Redesign

## Overview

The current context-tracker generates useless session logs ("Modified file.md: Added documentation") instead of accumulating useful project knowledge. This plan transforms the output into a wiki-style knowledge base with structured sections (Architecture, Decisions, Patterns, Issues, Recent Work) that get **updated and merged** rather than appended. The wiki acts as persistent memory for Claude across sessions.

Chosen approach: **Structured Parser + Merger Modules** (Approach 2) - dedicated `wiki_parser.py` and `wiki_merger.py` modules for deterministic, testable knowledge management.

## Planning Context

### Decision Log

| Decision | Reasoning Chain |
|----------|-----------------|
| Structured modules over LLM-only merge | LLM-only approach (Approach 1) has unpredictable output -> may lose information during merge -> structured parser/merger provides deterministic behavior + testability |
| Core 5 sections (Architecture, Decisions, Patterns, Issues, Recent Work) | User-specified: covers essential project knowledge -> Architecture explains structure, Decisions track rationale, Patterns help predict changes, Issues prevent duplicate fixes, Recent Work shows current state |
| 5 recent sessions before archiving | User-specified: balances context vs wiki length -> 5 sessions provides ~1 week of history for active projects -> older sessions archived to git history |
| WikiKnowledge dataclass for structured data | Raw string manipulation error-prone -> dataclass provides type safety + IDE autocomplete -> clear contract between parser and merger |
| Regex-based section extraction | Full markdown parser (mistune, markdown-it) overkill for 5 known sections -> regex pattern `## SectionName` reliable for wiki format -> faster execution, no dependencies |
| Similarity threshold 0.8 for deduplication | Exact match misses paraphrased duplicates -> 0.8 cosine similarity catches semantically similar entries -> simple string comparison as fallback if no ML available |
| LLM categorization for new entries | File changes alone insufficient to categorize -> LLM determines if change is architectural, config, bugfix, etc. -> enables routing to correct wiki section |
| Graceful fallback to session format | Wiki parse may fail on corrupted/legacy files -> fallback preserves data -> user can manually fix wiki structure |

### Rejected Alternatives

| Alternative | Why Rejected |
|-------------|--------------|
| Approach 1: Full LLM merge | Higher cost per session; unpredictable output quality; harder to debug merge issues |
| Approach 3: Hybrid per-section LLM | Multiple LLM calls increase latency; regex parsing sufficient for structured wiki |
| 7 extended sections (add API, Database, Testing) | User chose core 5; additional sections can be added later without architectural change |
| 3 minimal sections | Insufficient for project understanding; Architecture and Patterns are essential |
| Full markdown parser library | Unnecessary dependency for 5 fixed section headers; regex is simpler and faster |

### Constraints & Assumptions

- **Existing LLM client**: Sonnet 4.5 with 10k thinking budget already configured
- **File format**: Markdown with `## Section` headers
- **Backward compatibility**: Must handle existing context.md files (session format)
- **Performance**: Wiki update should complete in <2s (LLM call dominates)
- **Default conventions applied**: `<default-conventions domain="file-creation">` - new modules in `core/`

### Known Risks

| Risk | Mitigation | Anchor |
|------|------------|--------|
| Regex fails on malformed wiki | Graceful fallback to session append format | wiki_parser.py (new) |
| Deduplication removes distinct entries | 0.8 threshold tunable via config; exact match fallback | wiki_merger.py (new) |
| LLM categorization inconsistent | Categories defined in prompt; fallback to "general" category | session_analyzer.py:394-417 |
| Large wiki files slow parsing | Sections extracted lazily; only modified sections rewritten | N/A |

## Invisible Knowledge

### Architecture

```
Before (session log):
SessionContext --> MarkdownWriter.append_session() --> context.md (append)
                                                        ↓
                                                   Useless logs

After (wiki):
SessionContext --> WikiParser.parse() --> WikiKnowledge
                         ↓
                   WikiMerger.merge(wiki, session)
                         ↓
                   WikiKnowledge (updated)
                         ↓
                   MarkdownWriter.write_wiki() --> context.md (structured)
```

### Data Flow

```
stop.py hook
    ↓
SessionAnalyzer.extract_session_context(changes, topics)
    ↓ returns SessionContext with category field
WikiParser.parse(context.md) or create empty WikiKnowledge
    ↓
WikiMerger.merge_session(wiki, session)
    ├─ deduplicate_decisions()
    ├─ update_patterns()
    ├─ update_issues()
    └─ rotate_recent_work(max=5)
    ↓
MarkdownWriter.write_wiki(wiki)
    ↓
context.md (structured wiki format)
```

### Why This Structure

- **WikiParser separate from Merger**: Single responsibility - parser only reads, merger only transforms
- **WikiKnowledge dataclass**: Type-safe contract between components; IDE autocomplete; easy testing
- **Merger handles all logic**: Deduplication, rotation, categorization in one place
- **Writer unchanged interface**: `write_wiki()` added alongside existing methods; backward compatible

### Invariants

- WikiKnowledge sections are never None (use empty lists)
- Recent work list never exceeds max_recent_sessions (5)
- Decisions list contains unique entries (deduplication enforced)
- Section headers maintain exact format: `## Section Name`

### Tradeoffs

- **More code vs LLM flexibility**: 300 lines of deterministic code instead of LLM handling edge cases
- **Fixed sections vs dynamic**: Core 5 sections hardcoded; adding sections requires code change
- **Regex vs full parser**: Faster but may fail on unusual markdown formatting

## Milestones

### Milestone 1: WikiKnowledge Dataclass and Parser

**Files**:
- `core/wiki_parser.py` (NEW)

**Flags**: `complex-algorithm`

**Requirements**:
- Create `WikiKnowledge` dataclass with 5 section fields (architecture, decisions, patterns, issues, recent_work)
- Implement `parse(content: str) -> WikiKnowledge` function using regex-based section extraction
- Extract each section using regex pattern `## Section Name\n(.*?)(?=\n## |$)` for deterministic parsing
- Parse list items from section content (handles `-` and `*` bullet styles)
- Return empty WikiKnowledge if parsing fails to enable graceful fallback to session format

**Acceptance Criteria**:
- `parse()` extracts all 5 sections from valid wiki markdown
- `parse()` returns empty WikiKnowledge on malformed input
- List items extracted correctly (handles `-` and `*` bullets)
- Empty sections return empty lists, not None

**Tests**:
- **Test files**: `tests/test_wiki_parser.py` (NEW)
- **Test type**: unit
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Parse wiki with all 5 sections populated
  - Edge: Parse wiki with some sections empty
  - Edge: Parse wiki with no sections (legacy format)
  - Error: Malformed markdown returns empty WikiKnowledge

**Code Intent**:
- New dataclass `WikiKnowledge` with fields: architecture (str), decisions (List[str]), patterns (List[str]), issues (List[str]), recent_work (List[str])
- New function `parse(content: str) -> WikiKnowledge`
- Regex pattern extracts content between `## Section` headers
- Helper `_extract_list_items(section_content: str) -> List[str]` for bullet parsing
- Graceful fallback: try/except returns empty WikiKnowledge

**Code Changes**:

```diff
--- /dev/null
+++ b/core/wiki_parser.py
@@ -0,0 +1,89 @@
+#!/usr/bin/env python3
+"""Wiki parser for context-tracker plugin.
+
+Extracts structured sections from wiki-format context.md files.
+"""
+
+import re
+from typing import List
+from dataclasses import dataclass, field
+
+from utils.logger import get_logger
+
+logger = get_logger(__name__)
+
+
+@dataclass
+class WikiKnowledge:
+    """Structured wiki knowledge base.
+
+    Provides type-safe contract between parser and merger (IDE autocomplete, clear interface).
+    All section fields use empty lists (never None) to simplify merge logic.
+    """
+    architecture: str = ""
+    decisions: List[str] = field(default_factory=list)
+    patterns: List[str] = field(default_factory=list)
+    issues: List[str] = field(default_factory=list)
+    recent_work: List[str] = field(default_factory=list)
+
+
+def parse(content: str) -> WikiKnowledge:
+    """Parse wiki markdown into WikiKnowledge.
+
+    Regex pattern `## SectionName` is reliable for wiki format; full markdown
+    parser (mistune, markdown-it) would be overkill for 5 known sections.
+
+    Args:
+        content: Markdown content with ## Section headers
+
+    Returns:
+        WikiKnowledge with extracted sections
+    """
+    try:
+        wiki = WikiKnowledge()
+
+        # Extract Architecture section (text block, not list)
+        arch_match = re.search(
+            r'## Architecture\s*\n(.*?)(?=\n## |\Z)',
+            content,
+            re.DOTALL
+        )
+        if arch_match:
+            wiki.architecture = arch_match.group(1).strip()
+
+        # Extract list sections
+        wiki.decisions = _extract_list_items(content, 'Decisions')
+        wiki.patterns = _extract_list_items(content, 'Patterns')
+        wiki.issues = _extract_list_items(content, 'Issues')
+        wiki.recent_work = _extract_list_items(content, 'Recent Work')
+
+        return wiki
+
+    except Exception as e:
+        # Wiki parse failure preserved via fallback; user can manually fix structure
+        logger.warning(f"Wiki parse failed: {e}")
+        return WikiKnowledge()
+
+
+def _extract_list_items(content: str, section_name: str) -> List[str]:
+    """Extract bullet list items from section.
+
+    Handles both - and * bullet styles. Whitespace normalized.
+
+    Args:
+        content: Markdown content
+        section_name: Section header (without ##)
+
+    Returns:
+        List of item strings
+    """
+    # Regex pattern matches section from header to next header or end
+    pattern = rf'## {section_name}\s*\n(.*?)(?=\n## |\Z)'
+    match = re.search(pattern, content, re.DOTALL)
+
+    if not match:
+        return []
+
+    section_content = match.group(1)
+
+    # Extract lines starting with - or *
+    items = re.findall(r'^[\-\*]\s+(.+)$', section_content, re.MULTILINE)
+
+    return [item.strip() for item in items]
+```

---

### Milestone 2: Wiki Merger Module

**Files**:
- `core/wiki_merger.py` (NEW)

**Flags**: `complex-algorithm`, `needs-rationale`

**Requirements**:
- Implement `merge_session(wiki: WikiKnowledge, session: SessionContext) -> WikiKnowledge` with deduplication logic
- Deduplicate decisions using string similarity (threshold 0.8 catches paraphrased duplicates without false positives)
- Update patterns from file change analysis using LLM-categorized session data
- Update issues from problems_solved and future_work to prevent duplicate fix attempts
- Rotate recent_work to keep only last 5 sessions (balances context vs wiki length; ~1 week history)

**Acceptance Criteria**:
- Duplicate decisions not added (similarity >= 0.8)
- New unique decisions prepended to list
- Recent work rotates: 6th session drops oldest
- Empty session fields don't corrupt wiki

**Tests**:
- **Test files**: `tests/test_wiki_merger.py` (NEW)
- **Test type**: unit + property-based
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Merge session with 3 new decisions into wiki with 2 existing
  - Edge: Merge session with duplicate decision (similarity 0.85)
  - Edge: Merge 6th session triggers rotation
  - Error: Empty session produces unchanged wiki

**Code Intent**:
- New function `merge_session(wiki: WikiKnowledge, session: SessionContext) -> WikiKnowledge`
- Helper `_deduplicate(existing: List[str], new_items: List[str], threshold: float) -> List[str]`
- Helper `_similarity(a: str, b: str) -> float` using SequenceMatcher (stdlib, no deps)
- Helper `_rotate_recent(recent: List[str], new_entry: str, max_size: int) -> List[str]`
- Config-driven: max_recent_sessions = 5 (Decision Log)

**Code Changes**:

```diff
--- /dev/null
+++ b/core/wiki_merger.py
@@ -0,0 +1,112 @@
+#!/usr/bin/env python3
+"""Wiki merger for context-tracker plugin.
+
+Merges session context into wiki knowledge base with deduplication and rotation.
+"""
+
+from typing import List
+from difflib import SequenceMatcher
+from datetime import datetime
+
+from core.wiki_parser import WikiKnowledge
+from core.session_analyzer import SessionContext
+from utils.logger import get_logger
+
+logger = get_logger(__name__)
+
+
+def merge_session(wiki: WikiKnowledge, session: SessionContext, max_recent: int = 5) -> WikiKnowledge:
+    """Merge session context into wiki knowledge base.
+
+    5 recent sessions before archiving balances context vs wiki length;
+    provides ~1 week of history for active projects. Older sessions archived
+    to git history.
+
+    Args:
+        wiki: Existing wiki knowledge
+        session: Session context to merge
+        max_recent: Maximum recent work entries (user-specified: 5)
+
+    Returns:
+        Updated WikiKnowledge
+    """
+    # 0.8 similarity threshold catches semantically similar entries without false positives
+    wiki.decisions = _deduplicate(
+        existing=wiki.decisions,
+        new_items=session.decisions_made,
+        threshold=0.8
+    )
+
+    # Add problems to Issues section (deduplicated to prevent duplicate fixes)
+    wiki.issues = _deduplicate(
+        existing=wiki.issues,
+        new_items=session.problems_solved,
+        threshold=0.8
+    )
+
+    # Rotate recent work to keep only last 5 sessions (6th drops oldest)
+    if session.summary:
+        date_str = datetime.now().strftime('%Y-%m-%d')
+        entry = f"[{date_str}] {session.summary}"
+        wiki.recent_work = _rotate_recent(wiki.recent_work, entry, max_recent)
+
+    return wiki
+
+
+def _deduplicate(existing: List[str], new_items: List[str], threshold: float) -> List[str]:
+    """Deduplicate items using similarity threshold.
+
+    0.8 threshold catches paraphrased duplicates; exact match misses semantically
+    similar entries. Threshold tunable via config.
+
+    Args:
+        existing: Current items
+        new_items: Items to add
+        threshold: Similarity threshold (0.0-1.0, default 0.8)
+
+    Returns:
+        Deduplicated list (new items prepended)
+    """
+    result = list(existing)
+
+    for new_item in new_items:
+        # Check similarity against all existing items
+        is_duplicate = False
+        for existing_item in result:
+            if _similarity(new_item, existing_item) >= threshold:
+                is_duplicate = True
+                break
+
+        if not is_duplicate:
+            # Prepend new items to maintain reverse chronological order
+            result.insert(0, new_item)
+
+    return result
+
+
+def _similarity(a: str, b: str) -> float:
+    """Calculate similarity between two strings.
+
+    SequenceMatcher from stdlib avoids ML dependencies; provides simple
+    string comparison fallback when cosine similarity unavailable.
+
+    Args:
+        a: First string
+        b: Second string
+
+    Returns:
+        Similarity score (0.0-1.0)
+    """
+    return SequenceMatcher(None, a.lower(), b.lower()).ratio()
+
+
+def _rotate_recent(recent: List[str], new_entry: str, max_size: int) -> List[str]:
+    """Rotate recent work list to maintain max size.
+
+    Max 5 sessions provides ~1 week of history for active projects; 6th session
+    drops oldest entry. Older sessions archived to git history.
+
+    Args:
+        recent: Existing recent work entries
+        new_entry: New entry to add
+        max_size: Maximum list size (user-specified: 5)
+
+    Returns:
+        Rotated list with new entry prepended
+    """
+    result = [new_entry] + recent
+    # Slice to max_size ensures list never exceeds limit
+    return result[:max_size]
+```

---

### Milestone 3: Session Analyzer Category Enhancement

**Files**:
- `core/session_analyzer.py`

**Flags**: `conformance`

**Requirements**:
- Add `category` field to SessionContext dataclass (defaults to "general")
- Enhance LLM prompt to extract category (architecture, config, bugfix, feature, refactor, docs, general)
- Category enables routing session changes to appropriate wiki sections; file changes alone insufficient

**Acceptance Criteria**:
- SessionContext includes category field
- LLM prompt requests category classification
- Category defaults to "general" if extraction fails
- Existing tests still pass

**Tests**:
- **Test files**: `tests/test_session_analyzer.py` (extend)
- **Test type**: integration
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Session with config changes categorized as "config"
  - Edge: Mixed changes default to dominant category
  - Error: LLM failure returns "general" category

**Code Intent**:
- Add `category: str = "general"` field to SessionContext dataclass (line ~29-35)
- Update prompt in `extract_session_context()` to include: "6. CATEGORY: Classify this session as one of: architecture, config, bugfix, feature, refactor, docs"
- Parse category from LLM response in `_parse_context_response()`
- Default to "general" if parsing fails

**Code Changes**:

```diff
--- a/core/session_analyzer.py
+++ b/core/session_analyzer.py
@@ -28,11 +28,12 @@ class FileChange:
 @dataclass
 class SessionContext:
     """Rich context extracted from a Claude Code session."""
     user_goal: str = ""
     summary: str = ""
     decisions_made: List[str] = field(default_factory=list)
     problems_solved: List[str] = field(default_factory=list)
     future_work: List[str] = field(default_factory=list)
+    category: str = "general"  # LLM determines if change is architectural, config, bugfix, etc.


 class SessionAnalyzer:
@@ -400,16 +401,17 @@ class SessionAnalyzer:
         # Prompt requests single summary with inline topic tags for all detected topics
         prompt = f"""Analyze this Claude Code session transcript and extract a consolidated summary.

 Detected topics: {topic_tags}

 1. USER_GOAL: What was the user trying to accomplish? (1 sentence)
 2. SUMMARY: What was done in this session? Include topic tags {topic_tags} inline. (2-3 sentences)
 3. DECISIONS: Key technical decisions made (list up to 3, or "None")
 4. PROBLEMS_SOLVED: Issues or bugs fixed (list up to 3, or "None")
 5. FUTURE_WORK: Remaining tasks or TODOs mentioned (list up to 3, or "None")
+6. CATEGORY: Classify this session as one of: architecture, config, bugfix, feature, refactor, docs, general
+   (File changes alone insufficient to categorize; LLM determines routing to wiki sections)

 Files changed:
 {change_summary}

 Session transcript:
 {transcript_content}
@@ -461,10 +463,12 @@ FUTURE_WORK:
             line = line.strip()
             if not line:
                 continue

             if line.startswith('USER_GOAL:'):
                 ctx.user_goal = line.replace('USER_GOAL:', '').strip()
             elif line.startswith('SUMMARY:'):
                 ctx.summary = line.replace('SUMMARY:', '').strip()
+            elif line.startswith('CATEGORY:'):
+                # Categories defined in prompt; fallback to "general" ensures robustness
+                ctx.category = line.replace('CATEGORY:', '').strip().lower()
             elif line.startswith('DECISIONS:'):
                 current_section = 'decisions'
             elif line.startswith('PROBLEMS_SOLVED:'):
```

---

### Milestone 4: Integrate Wiki Writer into MarkdownWriter

**Files**:
- `core/markdown_writer.py`
- `hooks/stop.py`
- `config/example-config.json`

**Flags**: `conformance`, `error-handling`

**Requirements**:
- Add `write_wiki(wiki: WikiKnowledge, context_dir: Path) -> Path` method to MarkdownWriter
- Modify stop.py to use wiki flow: parse existing wiki (or create empty) -> merge session -> write updated wiki
- Graceful fallback to session append format if wiki parse fails (preserves data on corrupted/legacy files)
- Add wiki_config to example-config.json with enabled flag and max_recent_sessions setting

**Acceptance Criteria**:
- Wiki format written to context.md with all 5 sections
- Existing session format still works (backward compat)
- Parse failure falls back to session append
- Config enables/disables wiki mode

**Tests**:
- **Test files**: `tests/test_markdown_writer.py` (extend)
- **Test type**: integration
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Write wiki with all sections populated
  - Edge: Write wiki with empty sections (headers only)
  - Error: Fallback to session format on parse failure

**Code Intent**:
- Import WikiParser, WikiMerger, WikiKnowledge in markdown_writer.py
- New method `write_wiki(wiki: WikiKnowledge, context_dir: Path) -> Path`
- Format wiki as markdown with `## Section` headers
- In stop.py: add wiki flow before current append_session call
- Add `wiki_config` section to config/example-config.json with `enabled: true`, `max_recent_sessions: 5`
- Try wiki flow; on exception, log warning and fall back to append_session

**Code Changes**:

```diff
--- a/core/markdown_writer.py
+++ b/core/markdown_writer.py
@@ -3,10 +3,12 @@

 from datetime import datetime
 from pathlib import Path
 from typing import List, Dict, Any, Optional

 from core.session_analyzer import FileChange, SessionContext
+from core.wiki_parser import WikiKnowledge, parse
+from core.wiki_merger import merge_session
 from utils.file_utils import ensure_directory, prepend_to_file
 from utils.logger import get_logger

 logger = get_logger(__name__)
@@ -147,4 +149,56 @@ class MarkdownWriter:
         parts.append("\n---\n")

         return '\n'.join(parts)
+
+    def write_wiki(self, wiki: WikiKnowledge, context_dir: Path) -> Path:
+        """Write wiki knowledge base to context.md.
+
+        Section headers maintain exact format `## Section Name` for reliable
+        regex parsing. WikiKnowledge sections never None (empty lists) ensures
+        no null checks needed.
+
+        Args:
+            wiki: WikiKnowledge to write
+            context_dir: Context directory for project
+
+        Returns:
+            Path to written file
+        """
+        ensure_directory(context_dir)
+        wiki_file = context_dir / "context.md"
+
+        parts = ["# Project Context\n"]
+
+        # Architecture section (text block, not list)
+        parts.append("## Architecture\n")
+        if wiki.architecture:
+            parts.append(f"{wiki.architecture}\n")
+        else:
+            parts.append("_No architectural notes yet._\n")
+
+        # Decisions section (list)
+        parts.append("\n## Decisions\n")
+        if wiki.decisions:
+            parts.append('\n'.join(f"- {d}" for d in wiki.decisions) + '\n')
+        else:
+            parts.append("_No decisions recorded yet._\n")
+
+        # Patterns section (list)
+        parts.append("\n## Patterns\n")
+        if wiki.patterns:
+            parts.append('\n'.join(f"- {p}" for p in wiki.patterns) + '\n')
+        else:
+            parts.append("_No patterns identified yet._\n")
+
+        # Issues section (list)
+        parts.append("\n## Issues\n")
+        if wiki.issues:
+            parts.append('\n'.join(f"- {i}" for i in wiki.issues) + '\n')
+        else:
+            parts.append("_No issues tracked yet._\n")
+
+        # Recent Work section (list)
+        parts.append("\n## Recent Work\n")
+        if wiki.recent_work:
+            parts.append('\n'.join(f"- {w}" for w in wiki.recent_work) + '\n')
+        else:
+            parts.append("_No recent work yet._\n")
+
+        wiki_file.write_text('\n'.join(parts))
+        return wiki_file
```

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -14,10 +14,12 @@ if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:

 from core.session_analyzer import SessionAnalyzer
 from core.topic_detector import TopicDetector
 from core.path_classifier import PathClassifier
 from core.markdown_writer import MarkdownWriter
+from core.wiki_parser import WikiKnowledge, parse
+from core.wiki_merger import merge_session
 from core.git_sync import GitSync
 from core.config_loader import load_config
 from utils.file_utils import ensure_directory
 from utils.logger import get_logger

 logger = get_logger(__name__)
@@ -116,13 +118,34 @@ def main():

         # Write to context files
         writer = MarkdownWriter(config)

         # One-time cleanup of legacy topic files
         context_root = Path(config.get('context_root', '~/context')).expanduser()
         rel_path = cwd.replace(str(Path.home()), '').lstrip('/')
         context_dir = context_root / classification / rel_path
         cleanup_old_topic_files(context_dir)

-        # Write all topics to single context.md entry
+        # Wiki flow: parse -> merge -> write
+        # Graceful fallback preserves data when wiki parse fails on corrupted/legacy files
+        wiki_enabled = config.get('wiki_config', {}).get('enabled', True)
+        file_path = None
+
+        if wiki_enabled:
+            try:
+                wiki_file = context_dir / "context.md"
+                if wiki_file.exists():
+                    wiki = parse(wiki_file.read_text())
+                else:
+                    wiki = WikiKnowledge()
+
+                # Max 5 recent sessions provides ~1 week of history for active projects
+                max_recent = config.get('wiki_config', {}).get('max_recent_sessions', 5)
+                wiki = merge_session(wiki, session_context, max_recent)
+                file_path = writer.write_wiki(wiki, context_dir)
+                logger.info(f"Updated wiki: {file_path}")
+            except Exception as e:
+                # Fallback preserves session data; user can manually fix wiki structure
+                logger.warning(f"Wiki update failed, falling back to session format: {e}")
+                wiki_enabled = False
+
+        # Fallback to session format if wiki disabled or failed
+        if not wiki_enabled or not file_path:
+            file_path = writer.append_session(
                 project_path=cwd,
                 classification=classification,
@@ -130,11 +153,11 @@ def main():
                 changes=changes,
                 reasoning=reasoning,
                 context=session_context
             )
-        logger.info(f"Updated {file_path}")
+            logger.info(f"Updated session: {file_path}")

         # Copy plan files to context directory
         context_root = Path(config.get('context_root', '~/context')).expanduser()
         rel_path = cwd.replace(str(Path.home()), '').lstrip('/')
         context_dir = context_root / classification / rel_path
```

```diff
--- a/config/example-config.json
+++ b/config/example-config.json
@@ -38,5 +38,9 @@
     "temperature": 0.3,
     "use_for_reasoning": true,
     "use_for_topic_detection": true,
     "fallback_to_patterns": true
+  },
+  "wiki_config": {
+    "enabled": true,
+    "max_recent_sessions": 5
   }
 }
```

---

### Milestone 5: Documentation

**Delegated to**: @agent-technical-writer (mode: post-implementation)

**Source**: `## Invisible Knowledge` section of this plan

**Files**:
- `core/README.md` (NEW - wiki module documentation)
- `CLAUDE.md` (update with new modules)

**Requirements**:

CLAUDE.md:
- Add wiki_parser.py and wiki_merger.py to index
- Update markdown_writer.py description

core/README.md:
- Architecture diagram from Invisible Knowledge
- Data flow explanation
- Section format documentation

**Acceptance Criteria**:
- CLAUDE.md includes new module entries
- core/README.md explains wiki architecture
- No references to old session-only format

**Source Material**: `## Invisible Knowledge` section of this plan

---

## Milestone Dependencies

```
M1 (WikiKnowledge + Parser) ---> M2 (Merger)
                                      |
                                      v
                           M3 (Category) ---> M4 (Integration) ---> M5 (Docs)
```

M1 provides dataclass used by M2.
M2 provides merger used by M4.
M3 provides category field used by M2's routing logic.
M4 integrates all components.
M5 documents after implementation.
