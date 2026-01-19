# hooks/

## Files

| File         | What                                          | When to read                                  |
| ------------ | --------------------------------------------- | --------------------------------------------- |
| `stop.py`    | Session capture hook, orchestrates analysis   | Debugging hook execution, understanding flow  |
| `hooks.json` | Hook configuration for Claude Code            | Modifying hook settings                       |
| `GEMINI.md`  | Gemini-specific context index                 | Understanding Gemini integration              |
| `__init__.py`| Python package marker                         | Understanding package structure               |

## Functions

| Function                 | What                                                   | When to read                                       |
| ------------------------ | ------------------------------------------------------ | -------------------------------------------------- |
| `analyze_codebase()`     | Extracts git history and directory structure for LLM analysis | Understanding enrichment inputs, analyzing codebase |
| `enrich_empty_sections()` | Populates empty context.md sections via Gemini        | Debugging enrichment failures, understanding flow  |
