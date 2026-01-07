#!/usr/bin/env python3
"""File utilities for context-tracker plugin."""

from pathlib import Path
from typing import Union
from utils.logger import get_logger

logger = get_logger(__name__)


def ensure_directory(path: Union[str, Path]) -> Path:
    """Ensure a directory exists, creating it if necessary.

    Args:
        path: Directory path

    Returns:
        Path object for the directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def prepend_to_file(file_path: Union[str, Path], content: str) -> None:
    """Prepend content to a file.

    Args:
        file_path: Path to file
        content: Content to prepend
    """
    file_path = Path(file_path)

    try:
        # Read existing content
        if file_path.exists():
            existing_content = file_path.read_text()
        else:
            existing_content = ""

        # Write new content + existing content
        file_path.write_text(content + existing_content)

    except (IOError, OSError) as e:
        logger.error(f"Failed to prepend to file {file_path}: {e}")
        raise
