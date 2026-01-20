# Claude Context Tracker

## The Problem
You start a Claude Code session, build a feature, and exit. Two weeks later, you return. **Context is gone.**
*   "Why did I choose this library?"
*   "What was I working on last time?"
*   "Did I finish that refactor?"

You waste 15 minutes re-reading code to rebuild your mental model. Claude Code starts fresh, unaware of your previous decisions, architectural patterns, or unfinished tasks.

## The Solution
This plugin automatically builds a **persistent memory** for your projects.
Every time you exit a session, it:
1.  **Analyzes** your session transcript
2.  **Extracts** architectural decisions, patterns, and progress
3.  **Updates** a consolidated `context.md` file
4.  **Syncs** to a private Git repository

When you return, you (and Claude) have a single source of truth for the project's history.

## How It Works

1. **Stop Hook Triggers:** When you end a Claude Code session
2. **Confirm Execution:** Prompts you to confirm context generation
3. **Analyze Changes:** Extracts modified files from session transcript
3. **Detect Topics:** Maps files to topics (testing, api-endpoints, etc.)
4. **Extract Reasoning:** Uses LLM with extended thinking to explain WHY changes were made
5. **Write Markdown:** Appends single consolidated entry with topic tags to `context.md`
6. **Git Sync:** Commits and pushes to your private repository

## Features

- 🎯 **Interactive capture** of file changes and reasoning after each session
- 📄 **Consolidated output** - single `context.md` per project with inline topic tags
- 🧠 **Extended thinking** - Sonnet 4.5 provides richer, more coherent summaries
- 💎 **Context Enrichment** - Automatically fills empty architecture and pattern sections using codebase analysis via Gemini
- 🔀 **Git sync** to private repository
- 🏢 **Personal/Work classification** based on project paths
- 🤖 **LLM-powered reasoning** extraction with 20k token context window
- 📊 **Minimal intervention** (single confirmation prompt)
- 📁 **Monorepo support** - hierarchical context for NX, Turborepo, Lerna, and custom workspaces

## Installation

### Prerequisites
- Claude Code CLI
- Python 3.8+
- Git
- Google Gemini CLI (optional, for context enrichment)
- jq (optional, recommended)

### Quick Install

```bash
git clone https://github.com/axatbhardwaj/context-tracker.git
cd context-tracker
./install.sh
```

The installer will:
1. Create the plugin symlink
2. Configure Claude Code hooks automatically
3. Prompt you to set up your paths (work/personal directories)
4. Initialize the context repository

### Non-Interactive Install

For scripted installs, use flags to skip prompts:

```bash
./install.sh --yes \
  --context-root=~/context \
  --work-patterns="~/work, ~/company" \
  --personal-patterns="~/personal, ~/projects"
```

### Manual Setup

<details>
<summary>Click to expand manual installation steps</summary>

1. **Clone the plugin:**
   ```bash
   git clone https://github.com/axatbhardwaj/context-tracker.git ~/context-tracker
   ln -s ~/context-tracker ~/.claude/plugins/user/context-tracker
   ```

2. **Add hook to Claude settings:**
   Edit `~/.claude/settings.json` and add:
   ```json
   {
     "hooks": {
       "Stop": [{
         "hooks": [{
           "type": "command",
           "command": "CLAUDE_PLUGIN_ROOT=~/context-tracker python3 ~/context-tracker/hooks/stop.py",
           "timeout": 30
         }]
       }]
     }
   }
   ```

3. **Configure paths:**
   ```bash
   cp config/example-config.json config/config.json
   # Edit config/config.json with your paths
   ```

4. **Create context repository:**
   ```bash
   mkdir -p ~/context/{personal,work}
   cd ~/context && git init
   ```

</details>

### Uninstall

```bash
./uninstall.sh
```

This removes the hook and symlink but preserves your context data.

### Test

After installation, start a Claude Code session, make some changes, and exit. Check `~/context/` for new entries.

## Using Captured Context

### 1. Add to Your Claude Config
To make Claude aware of its own history, add this to your global `~/.claude/CLAUDE.md`:

```markdown
# Context Instructions
- Check project context at: ~/context/{personal|work}/{project_name}/context.md
- Use this file to understand architecture, decisions, and patterns before starting work.
```

### 2. What's in context.md?
- **Architecture**: High-level system design.
- **Decisions**: "Why" we did things (alternatives considered, rationale).
- **Patterns**: Established coding standards to follow.
- **Recent Work**: Summary of previous sessions.

### 3. Example Queries
Once configured, you can ask things like:
- "Check context.md for the auth pattern we decided on."
- "What was the last thing I worked on regarding the API?"
- "Why did we choose generic views? Check the Decisions section."

## Examples

See the [examples/](examples/) directory for complete files:

- **[Simple Example](examples/context-simple.md)**: Typical for a new project or script.
- **[Detailed Example](examples/context-detailed.md)**: Shows a mature project with complex architecture.

## Architecture

### Consolidated Context Flow

```
Before (fragmented):
Session -> TopicDetector -> [topic1, topic2, topic3]
                                |       |       |
                                v       v       v
                           topic1.md topic2.md topic3.md

After (consolidated):
Session -> TopicDetector -> [topic1, topic2, topic3]
                                      |
                                      v
                              context.md (all topics as tags)
```

### Data Flow

```
stop.py hook input (stdin JSON)
         |
         v
SessionAnalyzer.get_changes() -> List[FileChange]
         |
         v
TopicDetector.detect_topics() -> Dict[topic: List[FileChange]]
         |
         v
SessionAnalyzer.extract_session_context() -> SessionContext
         |                                    (uses extended thinking)
         v
MarkdownWriter.write_session_log() -> writes history/YYYY-MM-DD_topic.md
         |
         v
analyze_with_skill() -> updates context.md (using Gemini/LLM)
         |
         v
enrich_empty_sections() -> populates empty sections (using Gemini)
         |
         v
copy_plan_files() -> plans/ directory
         |
         v
GitSync.commit_and_push()
```

### Output Format

Each session produces a single entry in `context.md`:

```markdown
## Session [testing] [api-endpoints] - 2024-01-07 14:30

### Goal
Implement user authentication endpoint with JWT tokens

### Summary
[testing] Added unit tests for token validation
[api-endpoints] Created /auth/login endpoint with bcrypt password hashing

### Decisions Made
- JWT tokens expire after 24h (balance security vs UX)
- Bcrypt cost factor 12 (OWASP recommendation)

### Problems Solved
- Fixed race condition in token refresh logic

### Future Work
- Add refresh token rotation
- Implement rate limiting
```

Topics appear as inline tags `[topic-name]` rather than separate files, enabling:
- Complete session context in one location
- Easy filtering by topic via text search
- No cross-file correlation needed

## Configuration

The plugin uses `config/config.json` for user configuration. If this file doesn't exist, it falls back to `config/example-config.json`.

### Configuration Options

- **context_root**: Directory where context files are stored (default: `~/context`)
- **work_path_patterns**: List of directory patterns for work projects
- **personal_path_patterns**: List of directory patterns for personal projects
- **excluded_paths**: Paths to ignore when tracking changes
- **git_config**: Git synchronization settings
  - `auto_commit`: Automatically commit changes (default: true)
  - `auto_push`: Automatically push to remote (default: true)
  - `commit_message_template`: Template for commit messages
- **session_config**: Session tracking settings
  - `min_changes_threshold`: Minimum file changes to trigger tracking
  - `max_session_entries_per_topic`: Max entries per topic file
- **llm_config**: LLM settings for reasoning extraction
  - `model`: Claude model to use (default: "claude-sonnet-4-5-20250514")
  - `max_tokens`: Maximum tokens for session summary (default: 20000)
  - `thinking_budget`: Extended thinking token budget (default: 10000)
  - `temperature`: LLM temperature for generation (default: 0.3)

See `config/example-config.json` for a complete example with all available options.

### Extended Thinking Configuration

The plugin uses Claude's extended thinking capability for richer context extraction:

- **thinking_budget**: 10,000 tokens by default - balances quality vs cost
- Adds ~5-10 seconds latency per session (acceptable for background operation)
- Produces more coherent consolidated summaries than standard mode
- Set `thinking_budget: 0` to disable extended thinking if needed

The 20,000 token context window allows analysis of full session transcripts without truncation.

## Monorepo Support

The plugin automatically detects and supports monorepo structures, creating hierarchical context files that mirror your repository organization.

### Supported Monorepo Types

- **NX Workspaces**: Detects `nx.json` and creates context for `apps/` and `libs/` directories
- **Turborepo**: Detects `turbo.json` with `packages/` workspaces
- **Lerna**: Detects `lerna.json` with `packages/` workspaces
- **pnpm Workspaces**: Detects `pnpm-workspace.yaml`
- **npm/Yarn Workspaces**: Detects `workspaces` field in `package.json`
- **Custom Patterns**: Supports The Graph subgraphs and other custom workspace layouts

### How It Works

When you end a session in a monorepo workspace (e.g., `~/work/autonolas-frontend-mono/apps/marketplace`), the plugin:

1. **Detects the monorepo** by walking up the filesystem looking for markers (nx.json, turbo.json, etc.)
2. **Prompts for confirmation** the first time: `Detected NX monorepo. Use hierarchical context? [Y/n]`
3. **Creates two context files**:
   - **Root context**: `~/context/work/autonolas-frontend-mono/context.md` - captures cross-cutting architecture decisions
   - **Workspace context**: `~/context/work/autonolas-frontend-mono/apps/marketplace/context.md` - tracks workspace-specific changes

### Example Structure

For a typical NX monorepo like `autonolas-frontend-mono`:

```
~/context/work/autonolas-frontend-mono/
├── context.md                           # Root: shared patterns, NX config, architecture
├── apps/
│   ├── marketplace/
│   │   └── context.md                   # Marketplace app: features, API, UI components
│   └── dashboard/
│       └── context.md                   # Dashboard app: analytics, reporting
└── libs/
    ├── ui-components/
    │   └── context.md                   # Shared UI library: design system, components
    └── auth/
        └── context.md                   # Shared auth library: JWT, permissions
```

### Benefits

- **Workspace isolation**: Each app/lib gets its own context history
- **Shared knowledge**: Root context captures decisions affecting all workspaces
- **Navigation efficiency**: LLM can find relevant context without searching unrelated workspace histories
- **Scalability**: Works with monorepos containing dozens of workspaces

### Configuration

Once confirmed, the monorepo is cached in `config/config.json`:

```json
{
  "monorepo_confirmed_projects": [
    "/home/user/work/autonolas-frontend-mono"
  ]
}
```

You won't be prompted again for subsequent sessions in this monorepo.

### Custom Workspace Patterns

To add custom workspace directories beyond the defaults (`apps/`, `libs/`, `packages/`, `subgraphs/`), edit `config/config.json`:

```json
{
  "monorepo_config": {
    "enabled": true,
    "custom_workspace_dirs": [
      "subgraphs",
      "services",
      "plugins"
    ]
  }
}
```

See [examples/context-monorepo.md](examples/context-monorepo.md) for a complete example.

## Opencode Integration

The plugin supports Opencode via manual synchronization since Opencode currently lacks automatic stop hooks.

### Setup

1. **Copy the agent definition**:
   ```bash
   cp agents/context-tracker.md ~/.config/opencode/agents/
   ```

2. **Add global rules** (optional but recommended):
   Add the following to `~/.config/opencode/AGENTS.md`:
   ```markdown
   # Context Tracking (Opencode)

   At the end of a session, invoke the context-tracker:
   @context-tracker Sync: <brief summary of what was done>
   ```

### Usage

Trigger a manual sync by mentioning the agent with a summary of your changes:

`@context-tracker Sync: Added login feature`

The agent will then:
1. Generate a detailed session log.
2. Call `opencode_sync.py` to update your `context.md` and history.
3. Sync the changes to your private Git repository.

## License

MIT License - see LICENSE file

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
