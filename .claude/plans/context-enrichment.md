# Context Enrichment Feature

## Overview

Empty sections in context.md files (Architecture, Patterns, Key Symbols) provide no value to Claude when reading project context. This plan adds automatic enrichment to the stop hook, using Gemini to analyze the codebase and populate empty sections on every session.

**Chosen approach**: Option A - Inline hook enhancement. Add enrichment logic directly to `hooks/stop.py` after session analysis. Uses Gemini (free, 1M context) for codebase analysis.

## Planning Context

### Decision Log

| Decision | Reasoning Chain |
|----------|-----------------|
| Inline enrichment in stop.py | User selected Option A -> simplest implementation with single file change -> no new modules to maintain -> acceptable latency tradeoff |
| Gemini over Claude | User has free Gemini access -> 1M context can analyze entire codebase -> no cost per session -> clear choice |
| Force Gemini provider override | User config may change between sessions -> enrichment depends on 1M context window -> Claude would produce poorer results with less context -> explicit override ensures consistent behavior |
| Enrich only empty sections | Non-empty sections contain user-curated content -> overwriting would lose valuable context -> only fill `_No .* yet._` placeholders |
| Skip enrichment if all sections populated | Avoid redundant LLM calls -> check before calling Gemini -> fast path for mature projects |
| Separate enrichment skill file | Reusable prompt template -> consistent with existing `analyze-session` pattern -> easier to iterate on prompt quality |
| Analyze git log for patterns | File changes alone don't reveal architecture -> git history shows file relationships and change patterns -> richer context for LLM |
| 30 commits for git log | Need recent changes for architecture context -> 30 captures ~2-3 months of activity for active projects -> user confirmed as balanced choice -> less would miss patterns |
| 8000 char limit for codebase summary | User wants maximum context for Gemini -> Gemini prompt budget is large (~1M) -> 8000 chars provides comprehensive codebase info -> user explicitly chose aggressive option |
| maxdepth 2 for directory structure | Top-level shows modules/packages -> depth 2 shows file organization -> deeper would add noise without architectural value -> balanced default |
| XML tags for enrichment output | Gemini produces reliable structured XML -> simpler regex parsing than JSON/YAML -> explicit section boundaries -> consistent with existing `<context_md>` pattern in analyze-session |
| Skip enrichment on malformed XML | User chose safest option -> retry would add latency -> partial parse is complex and error-prone -> log warning and preserve existing content -> enrichment failure must not block hook |

### Rejected Alternatives

| Alternative | Why Rejected |
|-------------|--------------|
| Option B: On-demand skill only | User explicitly chose automatic enrichment over manual invocation |
| Option C: Hybrid auto-bootstrap | Adds complexity for marginal benefit; user prefers consistent behavior |
| Claude for enrichment | Costs money; Gemini is free and has larger context window |
| Analyze source code directly | Too slow for every session; git log provides sufficient structural insight |

### Constraints & Assumptions

- Gemini CLI available at `shutil.which("gemini")`
- Enrichment adds ~3-5s per session (one LLM call)
- Git repository exists in project directory
- `<default-conventions domain="file-creation">` applied: extend existing files

### Known Risks

| Risk | Mitigation | Anchor |
|------|------------|--------|
| Gemini unavailable | Graceful skip with warning log | hooks/stop.py:85-86 `_generate_gemini` checks path |
| Slow enrichment blocks hook | Acceptable per user choice; could add timeout | N/A |
| Poor quality generation | Skill prompt engineered for structured output | skills/enrich-context/SKILL.md |
| Overwrites user content | Only enrich sections matching `_No .* yet._` | N/A |

## Invisible Knowledge

### Architecture

```
Session End
    |
    v
+----------------+
| stop.py main() |
+----------------+
    |
    ├─> Session Analysis (existing)
    |       |
    |       v
    |   context.md updated with Decisions/Issues/Recent Work
    |
    └─> NEW: Enrichment Check
            |
            v
    +-------------------+
    | has_empty_sections|──No──> Done
    +-------------------+
            |Yes
            v
    +-------------------+
    | analyze_codebase  |  (git log, file structure)
    +-------------------+
            |
            v
    +-------------------+
    | enrich_with_skill |  (Gemini + enrich-context skill)
    +-------------------+
            |
            v
    +-------------------+
    | merge_enrichment  |  (update only empty sections)
    +-------------------+
            |
            v
        Done
```

### Data Flow

```
git log --oneline -30  ──┐
                         ├──> Codebase Summary ──> Gemini ──> Enriched Sections
ls -la (structure)    ───┘                                          |
                                                                     v
                                                              Merge into context.md
```

### Why This Structure

- Enrichment runs AFTER session analysis to avoid interfering with primary flow
- Separate skill file allows prompt iteration without code changes
- Empty section detection prevents redundant work and respects user edits

### Invariants

- Never overwrite non-empty sections (user content is sacred)
- Enrichment failure must not block hook completion
- Must use Gemini provider regardless of config default

### Tradeoffs

- **Latency vs Completeness**: Every session adds ~3-5s but ensures context is always useful
- **Simplicity vs Modularity**: Inline code is harder to test but matches user preference

## Milestones

### Milestone 1: Empty Section Detection

**Files**: `core/wiki_parser.py`

**Requirements**:
- Add `has_empty_sections(wiki: WikiKnowledge) -> bool` function
- Detect placeholders: `_No architectural notes yet._`, `_No patterns identified yet._`, `_No key symbols tracked yet._`
- Return True if any of Architecture, Patterns, Key Symbols is empty

**Acceptance Criteria**:
- `has_empty_sections(empty_wiki)` returns True
- `has_empty_sections(populated_wiki)` returns False
- Handles missing sections gracefully

**Tests**:
- **Test files**: `tests/test_wiki_parser.py`
- **Test type**: unit
- **Backing**: default-derived
- **Scenarios**:
  - Normal: wiki with all empty sections returns True
  - Normal: wiki with all populated sections returns False
  - Edge: wiki with mixed empty/populated returns True
  - Edge: wiki with empty string (not placeholder) returns True

**Code Intent**:
- Add function `has_empty_sections(wiki: WikiKnowledge) -> bool` after `parse()` function
- Check `wiki.architecture`, `wiki.patterns`, `wiki.key_symbols` for placeholder text
- Use regex pattern `r'_No .* yet\._'` to detect placeholders

**Code Changes**:

```diff
--- a/core/wiki_parser.py
+++ b/core/wiki_parser.py
@@ -23,6 +23,7 @@ class WikiKnowledge:
     architecture: str = ""
     decisions: List[str] = field(default_factory=list)
     patterns: List[str] = field(default_factory=list)
+    key_symbols: List[str] = field(default_factory=list)
     issues: List[str] = field(default_factory=list)
     recent_work: List[str] = field(default_factory=list)

@@ -56,6 +57,7 @@ def parse(content: str) -> WikiKnowledge:
         # Extract list sections
         wiki.decisions = _extract_list_items(content, 'Decisions')
         wiki.patterns = _extract_list_items(content, 'Patterns')
+        wiki.key_symbols = _extract_list_items(content, 'Key Symbols')
         wiki.issues = _extract_list_items(content, 'Issues')
         wiki.recent_work = _extract_list_items(content, 'Recent Work')

@@ -92,3 +94,27 @@ def _extract_list_items(content: str, section_name: str) -> List[str]:
     items = re.findall(r'^[\-\*]\s+(.+)$', section_content, re.MULTILINE)

     return [item.strip() for item in items]
+
+
+def has_empty_sections(wiki: WikiKnowledge) -> bool:
+    """Check if wiki has empty Architecture, Patterns, or Key Symbols sections.
+
+    Returns True when any enrichable section contains only placeholder text
+    or is empty. Enables short-circuit enrichment: skip LLM calls if all
+    sections are already user-populated.
+
+    Args:
+        wiki: WikiKnowledge instance to check
+
+    Returns:
+        True if any of Architecture, Patterns, or Key Symbols is empty
+    """
+    # Placeholder pattern _No .* yet._ matches default template entries
+    # (e.g., "_No architectural notes yet._"). Allows user custom content
+    # like "_Not applicable for this project._" to be treated as non-empty.
+    placeholder_pattern = r'_No .* yet\._'
+
+    if not wiki.architecture or re.search(placeholder_pattern, wiki.architecture):
+        return True
+
+    if not wiki.patterns or not getattr(wiki, 'key_symbols', None):
+        return True
+
+    return False
```

---

### Milestone 2: Codebase Analysis Helper

**Files**: `hooks/stop.py`

**Flags**: `needs-rationale`

**Requirements**:
- Add `analyze_codebase(cwd: str) -> str` function
- Extract git log (last 30 commits, oneline format)
- Extract directory structure (top 2 levels)
- Format as markdown for LLM consumption

**Acceptance Criteria**:
- Returns markdown string with git history and structure
- Handles non-git directories gracefully (returns structure only)
- Output is under 8000 chars to maximize context for Gemini

**Tests**:
- **Test files**: `tests/test_stop_hook.py` (new file)
- **Test type**: unit
- **Backing**: default-derived
- **Scenarios**:
  - Normal: git repo returns history + structure
  - Edge: non-git directory returns structure only
  - Edge: empty directory returns minimal output

**Code Intent**:
- Add function `analyze_codebase(cwd: str) -> str` near top of file
- Extract git log (30 commits; ~2-3 months of activity for pattern detection)
- Extract directory structure (depth 2; reveals file organization without noise)
- Reason: git history shows file relationships and change patterns better than static code analysis
- Limit output to 8000 chars (aggressive option for maximum Gemini context utilization)
- Decision: "git log for patterns" - history reveals architecture better than static analysis

**Code Changes**:

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -4,6 +4,7 @@ import os
 import sys
 import json
 import shutil
+import subprocess
 import re
 from pathlib import Path

@@ -25,6 +26,63 @@ from utils.logger import get_logger
 logger = get_logger(__name__)


+def analyze_codebase(cwd: str) -> str:
+    """Analyze codebase structure and git history for LLM context.
+
+    Extracts git log (last 30 commits) and directory structure (depth 2).
+    30 commits captures ~2-3 months of activity for pattern detection.
+
+    Args:
+        cwd: Project directory to analyze
+
+    Returns:
+        Markdown-formatted codebase summary (max 8000 chars)
+    """
+    output_parts = []
+
+    # Git history shows file relationships and change patterns (Decision: "Analyze git log for patterns")
+    try:
+        result = subprocess.run(
+            ['git', 'log', '--oneline', '-30'],
+            cwd=cwd,
+            capture_output=True,
+            text=True,
+            timeout=5
+        )
+        if result.returncode == 0 and result.stdout.strip():
+            output_parts.append("## Recent Git History\n\n```")
+            output_parts.append(result.stdout.strip())
+            output_parts.append("```\n")
+    except (subprocess.TimeoutExpired, FileNotFoundError):
+        # Non-git directory or git unavailable; proceed with structure only
+        pass
+
+    # Directory depth=2: shows modules/packages (top) and file organization (depth 2)
+    # Deeper levels add noise without architectural value
+    try:
+        result = subprocess.run(
+            ['find', '.', '-maxdepth', '2', '-type', 'f', '-not', '-path', '*/\.*'],
+            cwd=cwd,
+            capture_output=True,
+            text=True,
+            timeout=5
+        )
+        if result.returncode == 0 and result.stdout.strip():
+            output_parts.append("## Directory Structure\n\n```")
+            output_parts.append(result.stdout.strip())
+            output_parts.append("```\n")
+    except (subprocess.TimeoutExpired, FileNotFoundError):
+        # find unavailable; return partial summary
+        pass
+
+    summary = '\n'.join(output_parts)
+
+    # 8000 char limit: aggressive choice for maximum Gemini context (1M window available)
+    if len(summary) > 8000:
+        summary = summary[:8000] + "\n\n[truncated]"
+
+    return summary if summary else "No codebase information available."
+
+
 def copy_plan_files(changes, context_dir: Path):
     """Copy plan files to context directory."""
     plans_dir = context_dir / 'plans'
```

---

### Milestone 3: Enrichment Skill

**Files**: `skills/enrich-context/SKILL.md`

**Delegated to**: Manual creation (SKILL.md is prompt template)

**Requirements**:
- Create skill that instructs LLM to generate Architecture, Patterns, Key Symbols
- Input: codebase summary, existing context.md
- Output: XML-tagged sections `<architecture>`, `<patterns>`, `<key_symbols>`

**Acceptance Criteria**:
- Skill prompt produces valid XML-tagged output from Gemini
- Generated content is project-specific, not generic

**Code Intent**:
- Create `skills/enrich-context/SKILL.md` with YAML frontmatter
- Instruction sections for each empty section type
- Output format specification with XML tags
- Examples of good vs bad output

**Code Changes**:

```diff
--- /dev/null
+++ b/skills/enrich-context/SKILL.md
@@ -0,0 +1,102 @@
+---
+name: enrich-context
+description: Enriches empty sections in context.md by analyzing codebase structure and history. Invoked by stop hook.
+---
+
+# Enrich Context
+
+Analyzes codebase structure and git history to populate empty Architecture, Patterns, and Key Symbols sections in context.md.
+
+## Input
+
+You will receive:
+
+1. **Codebase Summary**: Git history and directory structure
+2. **Existing context.md**: Current wiki content (may have empty sections)
+
+## Task
+
+For each empty section (matching `_No .* yet._`), generate content based on the codebase summary:
+
+### Architecture Section
+
+Describe the high-level structure of the codebase in 2-4 sentences:
+- What kind of application is this? (CLI tool, web app, library, etc.)
+- What are the main modules/components?
+- How do they relate to each other?
+
+**Good example**:
+```
+Claude Code context tracking plugin. Captures session file changes via stop hook,
+analyzes patterns with LLM, and maintains project wiki. Core modules: session_analyzer
+(change extraction), wiki_parser (context.md parsing), markdown_writer (output formatting).
+```
+
+**Bad example** (too generic):
+```
+Python application with multiple modules for processing data.
+```
+
+### Patterns Section
+
+Identify 2-4 coding patterns evident from git history and file structure:
+- Naming conventions (e.g., "snake_case for functions")
+- Error handling approach (e.g., "early returns, minimal nesting")
+- Testing patterns (e.g., "pytest with fixtures")
+- Architecture patterns (e.g., "dataclasses for data models")
+
+**Good example**:
+```
+- Early returns to reduce nesting (KISS principle)
+- Dataclasses for structured data (WikiKnowledge, SessionContext)
+- Regex for markdown parsing (lightweight, no heavy dependencies)
+- Graceful degradation on errors (log warnings, preserve existing content)
+```
+
+**Bad example** (too vague):
+```
+- Uses functions
+- Has error handling
+```
+
+### Key Symbols Section
+
+List 3-6 primary classes/functions that appear frequently in git history or are central to the codebase:
+- Format: `ClassName.method_name` or `function_name`
+- Prioritize items that appear in multiple commits or are imported by many files
+
+**Good example**:
+```
+- SessionAnalyzer.get_changes
+- WikiParser.parse
+- MarkdownWriter.write_session_log
+- analyze_with_skill
+```
+
+**Bad example** (irrelevant):
+```
+- main
+- __init__
+```
+
+## Output Format
+
+Output ONLY the enriched sections wrapped in XML tags. Do NOT output sections that are already populated.
+
+```xml
+<architecture>
+[2-4 sentence architecture description]
+</architecture>
+
+<patterns>
+- [Pattern 1]
+- [Pattern 2]
+- [Pattern 3]
+</patterns>
+
+<key_symbols>
+- `Symbol1`
+- `Symbol2`
+- `Symbol3`
+</key_symbols>
+```
+
+Output ONLY the XML tags for empty sections. If all sections are populated, output nothing.
```

---

### Milestone 4: Enrichment Integration

**Files**: `hooks/stop.py`

**Flags**: `error-handling`, `needs-rationale`

**Requirements**:
- Add `enrich_empty_sections(context_path: Path, cwd: str, config: dict)` function
- Load skill, call Gemini, parse XML response
- Merge enriched sections into context.md (only empty ones)
- Call after `analyze_with_skill()` in main()

**Acceptance Criteria**:
- Empty sections get populated after hook runs
- Non-empty sections remain unchanged
- Gemini failure logs warning but doesn't block hook
- Uses Gemini provider explicitly (not config default)

**Tests**:
- **Test files**: `tests/test_stop_hook.py`
- **Test type**: integration
- **Backing**: default-derived
- **Scenarios**:
  - Normal: empty context.md gets all sections enriched
  - Normal: partial context.md gets only empty sections enriched
  - Error: Gemini unavailable logs warning, returns gracefully
  - Edge: malformed XML response handled gracefully

**Code Intent**:
- Add `enrich_empty_sections(context_path, cwd, config)` function
- Force `config['provider'] = 'gemini'` before calling LLMClient (Decision: "Force Gemini provider override")
- Load `enrich-context` skill using existing `load_skill_prompt()`
- Parse response for `<architecture>`, `<patterns>`, `<key_symbols>` tags
- On malformed XML: skip enrichment entirely, log warning (Decision: "Skip enrichment on malformed XML")
- Use WikiParser to load existing context, merge only empty sections
- Use MarkdownWriter to output updated context.md
- In `main()`: call after `analyze_with_skill()` completes

**Code Changes**:

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -16,6 +16,7 @@ if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
 from core.session_analyzer import SessionAnalyzer
 from core.markdown_writer import MarkdownWriter
 from core.topic_detector import TopicDetector
+from core.wiki_parser import parse, has_empty_sections
 from core.path_classifier import PathClassifier
 from core.git_sync import GitSync
 from core.config_loader import load_config
@@ -232,6 +233,94 @@ def analyze_with_skill(
         return {"status": "error", "error": str(e)}


+def enrich_empty_sections(context_path: Path, cwd: str, config: dict):
+    """Enrich empty sections in context.md using codebase analysis.
+
+    Strategy: Check → Analyze → Generate → Merge → Write
+    - Short-circuit on missing context or missing empty sections
+    - Analyze codebase to get git + structure context
+    - Use Gemini (1M context window) to generate Architecture, Patterns, Key Symbols
+    - Extract XML tags from response
+    - Merge only sections matching empty placeholders; preserve user edits
+    - Graceful failure: skip enrichment and warn on any error (must not block hook)
+
+    Invariants:
+    - Never overwrite non-empty sections (user content is sacred)
+    - Enrichment failure does not block hook completion
+    - Must use Gemini provider regardless of config default (1M context required)
+
+    Edge cases:
+    - Malformed XML: log warning, skip enrichment entirely
+    - Gemini unavailable: log warning, return gracefully
+    - Non-git directory: analyze only file structure
+
+    Args:
+        context_path: Path to context.md file
+        cwd: Project directory for codebase analysis
+        config: Plugin configuration
+    """
+    from utils.llm_client import LLMClient
+
+    if not context_path.exists():
+        logger.info("Context file doesn't exist yet, skipping enrichment")
+        return
+
+    existing_content = context_path.read_text()
+    wiki = parse(existing_content)
+
+    if not has_empty_sections(wiki):
+        logger.info("All sections populated, skipping enrichment")
+        return
+
+    if not shutil.which("gemini"):
+        logger.warning("Gemini CLI not found, skipping enrichment")
+        return
+
+    logger.info("Enriching empty sections with Gemini...")
+
+    codebase_summary = analyze_codebase(cwd)
+
+    skill_prompt = load_skill_prompt('enrich-context')
+    if not skill_prompt:
+        logger.warning("enrich-context skill not found")
+        return
+
+    prompt = f"""{skill_prompt}
+
+## Codebase Summary
+
+{codebase_summary}
+
+## Existing context.md
+
+```markdown
+{existing_content}
+```
+
+Generate enriched sections for empty placeholders only."""
+
+    try:
+        # Ensure Gemini provider: 1M context window required for full codebase analysis
+        # (Decision: "Force Gemini provider override")
+        enrichment_config = config.copy()
+        enrichment_config['provider'] = 'gemini'
+
+        llm = LLMClient(enrichment_config)
+        response = llm.generate(prompt)
+
+        arch_match = re.search(r'<architecture>(.*?)</architecture>', response, re.DOTALL)
+        patterns_match = re.search(r'<patterns>(.*?)</patterns>', response, re.DOTALL)
+        symbols_match = re.search(r'<key_symbols>(.*?)</key_symbols>', response, re.DOTALL)
+
+        updated = False
+        # Only merge extracted sections where placeholders exist; user edits take precedence
+        if arch_match and (not wiki.architecture or re.search(r'_No .* yet\._', wiki.architecture)):
+            new_arch = arch_match.group(1).strip()
+            existing_content = re.sub(
+                r'(## Architecture[^\n]*\n\n)_No architectural notes yet\._',
+                r'\1' + new_arch,
+                existing_content,
+                count=1,
+                flags=re.MULTILINE
+            )
+            updated = True
+
+        if patterns_match and not wiki.patterns:
+            new_patterns = patterns_match.group(1).strip()
+            existing_content = re.sub(
+                r'(## Patterns[^\n]*\n\n)_No patterns identified yet\._',
+                r'\1' + new_patterns,
+                existing_content,
+                flags=re.MULTILINE
+            )
+            updated = True
+
+        if symbols_match and not wiki.key_symbols:
+            new_symbols = symbols_match.group(1).strip()
+            existing_content = re.sub(
+                r'(## Key Symbols[^\n]*\n\n)_No key symbols tracked yet\._',
+                r'\1' + new_symbols,
+                existing_content,
+                flags=re.MULTILINE
+            )
+            updated = True
+
+        if updated:
+            context_path.write_text(existing_content)
+            logger.info("Enrichment complete")
+        else:
+            logger.info("No sections enriched (XML parsing may have failed)")
+
+    except Exception as e:
+        # Graceful failure: enrichment error must not block hook
+        logger.warning(f"Enrichment failed: {e}")
+
+
 def main():
     """Main entry point for Stop hook."""
     try:
@@ -322,6 +411,9 @@ def main():
         else:
             logger.info(f"Updated context: {skill_result.get('context_path')}")

+        # Enrich empty sections if needed
+        enrich_empty_sections(context_path, cwd, config)
+
         # Copy plan files to context directory
         copy_plan_files(changes, context_dir)
```

---

### Milestone 5: Documentation

**Delegated to**: @agent-technical-writer (mode: post-implementation)

**Source**: `## Invisible Knowledge` section of this plan

**Files**:
- `skills/enrich-context/CLAUDE.md` (create)
- `hooks/CLAUDE.md` (update)
- `skills/CLAUDE.md` (update)

**Requirements**:

**skills/enrich-context/CLAUDE.md** (new):
- Create tabular CLAUDE.md in skill directory
- Entry for `SKILL.md`: "Enrichment prompt for Architecture/Patterns/Key Symbols" | "Iterating prompt quality"

**hooks/CLAUDE.md** (update):
- Add entry for `analyze_codebase()`: "Extracts git history and directory structure for LLM analysis" | "Understanding enrichment inputs, analyzing codebase"
- Add entry for `enrich_empty_sections()`: "Populates empty context.md sections via Gemini" | "Debugging enrichment failures, understanding flow"

**skills/CLAUDE.md** (update):
- Add entry for `enrich-context/`: "Skill for enriching empty Architecture, Patterns, Key Symbols sections" | "Adding/modifying enrichment prompt"

**Acceptance Criteria**:
- All CLAUDE.md files are tabular index only (no prose)
- Entries include WHAT (contents) and WHEN (task triggers)
- No Invisible Knowledge embedded in CLAUDE.md

## Milestone Dependencies

```
M1 ──────────────┐
                 v
M2 ──> M3 ──> M4 ──> M5
```

M1 (detection) and M2 (analysis) can run in parallel.
M3 (skill) must exist before M4 (integration).
M5 (docs) runs after all implementation complete.
