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

### Setup

1. **Clone the plugin:**
   ```bash
   git clone https://github.com/axatbhardwaj/claude-context-tracker.git ~/personal/claude-context-tracker
   ln -s ~/personal/claude-context-tracker ~/.claude/plugins/user/context-tracker
   ```

2. **Create context repository:**
   ```bash
   mkdir -p ~/context/{personal,work}
   cd ~/context
   git init
   git remote add origin git@github.com:axatbhardwaj/claude-context.git  # Private repo
   ```

3. **Configure paths:**
   Edit `~/.claude/plugins/user/context-tracker/config/default-config.json`:
   ```json
   {
     "work_path_patterns": ["/home/xzat/valory/", "/home/xzat/work/"],
     "personal_path_patterns": ["/home/xzat/personal/"]
   }
   ```

4. **Test:**
   Make a change in any project and end your Claude Code session. Check `~/context/` for new entries.

## How It Works

1. **Stop Hook Triggers:** When you end a Claude Code session
2. **Analyze Changes:** Extracts modified files from session transcript
3. **Detect Topics:** Maps files to topics (testing, api-endpoints, etc.)
4. **Extract Reasoning:** Uses LLM to explain WHY changes were made
5. **Write Markdown:** Appends entry to topic file in `~/context/`
6. **Git Sync:** Commits and pushes to your private repository

## Configuration

See `config/default-config.json` for full configuration options.

## License

MIT License - see LICENSE file

## Author

axatbhardwaj
