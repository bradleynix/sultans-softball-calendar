#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
GIT_ROOT="$(git -C "$REPO_DIR" rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$GIT_ROOT" ]]; then
  echo "ERROR: $REPO_DIR is not inside a Git repository." >&2
  exit 2
fi

if [[ "$GIT_ROOT" != "$REPO_DIR" ]]; then
  echo "ERROR: refresh_local.sh is not at the repository root." >&2
  echo "Repository root: $GIT_ROOT" >&2
  echo "Script location: $REPO_DIR" >&2
  echo "Move refresh_local.sh, install_macos_schedule.sh, and scripts/ to the repository root, then run again." >&2
  exit 2
fi

APPLE_SCRIPT="$REPO_DIR/scripts/fetch_with_safari.applescript"
if [[ ! -f "$APPLE_SCRIPT" ]]; then
  echo "ERROR: Missing $APPLE_SCRIPT" >&2
  echo "Make sure the scripts folder from the v5 package is copied to the repository root." >&2
  exit 2
fi

cd "$REPO_DIR"

SOURCE_URL='https://vaarlingtonweb.myvscloud.com/webtrac/web/schedule.html?action=leaguedetails&awayid=304539538&fmid=345063462'
mkdir -p debug site published

/usr/bin/osascript "$APPLE_SCRIPT" \
  "$SOURCE_URL" "$REPO_DIR/debug/source-safari.html"

if [[ ! -d .venv ]]; then
  /usr/bin/python3 -m venv .venv
fi
source .venv/bin/activate
python -m pip install --quiet --upgrade pip
python -m pip install --quiet -r requirements.txt

SOURCE_HTML_FILE="$REPO_DIR/debug/source-safari.html" \
SOURCE_URL="$SOURCE_URL" \
TEAM_NAME='Sultans' \
LEAGUE_ID='345063462' \
TIMEZONE='America/New_York' \
MIN_NIGHTS='3' \
GAME_DURATION_MINUTES='55' \
DOUBLEHEADER_GAP_MINUTES='60' \
python scrape_schedule.py

cp site/sultans-softball.ics published/sultans-softball.ics
cp debug/parsed-nights.json published/last-parsed-nights.json
cp debug/parsed-games.json published/last-parsed-games.json
/bin/date -u +'%Y-%m-%dT%H:%M:%SZ' > published/last-successful-refresh.txt

git add site/ published/
if ! git diff --cached --quiet; then
  git commit -m "Refresh Sultans softball calendar"
  git push origin main
else
  echo "No schedule changes detected; nothing to push."
fi
