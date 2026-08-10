#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLIST="$HOME/Library/LaunchAgents/com.bradleynix.sultans-calendar.plist"
UID_NUM="$(id -u)"
mkdir -p "$HOME/Library/LaunchAgents" "$REPO_DIR/debug"

cat > "$PLIST" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.bradleynix.sultans-calendar</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string>
    <string>${REPO_DIR}/refresh_local.sh</string>
  </array>
  <key>WorkingDirectory</key>
  <string>${REPO_DIR}</string>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key><integer>6</integer>
    <key>Minute</key><integer>23</integer>
  </dict>
  <key>StandardOutPath</key>
  <string>${REPO_DIR}/debug/launchd.out.log</string>
  <key>StandardErrorPath</key>
  <string>${REPO_DIR}/debug/launchd.err.log</string>
</dict>
</plist>
PLIST

launchctl bootout "gui/${UID_NUM}" "$PLIST" 2>/dev/null || true
launchctl bootstrap "gui/${UID_NUM}" "$PLIST"
launchctl enable "gui/${UID_NUM}/com.bradleynix.sultans-calendar"

echo "Installed daily refresh at 6:23 AM local time."
echo "Test now with: $REPO_DIR/refresh_local.sh"
echo "LaunchAgent: $PLIST"
