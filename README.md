# Claude Context Tracker

Automated context tracking plugin for Claude Code that captures what changed and why in every session.

## Features

- 🎯 **Automatic capture** of file changes and reasoning after each session
- 📁 **Topic-based organization** (testing, api-endpoints, configuration, etc.)
- 🔀 **Git sync** to private repository
- 🏢 **Personal/Work classification** based on project paths
- 🤖 **LLM-powered reasoning** extraction
- 📊 **Zero manual intervention** required

## Installation

### Prerequisites
- Claude Code CLI
- Python 3.8+
- Git
- jq (optional, recommended)

### Quick Install

```bash
git clone https://github.com/YOUR_USERNAME/claude-context-tracker.git
cd claude-context-tracker
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
   git clone https://github.com/YOUR_USERNAME/claude-context-tracker.git ~/claude-context-tracker
   ln -s ~/claude-context-tracker ~/.claude/plugins/user/context-tracker
   ```

2. **Add hook to Claude settings:**
   Edit `~/.claude/settings.json` and add:
   ```json
   {
     "hooks": {
       "Stop": [{
         "hooks": [{
           "type": "command",
           "command": "CLAUDE_PLUGIN_ROOT=~/claude-context-tracker python3 ~/claude-context-tracker/hooks/stop.py",
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
2. **Analyze Changes:** Extracts modified files from session transcript
3. **Detect Topics:** Maps files to topics (testing, api-endpoints, etc.)
4. **Extract Reasoning:** Uses LLM to explain WHY changes were made
5. **Write Markdown:** Appends entry to topic file in `~/context/`
6. **Git Sync:** Commits and pushes to your private repository

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
  - `model`: Claude model to use (default: "haiku")
  - `max_tokens`: Maximum tokens for reasoning (default: 150)

See `config/example-config.json` for a complete example with all available options.

## License

MIT License - see LICENSE file

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
