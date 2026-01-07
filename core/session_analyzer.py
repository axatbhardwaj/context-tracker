#!/usr/bin/env python3
"""Session analyzer for context-tracker plugin.

Extracts file changes and reasoning from Claude Code sessions.
"""

import json
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path

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


@dataclass
class SessionContext:
    """Rich context extracted from a Claude Code session."""
    user_goal: str = ""
    summary: str = ""
    decisions_made: List[str] = field(default_factory=list)
    problems_solved: List[str] = field(default_factory=list)
    future_work: List[str] = field(default_factory=list)


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
        """Generate meaningful description of change.

        Args:
            tool_name: Name of the tool used
            file_path: Path to file
            tool_input: Tool input parameters

        Returns:
            Brief description string
        """
        file_name = Path(file_path).name

        if tool_name == 'Write':
            return self._describe_new_file(file_path, tool_input)

        if tool_name == 'Edit':
            return self._describe_edit(file_path, tool_input)

        if tool_name == 'MultiEdit':
            edit_count = len(tool_input.get('edits', []))
            return f"Multiple updates ({edit_count} changes)"

        return "Modified"

    def _describe_new_file(self, file_path: str, tool_input: Dict[str, Any]) -> str:
        """Describe a newly created file."""
        content = tool_input.get('content', '')
        file_name = Path(file_path).name
        ext = Path(file_path).suffix

        # Detect file type and purpose
        if 'test' in file_path.lower() or file_name.startswith('test_'):
            return "Added test file"
        if file_name == 'conftest.py':
            return "Added pytest fixtures"
        if ext == '.md':
            return "Added documentation"
        if 'config' in file_name.lower():
            return "Added configuration"

        # Check content for clues
        if 'class ' in content:
            match = self._extract_pattern(content, r'class\s+(\w+)')
            if match:
                return f"Added {match} class"
        if 'def ' in content:
            match = self._extract_pattern(content, r'def\s+(\w+)')
            if match:
                return f"Added {match} function"

        return "Created new file"

    def _describe_edit(self, file_path: str, tool_input: Dict[str, Any]) -> str:
        """Describe an edit to existing file."""
        old_text = tool_input.get('old_string', '')
        new_text = tool_input.get('new_string', '')

        if not old_text or not new_text:
            return "Updated file"

        # Check for common patterns
        if 'def ' in new_text and 'def ' not in old_text:
            match = self._extract_pattern(new_text, r'def\s+(\w+)')
            if match:
                return f"Added {match} function"

        if 'class ' in new_text and 'class ' not in old_text:
            match = self._extract_pattern(new_text, r'class\s+(\w+)')
            if match:
                return f"Added {match} class"

        if 'import ' in new_text and 'import ' not in old_text:
            return "Added imports"

        if len(new_text) > len(old_text) * 1.5:
            return "Extended functionality"

        if len(new_text) < len(old_text) * 0.7:
            return "Simplified code"

        # Check for fix patterns
        if 'fix' in new_text.lower() or 'bug' in new_text.lower():
            return "Fixed bug"

        return "Updated logic"

    def _extract_pattern(self, text: str, pattern: str) -> str:
        """Extract first match from text using regex."""
        import re
        match = re.search(pattern, text)
        return match.group(1) if match else ""

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

    def extract_session_context(self, changes: List[FileChange]) -> SessionContext:
        """Extract rich session context using LLM analysis.

        Args:
            changes: List of FileChange objects

        Returns:
            SessionContext with goal, summary, decisions, problems, future work
        """
        transcript_content = self._get_full_transcript()
        if not transcript_content:
            return self._fallback_context(changes)

        change_summary = '\n'.join([
            f"- {c.action}: {c.file_path}" for c in changes[:15]
        ])

        prompt = f"""Analyze this Claude Code session transcript and extract:

1. USER_GOAL: What was the user trying to accomplish? (1 sentence)
2. SUMMARY: What was done in this session? (1-2 sentences)
3. DECISIONS: Key technical decisions made (list up to 3, or "None")
4. PROBLEMS_SOLVED: Issues or bugs fixed (list up to 3, or "None")
5. FUTURE_WORK: Remaining tasks or TODOs mentioned (list up to 3, or "None")

Files changed:
{change_summary}

Session transcript (last 20000 chars):
{transcript_content[-20000:]}

Respond in this exact format:
USER_GOAL: <goal>
SUMMARY: <summary>
DECISIONS:
- <decision 1>
- <decision 2>
PROBLEMS_SOLVED:
- <problem 1>
FUTURE_WORK:
- <todo 1>"""

        try:
            response = self.llm_client.generate(prompt, max_tokens=600)
            return self._parse_context_response(response)
        except Exception as e:
            logger.warning(f"Failed to extract session context: {e}")
            return self._fallback_context(changes)

    def _get_full_transcript(self) -> str:
        """Get full transcript content for analysis."""
        transcript_path = self.input_data.get('transcript_path')
        if not transcript_path or not Path(transcript_path).exists():
            return ""

        try:
            with open(transcript_path, 'r') as f:
                return f.read()
        except (IOError, OSError):
            return ""

    def _parse_context_response(self, response: str) -> SessionContext:
        """Parse LLM response into SessionContext."""
        ctx = SessionContext()

        lines = response.strip().split('\n')
        current_section = None

        for line in lines:
            line = line.strip()
            if not line:
                continue

            if line.startswith('USER_GOAL:'):
                ctx.user_goal = line.replace('USER_GOAL:', '').strip()
            elif line.startswith('SUMMARY:'):
                ctx.summary = line.replace('SUMMARY:', '').strip()
            elif line.startswith('DECISIONS:'):
                current_section = 'decisions'
            elif line.startswith('PROBLEMS_SOLVED:'):
                current_section = 'problems'
            elif line.startswith('FUTURE_WORK:'):
                current_section = 'future'
            elif line.startswith('- ') and current_section:
                item = line[2:].strip()
                if item.lower() == 'none':
                    continue
                if current_section == 'decisions':
                    ctx.decisions_made.append(item)
                elif current_section == 'problems':
                    ctx.problems_solved.append(item)
                elif current_section == 'future':
                    ctx.future_work.append(item)

        return ctx

    def _fallback_context(self, changes: List[FileChange]) -> SessionContext:
        """Generate fallback context without LLM."""
        file_types = set()
        for c in changes:
            ext = Path(c.file_path).suffix
            if ext:
                file_types.add(ext)

        summary = f"Modified {len(changes)} file(s)"
        if file_types:
            summary += f" ({', '.join(sorted(file_types))})"

        return SessionContext(
            user_goal="",
            summary=summary,
            decisions_made=[],
            problems_solved=[],
            future_work=[]
        )
