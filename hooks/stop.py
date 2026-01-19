#!/usr/bin/env python3
"""Stop hook for context-tracker plugin."""

import os
import sys
import json
import shutil
import subprocess
import re
from pathlib import Path

# Add plugin root to path
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT')
if PLUGIN_ROOT and PLUGIN_ROOT not in sys.path:
    sys.path.insert(0, PLUGIN_ROOT)

from core.session_analyzer import SessionAnalyzer
from core.markdown_writer import MarkdownWriter
from core.topic_detector import TopicDetector
from core.wiki_parser import parse, has_empty_sections
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

    # 8000 char limit: aggressive choice for maximum Gemini context (1M window available)
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


def _build_prompt_message(info) -> str:
    """Build confirmation prompt message.

    Called by prompt_monorepo_confirmation to format user prompt.

    Args:
        info: MonorepoInfo from detection

    Returns:
        Formatted prompt string
    """
    return (
        f"\nDetected {info.type} monorepo at {info.root}.\n"
        f"Workspace: {info.workspace_relative}\n"
        "Use hierarchical context? [Y/n]: "
    )


def _get_user_confirmation() -> bool:
    """Get user confirmation from stdin.

    Called by prompt_monorepo_confirmation to read user input.
    Empty response treated as Yes for faster workflow.

    Returns:
        True if user confirms
    """
    try:
        response = input().strip().lower()
        return response in ('', 'y', 'yes')
    except (EOFError, KeyboardInterrupt):
        print(file=sys.stderr)
        return False


def prompt_monorepo_confirmation(info, config: dict) -> bool:
    """Prompt user to confirm hierarchical context for monorepo.

    Prints to stderr: hook stdout reserved for automation, stderr for user interaction.

    Args:
        info: MonorepoInfo from detection
        config: Plugin configuration

    Returns:
        True if user confirms hierarchical mode
    """
    if _is_previously_confirmed(info, config):
        logger.info(f"Monorepo {info.root} previously confirmed")
        return True

    prompt = _build_prompt_message(info)
    print(prompt, file=sys.stderr, end='', flush=True)

    confirmed = _get_user_confirmation()
    if confirmed:
        if not _save_confirmed_project(info, config):
            logger.warning("Monorepo confirmation not cached; will re-prompt on next session")
        logger.info(f"Monorepo confirmed: {info.root}")

    return confirmed


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


def analyze_with_skill(
    session_content: str,
    context_path: str,
    topics: list,
    config: dict,
    log_file_name: str = "",
) -> dict:
    """Analyze session using skill-based prompt via LLM client.

    Args:
        session_content: Content of the session log
        context_path: Path to context.md file
        topics: List of detected topics
        config: Plugin configuration

    Returns:
        Dict with analysis result
    """
    from utils.llm_client import LLMClient

    skill_prompt = load_skill_prompt('analyze-session')
    if not skill_prompt:
        return {"status": "error", "error": "Skill not found"}

    # Read existing context.md
    existing_context = ""
    if Path(context_path).exists():
        existing_context = Path(context_path).read_text()

    topics_str = ','.join(topics) if topics else 'general-changes'

    # Build prompt with skill instructions and data
    prompt = f"""{skill_prompt}

## Current Task

Analyze this session summary and update the context wiki.

Arguments:
- topics: {topics_str}
- log_file: history/{log_file_name}

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
        # Force provider to be gemini if not specified, or respect config?
        # The user requested generic "gemini integration", so we should prefer gemini here.
        # But LLMClient logic handles config. We should ensure config has provider='gemini'
        # if the user hasn't set it, OR rely on LLMClient default.
        # For now, we trust the config passed in.
        llm = LLMClient(config)
        response = llm.generate(prompt)  # Gemini has large context

        # Extract context.md content from response
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
        logger.warning(f"Skill analysis failed: {e}")
        return {"status": "error", "error": str(e)}


def enrich_empty_sections(context_path: Path, cwd: str, config: dict):
    """Enrich empty sections in context.md using codebase analysis.

    Strategy: Check → Analyze → Generate → Merge → Write
    - Short-circuit on missing context or missing empty sections
    - Analyze codebase to get git + structure context
    - Use Gemini (1M context window) to generate Architecture, Patterns, Key Symbols
    - Extract XML tags from response
    - Merge only sections matching empty placeholders; preserve user edits
    - Graceful failure: skip enrichment and warn on any error (must not block hook)

    Invariants:
    - Never overwrite non-empty sections (user content is sacred)
    - Enrichment failure does not block hook completion
    - Must use Gemini provider regardless of config default (1M context required)

    Edge cases:
    - Malformed XML: log warning, skip enrichment entirely
    - Gemini unavailable: log warning, return gracefully
    - Non-git directory: analyze only file structure

    Args:
        context_path: Path to context.md file
        cwd: Project directory for codebase analysis
        config: Plugin configuration
    """
    from utils.llm_client import LLMClient

    if not context_path.exists():
        logger.info("Context file doesn't exist yet, skipping enrichment")
        return

    existing_content = context_path.read_text()
    wiki = parse(existing_content)

    if not has_empty_sections(wiki):
        logger.info("All sections populated, skipping enrichment")
        return

    if not shutil.which("gemini"):
        logger.warning("Gemini CLI not found, skipping enrichment")
        return

    logger.info("Enriching empty sections with Gemini...")

    codebase_summary = analyze_codebase(cwd)

    skill_prompt = load_skill_prompt('enrich-context')
    if not skill_prompt:
        logger.warning("enrich-context skill not found")
        return

    prompt = f"""{skill_prompt}

## Codebase Summary

{codebase_summary}

## Existing context.md

```markdown
{existing_content}
```

Generate enriched sections for empty placeholders only."""

    try:
        # Ensure Gemini provider: 1M context window required for full codebase analysis
        enrichment_config = config.copy()
        enrichment_config['provider'] = 'gemini'

        llm = LLMClient(enrichment_config)
        response = llm.generate(prompt)

        arch_match = re.search(r'<architecture>(.*?)</architecture>', response, re.DOTALL)
        patterns_match = re.search(r'<patterns>(.*?)</patterns>', response, re.DOTALL)
        symbols_match = re.search(r'<key_symbols>(.*?)</key_symbols>', response, re.DOTALL)

        updated = False
        # Only merge extracted sections where placeholders exist; user edits take precedence
        if arch_match and (not wiki.architecture or re.search(r'_No .* yet\._', wiki.architecture)):
            new_arch = arch_match.group(1).strip()
            existing_content = re.sub(
                r'(## Architecture[^\n]*\n\n)_No architectural notes yet\._',
                r'\1' + new_arch,
                existing_content,
                count=1,
                flags=re.MULTILINE
            )
            updated = True

        if patterns_match and not wiki.patterns:
            new_patterns = patterns_match.group(1).strip()
            existing_content = re.sub(
                r'(## Patterns[^\n]*\n\n)_No patterns identified yet\._',
                r'\1' + new_patterns,
                existing_content,
                flags=re.MULTILINE
            )
            updated = True

        if symbols_match and not wiki.key_symbols:
            new_symbols = symbols_match.group(1).strip()
            existing_content = re.sub(
                r'(## Key Symbols[^\n]*\n\n)_No key symbols tracked yet\._',
                r'\1' + new_symbols,
                existing_content,
                flags=re.MULTILINE
            )
            updated = True

        if updated:
            context_path.write_text(existing_content)
            logger.info("Enrichment complete")
        else:
            logger.info("No sections enriched (XML parsing may have failed)")

    except Exception as e:
        # Graceful failure: enrichment error must not block hook
        logger.warning(f"Enrichment failed: {e}")


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

        # One-time cleanup of legacy topic files
        cleanup_old_topic_files(context_dir)

        # Detect topics from changes
        detector = TopicDetector(config)
        topics_map = detector.detect_topics(changes)
        all_topics = list(topics_map.keys())

        # Use skill-based analysis to update context.md
        logger.info("Extracting session context...")
        session_ctx = analyzer.extract_session_context(changes, all_topics)

        # Write immutable log
        writer = MarkdownWriter(config)
        log_path = writer.write_session_log(
            context_dir,
            all_topics,
            changes,
            reasoning=session_ctx.summary,
            context=session_ctx,
        )
        logger.info(f"Written session log: {log_path}")

        # Update wiki using log content
        logger.info("Updating wiki with Gemini...")
        log_content = log_path.read_text()
        skill_result = analyze_with_skill(
            log_content,
            str(context_path),
            all_topics,
            config,
            log_file_name=log_path.name,
        )

        if skill_result.get('status') == 'error':
            logger.warning(f"Skill analysis failed: {skill_result.get('error')}")
        else:
            logger.info(f"Updated context: {skill_result.get('context_path')}")

        # Enrich empty sections if needed
        enrich_empty_sections(context_path, cwd, config)

        # Root context captures cross-cutting architecture decisions
        if len(context_paths) > 1:
            root_context_path = context_paths[0]
            ensure_directory(root_context_path.parent)
            try:
                root_result = analyze_with_skill(
                    log_content,
                    str(root_context_path),
                    all_topics,
                    config,
                    log_file_name=log_path.name,
                )
                logger.info(f"Updated root context: {root_result.get('context_path')}")
            except Exception as e:
                logger.warning(f"Failed to update root context: {e}")

        # Copy plan files to context directory
        copy_plan_files(changes, context_dir)

        # Git sync
        git = GitSync(config.get('context_root', '~/context'), config)
        project_name = Path(cwd).name

        if git.commit_and_push(project_name, all_topics):
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
