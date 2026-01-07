# Context Generation Consolidation Plan

## Overview

The claude-context-tracker plugin currently generates 7+ separate topic files per project (testing.md, configuration.md, etc.), resulting in fragmented, repetitive context. This plan consolidates output to a single `context.md` file per project using Sonnet 4.5 with extended thinking for richer summaries. Topics become inline metadata rather than separate files. Old topic files will be deleted for a clean slate.

Chosen approach: **Summary-Based Context with Extended Thinking** (Approach 2 per user selection).

## Planning Context

### Decision Log

| Decision | Reasoning Chain |
|----------|-----------------|
| Single context.md per project | Multiple topic files create fragmentation -> readers must correlate across files to understand a session -> single file presents complete session context in one location |
| Sonnet 4.5 with extended thinking | User needs richer summaries -> extended thinking provides deeper reasoning -> produces more coherent consolidated summaries than standard mode |
| Topics as inline tags | Per-topic files cause repetition -> same session scattered across files -> inline `[testing] [config]` tags preserve categorization without fragmentation |
| 20,000 token context | Current 150 token limit severely restricts LLM output -> 20k allows full session analysis -> matches transcript length being fed to LLM |
| Delete old topic files | User specified clean slate -> old format incompatible with new -> migration complexity exceeds value of preserving old data |
| Remove TopicDetector iteration | stop.py loops over topics creating files -> consolidated approach needs single write call -> topic detection still runs but output merges into one entry |
| Extended thinking budget 10,000 tokens | User-specified: good balance of quality and cost -> adds ~5-10s latency which is acceptable for background hook -> 5k too shallow, 16k excessive cost |
| Session summary max_tokens 2,000 | User-specified: sufficient for goal(200) + summary(400) + decisions(400) + problems(400) + future(400) + topic tags(200) -> 1k too restrictive for consolidated format |
| Marker file `.migrated` for cleanup | File presence check is simpler than version tracking -> prevents accidental re-deletion on subsequent runs -> hidden file doesn't clutter user context directory |
| Plans directory preservation (non-recursive cleanup) | List .md files in context dir root only -> plans/ subdirectory naturally excluded -> simpler than explicit exclusion logic |
| Timeout unchanged at 120s | Extended thinking adds 5-10s per session -> current 120s timeout provides 110s+ headroom -> no adjustment needed |

### Rejected Alternatives

| Alternative | Why Rejected |
|-------------|--------------|
| Approach 1: Minimal change (topic sub-sections) | Still verbose with section headers per topic; doesn't leverage extended thinking for summarization |
| Approach 3: Hybrid (separate consolidator class) | More complexity than needed; can achieve goal by modifying existing MarkdownWriter |
| Keep old files alongside new | User explicitly chose deletion; dual formats would confuse readers |
| Per-session files instead of append | Would create even more files; append-to-single-file matches user's 1-2 file target |

### Constraints & Assumptions

- **API constraint**: Extended thinking requires `thinking.type: enabled` and `budget_tokens` parameter
- **CLI constraint**: Using `claude` CLI subprocess; must pass model and thinking params correctly
- **Existing pattern**: MarkdownWriter.append_session() prepends entries (most recent first)
- **Default conventions applied**: `<default-conventions domain="file-creation">` - modify existing files over creating new

### Known Risks

| Risk | Mitigation | Anchor |
|------|------------|--------|
| Extended thinking CLI flags may differ | Test with `claude --help` before implementation; fallback to standard mode if unavailable | N/A |
| Large context.md files over time | Existing prepend pattern keeps recent at top; user can manually prune old entries | markdown_writer.py:L45-47 |
| Topic detection wasted if not used for files | Topics still valuable as inline tags; detection logic unchanged | topic_detector.py |

## Invisible Knowledge

### Architecture

```
Before (fragmented):
Session -> TopicDetector -> [topic1, topic2, topic3]
                                |       |       |
                                v       v       v
                           topic1.md topic2.md topic3.md

After (consolidated):
Session -> TopicDetector -> [topic1, topic2, topic3]
                                      |
                                      v
                              context.md (all topics as tags)
```

### Data Flow

```
stop.py hook input (stdin JSON)
         |
         v
SessionAnalyzer.get_changes() -> List[FileChange]
         |
         v
TopicDetector.detect_topics() -> Dict[topic: List[FileChange]]
         |
         v
SessionAnalyzer.extract_session_context() -> SessionContext
         |                                    (uses extended thinking)
         v
MarkdownWriter.append_session() -> writes single context.md
         |
         v
copy_plan_files() -> plans/ directory
         |
         v
GitSync.commit_and_push()
```

### Why This Structure

- TopicDetector preserved because topic tags provide useful categorization
- MarkdownWriter modified rather than replaced to maintain existing prepend logic
- LLM client upgraded in-place to minimize integration changes

### Invariants

- Each session produces exactly ONE append to context.md (not one per topic)
- Topics array always passed to writer even if empty (uses ["general-changes"] fallback)
- Extended thinking timeout must exceed standard timeout (LLM needs reasoning time)

### Tradeoffs

- **Higher LLM cost**: Extended thinking uses more tokens; accepted for better quality
- **Longer latency**: Extended thinking adds ~5-10s; acceptable for background hook
- **Lost topic file history**: Deleting old files loses historical context; user explicitly accepted

## Milestones

### Milestone 1: Upgrade LLM Client to Sonnet 4.5 with Extended Thinking

**Files**:
- `utils/llm_client.py`
- `config/example-config.json`
- `plugin.json`

**Flags**: `needs-rationale`

**Requirements**:
- Update default model to `claude-sonnet-4-5-20250514`
- Set max_tokens to 20000
- Add extended thinking support with budget_tokens parameter
- Update CLI call to pass thinking parameters

**Acceptance Criteria**:
- LLM client uses Sonnet 4.5 model by default
- Extended thinking enabled with 10000 budget_tokens
- Config files reflect new defaults
- Fallback to standard mode if extended thinking unavailable

**Tests**:
- **Test files**: `tests/test_llm_client.py` (create if not exists)
- **Test type**: unit (mocking subprocess)
- **Backing**: default-derived
- **Scenarios**:
  - Normal: CLI called with correct model and thinking params
  - Edge: Empty response handled gracefully
  - Error: CLI failure returns fallback response

**Code Intent**:
- Modify `LLMClient.__init__()`: change default model to `claude-sonnet-4-5-20250514`
- Modify `LLMClient.__init__()`: set max_tokens default to 20000
- Add `thinking_budget` parameter (default 10000) to config
- Modify `LLMClient.generate()`: add `--thinking-budget` flag to CLI call
- Update `config/example-config.json`: change llm_config.model and max_tokens
- Update `plugin.json`: change llm_model and llm_max_tokens

**Code Changes**:

```diff
--- a/utils/llm_client.py
+++ b/utils/llm_client.py
@@ -25,8 +25,18 @@ class LLMClient:
         """
         self.config = config
-        self.model = config.get('model', 'haiku')
+        # Sonnet 4.5 provides deeper reasoning via extended thinking (10k token budget)
+        self.model = config.get('model', 'claude-sonnet-4-5-20250514')
+        # 20k tokens allows full session transcript analysis without truncation
         self.max_tokens = config.get('max_tokens', 20000)
+        # 10k thinking budget balances quality vs cost; adds 5-10s latency (user-specified balance)
+        self.thinking_budget = config.get('thinking_budget', 10000)
         self._claude_path = shutil.which('claude')
+        self.extended_thinking_available = self._check_extended_thinking()
+
+    def _check_extended_thinking(self) -> bool:
+        """Check if claude CLI supports extended thinking parameters.
+
+        Returns True if claude CLI binary exists; fallback handles unsupported flags gracefully.
+        """
+        if not self._claude_path:
+            return False
+        # Assume modern CLI supports extended thinking; generate() handles failure
+        return True

@@ -44,8 +54,14 @@ class LLMClient:
         try:
             cmd = [
                 self._claude_path,
                 '-p', prompt,
-                '--model', self.model
+                '--model', self.model
             ]
+
+            # Extended thinking requires --thinking-budget flag with token count
+            if self.extended_thinking_available and self.thinking_budget > 0:
+                cmd.extend(['--thinking-budget', str(self.thinking_budget)])

             result = subprocess.run(
```

```diff
--- a/config/example-config.json
+++ b/config/example-config.json
@@ -31,8 +31,9 @@
     "include_session_id": false
   },
   "llm_config": {
-    "model": "haiku",
-    "max_tokens": 150,
+    "model": "claude-sonnet-4-5-20250514",
+    "max_tokens": 20000,
+    "thinking_budget": 10000,
     "temperature": 0.3,
     "use_for_reasoning": true,
```

```diff
--- a/plugin.json
+++ b/plugin.json
@@ -14,7 +14,8 @@
     "min_changes_threshold": 1,
     "max_session_entries_per_topic": 50,
     "archive_after_sessions": 100,
-    "llm_model": "haiku",
-    "llm_max_tokens": 150
+    "llm_model": "claude-sonnet-4-5-20250514",
+    "llm_max_tokens": 20000
   }
 }
```

---

### Milestone 2: Modify Session Context Extraction for Extended Thinking

**Files**:
- `core/session_analyzer.py`

**Flags**: `needs-rationale`, `complex-algorithm`

**Requirements**:
- Update extract_session_context() prompt for consolidated summary format
- Include all topics in single comprehensive summary
- Remove per-topic separation in output format
- Increase context window usage to leverage 20k tokens

**Acceptance Criteria**:
- SessionContext.summary contains consolidated narrative (not topic-separated)
- Full transcript (up to 20k chars) passed to LLM
- Topics included as metadata tags in summary
- Fallback still works if LLM fails

**Tests**:
- **Test files**: `tests/test_session_analyzer.py`
- **Test type**: integration (with mock LLM)
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Multi-topic session produces single coherent summary
  - Edge: Empty changes returns minimal context
  - Error: LLM timeout triggers fallback

**Code Intent**:
- Modify `extract_session_context()`: update prompt to request consolidated summary
- Modify `extract_session_context()`: include topics array in prompt for inline tagging
- Modify `extract_session_context()`: increase transcript slice from 20000 to full available
- Modify `extract_session_context()`: set max_tokens to 2000 (per Decision Log: "Session summary max_tokens 2,000")
- Update prompt template to produce: goal, summary (with topic tags), decisions, problems, future work

**Code Changes**:

```diff
--- a/core/session_analyzer.py
+++ b/core/session_analyzer.py
@@ -377,11 +377,12 @@ class SessionAnalyzer:
         return f"Session involved {', '.join(parts)} in the project."

-    def extract_session_context(self, changes: List[FileChange]) -> SessionContext:
+    def extract_session_context(self, changes: List[FileChange], topics: List[str] = None) -> SessionContext:
         """Extract rich session context using LLM analysis.

         Args:
             changes: List of FileChange objects
+            topics: List of detected topic names for inline tagging

         Returns:
             SessionContext with goal, summary, decisions, problems, future work
@@ -390,10 +391,15 @@ class SessionAnalyzer:
         if not transcript_content:
             return self._fallback_context(changes)

+        # Topics passed to LLM for inline tagging (consolidation approach)
+        if not topics:
+            topics = ['general-changes']
+        topic_tags = ', '.join(f'[{t}]' for t in topics)
+
         change_summary = '\n'.join([
             f"- {c.action}: {c.file_path}" for c in changes[:15]
         ])

-        prompt = f"""Analyze this Claude Code session transcript and extract:
+        # Prompt requests single summary with inline topic tags for all detected topics
+        prompt = f"""Analyze this Claude Code session transcript and extract a consolidated summary.
+
+Detected topics: {topic_tags}

 1. USER_GOAL: What was the user trying to accomplish? (1 sentence)
-2. SUMMARY: What was done in this session? (1-2 sentences)
+2. SUMMARY: What was done in this session? Include topic tags {topic_tags} inline. (2-3 sentences)
 3. DECISIONS: Key technical decisions made (list up to 3, or "None")
 4. PROBLEMS_SOLVED: Issues or bugs fixed (list up to 3, or "None")
 5. FUTURE_WORK: Remaining tasks or TODOs mentioned (list up to 3, or "None")
@@ -402,8 +408,8 @@ class SessionAnalyzer:
 Files changed:
 {change_summary}

-Session transcript (last 20000 chars):
-{transcript_content[-20000:]}
+Session transcript:
+{transcript_content}

 Respond in this exact format:
 USER_GOAL: <goal>
@@ -417,7 +423,7 @@ FUTURE_WORK:
 - <todo 1>"""

         try:
-            response = self.llm_client.generate(prompt, max_tokens=600)
+            # 2k tokens sufficient for goal(200) + summary(400) + decisions(400) + problems(400) + future(400) + tags(200)
+            response = self.llm_client.generate(prompt, max_tokens=2000)
             return self._parse_context_response(response)
         except Exception as e:
             logger.warning(f"Failed to extract session context: {e}")
```

---

### Milestone 3: Consolidate MarkdownWriter Output

**Files**:
- `core/markdown_writer.py`
- `hooks/stop.py`

**Flags**: `conformance`

**Requirements**:
- Modify append_session() to write single consolidated entry
- Accept all topics at once instead of single topic
- Format topics as inline tags in entry header
- Single output file: `context.md`

**Acceptance Criteria**:
- Only `context.md` created per project (no topic-specific files)
- Entry header shows all topics as tags: `## Session [testing] [config] - 2024-01-07`
- stop.py calls writer once (not in loop)
- Prepend behavior preserved (newest first)

**Tests**:
- **Test files**: `tests/test_markdown_writer.py` (create if not exists)
- **Test type**: integration
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Multi-topic session creates single entry in context.md
  - Edge: No topics defaults to [general-changes] tag
  - Edge: Empty changes skipped (no write)

**Code Intent**:
- Modify `append_session()` signature: `topics: List[str]` instead of `topic: str`
- Modify `append_session()`: construct single filename `context.md`
- Modify entry header format: include all topic tags inline
- Modify `stop.py`: remove topic iteration loop (lines 89-99)
- Modify `stop.py`: call append_session once with all detected topics

**Code Changes**:

```diff
--- a/core/markdown_writer.py
+++ b/core/markdown_writer.py
@@ -26,10 +26,10 @@ class MarkdownWriter:

     def append_session(
         self,
         project_path: str,
         classification: str,
-        topic: str,
+        topics: List[str],
         changes: List[FileChange],
         reasoning: str,
         context: Optional[SessionContext] = None
     ) -> Path:
@@ -38,7 +38,7 @@ class MarkdownWriter:
         Args:
             project_path: Full path to project
             classification: 'work' or 'personal'
-            topic: Topic name
+            topics: List of topic names
             changes: List of FileChange objects
             reasoning: Reasoning string (fallback if no context)
             context: Rich session context from LLM
@@ -50,13 +50,15 @@ class MarkdownWriter:
         context_dir = self.context_root / classification / rel_path

         ensure_directory(context_dir)

-        entry = self._format_session_entry(topic, changes, reasoning, context)
+        # Fallback maintains consistency when topic detection fails
+        if not topics:
+            topics = ["general-changes"]

-        topic_file = context_dir / f"{topic}.md"
+        entry = self._format_session_entry(topics, changes, reasoning, context)

-        if not topic_file.exists():
-            header = f"# {topic.replace('-', ' ').title()}\n\n"
-            topic_file.write_text(header + entry)
+        # All sessions for this project append to context.md
+        topic_file = context_dir / "context.md"
+
+        if not topic_file.exists():
+            header = "# Project Context\n\n"
+            topic_file.write_text(header + entry)
         else:
@@ -78,9 +80,9 @@ class MarkdownWriter:

     def _format_session_entry(
         self,
-        topic: str,
+        topics: List[str],
         changes: List[FileChange],
         reasoning: str,
         context: Optional[SessionContext] = None
@@ -88,7 +90,7 @@ class MarkdownWriter:
         """Format session entry as markdown.

         Args:
-            topic: Topic name
+            topics: List of topic names
             changes: List of FileChange objects
             reasoning: Reasoning string (fallback)
             context: Rich session context
@@ -99,7 +101,10 @@ class MarkdownWriter:
         now = datetime.now()
         date_str = now.strftime('%Y-%m-%d')
         time_str = now.strftime('%H:%M')

-        parts = [f"## Session: {date_str} {time_str}"]
+        # Topic tags enable filtering while keeping all sessions in single file
+        topic_tags = ' '.join(f"[{t}]" for t in topics)
+
+        parts = [f"## Session {topic_tags} - {date_str} {time_str}"]

         # Goal section
         if context and context.user_goal:
```

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -75,9 +75,12 @@ def main():
         detector = TopicDetector(config)
         topics_map = detector.detect_topics(changes)

-        # Extract rich session context via LLM
-        session_context = analyzer.extract_session_context(changes)
+        # Pass topics to LLM for inline tagging in consolidated summary
+        all_topics = list(topics_map.keys())
+        session_context = analyzer.extract_session_context(changes, topics=all_topics)

         # Fallback reasoning if context extraction failed
         reasoning = session_context.summary or analyzer.extract_reasoning(changes)

@@ -85,18 +88,13 @@ def main():
         # Write to context files
         writer = MarkdownWriter(config)
-        written_files = []

-        for topic, topic_changes in topics_map.items():
-            file_path = writer.append_session(
-                project_path=cwd,
-                classification=classification,
-                topic=topic,
-                changes=topic_changes,
-                reasoning=reasoning,
-                context=session_context
-            )
-            written_files.append(file_path)
-            logger.info(f"Updated {file_path}")
+        # Write all topics to single context.md entry
+        file_path = writer.append_session(
+            project_path=cwd,
+            classification=classification,
+            topics=all_topics,
+            changes=changes,
+            reasoning=reasoning,
+            context=session_context
+        )
+        logger.info(f"Updated {file_path}")

         # Copy plan files to context directory
```

---

### Milestone 4: Add Old File Cleanup

**Files**:
- `hooks/stop.py`

**Flags**: `error-handling`

**Requirements**:
- Delete existing topic-specific .md files on first run
- Preserve plans/ directory and its contents
- One-time cleanup, not repeated on every run

**Acceptance Criteria**:
- Old files (testing.md, configuration.md, etc.) deleted
- context.md is the only .md file after cleanup
- plans/ directory untouched
- Cleanup logged for visibility

**Tests**:
- **Test files**: `tests/test_stop_hook.py` (extend existing)
- **Test type**: integration
- **Backing**: default-derived
- **Scenarios**:
  - Normal: Old topic files deleted, context.md preserved
  - Edge: No old files to delete (clean directory)
  - Edge: plans/ directory preserved

**Code Intent**:
- Add `cleanup_old_topic_files()` function in stop.py
- Function lists .md files in context dir root only (non-recursive per Decision Log)
- Deletes any .md file that is NOT `context.md`
- plans/ subdirectory naturally excluded by non-recursive listing
- Call cleanup before first write (check for `.migrated` marker file)
- Create `.migrated` marker file after cleanup to prevent re-running (per Decision Log: "Marker file `.migrated`")

**Code Changes**:

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -40,6 +40,33 @@ def copy_plan_files(changes, context_dir: Path):
                 logger.info(f"Copied plan file: {file_path.name}")


+def cleanup_old_topic_files(context_dir: Path):
+    """Delete legacy .md files in context directory, preserving context.md.
+
+    Runs once per project (marker file gates re-execution). Non-recursive glob
+    excludes plans/ subdirectory. Skips execution if marker exists.
+
+    Args:
+        context_dir: Context directory for current project
+    """
+    marker_file = context_dir / '.migrated'
+
+    # Marker file gates cleanup execution (only runs once per project)
+    if marker_file.exists():
+        return
+
+    # Non-recursive glob naturally excludes plans/ subdirectory
+    if not context_dir.exists():
+        return
+
+    for md_file in context_dir.glob('*.md'):
+        # Skip context.md during cleanup
+        if md_file.name == 'context.md':
+            continue
+
+        md_file.unlink()
+        logger.info(f"Deleted old topic file: {md_file.name}")
+
+    # Marker prevents accidental re-deletion on subsequent runs
+    marker_file.touch()
+
+
 def main():
     """Main entry point for Stop hook."""
     try:
@@ -83,6 +110,11 @@ def main():

         # Write to context files
         writer = MarkdownWriter(config)
+
+        # One-time cleanup of legacy topic files
+        context_root = Path(config.get('context_root', '~/context')).expanduser()
+        rel_path = cwd.replace(str(Path.home()), '').lstrip('/')
+        context_dir = context_root / classification / rel_path
+        cleanup_old_topic_files(context_dir)

         # Consolidate all topics into single context.md entry
```

---

### Milestone 5: Documentation

**Delegated to**: @agent-technical-writer (mode: post-implementation)

**Source**: `## Invisible Knowledge` section of this plan

**Files**:
- `CLAUDE.md` (update)
- `README.md` (update with architecture diagram)

**Requirements**:

CLAUDE.md:
- Update to reflect new single-file output format
- Document context.md as primary output

README.md:
- Add consolidated architecture diagram from Invisible Knowledge
- Document extended thinking configuration
- Explain topic tagging format

**Acceptance Criteria**:
- CLAUDE.md updated with new output format
- README.md contains architecture diagram
- No references to old per-topic file format

**Source Material**: `## Invisible Knowledge` section of this plan

---

## Milestone Dependencies

```
M1 (LLM upgrade) ---> M2 (session context)
                             |
                             v
                      M3 (markdown writer) ---> M4 (cleanup) ---> M5 (docs)
```

M1 and M2 are sequential (M2 depends on extended thinking from M1).
M3 depends on M2 for new context format.
M4 depends on M3 (cleanup after new format works).
M5 after all implementation complete.
