"""Tests for session_analyzer module."""

import pytest
from core.session_analyzer import SessionAnalyzer, FileChange


class TestParseTranscript:
    """Tests for transcript parsing - tool uses nested in message.content[]."""

    def test_extracts_edit_tool_from_nested_content(self, transcript_single_edit, sample_config):
        """Tool uses are in message.content[], not at top level."""
        input_data = {"transcript_path": str(transcript_single_edit), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 1
        assert changes[0].file_path == "/home/user/project/src/utils.py"
        assert changes[0].action == "modified"

    def test_extracts_multiple_tools(self, transcript_multiple_edits, sample_config):
        """Multiple tool uses across lines are extracted."""
        input_data = {"transcript_path": str(transcript_multiple_edits), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 3
        paths = [c.file_path for c in changes]
        assert "/home/user/project/src/utils.py" in paths
        assert "/home/user/project/src/new_file.py" in paths
        assert "/home/user/project/tests/test_utils.py" in paths

    def test_ignores_non_file_modification_tools(self, transcript_with_non_file_tools, sample_config):
        """Bash, Read, Grep tools are ignored - only Edit/Write/MultiEdit/NotebookEdit."""
        input_data = {"transcript_path": str(transcript_with_non_file_tools), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 1
        assert changes[0].file_path == "/home/user/project/src/main.py"

    def test_deduplicates_same_file_edits(self, transcript_duplicate_files, sample_config):
        """Multiple edits to same file result in single FileChange."""
        input_data = {"transcript_path": str(transcript_duplicate_files), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 1
        assert changes[0].file_path == "/home/user/project/src/config.py"


class TestHandleEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_transcript_returns_empty_list(self, transcript_empty, sample_config):
        """Empty transcript file returns no changes."""
        input_data = {"transcript_path": str(transcript_empty), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert changes == []

    def test_malformed_json_lines_skipped(self, transcript_malformed, sample_config):
        """Invalid JSON lines are skipped, valid ones processed."""
        input_data = {"transcript_path": str(transcript_malformed), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 2
        paths = [c.file_path for c in changes]
        assert "/home/user/project/valid.py" in paths
        assert "/home/user/project/also_valid.py" in paths

    def test_missing_transcript_path_returns_empty(self, sample_config):
        """Missing transcript_path in input returns empty list."""
        input_data = {"cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert changes == []

    def test_nonexistent_transcript_file_returns_empty(self, sample_config):
        """Nonexistent transcript file returns empty list."""
        input_data = {"transcript_path": "/nonexistent/path.jsonl", "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert changes == []


class TestToolTypes:
    """Tests for different tool type handling."""

    def test_extracts_multi_edit_tool(self, transcript_multi_edit, sample_config):
        """MultiEdit tool is recognized and extracted."""
        input_data = {"transcript_path": str(transcript_multi_edit), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 1
        assert changes[0].file_path == "/home/user/project/src/app.py"

    def test_extracts_notebook_edit_tool(self, transcript_notebook_edit, sample_config):
        """NotebookEdit tool is recognized and extracted."""
        input_data = {"transcript_path": str(transcript_notebook_edit), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 1
        assert "analysis.ipynb" in changes[0].file_path

    def test_mixed_text_and_tool_content(self, transcript_mixed_content, sample_config):
        """Text content is ignored, only tool_use extracted."""
        input_data = {"transcript_path": str(transcript_mixed_content), "cwd": "/home/user/project"}
        analyzer = SessionAnalyzer(input_data, sample_config)
        changes = analyzer.get_changes()

        assert len(changes) == 1
        assert changes[0].file_path == "/home/user/project/src/handler.py"


class TestFileChange:
    """Tests for FileChange dataclass."""

    def test_file_change_attributes(self):
        """FileChange has required attributes."""
        change = FileChange(
            file_path="/home/user/project/file.py",
            action="modified",
            description="Updated function"
        )

        assert change.file_path == "/home/user/project/file.py"
        assert change.action == "modified"
        assert change.description == "Updated function"

    def test_file_change_default_values(self):
        """FileChange has sensible defaults."""
        change = FileChange(
            file_path="/home/user/project/file.py",
            action="created",
            description="New file"
        )

        assert change.lines_added == 0
        assert change.lines_removed == 0
