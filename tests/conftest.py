"""Pytest configuration and shared fixtures."""

import os
import sys
import tempfile
import pytest
from pathlib import Path

# Add plugin root to path for imports
PLUGIN_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PLUGIN_ROOT))

# Set environment variable for config loading
os.environ['CLAUDE_PLUGIN_ROOT'] = str(PLUGIN_ROOT)

from tests.fixtures.sample_transcripts import (
    TRANSCRIPT_SINGLE_EDIT,
    TRANSCRIPT_MULTIPLE_EDITS,
    TRANSCRIPT_WITH_NON_FILE_TOOLS,
    TRANSCRIPT_DUPLICATE_FILES,
    TRANSCRIPT_EMPTY,
    TRANSCRIPT_MALFORMED,
    TRANSCRIPT_MULTI_EDIT,
    TRANSCRIPT_NOTEBOOK_EDIT,
    TRANSCRIPT_MIXED_CONTENT,
    TRANSCRIPT_TOPIC_FILES,
    get_sample_hook_input,
    get_sample_config,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def transcript_single_edit(temp_dir):
    """Create transcript file with single edit."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_SINGLE_EDIT)
    return transcript_path


@pytest.fixture
def transcript_multiple_edits(temp_dir):
    """Create transcript file with multiple edits."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_MULTIPLE_EDITS)
    return transcript_path


@pytest.fixture
def transcript_with_non_file_tools(temp_dir):
    """Create transcript file with non-file-modification tools."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_WITH_NON_FILE_TOOLS)
    return transcript_path


@pytest.fixture
def transcript_duplicate_files(temp_dir):
    """Create transcript file with duplicate file edits."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_DUPLICATE_FILES)
    return transcript_path


@pytest.fixture
def transcript_empty(temp_dir):
    """Create empty transcript file."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_EMPTY)
    return transcript_path


@pytest.fixture
def transcript_malformed(temp_dir):
    """Create transcript file with malformed JSON."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_MALFORMED)
    return transcript_path


@pytest.fixture
def transcript_multi_edit(temp_dir):
    """Create transcript file with MultiEdit tool."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_MULTI_EDIT)
    return transcript_path


@pytest.fixture
def transcript_notebook_edit(temp_dir):
    """Create transcript file with NotebookEdit tool."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_NOTEBOOK_EDIT)
    return transcript_path


@pytest.fixture
def transcript_mixed_content(temp_dir):
    """Create transcript file with mixed content types."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_MIXED_CONTENT)
    return transcript_path


@pytest.fixture
def transcript_topic_files(temp_dir):
    """Create transcript file with topic-specific files."""
    transcript_path = temp_dir / "transcript.jsonl"
    transcript_path.write_text(TRANSCRIPT_TOPIC_FILES)
    return transcript_path


@pytest.fixture
def sample_config(temp_dir):
    """Get sample configuration with temp directory as context root."""
    return get_sample_config(context_root=str(temp_dir / "context"))


@pytest.fixture
def sample_hook_input(transcript_single_edit, temp_dir):
    """Get sample hook input with valid transcript path."""
    return get_sample_hook_input(
        transcript_path=str(transcript_single_edit),
        cwd=str(temp_dir / "project")
    )
