#!/usr/bin/env python3
"""Markdown writer for context-tracker plugin."""

from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from core.session_analyzer import FileChange
from utils.file_utils import ensure_directory, prepend_to_file
from utils.logger import get_logger

logger = get_logger(__name__)


class MarkdownWriter:
    """Writes session entries to markdown files."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize markdown writer.

        Args:
            config: Plugin configuration
        """
        self.config = config
        self.context_root = Path(config.get('context_root', '~/context')).expanduser()

    def append_session(
        self,
        project_path: str,
        classification: str,
        topic: str,
        changes: List[FileChange],
        reasoning: str
    ) -> Path:
        """Append session entry to topic file.

        Args:
            project_path: Full path to project
            classification: 'work' or 'personal'
            topic: Topic name
            changes: List of FileChange objects
            reasoning: Reasoning string

        Returns:
            Path to written file
        """
        # Determine context directory
        rel_path = self._get_relative_path(project_path)
        context_dir = self.context_root / classification / rel_path

        # Ensure directory exists
        ensure_directory(context_dir)

        # Format session entry
        entry = self._format_session_entry(topic, changes, reasoning)

        # Prepend to topic file (newest first)
        topic_file = context_dir / f"{topic}.md"

        if not topic_file.exists():
            # Create new file with header
            header = f"# {topic.replace('-', ' ').title()}\n\n"
            topic_file.write_text(header + entry)
        else:
            # Prepend to existing file
            prepend_to_file(topic_file, entry)

        return topic_file

    def _get_relative_path(self, project_path: str) -> str:
        """Extract relative path from project path.

        Args:
            project_path: Full project path

        Returns:
            Relative path for context directory
        """
        home = str(Path.home())
        if project_path.startswith(home):
            return project_path[len(home):].lstrip('/')
        return Path(project_path).name

    def _format_session_entry(
        self,
        topic: str,
        changes: List[FileChange],
        reasoning: str
    ) -> str:
        """Format session entry as markdown.

        Args:
            topic: Topic name
            changes: List of FileChange objects
            reasoning: Reasoning string

        Returns:
            Formatted markdown string
        """
        now = datetime.now()
        date_str = now.strftime('%Y-%m-%d')
        time_str = now.strftime('%H:%M')

        # Format changes
        change_lines = []
        for change in changes:
            change_lines.append(
                f"- {change.action.capitalize()} `{change.file_path}`: "
                f"{change.description}"
            )

        changes_md = '\n'.join(change_lines)

        # Build entry
        entry = f"""## Session: {date_str} {time_str}

### Changes
{changes_md}

### Reasoning
{reasoning}

---

"""
        return entry
