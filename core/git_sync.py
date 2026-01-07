#!/usr/bin/env python3
"""Git synchronization for context-tracker plugin."""

import subprocess
from pathlib import Path
from typing import List, Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)


class GitSync:
    """Handles git operations for context repository."""

    def __init__(self, context_root: str, config: Dict[str, Any]):
        """Initialize git sync.

        Args:
            context_root: Path to context repository
            config: Plugin configuration
        """
        self.context_root = Path(context_root).expanduser()
        self.config = config.get('git_config', {})

    def commit_and_push(self, project_name: str, topics: List[str]) -> bool:
        """Commit and push changes to git repository.

        Args:
            project_name: Name of project
            topics: List of topics updated

        Returns:
            True if successful
        """
        if not self.config.get('auto_commit', True):
            return False

        try:
            # Stage all changes
            subprocess.run(
                ['git', 'add', '.'],
                cwd=self.context_root,
                check=True,
                capture_output=True
            )

            # Create commit message
            topic_str = ', '.join(topics[:3])
            if len(topics) > 3:
                topic_str += f" +{len(topics) - 3} more"

            message = self.config.get(
                'commit_message_template',
                'Context update: {project} - {topics}'
            )
            message = message.format(project=project_name, topics=topic_str)

            # Commit
            subprocess.run(
                ['git', 'commit', '-m', message],
                cwd=self.context_root,
                check=True,
                capture_output=True
            )

            # Push if enabled
            if self.config.get('auto_push', True):
                subprocess.run(
                    ['git', 'push'],
                    cwd=self.context_root,
                    check=True,
                    capture_output=True
                )

            return True

        except subprocess.CalledProcessError as e:
            logger.warning(f"Git operation failed: {e}")
            return False
