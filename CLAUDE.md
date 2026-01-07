# CLAUDE.md

## Overview

Automated context tracking plugin that captures file changes and reasoning from Claude Code sessions into a single consolidated context.md per project.

## Index

| File/Directory          | Contents (WHAT)                                                    | Read When (WHEN)                                                  |
| ----------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------------- |
| `hooks/stop.py`         | Session capture hook, topic detection, LLM analysis orchestration  | Debugging session capture, understanding hook flow                |
| `core/session_analyzer.py` | File change extraction, LLM-based context extraction with extended thinking | Modifying session analysis logic, adding new analysis features |
| `core/wiki_parser.py`   | Wiki markdown parser, WikiKnowledge dataclass                      | Modifying wiki format, debugging parse failures                   |
| `core/wiki_merger.py`   | Session-to-wiki merge logic, deduplication, rotation               | Changing merge behavior, tuning similarity threshold              |
| `core/markdown_writer.py` | Wiki and session format writer with structured sections         | Changing output format, debugging file writes                     |
| `core/topic_detector.py` | File-to-topic mapping, topic detection rules                      | Adding new topics, modifying detection patterns                   |
| `core/git_sync.py`      | Git commit and push automation                                     | Debugging git operations, modifying sync behavior                 |
| `core/README.md`        | Wiki architecture, data flow, design decisions                     | Understanding wiki system design                                  |
| `utils/llm_client.py`   | Claude CLI wrapper with extended thinking support                  | Changing LLM configuration, debugging API calls                   |
| `utils/file_utils.py`   | File system helpers, directory creation                            | Adding file utilities, debugging path operations                  |
| `config/config.json`    | User configuration (paths, git, LLM settings)                      | Configuring plugin for your environment                           |
| `config/example-config.json` | Default configuration template                                | Setting up new installation, understanding config options         |
| `plugin.json`           | Plugin metadata and CLI defaults                                   | Modifying plugin metadata                                         |
| `install.sh`            | Installation script with hook setup                                | Installing plugin, troubleshooting setup                          |
| `uninstall.sh`          | Removal script                                                     | Uninstalling plugin                                               |
| `README.md`             | Installation guide, architecture, configuration docs               | Getting started, understanding system design                      |
| `tests/`                | Test suite for all core components                                 | Running tests, adding new test coverage                           |

## Build

No build step required. Python plugin runs directly.

## Test

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python -m pytest tests/test_session_analyzer.py

# Run with coverage
python -m pytest --cov=core --cov=utils tests/
```

## Configuration

Edit `config/config.json` to customize:
- Context storage directory (`context_root`)
- Work/personal path patterns
- LLM model and extended thinking settings
- Git sync behavior

## Output Format

Plugin writes to `~/context/{classification}/{project}/context.md`:
- Wiki-style knowledge base with 5 structured sections (Architecture, Decisions, Patterns, Issues, Recent Work)
- Sessions merge into sections rather than appending logs
- Recent Work maintains last 5 sessions (newest first)
- Deduplication prevents repeated entries (0.8 similarity threshold)
- Graceful fallback to session format on parse failures
