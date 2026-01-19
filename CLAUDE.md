# Claude Context Tracker

Automated context tracking plugin for Claude Code sessions.

## Files

| File           | What                                   | When to read                                |
| -------------- | -------------------------------------- | ------------------------------------------- |
| `README.md`    | Installation, architecture, config     | Getting started, understanding system       |
| `plugin.json`  | Plugin metadata, CLI defaults          | Modifying plugin registration               |
| `install.sh`   | Installation script with hook setup    | Installing, troubleshooting setup           |
| `uninstall.sh` | Removal script                         | Uninstalling plugin                         |
| `GEMINI.md`    | Gemini-specific context index          | Understanding Gemini integration            |
| `Todo.md`      | Project todo list                      | Tracking tasks                              |
| `LICENSE`      | MIT license                            | Licensing questions                         |
| `.gitignore`   | Git ignore patterns                    | Adding ignore patterns                      |

## Subdirectories

| Directory  | What                                        | When to read                                  |
| ---------- | ------------------------------------------- | --------------------------------------------- |
| `core/`    | Session analysis, wiki parsing, git sync    | Modifying analysis logic, debugging core flow |
| `hooks/`   | Claude Code stop hook entry point           | Debugging hook execution, understanding flow  |
| `utils/`   | LLM client, file helpers, logging           | Changing LLM calls, adding utilities          |
| `config/`  | User config, topic patterns                 | Configuring paths, adding topics              |
| `tests/`   | Test suite for all components               | Running tests, adding test coverage           |
| `scripts/` | Shared shell utilities for install scripts  | Modifying install/uninstall behavior          |
| `skills/`  | Claude Code skills for context analysis     | Understanding skill-based analysis            |
| `examples/`| Sample context.md files                     | Understanding output format, learning patterns|

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
