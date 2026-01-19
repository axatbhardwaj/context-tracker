# core/

## Files

| File                   | What                                           | When to read                                     |
| ---------------------- | ---------------------------------------------- | ------------------------------------------------ |
| `session_analyzer.py`  | File change extraction, LLM context extraction | Modifying analysis logic, debugging LLM calls    |
| `wiki_parser.py`       | Wiki markdown parser, WikiKnowledge dataclass  | Modifying wiki format, debugging parse failures  |
| `wiki_merger.py`       | Session-to-wiki merge, deduplication, rotation | Changing merge behavior, tuning similarity       |
| `markdown_writer.py`   | Wiki and session format output                 | Changing output format, debugging file writes    |
| `topic_detector.py`    | File-to-topic mapping rules                    | Adding topics, modifying detection patterns      |
| `git_sync.py`          | Git commit and push automation                 | Debugging git operations, modifying sync         |
| `config_loader.py`     | Config file loading with fallbacks             | Changing config paths, debugging config issues   |
| `path_classifier.py`   | Personal/work project classification           | Changing classification logic, adding patterns   |
| `monorepo_detector.py` | Monorepo detection, workspace identification   | Adding monorepo support, debugging detection     |
| `README.md`            | Architecture, design decisions, invariants     | Understanding wiki system design                 |
| `GEMINI.md`            | Gemini-specific context index                  | Understanding Gemini integration                 |
| `__init__.py`          | Python package marker                          | Understanding package structure                  |
