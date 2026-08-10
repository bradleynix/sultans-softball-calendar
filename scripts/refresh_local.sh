#!/bin/zsh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

SOURCE_URL='https://vaarlingtonweb.myvscloud.com/webtrac/web/schedule.html?action=leaguedetails&awayid=304539538&fmid=345063462'
mkdir -p debug site published

# Fetch through a normal Safari session so WebTrac/Cloudflare can execute JavaScript
# and use normal browser cookies. The Python program only parses the rendered source.
/usr/bin/osascript "$REPO_DIR/scripts/fetch_with_safari.applescript" \
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

# Keep audit copies in the repository.
cp site/sultans-softball.ics published/sultans-softball.ics
cp debug/parsed-nights.json published/last-parsed-nights.json
cp debug/parsed-games.json published/last-parsed-games.json
/usr/bin/date -u +'%Y-%m-%dT%H:%M:%SZ' > published/last-successful-refresh.txt

# Push only if the generated output actually changed.
git add site/ published/
if ! git diff --cached --quiet; then
  git commit -m "Refresh Sultans softball calendar"
  git push origin main
fi
