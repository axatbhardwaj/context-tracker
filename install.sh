#!/usr/bin/env bash
set -e

# Context Tracker - Installation Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/scripts/setup_utils.sh"

# Configuration
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
PLUGINS_DIR="$CLAUDE_DIR/plugins/user"
PLUGIN_SYMLINK="$PLUGINS_DIR/context-tracker"

# Default values
DEFAULT_CONTEXT_ROOT="~/context"
DEFAULT_WORK_PATTERNS="~/work"
DEFAULT_PERSONAL_PATTERNS="~/personal, ~/projects"

# Parse arguments
NONINTERACTIVE=false
CONTEXT_ROOT=""
WORK_PATTERNS=""
PERSONAL_PATTERNS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes|--non-interactive)
            NONINTERACTIVE=true
            shift
            ;;
        --context-root=*)
            CONTEXT_ROOT="${1#*=}"
            shift
            ;;
        --work-patterns=*)
            WORK_PATTERNS="${1#*=}"
            shift
            ;;
        --personal-patterns=*)
            PERSONAL_PATTERNS="${1#*=}"
            shift
            ;;
        -h|--help)
            echo "Usage: ./install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -y, --yes              Non-interactive mode, use defaults"
            echo "  --context-root=PATH    Set context directory (default: ~/context)"
            echo "  --work-patterns=PATHS  Comma-separated work paths"
            echo "  --personal-patterns=PATHS  Comma-separated personal paths"
            echo "  -h, --help             Show this help"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Cleanup on failure
cleanup() {
    local exit_code=$?
    if [ $exit_code -ne 0 ]; then
        error "Installation failed!"
        if [ -n "$BACKUP_FILE" ] && [ -f "$BACKUP_FILE" ]; then
            warn "Restoring settings.json backup..."
            cp "$BACKUP_FILE" "$SETTINGS_FILE"
        fi
    fi
}
trap cleanup EXIT

# ============================================
# Main Installation
# ============================================

header "Context Tracker - Installation"
echo ""

# Step 1: Pre-flight checks
info "Checking dependencies..."
if ! check_dependencies; then
    exit 1
fi
success "Dependencies OK"

# Step 2: Check existing installation
if [ -L "$PLUGIN_SYMLINK" ]; then
    EXISTING_TARGET=$(readlink "$PLUGIN_SYMLINK" 2>/dev/null || echo "")
    if [ "$EXISTING_TARGET" = "$SCRIPT_DIR" ]; then
        info "Plugin already installed at correct location."
        ALREADY_INSTALLED=true
    else
        warn "Plugin symlink exists but points to: $EXISTING_TARGET"
        if $NONINTERACTIVE || prompt_yes_no "Update to current location?"; then
            rm "$PLUGIN_SYMLINK"
        else
            error "Installation cancelled."
            exit 1
        fi
    fi
fi

# Step 3: Create symlink
header "Setting up plugin symlink..."
mkdir -p "$PLUGINS_DIR"

if [ ! -L "$PLUGIN_SYMLINK" ]; then
    ln -sf "$SCRIPT_DIR" "$PLUGIN_SYMLINK"
    success "Created symlink: $PLUGIN_SYMLINK -> $SCRIPT_DIR"
else
    info "Symlink already exists"
fi

# Step 4: Configure settings.json
header "Configuring Claude Code settings..."

# Create settings.json if it doesn't exist
if [ ! -f "$SETTINGS_FILE" ]; then
    mkdir -p "$CLAUDE_DIR"
    echo '{}' > "$SETTINGS_FILE"
    info "Created new settings.json"
fi

# Validate existing settings
if ! validate_json "$SETTINGS_FILE"; then
    error "Existing settings.json is invalid JSON!"
    error "Please fix it manually and try again."
    exit 1
fi

# Check if hook already exists
if hook_exists "$SETTINGS_FILE"; then
    info "Hook already configured in settings.json"
else
    # Backup before modification
    BACKUP_FILE=$(backup_file "$SETTINGS_FILE")
    if [ -n "$BACKUP_FILE" ]; then
        info "Backup created: $BACKUP_FILE"
    fi

    # Define hook command
    HOOK_COMMAND="CLAUDE_PLUGIN_ROOT=$SCRIPT_DIR python3 $SCRIPT_DIR/hooks/stop.py"

    # Add hook
    if [ "$USE_PYTHON_JSON" = "true" ]; then
        add_hook_python "$SETTINGS_FILE" "$HOOK_COMMAND" > "${SETTINGS_FILE}.tmp"
    else
        add_hook_jq "$SETTINGS_FILE" "$HOOK_COMMAND" > "${SETTINGS_FILE}.tmp"
    fi

    # Validate and apply
    if validate_json "${SETTINGS_FILE}.tmp"; then
        mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
        success "Hook added to settings.json"
    else
        rm -f "${SETTINGS_FILE}.tmp"
        error "Failed to add hook - invalid JSON generated"
        exit 1
    fi
fi

# Step 5: Interactive config setup
header "Plugin Configuration"

if [ -f "$SCRIPT_DIR/config/config.json" ]; then
    info "Existing config.json found."
    # Read existing context_root
    EXISTING_CONTEXT_ROOT=$(python3 -c "
import json
with open('$SCRIPT_DIR/config/config.json') as f:
    print(json.load(f).get('context_root', '~/context'))
" 2>/dev/null || echo "~/context")

    if ! $NONINTERACTIVE && prompt_yes_no "Reconfigure?"; then
        RECONFIGURE=true
    else
        RECONFIGURE=false
        CONTEXT_ROOT="$EXISTING_CONTEXT_ROOT"
    fi
else
    RECONFIGURE=true
fi

if $RECONFIGURE; then
    echo ""

    # Context root
    if [ -z "$CONTEXT_ROOT" ]; then
        if $NONINTERACTIVE; then
            CONTEXT_ROOT="$DEFAULT_CONTEXT_ROOT"
        else
            echo "Where should context files be stored?"
            CONTEXT_ROOT=$(prompt_with_default "Context root" "$DEFAULT_CONTEXT_ROOT")
        fi
    fi

    # Work patterns
    if [ -z "$WORK_PATTERNS" ]; then
        if $NONINTERACTIVE; then
            WORK_PATTERNS="$DEFAULT_WORK_PATTERNS"
        else
            echo ""
            echo "Enter directory patterns for WORK projects (comma-separated)."
            WORK_PATTERNS=$(prompt_with_default "Work patterns" "$DEFAULT_WORK_PATTERNS")
        fi
    fi

    # Personal patterns
    if [ -z "$PERSONAL_PATTERNS" ]; then
        if $NONINTERACTIVE; then
            PERSONAL_PATTERNS="$DEFAULT_PERSONAL_PATTERNS"
        else
            echo ""
            echo "Enter directory patterns for PERSONAL projects (comma-separated)."
            PERSONAL_PATTERNS=$(prompt_with_default "Personal patterns" "$DEFAULT_PERSONAL_PATTERNS")
        fi
    fi

    # Convert to JSON arrays
    WORK_JSON=$(csv_to_json_array "$WORK_PATTERNS")
    PERSONAL_JSON=$(csv_to_json_array "$PERSONAL_PATTERNS")

    # Generate config.json
    cat > "$SCRIPT_DIR/config/config.json" << CONFIGEOF
{
  "context_root": "$CONTEXT_ROOT",
  "work_path_patterns": $WORK_JSON,
  "personal_path_patterns": $PERSONAL_JSON,
  "excluded_paths": [
    "/tmp/",
    "~/Downloads/",
    "~/.cache/",
    "~/.local/share/Trash/"
  ],
  "git_config": {
    "auto_commit": true,
    "auto_push": true,
    "commit_message_template": "Context update: {project} - {topics}",
    "push_on_every_commit": false,
    "batch_commits": true,
    "batch_timeout_minutes": 5
  },
  "session_config": {
    "min_changes_threshold": 1,
    "max_session_entries_per_topic": 50,
    "archive_after_sessions": 100,
    "include_file_paths": true,
    "include_timestamps": true,
    "include_session_id": false
  },
  "llm_config": {
    "model": "haiku",
    "max_tokens": 150,
    "temperature": 0.3,
    "use_for_reasoning": true,
    "use_for_topic_detection": true,
    "fallback_to_patterns": true
  }
}
CONFIGEOF

    success "Generated config.json"
fi

# Step 6: Initialize context repository
header "Setting up context repository..."

CONTEXT_DIR=$(expand_path "$CONTEXT_ROOT")

if [ -d "$CONTEXT_DIR/.git" ]; then
    info "Context repository already initialized at $CONTEXT_DIR"
else
    info "Initializing context repository at $CONTEXT_DIR..."

    mkdir -p "$CONTEXT_DIR/personal" "$CONTEXT_DIR/work"

    cd "$CONTEXT_DIR"
    git init -q

    # Create README
    cat > README.md << 'READMEEOF'
# Claude Code Context Repository

Automated context tracking for all Claude Code sessions.

## Structure

- `personal/` - Personal project contexts
- `work/` - Work project contexts

## Usage

This repository is automatically updated by the [context-tracker](https://github.com/YOUR_USERNAME/context-tracker) plugin.

Each markdown file contains session entries organized by topic (testing, api-endpoints, configuration, etc.).
READMEEOF

    # Create .gitignore
    cat > .gitignore << 'GITIGNOREEOF'
.DS_Store
*.log
*.tmp
GITIGNOREEOF

    # Create index file
    echo '{"projects": {}, "last_updated": null}' > .context-index.json

    # Initial commit
    git add .
    git commit -q -m "Initial context repository setup"

    success "Context repository initialized"

    # Optional: Configure remote
    if ! $NONINTERACTIVE; then
        echo ""
        if prompt_yes_no "Configure git remote for syncing?"; then
            echo "Enter remote URL (e.g., git@github.com:username/claude-context.git)"
            read -p "Remote URL: " REMOTE_URL
            if [ -n "$REMOTE_URL" ]; then
                git remote add origin "$REMOTE_URL"
                success "Remote configured"
                info "Run 'cd $CONTEXT_DIR && git push -u origin main' to push"
            fi
        fi
    fi

    cd - > /dev/null
fi

# Step 7: Verification
header "Verifying installation..."

VERIFY_FAILED=false

# Test Python imports
if python3 -c "
import sys
sys.path.insert(0, '$SCRIPT_DIR')
from core.config_loader import load_config
" 2>/dev/null; then
    success "Python modules: OK"
else
    warn "Python modules: Could not import (may work at runtime)"
fi

# Verify symlink
if [ -L "$PLUGIN_SYMLINK" ]; then
    success "Symlink: OK"
else
    error "Symlink: FAILED"
    VERIFY_FAILED=true
fi

# Verify settings.json has the hook
if hook_exists "$SETTINGS_FILE"; then
    success "Settings hook: OK"
else
    error "Settings hook: FAILED"
    VERIFY_FAILED=true
fi

# Verify config exists
if [ -f "$SCRIPT_DIR/config/config.json" ]; then
    success "Plugin config: OK"
else
    warn "Plugin config: Using example defaults"
fi

# Verify context directory
if [ -d "$CONTEXT_DIR" ]; then
    success "Context directory: OK"
else
    warn "Context directory: Not found"
fi

echo ""
if $VERIFY_FAILED; then
    error "Installation completed with errors. Please check above."
    exit 1
fi

success "Installation complete!"
echo ""
header "Next steps:"
echo "  1. Restart Claude Code (or start a new session)"
echo "  2. Make some changes in a project"
echo "  3. End the session to trigger context tracking"
echo "  4. Check $CONTEXT_DIR for context entries"
echo ""
if [ -d "$CONTEXT_DIR/.git" ] && ! git -C "$CONTEXT_DIR" remote get-url origin &>/dev/null; then
    info "Tip: Add a git remote to sync your context:"
    echo "  cd $CONTEXT_DIR"
    echo "  git remote add origin git@github.com:YOUR_USERNAME/context-tracker.git"
    echo "  git push -u origin main"
fi
