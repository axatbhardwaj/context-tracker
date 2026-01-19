#!/usr/bin/env python3
"""Monorepo detector for context-tracker plugin."""

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Optional
from utils.logger import get_logger

logger = get_logger(__name__)

# Standard markers take precedence over custom patterns to prevent false positives
STANDARD_MARKERS = {
    "nx.json": "nx",
    "turbo.json": "turbo",
    "lerna.json": "lerna",
    "pnpm-workspace.yaml": "pnpm"
}

# NX apps/ + libs/ both detected: apps are deployable, libs are shared
WORKSPACE_DIRS = ["apps", "libs", "packages", "subgraphs"]

# Max 10 levels provides 3x safety margin over real projects (depth=2-3)
MAX_WALK_LEVELS = 10


@dataclass
class MonorepoInfo:
    """Monorepo detection result."""
    root: str
    type: str
    workspace_relative: str
    workspace_name: str
    marker_file: str


def _build_monorepo_info(current: Path, repo_type: str, workspace_info: dict, marker: str) -> MonorepoInfo:
    """Build MonorepoInfo from detection results.

    Called by marker check functions after successful detection.

    Args:
        current: Monorepo root directory
        repo_type: Type identifier (nx, turbo, etc)
        workspace_info: Dict with 'relative' and 'name' keys
        marker: Marker file name

    Returns:
        MonorepoInfo instance
    """
    return MonorepoInfo(
        root=str(current),
        type=repo_type,
        workspace_relative=workspace_info['relative'],
        workspace_name=workspace_info['name'],
        marker_file=marker
    )


def _check_standard_markers(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
    """Check for standard monorepo markers at current directory.

    Called by _check_all_markers during filesystem walk.

    Args:
        current: Directory to check
        start_path: Original cwd for workspace determination

    Returns:
        MonorepoInfo if marker found, None otherwise
    """
    for marker, repo_type in STANDARD_MARKERS.items():
        marker_path = current / marker
        if marker_path.exists():
            workspace_info = _determine_workspace(start_path, current)
            if workspace_info:
                return _build_monorepo_info(current, repo_type, workspace_info, marker)
    return None


def _read_package_json(pkg_json: Path) -> Optional[dict]:
    """Read and parse package.json file.

    Called by _check_npm_workspaces to parse workspaces field.

    Args:
        pkg_json: Path to package.json

    Returns:
        Parsed JSON dict or None on error
    """
    try:
        with open(pkg_json, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _check_npm_workspaces(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
    """Check for npm workspaces in package.json.

    Called by _check_all_markers during filesystem walk.

    Args:
        current: Directory to check
        start_path: Original cwd for workspace determination

    Returns:
        MonorepoInfo if workspaces found, None otherwise
    """
    pkg_json = current / "package.json"
    if not pkg_json.exists():
        return None

    data = _read_package_json(pkg_json)
    if data and "workspaces" in data:
        workspace_info = _determine_workspace(start_path, current)
        if workspace_info:
            return _build_monorepo_info(current, "npm-workspaces", workspace_info, "package.json")
    return None


def _check_custom_patterns(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
    """Check for custom monorepo patterns (e.g., subgraphs/).

    Called by _check_all_markers as fallback after standard markers fail.
    Custom subgraphs/ pattern required: The Graph ecosystem lacks standard monorepo markers.
    Custom patterns run after standard markers to avoid false positives.

    Args:
        current: Directory to check
        start_path: Original cwd for workspace determination

    Returns:
        MonorepoInfo if pattern found, None otherwise
    """
    subgraphs_dir = current / "subgraphs"
    if subgraphs_dir.is_dir() and _has_nested_packages(subgraphs_dir):
        workspace_info = _determine_workspace(start_path, current)
        if workspace_info:
            return _build_monorepo_info(current, "subgraphs", workspace_info, "subgraphs/")
    return None


def _check_all_markers(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
    """Check all marker types at current directory.

    Called by detect_monorepo during upward filesystem walk.
    Standard markers take precedence over custom patterns to prevent false positives.

    Args:
        current: Directory to check
        start_path: Original cwd for workspace determination

    Returns:
        MonorepoInfo if any marker found, None otherwise
    """
    result = _check_standard_markers(current, start_path)
    if result:
        return result

    result = _check_npm_workspaces(current, start_path)
    if result:
        return result

    return _check_custom_patterns(current, start_path)


@lru_cache(maxsize=128)
def detect_monorepo(cwd: str) -> Optional[MonorepoInfo]:
    """Detect monorepo from current working directory.

    Walks up filesystem (max 10 levels) checking for:
    1. Standard markers: nx.json, turbo.json, lerna.json, pnpm-workspace.yaml
    2. package.json with workspaces field
    3. Custom pattern: subgraphs/ directory with nested package.json

    Strategy:
    - Walk upward from cwd to find authoritative markers at monorepo root
    - Standard markers checked first (high confidence), custom patterns second (fallback)
    - Early exit on first marker found: no need to continue walking
    - Workspace determination uses full relative path to prevent namespace collisions

    Why this approach:
    - Real projects nest deep (apps/marketplace/src/pages) but markers are at root
    - Standard markers are authoritative; custom patterns risk false positives
    - LRU cache essential: hook calls this multiple times per session

    Invariants:
    - Detection never blocks session capture (cached, max depth limit, early exit)
    - Standard markers always take precedence over custom patterns
    - Workspace path validation ensures only known conventions recognized

    Performance:
    - Typical case: 2-3 iterations before finding marker at depth 2-3
    - Worst case: 10 iterations (3x safety margin over real examples)
    - Cache hit after first call eliminates filesystem I/O
    - Target: <100ms per call (met by MAX_WALK_LEVELS=10 limit + early exit + LRU cache)

    Cache:
    - Results cached per session - CLI restart required after monorepo structure changes

    Args:
        cwd: Current working directory

    Returns:
        MonorepoInfo if detected, None otherwise
    """
    try:
        current = Path(cwd).resolve()
        start_path = current
    except (OSError, RuntimeError) as e:
        logger.error(f"Invalid path input: {cwd} - {e}")
        return None

    for level in range(MAX_WALK_LEVELS):
        result = _check_all_markers(current, start_path)
        if result:
            return result

        parent = current.parent
        if parent == current:
            break
        current = parent

    return None


def _build_workspace_info(parts: tuple) -> dict:
    """Build workspace info dict from path parts.

    Called by _determine_workspace after path validation.
    Full relative path prevents collisions (apps/marketplace vs libs/marketplace).

    Args:
        parts: Path parts from root to cwd

    Returns:
        Dict with 'relative' and 'name' keys
    """
    if len(parts) >= 2:
        workspace_relative = f"{parts[0]}/{parts[1]}"
        workspace_name = parts[1]
    else:
        workspace_relative = parts[0]
        workspace_name = parts[0]

    return {
        'relative': workspace_relative,
        'name': workspace_name
    }


def _determine_workspace(start_path: Path, root: Path) -> Optional[dict]:
    """Determine workspace relative path and name.

    Called by marker check functions to identify which workspace cwd belongs to.

    Args:
        start_path: Original cwd
        root: Monorepo root

    Returns:
        Dict with 'relative' and 'name' keys, or None if not in workspace
    """
    try:
        relative = start_path.relative_to(root)
    except ValueError:
        return None

    parts = relative.parts
    if not parts:
        return None

    # Workspace directory validation ensures only known conventions are recognized
    if parts[0] not in WORKSPACE_DIRS:
        return None

    return _build_workspace_info(parts)


def _find_package_json_in_subdirs(directory: Path) -> bool:
    """Search subdirectories for package.json files.

    Called by _has_nested_packages to validate nested structure.

    Args:
        directory: Directory to search

    Returns:
        True if package.json found in any subdir
    """
    try:
        for item in directory.iterdir():
            if item.is_dir() and (item / "package.json").exists():
                return True
    except (PermissionError, OSError):
        return False
    return False


def _has_nested_packages(directory: Path) -> bool:
    """Check if directory contains nested package.json files.

    Called by _check_custom_patterns to validate subgraphs/ structure.
    Nested structure detection prevents false positives from coincidental directories.

    Args:
        directory: Directory to check

    Returns:
        True if nested packages found
    """
    if not directory.is_dir():
        return False
    return _find_package_json_in_subdirs(directory)
