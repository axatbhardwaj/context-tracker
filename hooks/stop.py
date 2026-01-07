#!/usr/bin/env python3
"""Stop hook for context-tracker plugin."""

import os
import sys
import json
import shutil
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
from utils.file_utils import ensure_directory
from utils.logger import get_logger

logger = get_logger(__name__)


def copy_plan_files(changes, context_dir: Path):
    """Copy plan files to context directory."""
    plans_dir = context_dir / 'plans'

    for change in changes:
        file_path = Path(change.file_path)

        # Check if it's a plan file
        if '.claude/plans/' in str(file_path) or '/plans/' in str(file_path):
            if file_path.exists() and file_path.suffix == '.md':
                ensure_directory(plans_dir)
                dest = plans_dir / file_path.name
                shutil.copy2(file_path, dest)
                logger.info(f"Copied plan file: {file_path.name}")


def cleanup_old_topic_files(context_dir: Path):
    """Delete legacy .md files in context directory, preserving context.md.

    Runs once per project (marker file gates re-execution). Non-recursive glob
    excludes plans/ subdirectory. Skips execution if marker exists.

    Args:
        context_dir: Context directory for current project
    """
    marker_file = context_dir / '.migrated'

    # Marker file gates cleanup execution (only runs once per project)
    if marker_file.exists():
        return

    # Non-recursive glob naturally excludes plans/ subdirectory
    if not context_dir.exists():
        return

    for md_file in context_dir.glob('*.md'):
        # Skip context.md during cleanup
        if md_file.name == 'context.md':
            continue

        md_file.unlink()
        logger.info(f"Deleted old topic file: {md_file.name}")

    # Marker prevents accidental re-deletion on subsequent runs
    marker_file.touch()


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

        # Pass topics to LLM for inline tagging in consolidated summary
        all_topics = list(topics_map.keys())
        session_context = analyzer.extract_session_context(changes, topics=all_topics)

        # Fallback reasoning if context extraction failed
        reasoning = session_context.summary or analyzer.extract_reasoning(changes)

        # Write to context files
        writer = MarkdownWriter(config)

        # One-time cleanup of legacy topic files
        context_root = Path(config.get('context_root', '~/context')).expanduser()
        rel_path = cwd.replace(str(Path.home()), '').lstrip('/')
        context_dir = context_root / classification / rel_path
        cleanup_old_topic_files(context_dir)

        # Write all topics to single context.md entry
        file_path = writer.append_session(
            project_path=cwd,
            classification=classification,
            topics=all_topics,
            changes=changes,
            reasoning=reasoning,
            context=session_context
        )
        logger.info(f"Updated {file_path}")

        # Copy plan files to context directory
        context_root = Path(config.get('context_root', '~/context')).expanduser()
        rel_path = cwd.replace(str(Path.home()), '').lstrip('/')
        context_dir = context_root / classification / rel_path
        copy_plan_files(changes, context_dir)

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
