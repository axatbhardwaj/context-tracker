#!/usr/bin/env python3
"""Configuration loader for context-tracker plugin."""

import os
import json
from pathlib import Path
from typing import Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


def load_config() -> Dict[str, Any]:
    """Load plugin configuration.

    Returns:
        Configuration dictionary
    """
    plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
    if not plugin_root:
        logger.error("CLAUDE_PLUGIN_ROOT environment variable not set")
        return _get_default_config()

    # Configuration file paths
    user_config_path = Path(plugin_root) / 'config' / 'config.json'
    example_config_path = Path(plugin_root) / 'config' / 'example-config.json'
    topic_patterns_path = Path(plugin_root) / 'config' / 'topic-patterns.json'

    config = _get_default_config()

    # Prioritize user config, fall back to example config
    config_path = user_config_path if user_config_path.exists() else example_config_path

    if config_path.exists():
        try:
            with open(config_path, 'r') as f:
                config.update(json.load(f))
            logger.info(f"Loaded config from {config_path.name}")
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load config from {config_path}: {e}")
    else:
        logger.warning("No config file found. Using minimal defaults. Copy example-config.json to config.json and customize it.")

    # Load topic patterns
    if topic_patterns_path.exists():
        try:
            with open(topic_patterns_path, 'r') as f:
                config['topic_patterns'] = json.load(f)
        except (IOError, json.JSONDecodeError) as e:
            logger.warning(f"Failed to load topic patterns: {e}")

    return config


def _get_default_config() -> Dict[str, Any]:
    """Get minimal default configuration.

    Returns:
        Default configuration dictionary
    """
    return {
        'context_root': '~/context',
        'work_path_patterns': [],
        'personal_path_patterns': [],
        'excluded_paths': ['/tmp/', '~/.cache/'],
        'git_config': {
            'auto_commit': True,
            'auto_push': True,
            'commit_message_template': 'Context update: {project} - {topics}'
        },
        'session_config': {
            'min_changes_threshold': 1,
            'max_session_entries_per_topic': 50
        },
        'llm_config': {
            'model': 'haiku',
            'max_tokens': 150,
            'temperature': 0.3
        },
        'topic_patterns': {
            'patterns': {},
            'fallback_topic': 'general-changes'
        },
        'monorepo_config': {
            'enabled': True,
            'custom_workspace_dirs': ['subgraphs']
        },
        'monorepo_confirmed_projects': []
    }
