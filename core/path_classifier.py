#!/usr/bin/env python3
"""Path classifier for context-tracker plugin."""

from pathlib import Path
from typing import Dict, Any, List

from core.monorepo_detector import MonorepoInfo


class PathClassifier:
    """Classifies project paths as personal or work."""

    @staticmethod
    def classify(cwd: str, config: Dict[str, Any]) -> str:
        """Classify project path.

        Args:
            cwd: Current working directory
            config: Plugin configuration

        Returns:
            'work' or 'personal'
        """
        # Expand ~ in patterns
        work_patterns = [
            str(Path(p).expanduser()) for p in config.get('work_path_patterns', [])
        ]

        for pattern in work_patterns:
            if cwd.startswith(pattern):
                return 'work'

        return 'personal'

    @staticmethod
    def is_excluded(cwd: str, config: Dict[str, Any]) -> bool:
        """Check if path is excluded.

        Args:
            cwd: Current working directory
            config: Plugin configuration

        Returns:
            True if excluded
        """
        excluded = [
            str(Path(p).expanduser()) for p in config.get('excluded_paths', [])
        ]

        for pattern in excluded:
            if cwd.startswith(pattern):
                return True

        return False

    @staticmethod
    def get_relative_path(cwd: str, classification: str, config: Dict[str, Any]) -> str:
        """Extract relative path from cwd for context directory.

        Strips the classification prefix to avoid double nesting like
        ~/context/personal/personal/project.

        Args:
            cwd: Current working directory
            classification: 'work' or 'personal'
            config: Plugin configuration

        Returns:
            Relative path (e.g., 'claude-context-tracker' not 'personal/claude-context-tracker')
        """
        # Get matching pattern for classification
        if classification == 'work':
            patterns = config.get('work_path_patterns', [])
        else:
            patterns = config.get('personal_path_patterns', [])

        # Expand and find matching pattern
        for pattern in patterns:
            expanded = str(Path(pattern).expanduser())
            if cwd.startswith(expanded):
                # Return path after the pattern
                return cwd[len(expanded):].lstrip('/')

        # Fallback: remove home and classification from path
        home = str(Path.home())
        if cwd.startswith(home):
            rel_path = cwd[len(home):].lstrip('/')
            # Strip classification prefix if present
            if rel_path.startswith(classification + '/'):
                rel_path = rel_path[len(classification) + 1:]
            return rel_path

        # Last resort: use last 2 segments
        parts = Path(cwd).parts
        return '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]

    @staticmethod
    def get_monorepo_context_paths(
        info: MonorepoInfo,
        classification: str,
        config: Dict[str, Any]
    ) -> List[Path]:
        """Get context paths for monorepo structure.

        Args:
            info: Monorepo detection info
            classification: 'work' or 'personal'
            config: Plugin configuration

        Returns:
            List of [root_context_path, workspace_context_path]
        """
        if not info.workspace_relative:
            raise ValueError("workspace_relative cannot be empty")

        context_root = Path(config.get('context_root', '~/context')).expanduser()
        monorepo_name = Path(info.root).name

        root_path = context_root / classification / monorepo_name / "context.md"
        workspace_path = context_root / classification / monorepo_name / info.workspace_relative / "context.md"
        return [root_path, workspace_path]
