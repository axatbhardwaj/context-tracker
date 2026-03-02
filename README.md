# Claude Context Tracker

> **Archived.** Claude Code now has [built-in auto memory](https://docs.anthropic.com/en/docs/claude-code/memory) (`~/.claude/projects/*/memory/`) that auto-loads persistent context per project. This project is no longer maintained.

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

## Installation for Claude (LLM-Driven)

This section is written so an LLM assistant (Claude Code, etc.) can autonomously install and configure the plugin by following each step exactly.

### Step 0: Gather information from the user

Ask the user for:
1. **Clone location** - Where to clone this repo (default: `~/personal/context-tracker`)
2. **GitHub repo URL** - A private GitHub repo for syncing context (e.g. `git@github.com:username/claude-context.git`). The user must create this repo on GitHub first.
3. **Work directory patterns** - Comma-separated paths for work projects (default: `~/work`)
4. **Personal directory patterns** - Comma-separated paths for personal projects (default: `~/personal, ~/projects`)

### Step 1: Clone context-tracker

```bash
# Use the clone location from Step 0
git clone https://github.com/axatbhardwaj/context-tracker.git <CLONE_LOCATION>
```

**Verify:** The directory exists and contains `install.sh`.

### Step 2: Run the installer

```bash
cd <CLONE_LOCATION>
./install.sh --yes \
  --context-root=~/context \
  --work-patterns="<WORK_PATTERNS>" \
  --personal-patterns="<PERSONAL_PATTERNS>"
```

The `--yes` flag runs non-interactively. The installer will:
- Create the plugin symlink at `~/.claude/plugins/user/context-tracker`
- Add the stop hook to `~/.claude/settings.json`
- Generate `config/config.json` with the user's paths
- Initialize `~/context/` as a git repo with initial commit

**Verify:** All four checks pass:
```bash
test -L ~/.claude/plugins/user/context-tracker && echo "Symlink OK"
grep -q "context-tracker" ~/.claude/settings.json && echo "Hook OK"
test -f <CLONE_LOCATION>/config/config.json && echo "Config OK"
test -d ~/context/.git && echo "Context repo OK"
```

### Step 3: Configure git remote on `~/context/`

The installer creates `~/context/` as a local-only git repo. Without a remote, `git push` silently fails and context is never synced.

```bash
cd ~/context
git remote add origin <GITHUB_REPO_URL>
git push -u origin main
```

**Verify:**
```bash
cd ~/context && git push --dry-run 2>&1
```

**Decision tree based on output:**
- Output contains `Everything up-to-date` or no errors → **Success.** Skip to Step 5.
- Output contains `Permission denied` or `authentication` → **Auth problem.** Proceed to Step 4.
- Output contains `No configured push destination` → **Remote not set.** Re-run Step 3.
- Output contains `does not exist` → **Repo not created on GitHub.** Ask user to create the repo first, then re-run Step 3.

### Step 4: Configure git authentication for `~/context/`

This step ensures `git push` from `~/context/` actually works. **Choose ONE path** based on the user's setup - these are mutually exclusive:

- **Path A (includeIf):** User has `includeIf` entries in `~/.gitconfig` (multiple GitHub identities)
- **Path B (default SSH):** User has a single SSH key for GitHub (no `includeIf`)
- **Path C (HTTPS fallback):** SSH doesn't work; use `gh` CLI instead

**First, determine which path applies:**

```bash
grep -c 'includeIf' ~/.gitconfig 2>/dev/null
```

- If output is `1` or more → **Use Path A**
- If output is `0` or file doesn't exist → **Use Path B**

#### Path A: `includeIf` patterns in `~/.gitconfig`

Users with multiple GitHub identities use `includeIf` in `~/.gitconfig` to scope SSH keys by directory.

**Check if `~/context/` is already covered:**

```bash
cd ~/context && git config core.sshCommand
```

- If this outputs an SSH command (e.g., `ssh -i ~/.ssh/id_personal`) → `~/context/` is already covered. **Skip to Step 5.**
- If empty or no output → `~/context/` is NOT covered. Continue below.

**Fix:** Find which config file the user's personal projects use, then add the same mapping for `~/context/`.

```bash
# List all includeIf entries and their config files
grep -A1 'includeIf' ~/.gitconfig
```

**Ask the user:** "Which of these includeIf config files should `~/context/` use?" Let them pick one (typically the personal one).

Then append to `~/.gitconfig`:
```gitconfig
[includeIf "gitdir:~/context/"]
    path = <CONFIG_FILE_USER_CHOSE>
```

**Verify:**
```bash
cd ~/context && git config core.sshCommand
# Must output an ssh command. If empty, the includeIf entry is wrong.
```

**Done.** Skip to Step 5.

#### Path B: Default SSH key

Test if SSH authentication works with GitHub:

```bash
ssh -T git@github.com 2>&1
```

- If output contains `Hi` and `successfully authenticated` → **SSH works. Skip to Step 5.**
- If output contains `Permission denied` → **SSH not working. Proceed to Path C.**

#### Path C: HTTPS fallback with `gh` CLI

If SSH doesn't work, switch the remote to HTTPS and use `gh` CLI for authentication.

**Check `gh` is installed and authenticated:**
```bash
command -v gh && gh auth status 2>&1
```

- If `gh` is not found → **Ask user** to install it (`https://cli.github.com/`) or configure SSH manually.
- If `gh auth status` shows `Logged in` → Continue below.
- If not logged in → Run `gh auth login` and follow prompts.

**Switch remote to HTTPS** (derive from the SSH URL provided in Step 0):
```bash
cd ~/context
# Convert git@github.com:user/repo.git → https://github.com/user/repo.git
git remote set-url origin https://github.com/<USERNAME>/<REPO>.git
```

Replace `<USERNAME>/<REPO>` with the values from the GitHub repo URL the user provided in Step 0.

**Verify:**
```bash
cd ~/context && git push --dry-run 2>&1
# Must succeed without errors
```

### Step 5: Add context instructions to `~/.claude/CLAUDE.md`

**First, check if context instructions already exist** (idempotency):
```bash
grep -q "Project Context Memory" ~/.claude/CLAUDE.md 2>/dev/null
```

- If the grep matches → **Already present. Skip to Step 6.**
- If no match (or file doesn't exist) → Append the block below to `~/.claude/CLAUDE.md` (create the file if it doesn't exist):

```markdown
# Project Context Memory

Before starting work on any project, check for context at `~/context/{classification}/{project-name}/`:

**Structure:**
- `context.md` - Wiki with Architecture, Decisions, Patterns, Issues, Recent Work
- `history/` - Immutable session logs with full details
- `plans/` - Implementation plans for complex features

**On session start:**
1. Derive path: `~/context/personal/{project-name}/context.md` or `~/context/work/{project-name}/context.md`
2. Read `context.md` if it exists
3. Check Recent Work for what was done last
4. Review Decisions to follow established patterns
5. Check Issues to avoid repeating solved problems

**While working:**
- Follow patterns documented in Decisions section
- Reference history files via `[[Details](history/...)]` links for full context

**Example:**
For project at `~/personal/my-app/`, read `~/context/personal/my-app/context.md`
```

**Verify:** The block is present in `~/.claude/CLAUDE.md`.

### Step 6: End-to-end verification

Run a final push test to confirm everything works:

```bash
cd ~/context && git push --dry-run
```

**Expected:** No errors. If this succeeds, the plugin is fully installed and will sync context after every Claude Code session.

## Quick Install (Interactive)

For manual/interactive installation:

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

**Important:** After running the installer, you still need to:
- Add a git remote to `~/context/` (see Step 3 above)
- Configure git authentication if you use `includeIf` (see Step 4 above)
- Add context instructions to `~/.claude/CLAUDE.md` (see Step 5 above)

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

## How It Works

1. **Stop Hook Triggers:** When you end a Claude Code session
2. **Confirm Execution:** Prompts you to confirm context generation
3. **Analyze Changes:** Extracts modified files from session transcript
3. **Detect Topics:** Maps files to topics (testing, api-endpoints, etc.)
4. **Extract Reasoning:** Uses LLM to explain WHY changes were made
5. **Write Markdown:** Appends single consolidated entry with topic tags to `context.md`
6. **Git Sync:** Commits and pushes to your private repository

## Features

- **Interactive capture** of file changes and reasoning after each session
- **Consolidated output** - single `context.md` per project with inline topic tags
- **LLM-powered summaries** - Sonnet provides richer, more coherent session context
- **Context Enrichment** - Automatically fills empty architecture and pattern sections using codebase analysis via Gemini
- **Git sync** to private repository
- **Personal/Work classification** based on project paths
- **LLM-powered reasoning** extraction with ~12k token input context
- **Minimal intervention** (single confirmation prompt)
- **Monorepo support** - hierarchical context for NX, Turborepo, Lerna, and custom workspaces

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
  - `model`: Claude model to use (default: "sonnet")
  - `max_tokens`: Maximum tokens for session summary (default: 20000)
  - `temperature`: LLM temperature for generation (default: 0.3)

See `config/example-config.json` for a complete example with all available options.

### Context Window

The plugin uses a 50,000 character input context (~12,000 tokens) for transcript analysis, with a 20,000 token output limit for generated summaries. This allows analysis of most session transcripts without truncation.

### Advanced Configuration

#### Cooldown Period

The plugin implements a 2-hour cooldown per project to prevent excessive executions. If you end multiple sessions within 2 hours, subsequent runs will be skipped automatically. The cooldown state is tracked in `/tmp/context-tracker-cooldowns.json`.

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

## License

MIT License - see LICENSE file

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
