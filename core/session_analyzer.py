#!/usr/bin/env python3
"""Session analyzer for context-tracker plugin.

Extracts file changes and reasoning from Claude Code sessions.
"""

import json
from typing import List, Dict, Any
from dataclasses import dataclass
from pathlib import Path

# Import local modules
from utils.llm_client import LLMClient
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class FileChange:
    """Represents a single file change."""
    file_path: str
    action: str  # 'created', 'modified', 'deleted'
    description: str
    lines_added: int = 0
    lines_removed: int = 0


class SessionAnalyzer:
    """Analyzes Claude Code sessions to extract changes and reasoning."""

    # Tools that modify files
    FILE_MODIFICATION_TOOLS = {'Edit', 'Write', 'MultiEdit', 'NotebookEdit'}

    def __init__(self, input_data: Dict[str, Any], config: Dict[str, Any]):
        """Initialize session analyzer.

        Args:
            input_data: Hook input JSON from stdin
            config: Plugin configuration
        """
        self.input_data = input_data
        self.config = config
        self.session_id = input_data.get('session_id', 'unknown')
        self.cwd = input_data.get('cwd', '')
        self.llm_client = LLMClient(config.get('llm_config', {}))

    def get_changes(self) -> List[FileChange]:
        """Extract all file changes from session.

        Returns:
            List of FileChange objects
        """
        changes = []

        # Read session transcript if available
        transcript_path = self.input_data.get('transcript_path')
        if transcript_path and Path(transcript_path).exists():
            try:
                tool_uses = self._parse_transcript(transcript_path)
                changes = self._extract_changes_from_tools(tool_uses)
            except Exception as e:
                logger.warning(f"Failed to parse transcript: {e}")
                # Fallback to input_data
                changes = self._extract_changes_from_input()
        else:
            changes = self._extract_changes_from_input()

        return changes

    def _parse_transcript(self, transcript_path: str) -> List[Dict[str, Any]]:
        """Parse session transcript file for tool uses.

        Args:
            transcript_path: Path to transcript JSONL file

        Returns:
            List of tool use dictionaries
        """
        tool_uses = []

        try:
            with open(transcript_path, 'r') as f:
                for line in f:
                    try:
                        entry = json.loads(line)

                        # Tool uses are nested in message.content[]
                        message = entry.get('message', {})
                        content = message.get('content', [])

                        if isinstance(content, list):
                            for item in content:
                                if isinstance(item, dict) and item.get('type') == 'tool_use':
                                    tool_uses.append({
                                        'name': item.get('name'),
                                        'input': item.get('input', {}),
                                        'timestamp': entry.get('timestamp')
                                    })

                    except json.JSONDecodeError:
                        continue

        except (IOError, OSError) as e:
            logger.error(f"Cannot read transcript: {e}")

        return tool_uses

    def _extract_changes_from_tools(
        self,
        tool_uses: List[Dict[str, Any]]
    ) -> List[FileChange]:
        """Extract file changes from tool uses.

        Args:
            tool_uses: List of tool use dictionaries

        Returns:
            List of FileChange objects
        """
        changes = []
        seen_files = set()

        for tool in tool_uses:
            tool_name = tool.get('name')
            if tool_name not in self.FILE_MODIFICATION_TOOLS:
                continue

            tool_input = tool.get('input', {})
            file_path = tool_input.get('file_path')

            if not file_path:
                continue

            # Deduplicate by file path (keep first occurrence)
            if file_path in seen_files:
                continue
            seen_files.add(file_path)

            # Determine action
            action = 'modified'
            if tool_name == 'Write':
                # Check if file exists to determine created vs modified
                if not Path(file_path).exists():
                    action = 'created'

            # Extract description
            description = self._generate_change_description(
                tool_name,
                file_path,
                tool_input
            )

            changes.append(FileChange(
                file_path=file_path,
                action=action,
                description=description
            ))

        return changes

    def _extract_changes_from_input(self) -> List[FileChange]:
        """Fallback: Extract changes from hook input data.

        Returns:
            List of FileChange objects
        """
        changes = []

        # Check for tool_input in hook data
        tool_input = self.input_data.get('tool_input', {})
        file_path = tool_input.get('file_path')

        if file_path:
            changes.append(FileChange(
                file_path=file_path,
                action='modified',
                description='Modified'
            ))

        return changes

    def _generate_change_description(
        self,
        tool_name: str,
        file_path: str,
        tool_input: Dict[str, Any]
    ) -> str:
        """Generate brief description of change.

        Args:
            tool_name: Name of the tool used
            file_path: Path to file
            tool_input: Tool input parameters

        Returns:
            Brief description string
        """
        file_name = Path(file_path).name

        if tool_name == 'Write':
            return f"Created {file_name}"
        elif tool_name == 'Edit':
            old_text = tool_input.get('old_string', '')
            # Extract first meaningful line for context
            first_line = old_text.split('\n')[0][:50] if old_text else ''
            if first_line:
                return f"Updated {file_name} ({first_line}...)"
            return f"Updated {file_name}"
        elif tool_name == 'MultiEdit':
            edit_count = len(tool_input.get('edits', []))
            return f"Updated {file_name} ({edit_count} edits)"
        else:
            return f"Modified {file_name}"

    def extract_reasoning(self, changes: List[FileChange]) -> str:
        """Extract reasoning for changes using LLM.

        Args:
            changes: List of FileChange objects

        Returns:
            Reasoning string (2-3 sentences)
        """
        if not changes:
            return "No changes detected."

        # Build prompt
        change_summary = '\n'.join([
            f"- {c.action.capitalize()} `{c.file_path}`: {c.description}"
            for c in changes[:10]  # Limit to first 10 for token budget
        ])

        # Get transcript context (last 2000 chars)
        context = self._get_recent_context()

        prompt = f"""Based on this session, explain WHY these changes were made in 2-3 concise sentences.
Focus on the reasoning and purpose, not implementation details.

Changes:
{change_summary}

Session context:
{context}

Respond with reasoning only (no code, no implementation details):"""

        try:
            reasoning = self.llm_client.generate(
                prompt=prompt,
                max_tokens=self.config.get('llm_config', {}).get('max_tokens', 150)
            )
            return reasoning.strip()
        except Exception as e:
            logger.warning(f"Failed to extract reasoning via LLM: {e}")
            # Fallback to simple summary
            return self._fallback_reasoning(changes)

    def _get_recent_context(self, max_chars: int = 2000) -> str:
        """Get recent context from session transcript.

        Args:
            max_chars: Maximum characters to include

        Returns:
            Recent transcript context
        """
        transcript_path = self.input_data.get('transcript_path')
        if not transcript_path or not Path(transcript_path).exists():
            return ""

        try:
            with open(transcript_path, 'r') as f:
                content = f.read()
                # Take last max_chars
                return content[-max_chars:] if len(content) > max_chars else content
        except (IOError, OSError):
            return ""

    def _fallback_reasoning(self, changes: List[FileChange]) -> str:
        """Generate fallback reasoning without LLM.

        Args:
            changes: List of FileChange objects

        Returns:
            Simple reasoning string
        """
        action_counts = {}
        for change in changes:
            action_counts[change.action] = action_counts.get(change.action, 0) + 1

        parts = []
        if action_counts.get('created'):
            parts.append(f"Created {action_counts['created']} file(s)")
        if action_counts.get('modified'):
            parts.append(f"modified {action_counts['modified']} file(s)")
        if action_counts.get('deleted'):
            parts.append(f"deleted {action_counts['deleted']} file(s)")

        return f"Session involved {', '.join(parts)} in the project."
