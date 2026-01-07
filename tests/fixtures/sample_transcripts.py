"""Sample transcript data for testing.

These fixtures represent the JSONL transcript format used by Claude Code.
Tool uses are nested inside message.content[], NOT at the top level.
"""

import json


# Single Edit tool use - basic case
TRANSCRIPT_SINGLE_EDIT = """{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/utils.py", "old_string": "def foo():", "new_string": "def bar():"}}]}, "timestamp": "2026-01-07T01:10:13.389Z"}
"""

# Multiple tool uses across multiple lines
TRANSCRIPT_MULTIPLE_EDITS = """{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/utils.py", "old_string": "def foo():", "new_string": "def bar():"}}]}, "timestamp": "2026-01-07T01:10:13.389Z"}
{"message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/home/user/project/src/new_file.py", "content": "# New file"}}]}, "timestamp": "2026-01-07T01:10:15.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/tests/test_utils.py", "old_string": "assert True", "new_string": "assert result == expected"}}]}, "timestamp": "2026-01-07T01:10:17.000Z"}
"""

# Transcript with non-file-modification tools (should be ignored)
TRANSCRIPT_WITH_NON_FILE_TOOLS = """{"message": {"content": [{"type": "tool_use", "name": "Bash", "input": {"command": "ls -la"}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Read", "input": {"file_path": "/home/user/project/README.md"}}]}, "timestamp": "2026-01-07T01:10:11.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/main.py", "old_string": "print('hello')", "new_string": "print('world')"}}]}, "timestamp": "2026-01-07T01:10:12.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Grep", "input": {"pattern": "TODO", "path": "/home/user/project"}}]}, "timestamp": "2026-01-07T01:10:13.000Z"}
"""

# Transcript with duplicate file edits (should deduplicate)
TRANSCRIPT_DUPLICATE_FILES = """{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/config.py", "old_string": "DEBUG = False", "new_string": "DEBUG = True"}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/config.py", "old_string": "VERSION = 1", "new_string": "VERSION = 2"}}]}, "timestamp": "2026-01-07T01:10:11.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/config.py", "old_string": "NAME = 'old'", "new_string": "NAME = 'new'"}}]}, "timestamp": "2026-01-07T01:10:12.000Z"}
"""

# Empty transcript
TRANSCRIPT_EMPTY = ""

# Transcript with malformed JSON lines
TRANSCRIPT_MALFORMED = """{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/valid.py", "old_string": "a", "new_string": "b"}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
{this is not valid json
{"message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/home/user/project/also_valid.py", "content": "ok"}}]}, "timestamp": "2026-01-07T01:10:12.000Z"}
"""

# Transcript with MultiEdit tool
TRANSCRIPT_MULTI_EDIT = """{"message": {"content": [{"type": "tool_use", "name": "MultiEdit", "input": {"file_path": "/home/user/project/src/app.py", "edits": [{"old_string": "a", "new_string": "b"}, {"old_string": "c", "new_string": "d"}]}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
"""

# Transcript with NotebookEdit tool
TRANSCRIPT_NOTEBOOK_EDIT = """{"message": {"content": [{"type": "tool_use", "name": "NotebookEdit", "input": {"file_path": "/home/user/project/notebooks/analysis.ipynb", "cell_number": 0, "new_source": "import pandas as pd"}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
"""

# Transcript with text content mixed with tool uses
TRANSCRIPT_MIXED_CONTENT = """{"message": {"content": [{"type": "text", "text": "I will now edit the file."}]}, "timestamp": "2026-01-07T01:10:09.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/handler.py", "old_string": "pass", "new_string": "return True"}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
{"message": {"content": [{"type": "text", "text": "The file has been edited."}]}, "timestamp": "2026-01-07T01:10:11.000Z"}
"""

# Transcript with topic-specific files (testing, fees, handlers)
TRANSCRIPT_TOPIC_FILES = """{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/tests/test_calculator.py", "old_string": "def test_add():", "new_string": "def test_addition():"}}]}, "timestamp": "2026-01-07T01:10:10.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Edit", "input": {"file_path": "/home/user/project/src/fee_calculator.ts", "old_string": "const fee = 0;", "new_string": "const fee = calculateFee(amount);"}}]}, "timestamp": "2026-01-07T01:10:11.000Z"}
{"message": {"content": [{"type": "tool_use", "name": "Write", "input": {"file_path": "/home/user/project/src/handlers/event_handler.ts", "content": "export class EventHandler {}"}}]}, "timestamp": "2026-01-07T01:10:12.000Z"}
"""


def get_sample_hook_input(
    session_id: str = "test-session-123",
    transcript_path: str = "/tmp/test-transcript.jsonl",
    cwd: str = "/home/user/project",
    permission_mode: str = "default"
) -> dict:
    """Generate sample hook input data.

    Args:
        session_id: Session identifier
        transcript_path: Path to transcript file
        cwd: Current working directory
        permission_mode: Permission mode

    Returns:
        Hook input dictionary
    """
    return {
        "session_id": session_id,
        "transcript_path": transcript_path,
        "cwd": cwd,
        "permission_mode": permission_mode,
        "hook_event_name": "Stop",
        "stop_hook_active": True
    }


def get_sample_config(
    context_root: str = "/tmp/test-context",
    work_patterns: list = None,
    personal_patterns: list = None,
    excluded_paths: list = None
) -> dict:
    """Generate sample configuration.

    Args:
        context_root: Root directory for context files
        work_patterns: Work path patterns
        personal_patterns: Personal path patterns
        excluded_paths: Excluded path patterns

    Returns:
        Configuration dictionary
    """
    return {
        "context_root": context_root,
        "work_path_patterns": work_patterns or ["/home/user/work/"],
        "personal_path_patterns": personal_patterns or ["/home/user/personal/"],
        "excluded_paths": excluded_paths or ["/tmp/", "/home/user/.cache/"],
        "git_config": {
            "auto_commit": False,
            "auto_push": False,
            "commit_message_template": "Context update: {project} - {topics}"
        },
        "session_config": {
            "min_changes_threshold": 1,
            "max_session_entries_per_topic": 50
        },
        "llm_config": {
            "model": "haiku",
            "max_tokens": 150,
            "temperature": 0.3
        },
        "topic_patterns": {
            "patterns": {
                "testing": {
                    "file_patterns": ["**/tests/**", "**/*.test.ts"],
                    "priority": 10
                },
                "fee-calculations": {
                    "file_patterns": ["**/fee*.ts", "**/fee*.py"],
                    "priority": 8
                },
                "event-handlers": {
                    "file_patterns": ["**/handlers/**"],
                    "priority": 9
                }
            },
            "fallback_topic": "general-changes"
        }
    }
