# hooks/

## Files

| File             | What                                          | When to read                                  |
| ---------------- | --------------------------------------------- | --------------------------------------------- |
| `stop.py`        | Claude Code session capture hook              | Debugging Claude hook execution               |
| `gemini_stop.py` | Gemini CLI session capture hook               | Debugging Gemini hook execution               |
| `hooks.json`     | Hook configuration for Claude Code            | Modifying hook settings                       |

## Functions

| Function                 | What                                                   | When to read                                       |
| ------------------------ | ------------------------------------------------------ | -------------------------------------------------- |
| `analyze_codebase()`     | Extracts git history and directory structure for LLM analysis | Understanding enrichment inputs, analyzing codebase |
| `enrich_empty_sections()` | Populates empty context.md sections via Gemini        | Debugging enrichment failures, understanding flow  |
