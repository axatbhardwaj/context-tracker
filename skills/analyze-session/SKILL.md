---
name: analyze-session
description: Analyzes Claude Code session transcripts and updates project context wiki. Invoked by stop hook.
---

# Analyze Session

Analyzes a Claude Code session transcript and merges insights into the project's context wiki.

## Input

Arguments passed via `$ARGUMENTS`:
- `context_path`: Path to context.md file to update
- `topics`: Comma-separated topic tags
- `log_file`: Relative path to session log file for linking

## Workflow

### Step 1: Analyze Session

The session has already been summarized into the provided "Session Summary".
Analyze this summary to understand:

1. **USER_GOAL**: What was the user trying to accomplish? (1 sentence)
2. **SUMMARY**: What was done? Include topic tags inline. (2-3 sentences)
3. **DECISIONS**: Key technical decisions made (up to 3)
4. **PROBLEMS_SOLVED**: Issues or bugs fixed (up to 3)
5. **FUTURE_WORK**: Remaining tasks mentioned (up to 3)

### Step 2: Merge into Wiki

The wiki has 5 sections. Merge new content appropriately:

```markdown
# Project Context

## Architecture
[Keep existing. Only add if session reveals architectural insights.]

## Decisions
[Append new decisions. Deduplicate if similar exists (>80% overlap).]

## Patterns
[Keep existing. Only add if session establishes new patterns.]

## Issues
[Append problems solved. These become resolved issues for reference.]

## Recent Work
[Prepend new session summary. Keep last 5 entries. Oldest rotates out.]
[Add link to the detailed session log using the `log_file` argument.]
```

#### Recent Work Entry Format

```markdown
- [YYYY-MM-DD] <summary with [topic] tags inline> [[Details](<log_file>)]
```

Example:
```markdown
- [2026-01-08] Fixed [bugfix] authentication timeout. [[Details](history/2026-01-08-fix-auth.md)]
```

#### Deduplication Rules

Before adding to Decisions or Issues:
1. Compare with existing entries
2. If >80% word overlap, skip (already captured)
3. Prefer more specific/detailed version

### Step 5: Write Output

Write the merged wiki to `context_path` using the Write tool.

## Wiki Format Reference

```markdown
# Project Context

## Architecture

_No architectural notes yet._


## Decisions

- Decision 1 description
- Decision 2 description


## Patterns

_No patterns identified yet._


## Issues

- Issue 1 that was solved
- Issue 2 that was solved


## Recent Work

- [2026-01-08] Most recent session summary with [topic] tags
- [2026-01-07] Previous session summary
- [2026-01-06] Older session summary
```

## Output Format

Output the complete updated context.md between `<context_md>` and `</context_md>` tags:

```
<context_md>
# Project Context

## Architecture
...

## Decisions
...

## Patterns
...

## Issues
...

## Recent Work
...
</context_md>
```

Then output a brief JSON summary:
```json
{"status": "success", "decisions_added": 2, "issues_added": 1}
```

## Important Notes

- Keep summaries concise (2-3 sentences max)
- Use topic tags inline in Recent Work summaries (e.g., "Fixed [bugfix] issue...")
- Deduplicate before adding to Decisions/Issues
- Recent Work keeps only last 5 entries (newest first)
- Preserve existing Architecture and Patterns unless session adds to them
- Always output the COMPLETE context.md, not just changes
