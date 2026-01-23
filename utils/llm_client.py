#!/usr/bin/env python3
"""LLM client for context-tracker plugin.

Uses Claude Code CLI to make LLM calls - no separate API key needed.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict

from utils.logger import get_logger

logger = get_logger(__name__)


class LLMClient:
    """LLM client supporting Claude Code and Gemini CLI."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize LLM client.

        Args:
            config: LLM configuration
        """
        self.config = config
        self.provider = config.get("provider", "claude")
        self.model = config.get("model", "sonnet")
        self.max_tokens = config.get("max_tokens", 20000)

        self._claude_path = shutil.which("claude")
        self._gemini_path = shutil.which("gemini")

    def generate(self, prompt: str, max_tokens: int = None) -> str:
        """Generate text using configured provider.

        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens (not directly used by CLI)

        Returns:
            Generated text
        """
        if self.provider == "gemini":
            return self._generate_gemini(prompt)

        return self._generate_claude(prompt)

    def _generate_claude(self, prompt: str) -> str:
        """Generate using Claude CLI."""
        if not self._claude_path:
            logger.warning("claude CLI not found in PATH")
            return self._fallback_response(prompt)

        try:
            cmd = [self._claude_path, "--print", "--model", self.model]

            # Pass prompt via stdin to avoid shell argument length limits
            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                logger.error(f"claude CLI failed: returncode={result.returncode}")
                # Log stderr for debugging
                return self._fallback_response(prompt)

            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("claude CLI timed out (120s)")
            return self._fallback_response(prompt)
        except Exception as e:
            logger.error(f"claude CLI error: {e}")
            return self._fallback_response(prompt)

    def _generate_gemini(self, prompt: str) -> str:
        """Generate using Gemini CLI."""
        if not self._gemini_path:
            logger.warning("gemini CLI not found in PATH")
            return self._fallback_response(prompt)

        try:
            # Gemini CLI takes prompt via stdin or arg
            cmd = [self._gemini_path]

            result = subprocess.run(
                cmd, input=prompt, capture_output=True, text=True, timeout=120
            )

            if result.returncode != 0:
                logger.error(f"gemini CLI failed: returncode={result.returncode}")
                # Gemini CLI often prints output to stdout even on some errors or warnings
                # But if it failed, we check stderr
                logger.error(f"stderr: {result.stderr}")
                return self._fallback_response(prompt)

            # Clean up potential "Gemini:" prefix or similar if any (usually raw output)
            return result.stdout.strip()

        except subprocess.TimeoutExpired:
            logger.error("gemini CLI timed out (120s)")
            return self._fallback_response(prompt)
        except Exception as e:
            logger.error(f"gemini CLI error: {e}")
            return self._fallback_response(prompt)

    def _fallback_response(self, prompt: str) -> str:
        """Generate fallback when CLI unavailable.

        Warning: Callers cannot distinguish fallback from real LLM output.
        Check logs for 'Using fallback response' warnings.
        """
        logger.warning("Using fallback response - LLM CLI unavailable")
        if "session context" in prompt.lower():
            return ""
        return "Changes made during this session."
