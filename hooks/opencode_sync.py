#!/usr/bin/env python3
"""Opencode manual sync hook for context-tracker plugin.

Allows manual injection of context from agents that don't support
automatic stop hooks or transcript access.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path

# Add plugin root to path (parent of parent of this script)
PLUGIN_ROOT = Path(__file__).parent.parent.resolve()
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))

from core.path_classifier import PathClassifier
from core.config_loader import load_config
from core.git_sync import GitSync
from utils.file_utils import ensure_directory
from utils.logger import get_logger

logger = get_logger(__name__)

def update_context_file(context_file: Path, entry: str) -> None:
    """Updates context.md with the new recent work entry."""
    content = ""
    if context_file.exists():
        content = context_file.read_text()

    header = "## Recent Work"
    
    if header in content:
        # Insert after header
        parts = content.split(header, 1)
        pre = parts[0]
        post = parts[1]
        
        # Ensure we handle newlines correctly to keep the list clean
        if post.startswith("\n"):
            new_content = f"{pre}{header}\n{entry}{post}"
        else:
            new_content = f"{pre}{header}\n{entry}\n{post}"
    else:
        # Append header and entry
        if content and not content.endswith("\n"):
            content += "\n"
        new_content = f"{content}\n{header}\n{entry}\n"

    context_file.write_text(new_content)

def main():
    # Read input
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        print(json.dumps({"status": "error", "message": f"Invalid JSON input: {e}"}))
        sys.exit(1)
    
    cwd = input_data.get('cwd')
    session_log_content = input_data.get('session_log_content')
    recent_work_entry = input_data.get('recent_work_entry')
    topics = input_data.get('topics', ['general'])
    
    # Validation
    if not cwd or not os.path.isdir(cwd):
        print(json.dumps({"status": "error", "message": f"Invalid or missing cwd: {cwd}"}))
        sys.exit(1)

    if not session_log_content:
        print(json.dumps({"status": "error", "message": "Missing session_log_content"}))
        sys.exit(1)

    if not recent_work_entry:
        print(json.dumps({"status": "error", "message": "Missing recent_work_entry"}))
        sys.exit(1)

    # Load config
    config = load_config()
    context_root = Path(config.get('context_root', '~/context')).expanduser()
    
    # Classify path
    classification = PathClassifier.classify(cwd, config)
    rel_path = PathClassifier.get_relative_path(cwd, classification, config)
    
    # Determine context directory
    context_dir = context_root / classification / rel_path
    ensure_directory(context_dir)
    
    # 1. Write Session Log
    history_dir = context_dir / "history"
    ensure_directory(history_dir)
    
    now = datetime.now()
    date_str = now.strftime("%Y-%m-%d_%H-%M")
    topic_slug = topics[0].lower().replace(" ", "-")
    log_filename = f"{date_str}_{topic_slug}.md"
    log_file = history_dir / log_filename
    
    log_file.write_text(session_log_content)
    logger.info(f"Written session log: {log_file}")
    
    # 2. Update context.md
    context_file = context_dir / "context.md"
    update_context_file(context_file, recent_work_entry)
    logger.info(f"Updated context file: {context_file}")
    
    # 3. Git Sync
    project_name = Path(cwd).name
    git = GitSync(context_root, config)
    if git.commit_and_push(project_name, topics):
        logger.info("Changes committed and pushed to git")
        
    print(json.dumps({
        "status": "success", 
        "log_file": str(log_file),
        "context_file": str(context_file)
    }))

if __name__ == '__main__':
    main()
