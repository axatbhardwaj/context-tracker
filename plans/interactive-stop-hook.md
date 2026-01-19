# Interactive Stop Hook

## Overview

The user finds the automatic context generation and git sync in the stop hook to be too frequent and time-consuming.
This plan introduces an interactive prompt in `hooks/stop.py` to ask the user for confirmation before proceeding with these expensive operations.
The default behavior will be to ask.

## Planning Context

### Decision Log

| Decision | Reasoning Chain |
| :--- | :--- |
| Interactive Prompt in Stop Hook | User request -> Current automation is too slow/frequent -> Prompt gives user control over execution |
| Direct Modification of `stop.py` | Simple requirement -> Over-engineering config adds unnecessary complexity -> Direct implementation adheres to KISS |
| Use `sys.stderr` for prompts | Standard practice for interactive CLI tools -> Keeps stdout clean for piped output if necessary -> Ensures prompt is visible |
| Mocking for Tests | Interactive logic uses stdin/stderr -> Unit tests need to simulate user input -> `pytest` with `monkeypatch` or mocks is standard |

### Rejected Alternatives

| Alternative | Why Rejected |
| :--- | :--- |
| Configuration-only Approach | User explicitly asked for a prompt now, not just a config toggle to disable it. |
| Separate `ask` sub-agent | Overkill for a simple boolean confirmation. |

### Constraints & Assumptions

- **Technical**: Must run in the existing Python environment. `input()` is available.
- **Assumptions**: The session is interactive (user can respond to prompts). If run in a non-interactive CI environment, `input()` might fail or hang, but the hook is primarily for local `claude` sessions.

### Known Risks

| Risk | Mitigation | Anchor |
| :--- | :--- | :--- |
| Non-interactive environments | Use `sys.stdin.isatty()` check to default to valid behavior (skip or auto) if needed, or rely on `try-except EOFError`. | `hooks/stop.py` (to be added) |

## Invisible Knowledge

### User Experience
The hook will pause execution after session analysis (topic detection) but before the expensive context update and git push operations. It displays a summary of detected topics to help the user decide.

## Milestones

### Milestone 1: Interactive Prompt Implementation

**Files**: `hooks/stop.py`

**Flags**:
- `interaction`: Involves user input

**Requirements**:
- Prompt the user: "Generate context and push changes? [Y/n]"
- Default to "Yes" if user just hits Enter.
- Display this prompt AFTER topic detection.
- IF user confirms: Proceed with `analyzer.extract_session_context` and `GitSync`.
- IF user denies: Skip both and exit gracefully.

**Acceptance Criteria**:
- Running the hook prompts the user.
- Entering 'n' skips generation.
- Entering 'y' proceeds.
- Tests pass.

**Tests**:
- **Test files**: `tests/test_hooks_stop.py`
- **Test type**: Unit
- **Backing**: User-specified
- **Scenarios**:
  - User confirms (y) -> functions called.
  - User denies (n) -> functions not called.
  - Invalid input -> re-prompt or default.

**Code Changes**:

```diff
--- hooks/stop.py
+++ hooks/stop.py
@@ -196,6 +196,28 @@
     return confirmed
 
 
+def confirm_execution(topics_map: dict) -> bool:
+    """Ask user for confirmation before proceeding with expensive operations.
+
+    Args:
+        topics_map: Dictionary of detected topics
+
+    Returns:
+        True if user confirms or if input is empty/y/yes
+    """
+    # Use stderr to keep stdout clean for JSON output (pipe safety)
+    print("\nDetected topics:", file=sys.stderr)
+    if topics_map:
+        for topic in topics_map:
+            print(f"  - {topic}", file=sys.stderr)
+    else:
+        print("  - general-changes", file=sys.stderr)
+
+    print("\nGenerate context and push changes? [Y/n]: ", file=sys.stderr, end='', flush=True)
+    return _get_user_confirmation()
+
+
 def copy_plan_files(changes, context_dir: Path):
     """Copy plan files to context directory."""
     plans_dir = context_dir / 'plans'
@@ -607,6 +629,12 @@
         topics_map = detector.detect_topics(changes)
         all_topics = list(topics_map.keys())
 
+        # Prompt gives user control over execution
+        if not confirm_execution(topics_map):
+            logger.info("User skipped context generation")
+            print(json.dumps({}), file=sys.stdout)
+            sys.exit(0)
+
         # Use skill-based analysis to update context.md
         logger.info("Extracting session context...")
         session_ctx = analyzer.extract_session_context(changes, all_topics)
```

### Milestone 2: Documentation

**Delegated to**: @agent-technical-writer

**Source**: `## Invisible Knowledge` section

**Files**:
- `CLAUDE.md`

**Requirements**:
- Verify if any documentation needs updating regarding the new interactive flow.

**Acceptance Criteria**:
- Documentation reflects reality.
