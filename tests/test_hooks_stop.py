import sys
from unittest.mock import MagicMock, patch

import pytest

from hooks.stop import confirm_execution


def test_confirm_execution_yes(monkeypatch, capsys):
    """Test confirmation with 'y' input."""
    monkeypatch.setattr("builtins.input", lambda: "y")

    topics = {"topic1": [], "topic2": []}
    assert confirm_execution(topics) is True

    captured = capsys.readouterr()
    assert "Detected topics:" in captured.err
    assert "- topic1" in captured.err
    assert "Generate context and push changes? [Y/n]:" in captured.err


def test_confirm_execution_empty(monkeypatch, capsys):
    """Test confirmation with empty input (default yes)."""
    monkeypatch.setattr("builtins.input", lambda: "")

    topics = {"topic1": []}
    assert confirm_execution(topics) is True


def test_confirm_execution_no(monkeypatch, capsys):
    """Test confirmation with 'n' input."""
    monkeypatch.setattr("builtins.input", lambda: "n")
    # Force interactive mode by making stdin appear as TTY
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    topics = {"topic1": []}
    assert confirm_execution(topics) is False


def test_confirm_execution_no_topics(monkeypatch, capsys):
    """Test confirmation with no topics detected."""
    monkeypatch.setattr("builtins.input", lambda: "y")

    assert confirm_execution({}) is True

    captured = capsys.readouterr()
    assert "Detected topics:" in captured.err
    assert "- general-changes" in captured.err


def test_confirm_execution_keyboard_interrupt(monkeypatch):
    """Test confirmation with keyboard interrupt."""

    def raise_interrupt():
        raise KeyboardInterrupt()

    monkeypatch.setattr("builtins.input", raise_interrupt)
    # Force interactive mode by making stdin appear as TTY
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)

    assert confirm_execution({}) is False


@patch("hooks.stop.sys.exit")
@patch("hooks.stop.confirm_execution")
@patch("hooks.stop.TopicDetector")
@patch("hooks.stop.SessionAnalyzer")
@patch("hooks.stop.load_config")
@patch("hooks.stop.sys.stdin")
def test_main_skips_execution(
    mock_stdin, mock_config, mock_analyzer, mock_detector, mock_confirm, mock_exit
):
    """Test that main exits if user declines confirmation."""
    import hooks.stop

    # Setup mocks
    mock_stdin.read.return_value = '{"transcript_path": "path", "cwd": "/tmp"}'

    # Mock json.load to return dict
    hooks.stop.json.load = MagicMock(
        return_value={"transcript_path": "path", "cwd": "/tmp"}
    )

    mock_config.return_value = {}

    # Mock analyzer
    analyzer_instance = mock_analyzer.return_value
    analyzer_instance.get_changes.return_value = [
        MagicMock(file_path="file1", action="M")
    ]

    # Mock detector
    detector_instance = mock_detector.return_value
    detector_instance.detect_topics.return_value = {"topic1": []}

    # Mock confirmation to return False (User says No)
    mock_confirm.return_value = False

    # Mock PathClassifier to avoid file system calls
    with patch("hooks.stop.PathClassifier") as mock_classifier:
        mock_classifier.is_excluded.return_value = False
        mock_classifier.classify.return_value = "personal"
        mock_classifier.get_relative_path.return_value = "project"

        # Run main
        hooks.stop.main()

        # Verify confirm_execution was called
        mock_confirm.assert_called_once()

        # Verify sys.exit(0) was called
        mock_exit.assert_called_with(0)

        # Verify TopicDetector was called (confirming we got that far)
        detector_instance.detect_topics.assert_called()
