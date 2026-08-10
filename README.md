# Sultans Men's Softball Calendar

A self-updating, subscribable ICS calendar for the **Sultans** men's adult softball team in Arlington, Virginia.

Source schedule:

`https://vaarlingtonweb.myvscloud.com/webtrac/web/schedule.html?action=leaguedetails&fmid=345063462&homeid=304539538`

## What this repository does

- Reads the Sultans team schedule directly from Arlington's WebTrac HTML page.
- Converts every scheduled **doubleheader night** into two individual calendar events.
- Uses the listed time for Game 1 and creates Game 2 exactly one hour later.
- Uses a 55-minute duration for each game.
- Reverses the listed home/away designation for Game 2, matching Arlington's schedule instructions.
- Includes opponent, field name/diamond, and the address embedded in Arlington's Google Maps link.
- Publishes `sultans-softball.ics` through GitHub Pages.
- Refreshes automatically every morning at 6:23 AM Eastern.
- Keeps the last successfully parsed schedule under `published/` for troubleshooting.
- Refuses to overwrite the feed if the scraper suddenly finds fewer than three scheduled nights.

## Repository setup

Create a new public GitHub repository named:

` sultans-softball-calendar `

Upload the contents of this folder so the root of the repository looks like:

```text
.github/
  workflows/
    refresh-calendar.yml
README.md
requirements.txt
scrape_schedule.py
```

> On macOS, `.github` is a hidden directory. If you upload files through Finder, make sure the `.github` folder is included. You can also create `.github/workflows/refresh-calendar.yml` directly in GitHub's web interface.

## Enable GitHub Pages

1. Open the repository on GitHub.
2. Go to **Settings → Pages**.
3. Under **Build and deployment**, set **Source** to **GitHub Actions**.
4. Go to **Actions**.
5. Select **Refresh and publish Sultans softball calendar**.
6. Click **Run workflow → Run workflow**.

After the workflow succeeds, the website should be available at:

`https://YOUR-GITHUB-USERNAME.github.io/sultans-softball-calendar/`

and the subscribable ICS feed at:

`https://YOUR-GITHUB-USERNAME.github.io/sultans-softball-calendar/sultans-softball.ics`

For this repository under the `bradleynix` account, the expected addresses would be:

- Calendar page: `https://bradleynix.github.io/sultans-softball-calendar/`
- ICS feed: `https://bradleynix.github.io/sultans-softball-calendar/sultans-softball.ics`

## Why not use Arlington's built-in iCal download?

The WebTrac page does provide an iCal/Google Calendar download, but that download is generated through a request containing a session/CSRF token. This repository instead reads the public team schedule URL and creates a stable GitHub Pages subscription address for your team.

## Current doubleheader rules encoded in the calendar

Arlington's schedule comments state that:

- Teams play doubleheaders each night.
- Games have a 55-minute time limit.
- The games are scheduled one hour apart.
- Only the first game's start time appears in the schedule table.
- The team listed as home for Game 1 becomes the visiting team for Game 2.

Those rules are reflected automatically in `scrape_schedule.py`.

## Future seasons

Arlington will likely assign a new league ID and/or team ID for a future season. When that happens, replace `SOURCE_URL` and `LEAGUE_ID` in `.github/workflows/refresh-calendar.yml` with the new team's schedule URL and league ID. The rest of the workflow should continue to work without changes.
