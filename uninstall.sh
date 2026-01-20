#!/usr/bin/env bash
set -e

# Claude Context Tracker - Uninstallation Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/scripts/setup_utils.sh"

# Configuration
CLAUDE_DIR="$HOME/.claude"
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
PLUGINS_DIR="$CLAUDE_DIR/plugins/user"
PLUGIN_SYMLINK="$PLUGINS_DIR/context-tracker"

# Parse arguments
NONINTERACTIVE=false
REMOVE_CONFIG=false
REMOVE_REPO=false

while [[ $# -gt 0 ]]; do
    case $1 in
        -y|--yes)
            NONINTERACTIVE=true
            shift
            ;;
        --remove-config)
            REMOVE_CONFIG=true
            shift
            ;;
        --remove-repo)
            REMOVE_REPO=true
            shift
            ;;
        -h|--help)
            echo "Usage: ./uninstall.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -y, --yes          Non-interactive mode"
            echo "  --remove-config    Also remove config/config.json"
            echo "  --remove-repo      Also remove context repository (DANGER!)"
            echo "  -h, --help         Show this help"
            exit 0
            ;;
        *)
            error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================
# Main Uninstallation
# ============================================

header "Context Tracker - Uninstallation"
echo ""

# Get context root before we potentially remove config
CONTEXT_DIR="$HOME/context"
if [ -f "$SCRIPT_DIR/config/config.json" ]; then
    CONFIG_CONTEXT=$(python3 -c "
import json
with open('$SCRIPT_DIR/config/config.json') as f:
    c = json.load(f)
print(c.get('context_root', '~/context').replace('~', '$HOME'))
" 2>/dev/null || echo "~/context")
    CONTEXT_DIR=$(expand_path "$CONFIG_CONTEXT")
fi

warn "This will uninstall the Context Tracker plugin."
info "Your context repository at $CONTEXT_DIR will be preserved."
echo ""

if ! $NONINTERACTIVE; then
    if ! prompt_yes_no "Continue with uninstall?"; then
        info "Uninstall cancelled."
        exit 0
    fi
fi

echo ""

# Step 1: Remove hook from settings.json
header "Removing hook from settings.json..."

if [ -f "$SETTINGS_FILE" ]; then
    if hook_exists "$SETTINGS_FILE"; then
        # Backup before modification
        BACKUP_FILE=$(backup_file "$SETTINGS_FILE")
        info "Backup created: $BACKUP_FILE"

        # Remove hook
        if [ "$USE_PYTHON_JSON" = "true" ]; then
            remove_hook_python "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp"
        else
            remove_hook_jq "$SETTINGS_FILE" > "${SETTINGS_FILE}.tmp"
        fi

        # Validate and apply
        if validate_json "${SETTINGS_FILE}.tmp"; then
            mv "${SETTINGS_FILE}.tmp" "$SETTINGS_FILE"
            success "Hook removed from settings.json"
        else
            rm -f "${SETTINGS_FILE}.tmp"
            error "Failed to remove hook - keeping original"
        fi
    else
        info "Hook not found in settings.json (already removed?)"
    fi
else
    info "settings.json not found"
fi

# Step 2: Remove symlink
header "Removing plugin symlink..."

if [ -L "$PLUGIN_SYMLINK" ]; then
    rm "$PLUGIN_SYMLINK"
    success "Symlink removed: $PLUGIN_SYMLINK"
else
    info "Symlink not found (already removed?)"
fi

# Step 3: Optionally remove config.json
if [ -f "$SCRIPT_DIR/config/config.json" ]; then
    if $REMOVE_CONFIG; then
        rm "$SCRIPT_DIR/config/config.json"
        success "config.json removed"
    elif ! $NONINTERACTIVE; then
        echo ""
        if prompt_yes_no "Remove config/config.json (your custom settings)?"; then
            rm "$SCRIPT_DIR/config/config.json"
            success "config.json removed"
        else
            info "config.json preserved"
        fi
    else
        info "config.json preserved (use --remove-config to delete)"
    fi
fi

# Step 4: Handle context repository
echo ""
header "Context Repository"

if [ -d "$CONTEXT_DIR" ]; then
    if $REMOVE_REPO; then
        warn "Removing context repository at $CONTEXT_DIR..."
        rm -rf "$CONTEXT_DIR"
        success "Context repository removed"
    elif ! $NONINTERACTIVE; then
        warn "Your context repository contains your session history."
        if prompt_yes_no "Remove context repository at $CONTEXT_DIR? (DANGER!)"; then
            warn "Are you absolutely sure? This cannot be undone!"
            if prompt_yes_no "Type 'y' again to confirm deletion"; then
                rm -rf "$CONTEXT_DIR"
                success "Context repository removed"
            else
                info "Context repository preserved"
            fi
        else
            info "Context repository preserved at: $CONTEXT_DIR"
        fi
    else
        info "Context repository preserved at: $CONTEXT_DIR"
        info "(use --remove-repo to delete)"
    fi
else
    info "Context repository not found at $CONTEXT_DIR"
fi

echo ""
success "Uninstall complete!"
echo ""

info "The plugin source code remains at: $SCRIPT_DIR"
info "To completely remove, also run:"
echo "  rm -rf $SCRIPT_DIR"
echo ""

if [ -d "$CONTEXT_DIR" ]; then
    info "Your context data is preserved at: $CONTEXT_DIR"
fi
