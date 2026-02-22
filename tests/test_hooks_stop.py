import sys
import inspect
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open

import pytest

from hooks.stop import update_context_wiki
from hooks.stop import generate_architecture
from hooks.stop import review_generated_files
from hooks.stop import _revert_files


def test_update_context_wiki_no_log_file_name():
    """Verify update_context_wiki signature contains no log_file_name parameter."""
    sig = inspect.signature(update_context_wiki)
    assert "log_file_name" not in sig.parameters


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_update_context_wiki_success(mock_load_skill, mock_llm_class, tmp_path):
    """Writer agent extracts content from <context_md> tags and writes file."""
    mock_load_skill.return_value = "skill prompt content"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = (
        '<context_md>\n# Project Context\n\n## Decisions\n- Decision 1\n</context_md>\n'
        '{"status": "success"}'
    )

    context_file = tmp_path / "context.md"

    result = update_context_wiki("session text", str(context_file), ["topic1"], {})

    assert result["status"] == "success"
    assert result["context_path"] == str(context_file)
    assert context_file.read_text() == "# Project Context\n\n## Decisions\n- Decision 1"
    mock_load_skill.assert_called_once_with("writer-agent")

    # Verify technical-writer agent is used
    _, kwargs = mock_llm.generate.call_args
    assert kwargs["agent"] == "technical-writer"


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_update_context_wiki_no_tags(mock_load_skill, mock_llm_class, tmp_path):
    """Writer agent returns error when response has no <context_md> tags."""
    mock_load_skill.return_value = "skill prompt"
    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = "Some response without tags"

    context_file = tmp_path / "context.md"
    result = update_context_wiki("session text", str(context_file), [], {})

    assert result["status"] == "error"
    assert "No context_md tags" in result["error"]


@patch("hooks.stop.load_skill_prompt")
def test_update_context_wiki_missing_skill(mock_load_skill):
    """Writer agent returns error when skill prompt is missing."""
    mock_load_skill.return_value = ""

    result = update_context_wiki("session text", "/tmp/context.md", [], {})

    assert result["status"] == "error"
    assert "skill not found" in result["error"]


@patch("hooks.stop.shutil.which")
def test_generate_architecture_no_cli(mock_which, tmp_path):
    """Architect agent skips when Claude CLI is not available."""
    mock_which.return_value = None

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert not arch_file.exists()


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_success(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent writes architecture.md from <architecture_md> tags."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "## Git History\ncommit 1"
    mock_load_skill.return_value = "architect skill prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = (
        "<architecture_md>\nCLI plugin for tracking context.\n</architecture_md>"
    )

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert arch_file.exists()
    assert arch_file.read_text() == "CLI plugin for tracking context."
    mock_load_skill.assert_called_once_with("architect-agent")


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_uses_architect_agent(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent passes agent='architect' to LLMClient.generate()."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "summary"
    mock_load_skill.return_value = "prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = "<architecture_md>\narch\n</architecture_md>"

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    mock_llm.generate.assert_called_once()
    _, kwargs = mock_llm.generate.call_args
    assert kwargs["agent"] == "architect"


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_graceful_failure(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent handles LLM exceptions without raising."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "summary"
    mock_load_skill.return_value = "prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.side_effect = RuntimeError("LLM timeout")

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    # Should not raise
    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert not arch_file.exists()


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
@patch("hooks.stop.analyze_codebase")
@patch("hooks.stop.shutil.which")
def test_generate_architecture_no_tags(
    mock_which, mock_analyze, mock_load_skill, mock_llm_class, tmp_path
):
    """Architect agent skips write when response has no tags."""
    mock_which.return_value = "/usr/bin/claude"
    mock_analyze.return_value = "summary"
    mock_load_skill.return_value = "prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = "Some response without XML tags"

    context_file = tmp_path / "context.md"
    context_file.write_text("# Context")

    generate_architecture(context_file, "/tmp", {})

    arch_file = tmp_path / "architecture.md"
    assert not arch_file.exists()


# --- Quality review gate tests ---


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_review_generated_files_pass(mock_load_skill, mock_llm_class, tmp_path):
    """Quality reviewer returns PASS verdict and uses quality-reviewer agent."""
    mock_load_skill.return_value = "reviewer skill prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = (
        "All checks passed.\n\n<review_verdict>VERDICT: PASS</review_verdict>"
    )

    context_file = tmp_path / "context.md"
    context_file.write_text("# Project Context\n\n## Decisions\n- D1")
    arch_file = tmp_path / "architecture.md"
    arch_file.write_text("Plugin overview.")

    result = review_generated_files(
        str(context_file), str(arch_file), "", "", {}
    )

    assert result["verdict"] == "PASS"
    assert "All checks passed" in result["findings"]
    mock_load_skill.assert_called_once_with("reviewer-agent")

    # Verify quality-reviewer agent is used
    _, kwargs = mock_llm.generate.call_args
    assert kwargs["agent"] == "quality-reviewer"


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_review_generated_files_needs_changes(mock_load_skill, mock_llm_class, tmp_path):
    """Quality reviewer returns NEEDS_CHANGES verdict."""
    mock_load_skill.return_value = "reviewer skill prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.return_value = (
        "Missing Patterns section.\n\n"
        "<review_verdict>VERDICT: NEEDS_CHANGES</review_verdict>"
    )

    context_file = tmp_path / "context.md"
    context_file.write_text("# Project Context\n\n## Decisions\n- D1")
    arch_file = tmp_path / "architecture.md"
    arch_file.write_text("Overview.")

    result = review_generated_files(
        str(context_file), str(arch_file), "", "", {}
    )

    assert result["verdict"] == "NEEDS_CHANGES"


@patch("hooks.stop.load_skill_prompt")
def test_review_generated_files_missing_skill(mock_load_skill, tmp_path):
    """Quality reviewer defaults to PASS when skill prompt is missing."""
    mock_load_skill.return_value = ""

    result = review_generated_files(
        str(tmp_path / "context.md"), str(tmp_path / "arch.md"), "", "", {}
    )

    assert result["verdict"] == "PASS"


@patch("utils.llm_client.LLMClient")
@patch("hooks.stop.load_skill_prompt")
def test_review_generated_files_llm_failure(mock_load_skill, mock_llm_class, tmp_path):
    """Quality reviewer defaults to PASS when LLM raises an exception."""
    mock_load_skill.return_value = "reviewer skill prompt"

    mock_llm = mock_llm_class.return_value
    mock_llm.generate.side_effect = RuntimeError("LLM timeout")

    result = review_generated_files(
        str(tmp_path / "context.md"), str(tmp_path / "arch.md"), "", "", {}
    )

    assert result["verdict"] == "PASS"


def test_revert_files(tmp_path):
    """_revert_files restores backup content to existing files."""
    context_file = tmp_path / "context.md"
    arch_file = tmp_path / "architecture.md"

    # Write "new" (bad) content
    context_file.write_text("bad context")
    arch_file.write_text("bad arch")

    # Revert to backup
    backups = {
        str(context_file): "# Project Context\n\n## Decisions\n- Good",
        str(arch_file): "Original architecture.",
    }
    _revert_files(backups)

    assert context_file.read_text() == "# Project Context\n\n## Decisions\n- Good"
    assert arch_file.read_text() == "Original architecture."


def test_revert_files_removes_new(tmp_path):
    """_revert_files deletes file when backup is None (file was newly created)."""
    new_file = tmp_path / "context.md"
    new_file.write_text("should be deleted")

    backups = {str(new_file): None}
    _revert_files(backups)

    assert not new_file.exists()
