# Monorepo Support

## Overview

Currently the plugin creates a single `context.md` per project directory. For monorepos with multiple packages/services (like `autonolas-frontend-mono` with NX or `autonolas-subgraph` with custom subgraphs), all context gets mixed into one file.

**Chosen approach**: Nested hierarchy with interactive confirmation. Support both standard monorepo markers (nx.json, lerna.json, pnpm-workspace.yaml, turbo.json, npm workspaces) AND custom patterns (like `subgraphs/` directory for The Graph projects). When detected, prompt user to confirm, then create hierarchical context files.

## Planning Context

### Decision Log

| Decision | Reasoning Chain |
|----------|-----------------|
| Nested hierarchy over flat naming | User selected Option A -> mirrors mental model of monorepo structure -> easier to navigate (e.g., `~/context/work/autonolas-frontend-mono/apps/marketplace/context.md`) |
| Interactive confirmation when monorepo detected | User specified -> prevents false positives -> user controls activation -> can skip with config |
| Always create root context.md | User selected -> cross-cutting architecture decisions need home -> shared patterns documented once -> NX libs/ decisions affect all apps |
| Support all major monorepo types | User selected -> nx.json (autonolas-frontend-mono), lerna.json, pnpm-workspace.yaml, turbo.json, npm workspaces covers standard tools |
| Support custom subgraphs/ pattern | Real example: autonolas-subgraph uses `subgraphs/` directory -> no standard marker -> detect via nested package.json -> common in The Graph ecosystem |
| Detection order: markers first, then custom patterns | Standard markers are authoritative -> custom patterns (subgraphs/) as fallback -> prevents false positives from coincidental directories |
| Walk up filesystem to find monorepo root | cwd may be deep (apps/marketplace/src/pages) -> need to find root marker -> stop at filesystem root -> max 10 levels |
| Use full relative path for workspace name | apps/marketplace not just marketplace -> prevents collision (apps/auth vs libs/auth) -> matches mental model |
| NX workspaces in apps/ AND libs/ | autonolas-frontend-mono has both -> apps are deployable, libs are shared -> both deserve context tracking |
| Separate monorepo_detector module | Detection logic is complex (multiple marker types, custom patterns) -> deserves isolation -> easier testing |
| Max 10 filesystem levels for walk | Tested on real examples (autonolas-frontend-mono depth=3, autonolas-subgraph depth=2) -> 10 levels provides 3x safety margin -> early exit on marker found limits actual traversal -> alternative (unlimited) risks infinite loops on symlinks |
| Standard markers: nx.json, turbo.json, lerna.json, pnpm-workspace.yaml | nx.json (user's autonolas-frontend-mono uses NX) -> turbo.json, lerna.json, pnpm-workspace.yaml cover npm ecosystem -> package.json workspaces field covers Yarn/npm -> Rush NOT included (no user examples) -> extensible via custom patterns |
| Detect packages/ workspace directory | Lerna/Turborepo convention uses packages/ -> different from NX apps/libs pattern -> common in multi-tool monorepos -> covers broader ecosystem |
| Print prompt to stderr not stdout | Hook output goes to stdout for automation parsing -> user interaction on stderr keeps streams separate -> prevents prompt from corrupting structured output -> aligns with git hook conventions |
| No detection timeout | User specified -> filesystem walks complete quickly on local drives -> hook must not fail on slow network drives -> early exit on marker found limits actual time -> alternative (100ms timeout) risks false negatives |
| Prompt default [Y/n] - Enter accepts | User specified -> faster workflow for users who want hierarchical mode -> monorepo detection already has high confidence -> alternative [y/N] adds friction without benefit |

### Rejected Alternatives

| Alternative | Why Rejected |
|-------------|--------------|
| Flat naming (monorepo--marketplace.context.md) | User selected nested; flat loses structure |
| Auto-detect without confirmation | Risk of false positives; user wants control |
| Only standard markers (skip subgraphs/) | Real projects like autonolas-subgraph use custom patterns |
| Detect via directory names only (packages/, apps/) | Too many false positives; marker files + nested package.json are authoritative |

### Constraints & Assumptions

- Must preserve backward compatibility with single-repo projects
- Detection must complete in <100ms
- No external dependencies (stdlib only)
- Git sync must handle nested context directories
- Existing path classification (work/personal) must continue working
- Real examples: `~/valory/autonolas-frontend-mono` (NX), `~/valory/autonolas-subgraph` (custom)
- `<default-conventions domain="file-creation">` applied: new module for detector
- `<default-conventions domain="testing">` applied: unit tests for detection logic

### Known Risks

| Risk | Mitigation | Anchor |
|------|------------|--------|
| False positive monorepo detection | Interactive confirmation; standard markers take precedence over custom patterns | N/A |
| Custom pattern (subgraphs/) too specific | Make custom patterns configurable in config.json; default includes subgraphs/ | N/A |
| Performance from filesystem walks | Cache result; max 10 levels; early exit on marker found | N/A |
| NX apps vs libs confusion | Detect both as workspaces; both get context files | N/A |

## Invisible Knowledge

### Architecture

```
Session End (cwd = ~/valory/autonolas-frontend-mono/apps/marketplace/src)
        |
        v
+-------------------+
| detect_monorepo() |  <- Walk up to find nx.json
+-------------------+
        |
        v
+-------------------+
| MonorepoInfo      |  <- root=~/valory/autonolas-frontend-mono
|   type="nx"       |     workspace_relative="apps/marketplace"
|   workspace="marketplace"
+-------------------+
        |
        v
+-------------------+
| prompt_confirm()  |  <- "Detected NX monorepo. Use hierarchical context? [Y/n]"
+-------------------+
        |
        v (if confirmed)
+-------------------+
| context paths:    |
|  - root: ~/context/work/autonolas-frontend-mono/context.md
|  - workspace: ~/context/work/autonolas-frontend-mono/apps/marketplace/context.md
+-------------------+
```

### Data Flow

```
Standard Marker Detection:
  cwd -> walk up -> find nx.json/turbo.json/lerna.json/pnpm-workspace.yaml
       -> MonorepoInfo(type="nx", ...)

Custom Pattern Detection (fallback):
  cwd -> walk up -> find subgraphs/ with nested package.json
       -> MonorepoInfo(type="subgraphs", ...)

No Monorepo:
  cwd -> walk up -> no markers, no custom patterns
       -> None (use single-repo mode)
```

### Why This Structure

- **monorepo_detector.py separate from path_classifier.py**: Detection logic handles multiple marker types + custom patterns + filesystem walking -> complex enough for own module
- **Custom patterns configurable**: subgraphs/ is The Graph specific -> other ecosystems may have similar patterns -> config allows extension
- **NX apps/ + libs/ both detected**: autonolas-frontend-mono uses both -> libs contain shared code that also evolves -> both deserve context

### Invariants

- Single-repo projects must work exactly as before
- Monorepo detection must not block session capture on failure
- Root context.md always created when monorepo confirmed
- Standard markers take precedence over custom patterns
- Workspace path uses full relative path from monorepo root

### Tradeoffs

- **Complexity vs Coverage**: Supporting custom patterns (subgraphs/) adds complexity but covers real projects
- **Prompt vs Auto-detect**: Prompt adds friction but prevents false positives

## Milestones

### Milestone 1: Monorepo Detector Module

**Files**: `core/monorepo_detector.py` (NEW)

**Flags**: `needs-rationale`, `complex-algorithm`

**Requirements**:
- Create MonorepoInfo dataclass with: root, type, workspace_relative, workspace_name, marker_file. All fields needed for path construction and user prompt.
- Implement `detect_monorepo(cwd: str) -> Optional[MonorepoInfo]` that walks up filesystem from cwd (max 10 levels, Decision: "Max 10 filesystem levels" provides 3x safety margin)
- Support standard markers: nx.json, turbo.json, lerna.json, pnpm-workspace.yaml, package.json with workspaces (Decision: "Standard markers" covers npm ecosystem)
- Support custom pattern: `subgraphs/` directory with nested package.json (Decision: "Support custom subgraphs/ pattern" for The Graph ecosystem)
- Standard markers checked first, custom patterns second (Decision: "Detection order" prevents false positives)
- Determine workspace_relative based on workspace directories: apps/, libs/, packages/, subgraphs/ (Decision: "NX apps/ + libs/ both detected")
- Cache detection result using @lru_cache (performance: eliminates repeated filesystem I/O)

**Acceptance Criteria**:
- `detect_monorepo("~/valory/autonolas-frontend-mono/apps/marketplace/src")` returns MonorepoInfo(type="nx", workspace_relative="apps/marketplace")
- `detect_monorepo("~/valory/autonolas-subgraph/subgraphs/marketplace")` returns MonorepoInfo(type="subgraphs", workspace_relative="subgraphs/marketplace")
- `detect_monorepo("~/valory/simple-project")` returns None
- Detection completes in <100ms

**Tests**:
- **Test files**: `tests/test_monorepo_detector.py` (NEW)
- **Test type**: unit
- **Backing**: default-derived
- **Scenarios**:
  - Normal: nx.json at root, cwd in apps/marketplace
  - Normal: nx.json at root, cwd in libs/ui-components
  - Normal: subgraphs/ with nested package.json
  - Normal: lerna.json at root
  - Normal: package.json with workspaces field
  - Edge: cwd is monorepo root itself
  - Edge: max depth reached
  - Error: permission denied (graceful skip)

**Code Intent**:
- New file `core/monorepo_detector.py`
- `@dataclass` MonorepoInfo: root, type, workspace_relative, workspace_name, marker_file
- Constant `STANDARD_MARKERS = {"nx.json": "nx", "turbo.json": "turbo", "lerna.json": "lerna", "pnpm-workspace.yaml": "pnpm"}`
- Constant `WORKSPACE_DIRS = ["apps", "libs", "packages", "subgraphs"]` (Decision: "NX apps/ + libs/ both detected")
- Function `detect_monorepo(cwd: str) -> Optional[MonorepoInfo]`:
  - Walk up from cwd checking for standard markers first (Decision: "markers first, then custom patterns")
  - If no marker, check for custom pattern (subgraphs/ with nested package.json)
  - For package.json: parse JSON, check "workspaces" field
  - Determine workspace_relative by finding which WORKSPACE_DIR the cwd is under
  - Return MonorepoInfo or None
- Use `@lru_cache` for session caching

**Code Changes**:

```diff
--- /dev/null
+++ b/core/monorepo_detector.py
@@ -0,0 +1,178 @@
+#!/usr/bin/env python3
+"""Monorepo detector for context-tracker plugin."""
+
+import json
+from dataclasses import dataclass
+from functools import lru_cache
+from pathlib import Path
+from typing import Optional
+from utils.logger import get_logger
+
+logger = get_logger(__name__)
+
+# Standard markers take precedence over custom patterns to prevent false positives
+STANDARD_MARKERS = {
+    "nx.json": "nx",
+    "turbo.json": "turbo",
+    "lerna.json": "lerna",
+    "pnpm-workspace.yaml": "pnpm"
+}
+
+# NX apps/ + libs/ both detected: apps are deployable, libs are shared
+WORKSPACE_DIRS = ["apps", "libs", "packages", "subgraphs"]
+
+# Max 10 levels provides 3x safety margin over real projects (depth=2-3)
+MAX_WALK_LEVELS = 10
+
+
+@dataclass
+class MonorepoInfo:
+    """Monorepo detection result."""
+    root: str
+    type: str
+    workspace_relative: str
+    workspace_name: str
+    marker_file: str
+
+
+def _build_monorepo_info(current: Path, repo_type: str, workspace_info: dict, marker: str) -> MonorepoInfo:
+    """Build MonorepoInfo from detection results.
+
+    Called by marker check functions after successful detection.
+
+    Args:
+        current: Monorepo root directory
+        repo_type: Type identifier (nx, turbo, etc)
+        workspace_info: Dict with 'relative' and 'name' keys
+        marker: Marker file name
+
+    Returns:
+        MonorepoInfo instance
+    """
+    return MonorepoInfo(
+        root=str(current),
+        type=repo_type,
+        workspace_relative=workspace_info['relative'],
+        workspace_name=workspace_info['name'],
+        marker_file=marker
+    )
+
+
+def _check_standard_markers(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
+    """Check for standard monorepo markers at current directory.
+
+    Called by _check_all_markers during filesystem walk.
+
+    Args:
+        current: Directory to check
+        start_path: Original cwd for workspace determination
+
+    Returns:
+        MonorepoInfo if marker found, None otherwise
+    """
+    for marker, repo_type in STANDARD_MARKERS.items():
+        marker_path = current / marker
+        if marker_path.exists():
+            workspace_info = _determine_workspace(start_path, current)
+            if workspace_info:
+                return _build_monorepo_info(current, repo_type, workspace_info, marker)
+    return None
+
+
+def _read_package_json(pkg_json: Path) -> Optional[dict]:
+    """Read and parse package.json file.
+
+    Called by _check_npm_workspaces to parse workspaces field.
+
+    Args:
+        pkg_json: Path to package.json
+
+    Returns:
+        Parsed JSON dict or None on error
+    """
+    try:
+        with open(pkg_json, 'r') as f:
+            return json.load(f)
+    except (json.JSONDecodeError, IOError):
+        return None
+
+
+def _check_npm_workspaces(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
+    """Check for npm workspaces in package.json.
+
+    Called by _check_all_markers during filesystem walk.
+
+    Args:
+        current: Directory to check
+        start_path: Original cwd for workspace determination
+
+    Returns:
+        MonorepoInfo if workspaces found, None otherwise
+    """
+    pkg_json = current / "package.json"
+    if not pkg_json.exists():
+        return None
+
+    data = _read_package_json(pkg_json)
+    if data and "workspaces" in data:
+        workspace_info = _determine_workspace(start_path, current)
+        if workspace_info:
+            return _build_monorepo_info(current, "npm-workspaces", workspace_info, "package.json")
+    return None
+
+
+def _check_custom_patterns(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
+    """Check for custom monorepo patterns (e.g., subgraphs/).
+
+    Called by _check_all_markers as fallback after standard markers fail.
+    Custom subgraphs/ pattern required: The Graph ecosystem lacks standard monorepo markers.
+    Custom patterns run after standard markers to avoid false positives.
+
+    Args:
+        current: Directory to check
+        start_path: Original cwd for workspace determination
+
+    Returns:
+        MonorepoInfo if pattern found, None otherwise
+    """
+    subgraphs_dir = current / "subgraphs"
+    if subgraphs_dir.is_dir() and _has_nested_packages(subgraphs_dir):
+        workspace_info = _determine_workspace(start_path, current)
+        if workspace_info:
+            return _build_monorepo_info(current, "subgraphs", workspace_info, "subgraphs/")
+    return None
+
+
+def _check_all_markers(current: Path, start_path: Path) -> Optional[MonorepoInfo]:
+    """Check all marker types at current directory.
+
+    Called by detect_monorepo during upward filesystem walk.
+    Standard markers take precedence over custom patterns to prevent false positives.
+
+    Args:
+        current: Directory to check
+        start_path: Original cwd for workspace determination
+
+    Returns:
+        MonorepoInfo if any marker found, None otherwise
+    """
+    result = _check_standard_markers(current, start_path)
+    if result:
+        return result
+
+    result = _check_npm_workspaces(current, start_path)
+    if result:
+        return result
+
+    return _check_custom_patterns(current, start_path)
+
+
+@lru_cache(maxsize=128)
+def detect_monorepo(cwd: str) -> Optional[MonorepoInfo]:
+    """Detect monorepo from current working directory.
+
+    Walks up filesystem (max 10 levels) checking for:
+    1. Standard markers: nx.json, turbo.json, lerna.json, pnpm-workspace.yaml
+    2. package.json with workspaces field
+    3. Custom pattern: subgraphs/ directory with nested package.json
+
+    Strategy:
+    - Walk upward from cwd to find authoritative markers at monorepo root
+    - Standard markers checked first (high confidence), custom patterns second (fallback)
+    - Early exit on first marker found: no need to continue walking
+    - Workspace determination uses full relative path to prevent namespace collisions
+
+    Why this approach:
+    - Real projects nest deep (apps/marketplace/src/pages) but markers are at root
+    - Standard markers are authoritative; custom patterns risk false positives
+    - LRU cache essential: hook calls this multiple times per session
+
+    Invariants:
+    - Detection never blocks session capture (cached, max depth limit, early exit)
+    - Standard markers always take precedence over custom patterns
+    - Workspace path validation ensures only known conventions recognized
+
+    Performance:
+    - Typical case: 2-3 iterations before finding marker at depth 2-3
+    - Worst case: 10 iterations (3x safety margin over real examples)
+    - Cache hit after first call eliminates filesystem I/O
+
+    Args:
+        cwd: Current working directory
+
+    Returns:
+        MonorepoInfo if detected, None otherwise
+    """
+    current = Path(cwd).resolve()
+    start_path = current
+
+    for level in range(MAX_WALK_LEVELS):
+        result = _check_all_markers(current, start_path)
+        if result:
+            return result
+
+        parent = current.parent
+        if parent == current:
+            break
+        current = parent
+
+    return None
+
+
+def _build_workspace_info(parts: tuple) -> dict:
+    """Build workspace info dict from path parts.
+
+    Called by _determine_workspace after path validation.
+    Full relative path prevents collisions (apps/marketplace vs libs/marketplace).
+
+    Args:
+        parts: Path parts from root to cwd
+
+    Returns:
+        Dict with 'relative' and 'name' keys
+    """
+    if len(parts) >= 2:
+        workspace_relative = f"{parts[0]}/{parts[1]}"
+        workspace_name = parts[1]
+    else:
+        workspace_relative = parts[0]
+        workspace_name = parts[0]
+
+    return {
+        'relative': workspace_relative,
+        'name': workspace_name
+    }
+
+
+def _determine_workspace(start_path: Path, root: Path) -> Optional[dict]:
+    """Determine workspace relative path and name.
+
+    Called by marker check functions to identify which workspace cwd belongs to.
+
+    Args:
+        start_path: Original cwd
+        root: Monorepo root
+
+    Returns:
+        Dict with 'relative' and 'name' keys, or None if not in workspace
+    """
+    try:
+        relative = start_path.relative_to(root)
+    except ValueError:
+        return None
+
+    parts = relative.parts
+    if not parts:
+        return None
+
+    # Workspace directory validation ensures only known conventions are recognized
+    if parts[0] not in WORKSPACE_DIRS:
+        return None
+
+    return _build_workspace_info(parts)
+
+
+def _find_package_json_in_subdirs(directory: Path) -> bool:
+    """Search subdirectories for package.json files.
+
+    Called by _has_nested_packages to validate nested structure.
+
+    Args:
+        directory: Directory to search
+
+    Returns:
+        True if package.json found in any subdir
+    """
+    try:
+        for item in directory.iterdir():
+            if item.is_dir() and (item / "package.json").exists():
+                return True
+    except (PermissionError, OSError):
+        return False
+    return False
+
+
+def _has_nested_packages(directory: Path) -> bool:
+    """Check if directory contains nested package.json files.
+
+    Called by _check_custom_patterns to validate subgraphs/ structure.
+    Nested structure detection prevents false positives from coincidental directories.
+
+    Args:
+        directory: Directory to check
+
+    Returns:
+        True if nested packages found
+    """
+    if not directory.is_dir():
+        return False
+    return _find_package_json_in_subdirs(directory)
```

---

### Milestone 2: Path Classifier Integration

**Files**: `core/path_classifier.py`

**Flags**: `conformance`

**Requirements**:
- Add `get_monorepo_context_paths()` function that returns list of context paths: [root_path, workspace_path]. Root path captures cross-cutting architecture decisions (shared patterns, NX libs/ decisions). Workspace path captures workspace-specific changes.
- Preserve existing functions for backward compatibility: single-repo projects must work exactly as before (Invariant).

**Acceptance Criteria**:
- `get_monorepo_context_paths(info, "work", config)` returns correct paths for autonolas-frontend-mono structure
- Single-repo projects unchanged

**Tests**:
- **Test files**: `tests/test_path_classifier.py`
- **Test type**: unit
- **Backing**: default-derived
- **Scenarios**:
  - Normal: NX monorepo in work directory
  - Normal: subgraphs monorepo in work directory
  - Edge: workspace at root level

**Code Intent**:
- Import MonorepoInfo from monorepo_detector
- Add function `get_monorepo_context_paths(info: MonorepoInfo, classification: str, config: dict) -> List[Path]`:
  - Root path: context_root / classification / monorepo_name / "context.md"
  - Workspace path: context_root / classification / monorepo_name / workspace_relative / "context.md"
  - Return [root_path, workspace_path]

**Code Changes**:

```diff
--- a/core/path_classifier.py
+++ b/core/path_classifier.py
@@ -1,8 +1,10 @@
 #!/usr/bin/env python3
 """Path classifier for context-tracker plugin."""

 from pathlib import Path
-from typing import Dict, Any
+from typing import Dict, Any, List
+
+from core.monorepo_detector import MonorepoInfo


 class PathClassifier:
@@ -91,3 +93,26 @@ class PathClassifier:
         # Last resort: use last 2 segments
         parts = Path(cwd).parts
         return '/'.join(parts[-2:]) if len(parts) >= 2 else parts[-1]
+
+    @staticmethod
+    def get_monorepo_context_paths(
+        info: MonorepoInfo,
+        classification: str,
+        config: Dict[str, Any]
+    ) -> List[Path]:
+        """Get context paths for monorepo structure.
+
+        Args:
+            info: Monorepo detection info
+            classification: 'work' or 'personal'
+            config: Plugin configuration
+
+        Returns:
+            List of [root_context_path, workspace_context_path]
+        """
+        if not info.workspace_relative:
+            raise ValueError("workspace_relative cannot be empty")
+
+        context_root = Path(config.get('context_root', '~/context')).expanduser()
+        monorepo_name = Path(info.root).name
+
+        root_path = context_root / classification / monorepo_name / "context.md"
+        workspace_path = context_root / classification / monorepo_name / info.workspace_relative / "context.md"
+        return [root_path, workspace_path]
```

---

### Milestone 3: Hook Integration with User Prompt

**Files**: `hooks/stop.py`

**Flags**: `error-handling`, `needs-rationale`

**Requirements**:
- Import and call monorepo detector from cwd
- Prompt user for confirmation if detected (Decision: "Interactive confirmation" prevents false positives, user controls activation)
- On confirm, use hierarchical context paths from path_classifier
- Update both root and workspace context.md files (Decision: "Always create root context.md" for cross-cutting decisions)
- Save confirmed projects to config to avoid re-prompting on subsequent sessions
- Graceful fallback: detection errors must not block session capture (Invariant)

**Acceptance Criteria**:
- Prompt: "Detected NX monorepo at ~/valory/autonolas-frontend-mono. Use hierarchical context? [Y/n]"
- Both root and workspace context.md updated
- Previously confirmed projects skip prompt

**Tests**:
- **Test files**: `tests/test_stop_hook.py`
- **Test type**: integration
- **Backing**: default-derived
- **Scenarios**:
  - Normal: NX monorepo, user confirms
  - Normal: subgraphs monorepo, user confirms
  - Normal: user declines, single context used
  - Edge: previously confirmed project

**Code Intent**:
- Import from monorepo_detector and path_classifier
- Add `prompt_monorepo_confirmation(info: MonorepoInfo, config: dict) -> bool`:
  - Check config["monorepo_confirmed_projects"] for previous confirmation
  - If not confirmed, print prompt to stderr, read response
  - Save to config if confirmed
- In main():
  - Call detect_monorepo(cwd)
  - If detected and confirmed: use get_monorepo_context_paths()
  - Update both context files
  - Wrap in try/except for graceful fallback

**Code Changes**:

Add import statements at the top of the file:

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -19,6 +19,7 @@ from core.session_analyzer import SessionAnalyzer
 from core.markdown_writer import MarkdownWriter
 from core.topic_detector import TopicDetector
 from core.wiki_parser import parse, has_empty_sections
+from core.monorepo_detector import detect_monorepo
 from core.path_classifier import PathClassifier
 from core.git_sync import GitSync
 from core.config_loader import load_config
```

Add prompt_monorepo_confirmation function after analyze_codebase:

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -85,6 +85,60 @@ def analyze_codebase(cwd: str) -> str:
     return summary if summary else "No codebase information available."


+def _is_previously_confirmed(info, config: dict) -> bool:
+    """Check if monorepo was previously confirmed by user.
+
+    Called by prompt_monorepo_confirmation to check cache before prompting.
+    Cached confirmations avoid prompting user on every session for same monorepo.
+
+    Args:
+        info: MonorepoInfo from detection
+        config: Plugin configuration
+
+    Returns:
+        True if previously confirmed
+    """
+    confirmed_projects = config.get('monorepo_confirmed_projects', [])
+    return info.root in confirmed_projects
+
+
+def _save_confirmed_project(info, config: dict) -> None:
+    """Save confirmed monorepo to config file.
+
+    Called by prompt_monorepo_confirmation after user confirms.
+
+    Args:
+        info: MonorepoInfo from detection
+        config: Plugin configuration
+    """
+    confirmed_projects = config.get('monorepo_confirmed_projects', [])
+    confirmed_projects.append(info.root)
+    config['monorepo_confirmed_projects'] = confirmed_projects
+
+    plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
+    if plugin_root:
+        config_path = Path(plugin_root) / 'config' / 'config.json'
+        try:
+            with open(config_path, 'w') as f:
+                json.dump(config, f, indent=2)
+        except IOError as e:
+            logger.warning(f"Failed to save config: {e}")
+
+
+def _build_prompt_message(info) -> str:
+    """Build confirmation prompt message.
+
+    Called by prompt_monorepo_confirmation to format user prompt.
+
+    Args:
+        info: MonorepoInfo from detection
+
+    Returns:
+        Formatted prompt string
+    """
+    return (
+        f"\nDetected {info.type} monorepo at {info.root}.\n"
+        f"Workspace: {info.workspace_relative}\n"
+        "Use hierarchical context? [Y/n]: "
+    )
+
+
+def _get_user_confirmation() -> bool:
+    """Get user confirmation from stdin.
+
+    Called by prompt_monorepo_confirmation to read user input.
+    Empty response treated as Yes for faster workflow (Decision: "Prompt default [Y/n]").
+
+    Returns:
+        True if user confirms
+    """
+    try:
+        response = input().strip().lower()
+        return response in ('', 'y', 'yes')
+    except (EOFError, KeyboardInterrupt):
+        print(file=sys.stderr)
+        return False
+
+
+def prompt_monorepo_confirmation(info, config: dict) -> bool:
+    """Prompt user to confirm hierarchical context for monorepo.
+
+    Prints to stderr: hook stdout reserved for automation, stderr for user interaction.
+
+    Args:
+        info: MonorepoInfo from detection
+        config: Plugin configuration
+
+    Returns:
+        True if user confirms hierarchical mode
+    """
+    if _is_previously_confirmed(info, config):
+        logger.info(f"Monorepo {info.root} previously confirmed")
+        return True
+
+    prompt = _build_prompt_message(info)
+    print(prompt, file=sys.stderr, end='', flush=True)
+
+    confirmed = _get_user_confirmation()
+    if confirmed:
+        _save_confirmed_project(info, config)
+        logger.info(f"Monorepo confirmed: {info.root}")
+
+    return confirmed
+
+
 def copy_plan_files(changes, context_dir: Path):
     """Copy plan files to context directory."""
     plans_dir = context_dir / 'plans'
```

Update main() to integrate monorepo detection after path classification:

```diff
--- a/hooks/stop.py
+++ b/hooks/stop.py
@@ -453,12 +453,50 @@ def main():
             print(json.dumps({}), file=sys.stdout)
             sys.exit(0)

-        # Classify project path and build context path
+        # Classify project path
         classification = PathClassifier.classify(cwd, config)
         context_root = Path(config.get('context_root', '~/context')).expanduser()
-        rel_path = PathClassifier.get_relative_path(cwd, classification, config)
-        context_dir = context_root / classification / rel_path
-        context_path = context_dir / "context.md"
+
+        # Monorepo detection with graceful fallback
+        context_paths = []
+        try:
+            monorepo_info = detect_monorepo(cwd)
+            if monorepo_info:
+                if prompt_monorepo_confirmation(monorepo_info, config):
+                    # Hierarchical mode: both root and workspace contexts updated
+                    context_paths = PathClassifier.get_monorepo_context_paths(
+                        monorepo_info,
+                        classification,
+                        config
+                    )
+                    logger.info(f"Using hierarchical context for {monorepo_info.type} monorepo")
+                    logger.info(f"Root: {context_paths[0]}")
+                    logger.info(f"Workspace: {context_paths[1]}")
+                else:
+                    logger.info("User declined hierarchical mode, using single context")
+        except Exception as e:
+            # Detection errors must not block session capture (Invariant)
+            logger.warning(f"Monorepo detection failed: {e}")
+
+        # Fallback to single-repo mode
+        if not context_paths:
+            rel_path = PathClassifier.get_relative_path(cwd, classification, config)
+            context_dir = context_root / classification / rel_path
+            context_path = context_dir / "context.md"
+            context_paths = [context_path]
+        else:
+            # Workspace context is primary: session changes are workspace-scoped
+            context_dir = context_paths[1].parent
+            context_path = context_paths[1]

         # Ensure context directory exists
         ensure_directory(context_dir)
@@ -505,6 +543,17 @@ def main():
         # Enrich empty sections if needed
         enrich_empty_sections(context_path, cwd, config)

+        # Root context captures cross-cutting architecture decisions (Decision: "Always create root context.md")
+        if len(context_paths) > 1:
+            root_context_path = context_paths[0]
+            ensure_directory(root_context_path.parent)
+            try:
+                root_result = analyze_with_skill(
+                    log_content,
+                    str(root_context_path),
+                    all_topics,
+                    config,
+                    log_file_name=log_path.name,
+                )
+                logger.info(f"Updated root context: {root_result.get('context_path')}")
+            except Exception as e:
+                # Root is secondary to workspace: workspace failure would abort, root failure continues
+                logger.warning(f"Failed to update root context: {e}")
+
         # Copy plan files to context directory
         copy_plan_files(changes, context_dir)
```

---

### Milestone 4: Config Schema Update

**Files**: `config/example-config.json`, `core/config_loader.py`

**Requirements**:
- Add monorepo_config section with custom_workspace_dirs list (Decision: "Custom patterns configurable" for extension beyond subgraphs/)
- Add monorepo_confirmed_projects list to cache user confirmations and avoid re-prompting
- Update config loader with defaults for backward compatibility with existing configs

**Acceptance Criteria**:
- New fields documented in example-config.json
- Old configs work with defaults

**Tests**:
- **Test files**: `tests/test_config_loader.py`
- **Test type**: unit
- **Backing**: default-derived
- **Scenarios**:
  - Normal: new config loads correctly
  - Edge: old config uses defaults

**Code Intent**:
- Update example-config.json:
  ```json
  "monorepo_config": {
    "enabled": true,
    "custom_workspace_dirs": ["subgraphs"]
  },
  "monorepo_confirmed_projects": []
  ```
- Update config_loader.py _get_default_config() with defaults

**Code Changes**:

```diff
--- a/config/example-config.json
+++ b/config/example-config.json
@@ -42,5 +42,12 @@
   "wiki_config": {
     "enabled": true,
     "max_recent_sessions": 5
+  },
+  "monorepo_config": {
+    "enabled": true,
+    "custom_workspace_dirs": [
+      "subgraphs"
+    ]
-  }
+  },
+  "monorepo_confirmed_projects": []
 }
```

```diff
--- a/core/config_loader.py
+++ b/core/config_loader.py
@@ -81,5 +81,11 @@ def _get_default_config() -> Dict[str, Any]:
         'topic_patterns': {
             'patterns': {},
             'fallback_topic': 'general-changes'
+        },
+        'monorepo_config': {
+            'enabled': True,
+            'custom_workspace_dirs': ['subgraphs']
+        },
+        'monorepo_confirmed_projects': []
-        }
+    }
```

---

### Milestone 5: Documentation Update

**Delegated to**: @agent-technical-writer (mode: post-implementation)

**Source**: `## Invisible Knowledge` section of this plan

**Files**:
- `core/CLAUDE.md` (update)
- `core/README.md` (update)
- `README.md` (add Monorepo Support section)
- `examples/context-monorepo.md` (NEW)

**Requirements**:
- Document monorepo detection in core/CLAUDE.md
- Add architecture to core/README.md
- Add "Monorepo Support" section to main README
- Create example showing hierarchical structure

**Acceptance Criteria**:
- CLAUDE.md has monorepo_detector.py entry
- README explains monorepo support
- Example shows real structure like autonolas-frontend-mono

## Milestone Dependencies

```
M1 (detector) ──> M2 (path_classifier) ──> M3 (hook) ──> M5 (docs)
                                              |
                                              v
                                        M4 (config)
```
