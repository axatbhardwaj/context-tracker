"""Tests for config_loader module."""

import json
from pathlib import Path

import pytest

from core.config_loader import _get_default_config, load_config


class TestLoadConfig:
    """Tests for configuration loading."""

    def test_loads_config_json_when_present(self, temp_dir):
        """config.json takes priority over example-config.json."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        # Create both files
        example_config = {"context_root": "~/example"}
        user_config = {"context_root": "~/user"}

        (config_dir / "example-config.json").write_text(json.dumps(example_config))
        (config_dir / "config.json").write_text(json.dumps(user_config))

        import os

        os.environ["CLAUDE_PLUGIN_ROOT"] = str(temp_dir)

        config = load_config()
        assert config["context_root"] == "~/user"

    def test_falls_back_to_example_config(self, temp_dir):
        """Uses example-config.json when config.json doesn't exist."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        example_config = {
            "context_root": "~/example",
            "work_path_patterns": ["~/work/"],
        }
        (config_dir / "example-config.json").write_text(json.dumps(example_config))

        import os

        os.environ["CLAUDE_PLUGIN_ROOT"] = str(temp_dir)

        config = load_config()
        assert config["context_root"] == "~/example"

    def test_returns_defaults_when_no_config(self, temp_dir):
        """Returns default config when no config files exist."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        import os

        os.environ["CLAUDE_PLUGIN_ROOT"] = str(temp_dir)

        config = load_config()
        assert "context_root" in config
        assert config["context_root"] == "~/context"

    def test_merges_config_with_defaults(self, temp_dir):
        """Partial config is merged with defaults."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        partial_config = {"context_root": "~/custom"}
        (config_dir / "config.json").write_text(json.dumps(partial_config))

        import os

        os.environ["CLAUDE_PLUGIN_ROOT"] = str(temp_dir)

        config = load_config()
        assert config["context_root"] == "~/custom"
        assert "git_config" in config
        assert "session_config" in config


class TestDefaultConfig:
    """Tests for default configuration."""

    def test_default_config_has_required_keys(self):
        """Default config contains all required keys."""
        config = _get_default_config()

        assert "context_root" in config
        assert "work_path_patterns" in config
        assert "personal_path_patterns" in config
        assert "excluded_paths" in config
        assert "git_config" in config
        assert "session_config" in config
        assert "llm_config" in config

    def test_default_git_config(self):
        """Default git config has sensible values."""
        config = _get_default_config()

        assert config["git_config"]["auto_commit"] is True
        assert config["git_config"]["auto_push"] is True

    def test_default_llm_config(self):
        """Default LLM config uses sonnet model."""
        config = _get_default_config()

        assert config["llm_config"]["model"] == "sonnet"
        assert config["llm_config"]["max_tokens"] == 20000


class TestConfigValidation:
    """Tests for config validation edge cases."""

    def test_handles_invalid_json(self, temp_dir):
        """Invalid JSON in config file falls back to defaults."""
        config_dir = temp_dir / "config"
        config_dir.mkdir()

        (config_dir / "config.json").write_text("not valid json {")

        import os

        os.environ["CLAUDE_PLUGIN_ROOT"] = str(temp_dir)

        config = load_config()
        assert "context_root" in config

    def test_handles_missing_plugin_root(self):
        """Missing CLAUDE_PLUGIN_ROOT returns defaults."""
        import os

        if "CLAUDE_PLUGIN_ROOT" in os.environ:
            del os.environ["CLAUDE_PLUGIN_ROOT"]

        config = load_config()
        assert "context_root" in config
