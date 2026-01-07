#!/usr/bin/env python3
"""Topic detector for context-tracker plugin."""

import fnmatch
from typing import List, Dict, Any
from pathlib import Path
from collections import defaultdict

from core.session_analyzer import FileChange
from utils.logger import get_logger

logger = get_logger(__name__)


class TopicDetector:
    """Detects topics from file changes using pattern matching."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize topic detector.

        Args:
            config: Plugin configuration with topic patterns
        """
        self.config = config
        self.topic_patterns = config.get('topic_patterns', {}).get('patterns', {})
        self.fallback_topic = config.get('topic_patterns', {}).get('fallback_topic', 'general-changes')

    def detect_topics(self, changes: List[FileChange]) -> Dict[str, List[FileChange]]:
        """Map file changes to topics.

        Args:
            changes: List of FileChange objects

        Returns:
            Dictionary mapping topic names to lists of changes
        """
        topics = defaultdict(list)

        for change in changes:
            topic = self._match_file_to_topic(change.file_path)
            topics[topic].append(change)

        return dict(topics)

    def _match_file_to_topic(self, file_path: str) -> str:
        """Match a file path to a topic using patterns.

        Args:
            file_path: Path to file

        Returns:
            Topic name
        """
        best_match = None
        best_priority = -1

        for topic_name, topic_config in self.topic_patterns.items():
            patterns = topic_config.get('file_patterns', [])
            priority = topic_config.get('priority', 5)

            for pattern in patterns:
                if fnmatch.fnmatch(file_path, pattern):
                    # Higher priority wins
                    if priority > best_priority:
                        best_match = topic_name
                        best_priority = priority
                    break

        return best_match if best_match else self.fallback_topic
