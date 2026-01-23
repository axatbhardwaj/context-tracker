# Claude Context Tracker - Gemini Context

Automated context tracking plugin for Gemini CLI and Claude Code sessions.

## Files

| File           | What                                   | When to read                                |
| -------------- | -------------------------------------- | ------------------------------------------- |
| `README.md`    | Installation, architecture, config     | Getting started, understanding system       |
| `plugin.json`  | Plugin metadata, CLI defaults          | Modifying plugin registration               |
| `install.sh`   | Installation script with hook setup    | Installing, troubleshooting setup           |
| `uninstall.sh` | Removal script                         | Uninstalling plugin                         |
| `GEMINI.md`    | Gemini-specific context index          | Understanding Gemini integration            |
| `CLAUDE.md`    | Claude-specific context index          | Understanding Claude integration            |

## Subdirectories

| Directory  | What                                        | When to read                                  |
| ---------- | ------------------------------------------- | --------------------------------------------- |
| `core/`    | Session analysis, wiki parsing, git sync    | Modifying analysis logic, debugging core flow |
| `hooks/`   | Hook entry points (Claude & Gemini)         | Debugging hook execution, understanding flow  |
| `utils/`   | LLM client, file helpers, logging           | Changing LLM calls, adding utilities          |
| `config/`  | User config, topic patterns                 | Configuring paths, adding topics              |
| `tests/`   | Test suite for all components               | Running tests, adding test coverage           |
| `skills/`  | Skills for context analysis                 | Understanding skill-based analysis            |

## Gemini Usage

Gemini CLI integration is planned but not yet implemented. See `Todo.md` for status.

To use Gemini as the LLM provider for context enrichment (not session capture):
- Set `"provider": "gemini"` in `config/config.json`
- Ensure the `gemini` CLI is installed and authenticated

## Build & Test

```bash
# Run tests
python -m pytest tests/
```
