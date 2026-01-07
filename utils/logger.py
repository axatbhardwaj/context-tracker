#!/usr/bin/env python3
"""Logger utilities for context-tracker plugin."""

import logging
import sys
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__)
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)

    # Only configure if not already configured
    if not logger.handlers:
        # Set level
        logger.setLevel(level or logging.INFO)

        # Create console handler (stderr so it doesn't interfere with stdout JSON)
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)

        # Create formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)

        # Add handler
        logger.addHandler(handler)

    return logger
