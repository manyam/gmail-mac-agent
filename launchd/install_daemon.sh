#!/bin/bash
set -e

# Detect directories
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
AGENT_ROOT="$( cd "$SCRIPT_DIR/.." && pwd )"
MAIN_SCRIPT="$AGENT_ROOT/main.py"

# Detect Python interpreter (prefer virtualenv if active or present, else brew python3)
if [ -n "$VIRTUAL_ENV" ]; then
    PYTHON_EXEC="$VIRTUAL_ENV/bin/python"
elif [ -f "$AGENT_ROOT/.venv/bin/python" ]; then
    PYTHON_EXEC="$AGENT_ROOT/.venv/bin/python"
elif [ -f "/opt/homebrew/bin/python3" ]; then
    PYTHON_EXEC="/opt/homebrew/bin/python3"
else
    PYTHON_EXEC="$(which python3)"
fi

LOG_DIR="$HOME/.gmail_agent/logs"
mkdir -p "$LOG_DIR"

LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
mkdir -p "$LAUNCH_AGENTS_DIR"
PLIST_FILE="$LAUNCH_AGENTS_DIR/com.user.gmaildailybrief.plist"

# Check if GOOGLE_API_KEY is present
if [ -n "$GOOGLE_API_KEY" ]; then
    ENV_GOOGLE_API_KEY="<key>GOOGLE_API_KEY</key><string>$GOOGLE_API_KEY</string>"
else
    ENV_GOOGLE_API_KEY=""
fi

echo "=============================================="
echo "Installing macOS LaunchAgent for Gmail Brief"
echo "=============================================="
echo "Python Interpreter: $PYTHON_EXEC"
echo "Agent Script:       $MAIN_SCRIPT"
echo "Log Directory:      $LOG_DIR"
echo "Target Plist:       $PLIST_FILE"

# Unload previous instance if loaded
launchctl bootout "gui/$(id -u)" "$PLIST_FILE" 2>/dev/null || true

# Render plist
sed -e "s|{{PYTHON_EXEC}}|$PYTHON_EXEC|g" \
    -e "s|{{MAIN_SCRIPT}}|$MAIN_SCRIPT|g" \
    -e "s|{{LOG_DIR}}|$LOG_DIR|g" \
    -e "s|{{ENV_GOOGLE_API_KEY}}|$ENV_GOOGLE_API_KEY|g" \
    "$SCRIPT_DIR/com.user.gmaildailybrief.plist.template" > "$PLIST_FILE"

# Load into launchd
launchctl bootstrap "gui/$(id -u)" "$PLIST_FILE"

echo ""
echo "✅ LaunchAgent successfully installed and activated!"
echo "Scheduled to run daily at 7:30 AM (runs automatically upon waking if sleeping)."
echo "Logs available at:"
echo "  - $LOG_DIR/stdout.log"
echo "  - $LOG_DIR/stderr.log"
echo ""
echo "To test run immediately via launchd:"
echo "  launchctl kickstart -k gui/$(id -u)/com.user.gmaildailybrief"
echo ""
echo "To uninstall:"
echo "  launchctl bootout gui/$(id -u) $PLIST_FILE && rm $PLIST_FILE"
