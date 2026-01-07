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
    """LLM client using Claude Code CLI with Sonnet model."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        self.model = config.get('model', 'haiku')
        self.max_tokens = config.get('max_tokens', 20000)
        self._claude_path = shutil.which('claude')

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        """Generate text using Claude Code CLI with Sonnet.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens (not directly used by CLI)

        Returns:
            Generated text
        """
        if not self._claude_path:
            logger.warning("claude CLI not found in PATH")
            return self._fallback_response(prompt)

        try:
            cmd = [
                self._claude_path,
                '-p', prompt,
                '--model', self.model
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # Increased timeout for Sonnet
            )

            if result.returncode != 0:
                logger.error(f"claude CLI error: {result.stderr}")
                return self._fallback_response(prompt)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("claude CLI timed out (120s)")
            return self._fallback_response(prompt)
        except Exception as e:
            logger.error(f"claude CLI error: {e}")
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Generate fallback when CLI unavailable."""
        if "session context" in prompt.lower():
            return ""
        return "Changes made during this session."
