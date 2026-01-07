#!/usr/bin/env python3
"""Path classifier for context-tracker plugin."""

from pathlib import Path
from typing import Dict, Any


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
    def get_relative_path(cwd: str, classification: str) -> str:
        """Extract relative path from cwd for context directory.

        Args:
            cwd: Current working directory
            classification: 'work' or 'personal'

        Returns:
            Relative path (e.g., 'valory/autonolas-subgraph')
        """
        # Remove home directory prefix
        home = str(Path.home())
        if cwd.startswith(home):
            rel_path = cwd[len(home):].lstrip('/')
            return rel_path

        # Fallback: use last 2 segments
        parts = Path(cwd).parts
        return '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
