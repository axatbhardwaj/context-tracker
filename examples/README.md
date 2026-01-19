# Context Examples

This directory contains examples of the `context.md` file generated and maintained by the Claude Context Tracker.

## Which example should I look at?

### [context-simple.md](./context-simple.md)
**Look at this if:**
- You are starting a **new project**.
- You want to see what the file looks like after the first 2-3 sessions.
- You have a small codebase (script, CLI tool, simple lib).

### [context-detailed.md](./context-detailed.md)
**Look at this if:**
- You want to see a **mature project** history.
- You want to understand how the plugin handles complex architecture and decisions.
- You want to see how patterns and learnings accumulate over time.

## Anti-Patterns (What NOT to do)
*Do not manually edit these files unless necessary.*

The plugin is designed to manage this file automatically. While you *can* edit `context.md` manually to correct mistakes, the power comes from the AI's consistent structure.

**Bad Habits:**
- ❌ Deleting the file to "start fresh" (you lose all history).
- ❌ Manually deleting "old" sessions (Claude needs this history to understand evolution).
- ❌ Changing section headers (e.g., renaming `## Decisions` to `## My Choices`). The plugin relies on these headers to parse the file.
