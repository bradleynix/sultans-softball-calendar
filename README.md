# Sultans Men's Softball Calendar — local Safari refresh (v5)

This version fetches Arlington WebTrac through a normal Safari session on a local Mac, builds the ICS locally, pushes changed generated files to GitHub, and lets GitHub Pages publish them.

## Required repository layout

At the Git repository root you should have:

```
.github/workflows/refresh-calendar.yml
README.md
requirements.txt
scrape_schedule.py
refresh_local.sh
install_macos_schedule.sh
scripts/fetch_with_safari.applescript
```

Do not put another `sultans-softball-calendar` directory inside the repository.

## Manual test

From the repository root:

```bash
chmod +x refresh_local.sh install_macos_schedule.sh
./refresh_local.sh
```

If Safari displays a Cloudflare verification page, complete it in Safari and run the command again.

## Daily refresh

After the manual test succeeds:

```bash
./install_macos_schedule.sh
```
