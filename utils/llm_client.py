#!/usr/bin/env python3
"""LLM client for context-tracker plugin.

Uses Claude Code CLI to make LLM calls - no separate API key needed.
"""

import subprocess
import shutil
from typing import Dict, Any

from utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """LLM client using Claude Code CLI."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        self.max_tokens = config.get('max_tokens', 500)
        self._claude_path = shutil.which('claude')

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        """Generate text using Claude Code CLI.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens to generate (not used with CLI)

        Returns:
            Generated text
        """
        if not self._claude_path:
            logger.warning("claude CLI not found in PATH")
            return self._fallback_response(prompt)

        try:
            result = subprocess.run(
                [self._claude_path, '-p', prompt, '--no-input'],
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode != 0:
                logger.error(f"claude CLI error: {result.stderr}")
                return self._fallback_response(prompt)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("claude CLI timed out")
            return self._fallback_response(prompt)
        except Exception as e:
            logger.error(f"claude CLI error: {e}")
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Generate fallback when CLI unavailable."""
        if "session context" in prompt.lower():
            return ""
        return "Changes made during this session."
