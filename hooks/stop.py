#!/usr/bin/env python3
"""Stop hook for context-tracker plugin."""

import os
import sys
import json
import shutil
import subprocess
import re
import time
from pathlib import Path

# Add plugin root to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT')
if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.session_analyzer import SessionAnalyzer
from core.markdown_writer import MarkdownWriter
from core.topic_detector import TopicDetector
from core.wiki_parser import parse
from core.monorepo_detector import detect_monorepo
from core.path_classifier import PathClassifier
from core.git_sync import GitSync
from core.config_loader import load_config
from utils.file_utils import ensure_directory
from utils.logger import get_logger

logger = get_logger(__name__)


def analyze_codebase(cwd: str) -> str:
    """Analyze codebase structure and git history for LLM context.

    Extracts git log (last 30 commits) and directory structure (depth 2).
    30 commits captures ~2-3 months of activity for pattern detection.

    Args:
        cwd: Project directory to analyze

    Returns:
        Markdown-formatted codebase summary (max 8000 chars)
    """
    output_parts = []

    # Git history shows file relationships and change patterns
    try:
        result = subprocess.run(
            ['git', 'log', '--oneline', '-30'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            output_parts.append("## Recent Git History\n\n```")
            output_parts.append(result.stdout.strip())
            output_parts.append("```\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # Non-git directory or git unavailable; proceed with structure only
        pass

    # Directory depth=2: shows modules/packages (top) and file organization (depth 2)
    try:
        result = subprocess.run(
            ['find', '.', '-maxdepth', '2', '-type', 'f', '-not', '-path', r'*/\.*'],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            output_parts.append("## Directory Structure\n\n```")
            output_parts.append(result.stdout.strip())
            output_parts.append("```\n")
    except (subprocess.TimeoutExpired, FileNotFoundError):
        # find unavailable; return partial summary
        pass

    summary = '\n'.join(output_parts)

    # 8000 char limit for codebase summary sent to LLM
    if len(summary) > 8000:
        summary = summary[:8000] + "\n\n[truncated]"

    return summary if summary else "No codebase information available."


def _is_previously_confirmed(info, config: dict) -> bool:
    """Check if monorepo was previously confirmed by user.

    Called by prompt_monorepo_confirmation to check cache before prompting.
    Cached confirmations avoid prompting user on every session for same monorepo.

    Args:
        info: MonorepoInfo from detection
        config: Plugin configuration

    Returns:
        True if previously confirmed
    """
    confirmed_projects = config.get('monorepo_confirmed_projects', [])
    return info.root in confirmed_projects


def _save_confirmed_project(info, config: dict) -> bool:
    """Save confirmed monorepo to config file.

    Called by prompt_monorepo_confirmation after user confirms.

    Args:
        info: MonorepoInfo from detection
        config: Plugin configuration

    Returns:
        True if save succeeded, False on failure
    """
    confirmed_projects = config.get('monorepo_confirmed_projects', [])
    confirmed_projects.append(info.root)
    config['monorepo_confirmed_projects'] = confirmed_projects

    plugin_root = os.environ.get('CLAUDE_PLUGIN_ROOT')
    if plugin_root:
        config_path = Path(plugin_root) / 'config' / 'config.json'
        try:
            with open(config_path, 'w') as f:
                json.dump(config, f, indent=2)
            return True
        except IOError as e:
            logger.error(f"Failed to save config: {e}")
            return False
    return True


def prompt_monorepo_confirmation(info, config: dict) -> bool:
    """Auto-confirm hierarchical context for monorepo and cache the decision.

    Stop hooks run async without a terminal, so interactive prompts are
    impossible. Always confirms and caches for consistency.

    Args:
        info: MonorepoInfo from detection
        config: Plugin configuration

    Returns:
        True always
    """
    if _is_previously_confirmed(info, config):
        logger.info(f"Monorepo {info.root} previously confirmed")
        return True

    if not _save_confirmed_project(info, config):
        logger.warning("Monorepo confirmation not cached; will re-prompt on next session")
    logger.info(f"Monorepo auto-confirmed: {info.root}")
    return True


def extract_cwd_from_transcript(transcript_path: str) -> str:
    """Extract cwd from transcript path.

    Claude Code stores transcripts in ~/.claude/projects/-home-xzat-project/session.jsonl
    The directory name encodes the path with leading dash and dashes as separators.
    Since dashes in directory names are ambiguous, we try different interpretations.
    """
    if not transcript_path:
        return ''

    path = Path(transcript_path).expanduser()
    project_dir = path.parent.name

    if not project_dir.startswith('-'):
        return ''

    # Remove leading dash and split by dash
    parts = project_dir[1:].split('-')

    # Use dynamic programming to find valid path
    return _find_valid_path_dp(parts)


def _find_valid_path_dp(parts: list) -> str:
    """Find valid path using dynamic programming to try all groupings."""
    n = len(parts)
    if n == 0:
        return ''

    # memo[i] = valid path string for parts[0:i], or None if not found
    memo = [None] * (n + 1)
    memo[0] = ''

    for end in range(1, n + 1):
        # Try all possible last segments
        for start in range(end):
            if memo[start] is None:
                continue

            # Form segment from parts[start:end] joined with dashes
            segment = '-'.join(parts[start:end])
            candidate = memo[start] + '/' + segment

            if Path(candidate).exists():
                memo[end] = candidate
                break  # Take first valid path found

    return memo[n] if memo[n] else '/' + '/'.join(parts)


def load_skill_prompt(skill_name: str) -> str:
    """Load skill prompt from SKILL.md file.

    Args:
        skill_name: Name of skill directory

    Returns:
        Skill prompt content (without frontmatter)
    """
    skill_file = Path(PLUGIN_ROOT) / 'skills' / skill_name / 'SKILL.md'

    if not skill_file.exists():
        return ""

    content = skill_file.read_text()

    # Skip YAML frontmatter
    if content.startswith('---'):
        end_idx = content.find('---', 3)
        if end_idx != -1:
            content = content[end_idx + 3:].strip()

    return content


def update_context_wiki(
    session_content: str,
    context_path: str,
    topics: list,
    config: dict,
) -> dict:
    """Update context.md via technical-writer agent.

    Uses ~/.claude/agents/technical-writer.md (sonnet) for LLM-optimized merging.

    Args:
        session_content: In-memory session entry text
        context_path: Absolute path to context.md file
        topics: Detected topic tags for the session
        config: Plugin configuration dict

    Returns:
        Dict with 'status' and 'context_path' keys on success, 'error' on failure
    """
    from utils.llm_client import LLMClient

    skill_prompt = load_skill_prompt('writer-agent')
    if not skill_prompt:
        return {"status": "error", "error": "writer-agent skill not found"}

    existing_context = ""
    if Path(context_path).exists():
        existing_context = Path(context_path).read_text()

    topics_str = ','.join(topics) if topics else 'general-changes'

    prompt = f"""{skill_prompt}

## Current Task

Analyze this session summary and update the context wiki.

Arguments:
- topics: {topics_str}

### Existing context.md:
```markdown
{existing_context if existing_context else '(new file - create from scratch)'}
```

### Session Summary (Input):
```markdown
{session_content}
```

Output the complete updated context.md content between <context_md> tags.
Then output a JSON summary."""

    try:
        llm = LLMClient(config)
        response = llm.generate(prompt, agent="technical-writer")

        context_match = re.search(
            r'<context_md>(.*?)</context_md>',
            response,
            re.DOTALL
        )

        if context_match:
            new_content = context_match.group(1).strip()
            Path(context_path).parent.mkdir(parents=True, exist_ok=True)
            Path(context_path).write_text(new_content)
            return {"status": "success", "context_path": context_path}

        return {"status": "error", "error": "No context_md tags in response"}

    except Exception as e:
        logger.warning(f"Writer agent failed: {e}")
        return {"status": "error", "error": str(e)}


def generate_architecture(context_path: Path, cwd: str, config: dict):
    """Generate or update architecture.md via architect agent.

    Uses ~/.claude/agents/architect.md (opus) for deep architectural reasoning.
    Writes architecture.md to the same directory as context_path.

    Graceful failure: logs warning and returns without blocking the hook.

    Args:
        context_path: Path to context.md (architecture.md lives in same directory)
        cwd: Project directory for codebase analysis
        config: Plugin configuration
    """
    from utils.llm_client import LLMClient

    if not shutil.which("claude"):
        logger.warning("Claude CLI not found, skipping architecture generation")
        return

    arch_path = context_path.parent / "architecture.md"

    existing_arch = ""
    if arch_path.exists():
        existing_arch = arch_path.read_text()

    logger.info("Generating architecture via architect agent...")

    codebase_summary = analyze_codebase(cwd)

    skill_prompt = load_skill_prompt('architect-agent')
    if not skill_prompt:
        logger.warning("architect-agent skill not found")
        return

    prompt = f"""{skill_prompt}

## Codebase Summary

{codebase_summary}

## Existing architecture.md

```markdown
{existing_arch if existing_arch else '(empty - generate from scratch)'}
```

Output the complete architecture.md content between <architecture_md> tags."""

    try:
        llm = LLMClient(config)
        response = llm.generate(prompt, agent="architect")

        arch_match = re.search(
            r'<architecture_md>(.*?)</architecture_md>',
            response,
            re.DOTALL
        )

        if arch_match:
            new_content = arch_match.group(1).strip()
            if new_content:
                arch_path.parent.mkdir(parents=True, exist_ok=True)
                arch_path.write_text(new_content)
                logger.info(f"Updated architecture: {arch_path}")
            else:
                logger.warning("Architect agent returned empty content, skipping write")
        else:
            logger.warning("No architecture_md tags in response, skipping write")

    except Exception as e:
        logger.warning(f"Architecture generation failed: {e}")


def _revert_files(backups: dict):
    """Restore files from backup after failed quality review.

    For each path in backups:
    - If backup content is not None, write it back (restore previous version)
    - If backup content is None, the file was new — delete it

    Args:
        backups: Dict mapping file path strings to their backup content (str or None)
    """
    for file_path, content in backups.items():
        path = Path(file_path)
        if content is not None:
            path.write_text(content)
            logger.info(f"Reverted: {file_path}")
        else:
            if path.exists():
                path.unlink()
                logger.info(f"Removed new file: {file_path}")


def review_generated_files(
    context_path: str,
    arch_path: str,
    old_context: str,
    old_arch: str,
    config: dict,
) -> dict:
    """Review generated context.md and architecture.md via quality-reviewer agent.

    Graceful degradation: returns PASS verdict on any failure (missing skill,
    LLM error, unparseable response) so the hook is never blocked.

    Args:
        context_path: Path to the new context.md
        arch_path: Path to the new architecture.md
        old_context: Previous context.md content (empty string if new file)
        old_arch: Previous architecture.md content (empty string if new file)
        config: Plugin configuration

    Returns:
        Dict with 'verdict' (str) and 'findings' (str) keys
    """
    from utils.llm_client import LLMClient

    default_pass = {"verdict": "PASS", "findings": ""}

    skill_prompt = load_skill_prompt('reviewer-agent')
    if not skill_prompt:
        logger.warning("reviewer-agent skill not found, defaulting to PASS")
        return default_pass

    new_context = ""
    if Path(context_path).exists():
        new_context = Path(context_path).read_text()

    new_arch = ""
    if Path(arch_path).exists():
        new_arch = Path(arch_path).read_text()

    prompt = f"""{skill_prompt}

## Files to Review

### New context.md:
```markdown
{new_context if new_context else '(empty)'}
```

### Old context.md:
```markdown
{old_context if old_context else '(no previous version)'}
```

### New architecture.md:
```markdown
{new_arch if new_arch else '(empty)'}
```

### Old architecture.md:
```markdown
{old_arch if old_arch else '(no previous version)'}
```

Review these files and output your verdict."""

    try:
        llm = LLMClient(config)
        response = llm.generate(prompt, agent="quality-reviewer")

        verdict_match = re.search(
            r'<review_verdict>(.*?)</review_verdict>',
            response,
            re.DOTALL
        )

        if verdict_match:
            verdict_text = verdict_match.group(1).strip()
            # Extract just the verdict keyword (e.g., "PASS" from "VERDICT: PASS")
            keyword_match = re.search(
                r'VERDICT:\s*(PASS_WITH_CONCERNS|PASS|NEEDS_CHANGES|MUST_ISSUES)',
                verdict_text
            )
            verdict = keyword_match.group(1) if keyword_match else "PASS"
            return {"verdict": verdict, "findings": response}

        logger.warning("No review_verdict tags in response, defaulting to PASS")
        return default_pass

    except Exception as e:
        logger.warning(f"Quality review failed: {e}, defaulting to PASS")
        return default_pass


COOLDOWN_FILE = Path('/tmp/context-tracker-cooldowns.json')
COOLDOWN_HOURS = 2


def check_cooldown(project_path: str) -> bool:
    """Check if cooldown period has elapsed for this project.

    Returns:
        True if hook should run, False if still in cooldown
    """
    if not COOLDOWN_FILE.exists():
        return True

    try:
        cooldowns = json.loads(COOLDOWN_FILE.read_text())
        last_run = cooldowns.get(project_path)
        if not last_run:
            return True

        elapsed = time.time() - last_run
        cooldown_seconds = COOLDOWN_HOURS * 3600
        if elapsed < cooldown_seconds:
            remaining = (cooldown_seconds - elapsed) / 60
            logger.info(f"Cooldown active: {remaining:.0f} minutes remaining")
            return False
        return True
    except Exception as e:
        logger.warning(f"Cooldown check failed: {e}")
        return True


def update_cooldown(project_path: str):
    """Update last run timestamp for this project."""
    try:
        cooldowns = {}
        if COOLDOWN_FILE.exists():
            cooldowns = json.loads(COOLDOWN_FILE.read_text())
        cooldowns[project_path] = time.time()
        COOLDOWN_FILE.write_text(json.dumps(cooldowns, indent=2))
    except Exception as e:
        logger.warning(f"Failed to update cooldown: {e}")


def main():
    """Main entry point for Stop hook."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)

        # Debug: write input to file for inspection
        debug_file = Path('/tmp/claude-hook-debug.json')
        debug_file.write_text(json.dumps(input_data, indent=2))
        logger.info(f"Hook input keys: {list(input_data.keys())}")

        # Stop hooks don't receive cwd - extract from transcript_path
        transcript_path = input_data.get('transcript_path', '')
        cwd = input_data.get('cwd') or extract_cwd_from_transcript(transcript_path)

        logger.info(f"transcript_path: {transcript_path}")
        logger.info(f"Extracted cwd: {cwd}")

        # Load configuration
        config = load_config()

        # Check cooldown before proceeding
        if not check_cooldown(cwd):
            logger.info(f"Skipping due to cooldown: {cwd}")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Check if path is excluded
        if PathClassifier.is_excluded(cwd, config):
            logger.info(f"Skipping excluded path: {cwd}")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Analyze session for changes (lightweight - just file paths)
        analyzer = SessionAnalyzer(input_data, config)
        changes = analyzer.get_changes()
        logger.info(f"Found {len(changes)} file changes")
        for c in changes[:5]:
            logger.info(f"  - {c.action}: {c.file_path}")

        # Skip if no meaningful changes
        min_threshold = config.get('session_config', {}).get('min_changes_threshold', 1)
        if len(changes) < min_threshold:
            logger.info("No significant changes detected")
            print(json.dumps({}), file=sys.stdout)
            sys.exit(0)

        # Classify project path
        classification = PathClassifier.classify(cwd, config)
        context_root = Path(config.get('context_root', '~/context')).expanduser()

        # Monorepo detection with graceful fallback
        context_paths = []
        try:
            monorepo_info = detect_monorepo(cwd)
            if monorepo_info:
                if prompt_monorepo_confirmation(monorepo_info, config):
                    context_paths = PathClassifier.get_monorepo_context_paths(
                        monorepo_info,
                        classification,
                        config
                    )
                    logger.info(f"Using hierarchical context for {monorepo_info.type} monorepo")
                    logger.info(f"Root: {context_paths[0]}")
                    logger.info(f"Workspace: {context_paths[1]}")
                else:
                    logger.info("User declined hierarchical mode, using single context")
        except Exception as e:
            logger.warning(f"Monorepo detection failed: {e}")

        # Fallback to single-repo mode
        if not context_paths:
            rel_path = PathClassifier.get_relative_path(cwd, classification, config)
            context_dir = context_root / classification / rel_path
            context_path = context_dir / "context.md"
            context_paths = [context_path]
        else:
            context_dir = context_paths[1].parent
            context_path = context_paths[1]

        # Ensure context directory exists
        ensure_directory(context_dir)

        # Detect topics from changes
        detector = TopicDetector(config)
        topics_map = detector.detect_topics(changes)
        all_topics = list(topics_map.keys())

        # Snapshot existing files before generation for quality review
        arch_path = context_path.parent / "architecture.md"
        old_context = Path(context_path).read_text() if Path(context_path).exists() else None
        old_arch = arch_path.read_text() if arch_path.exists() else None

        # Use skill-based analysis to update context.md
        logger.info("Extracting session context...")
        session_ctx = analyzer.extract_session_context(changes, all_topics)

        # Session content formatted in-memory — no history file written (ref: DL-006)
        writer = MarkdownWriter(config)
        session_content = writer._format_session_entry(all_topics, changes, session_ctx.summary, session_ctx)

        # Architect agent: update architecture.md (opus) — run once
        generate_architecture(context_path, cwd, config)

        # Writer agent + quality review with retry (up to 3 attempts)
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            # On retry, restore context.md to pre-generation state
            if attempt > 1:
                logger.info(f"Retrying writer agent (attempt {attempt}/{max_attempts})...")
                if old_context is not None:
                    Path(context_path).write_text(old_context)
                elif Path(context_path).exists():
                    Path(context_path).unlink()

            # Writer agent: update context.md (sonnet)
            logger.info("Updating context.md via writer agent...")
            skill_result = update_context_wiki(
                session_content,
                str(context_path),
                all_topics,
                config,
            )

            if skill_result.get('status') == 'error':
                logger.warning(f"Writer agent failed: {skill_result.get('error')}")

            # Quality review gate
            logger.info("Running quality review...")
            review = review_generated_files(
                str(context_path),
                str(arch_path),
                old_context or "",
                old_arch or "",
                config,
            )
            logger.info(f"Quality review verdict: {review['verdict']} (attempt {attempt}/{max_attempts})")

            if review['verdict'] not in ('NEEDS_CHANGES', 'MUST_ISSUES'):
                break
        else:
            # All attempts exhausted — keep generated files (some context > no context)
            logger.warning(f"Quality review failed after {max_attempts} attempts, keeping generated files")

        # Root context captures cross-cutting decisions for monorepos
        if len(context_paths) > 1:
            root_context_path = context_paths[0]
            ensure_directory(root_context_path.parent)
            try:
                root_result = update_context_wiki(
                    session_content,
                    str(root_context_path),
                    all_topics,
                    config,
                )
                logger.info(f"Updated root context: {root_result.get('context_path')}")
            except Exception as e:
                logger.warning(f"Failed to update root context: {e}")

        # Git sync
        git = GitSync(config.get('context_root', '~/context'), config)
        project_name = Path(cwd).name

        if git.commit_and_push(project_name, all_topics):
            logger.info("Changes committed and pushed to git")

        # Update cooldown after successful execution
        update_cooldown(cwd)

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
