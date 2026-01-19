# Project Context

## Architecture
A Python CLI tool that parses CSV logs and generates daily summary reports.

## Decisions
- **Use standard `argparse` library**: Avoid external dependencies for simple argument parsing to keep installation lightweight.
- **Store config in JSON**: Chosen over YAML for native Python support without extra packages.

## Patterns
- **Error Handling**: Use `try/except` at the top level `main()` only; let low-level functions raise exceptions.
- **File Operations**: Always use `pathlib.Path` instead of `os.path` for cross-platform compatibility.

## Issues
- **Resolved**: Fixed UTF-8 encoding crash on Windows by forcing `encoding='utf-8'` in `open()`.

## Recent Work
### Session [parser] [cli] - 2024-01-15 10:30
#### Goal
Add support for custom delimiter in CSV parser

#### Summary
[parser] Updated `LogParser.parse()` to accept delimiter argument.
[cli] Added `--delimiter` flag to `main.py`.

#### Decisions Made
- Default delimiter remains `,` to preserve backward compatibility.

### Session [reporting] - 2024-01-14 16:45
#### Goal
Fix formatting in output report

#### Summary
[reporting] Adjusted padding in `ReportGenerator` to align columns for double-digit dates.
