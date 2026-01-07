#!/usr/bin/env python3
"""Stop hook for context-tracker plugin."""

import os
import sys
import json
from pathlib import Path

# Add plugin root to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT')
if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.session_analyzer import SessionAnalyzer
from core.topic_detector import TopicDetector
from core.path_classifier import PathClassifier
from core.markdown_writer import MarkdownWriter
from core.git_sync import GitSync
from core.config_loader import load_config
from utils.logger import get_logger

logger = get_logger(__name__)


def main():
    """Main entry point for Stop hook."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)

        cwd = input_data.get('cwd', '')
        session_id = input_data.get('session_id', '')

        # Load configuration
        config = load_config()

        # Check if path is excluded
        if PathClassifier.is_excluded(cwd, config):
            logger.info(f"Skipping excluded path: {cwd}")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Analyze session for changes
        analyzer = SessionAnalyzer(input_data, config)
        changes = analyzer.get_changes()

        # Skip if no meaningful changes
        min_threshold = config.get('session_config', {}).get('min_changes_threshold', 1)
        if len(changes) < min_threshold:
            logger.info("No significant changes detected")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Classify project path
        classification = PathClassifier.classify(cwd, config)

        # Detect topics from changes
        detector = TopicDetector(config)
        topics_map = detector.detect_topics(changes)

        # Extract rich session context via LLM
        session_context = analyzer.extract_session_context(changes)

        # Fallback reasoning if context extraction failed
        reasoning = session_context.summary or analyzer.extract_reasoning(changes)

        # Write to context files
        writer = MarkdownWriter(config)
        written_files = []

        for topic, topic_changes in topics_map.items():
            file_path = writer.append_session(
                project_path=cwd,
                classification=classification,
                topic=topic,
                changes=topic_changes,
                reasoning=reasoning,
                context=session_context
            )
            written_files.append(file_path)
            logger.info(f"Updated {file_path}")

        # Git sync
        git = GitSync(config.get('context_root', '~/context'), config)
        project_name = Path(cwd).name
        topics_list = list(topics_map.keys())

        if git.commit_and_push(project_name, topics_list):
            logger.info("Changes committed and pushed to git")

        # Success
        print(json.dumps({}), file=sys.stdout)

    except Exception as e:
        # Log error but don't block
        logger.error(f"Context tracker error: {e}", exc_info=True)
        error_msg = {"systemMessage": f"Context tracker error: {str(e)}"}
        print(json.dumps(error_msg), file=sys.stdout)

    finally:
        sys.exit(0)


if __name__ == '__main__':
    main()
