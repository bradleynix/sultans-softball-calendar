#!/usr/bin/env python3
"""Build a subscribable ICS feed for the Arlington Sultans men's softball team.

The Arlington WebTrac page exposes the team schedule in ordinary HTML. Each listed
schedule row represents a doubleheader night: Game 1 starts at the listed time and
Game 2 starts one hour later, with home/away reversed. Each game is 55 minutes.
"""

from __future__ import annotations

import hashlib
import html
import json
import os
import re
import traceback
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, unquote_plus, urlparse
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

SOURCE_URL = os.getenv(
    "SOURCE_URL",
    "https://vaarlingtonweb.myvscloud.com/webtrac/web/schedule.html?action=leaguedetails&fmid=345063462&homeid=304539538",
)
TEAM_NAME = os.getenv("TEAM_NAME", "Sultans")
LEAGUE_ID = os.getenv("LEAGUE_ID", "345063462")
LOCAL_TZ_NAME = os.getenv("TIMEZONE", "America/New_York")
LOCAL_TZ = ZoneInfo(LOCAL_TZ_NAME)
MIN_NIGHTS = int(os.getenv("MIN_NIGHTS", "3"))
GAME_DURATION_MINUTES = int(os.getenv("GAME_DURATION_MINUTES", "55"))
DOUBLEHEADER_GAP_MINUTES = int(os.getenv("DOUBLEHEADER_GAP_MINUTES", "60"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "site"))
DEBUG_DIR = Path(os.getenv("DEBUG_DIR", "debug"))
CALENDAR_FILENAME = os.getenv("CALENDAR_FILENAME", "sultans-softball.ics")

DATE_RE = re.compile(r"^\d{1,2}/\d{1,2}/\d{4}$")
TIME_RE = re.compile(r"^\d{1,2}:\d{2}\s*(?:am|pm)$", re.I)


@dataclass
class Night:
    date: str
    time: str
    location_label: str
    location_address: str
    away_team: str
    home_team: str


@dataclass
class Game:
    start_local: datetime
    end_local: datetime
    opponent: str
    location: str
    home_away: str
    game_number: int
    meeting_number: int
    uid: str


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\xa0", " ")).strip()


def extract_address(location_cell) -> str:
    """Prefer the address embedded in the location's Google Maps link."""
    link = location_cell.find("a", href=True)
    if not link:
        return ""
    href = link.get("href", "")
    try:
        q = parse_qs(urlparse(href).query).get("q", [""])[0]
        if q:
            return clean(unquote_plus(q))
    except Exception:
        pass
    return ""


def pretty_location(label: str) -> str:
    label = clean(label)
    m = re.match(r"Diamond:\s*Adult\s*\(#(?P<num>\d+)(?:-(?P<name>[^)]+))?\)@(?P<park>.+)$", label, re.I)
    if not m:
        return label
    park = clean(m.group("park"))
    num = m.group("num")
    field_name = clean(m.group("name") or "")
    if field_name:
        return f"{park} — Adult Diamond #{num} ({field_name})"
    return f"{park} — Adult Diamond #{num}"


def parse_nights(page_html: str) -> list[Night]:
    soup = BeautifulSoup(page_html, "html.parser")
    nights: list[Night] = []

    # WebTrac's schedule rows currently have seven columns:
    # Date | Time | Location | Away Team | Away Score | Home Team | Home Score.
    # Instead of depending on CSS classes, find any table row whose first two cells
    # look like a date and time and whose away/home columns include our team.
    for tr in soup.find_all("tr"):
        cells = tr.find_all(["td", "th"], recursive=False)
        if len(cells) < 6:
            continue
        values = [clean(c.get_text(" ", strip=True)) for c in cells]
        if not DATE_RE.match(values[0]) or not TIME_RE.match(values[1]):
            continue

        location_label = values[2]
        away = values[3]
        home = values[5]
        if TEAM_NAME.casefold() not in {away.casefold(), home.casefold()}:
            continue

        nights.append(
            Night(
                date=values[0],
                time=values[1],
                location_label=pretty_location(location_label),
                location_address=extract_address(cells[2]),
                away_team=away,
                home_team=home,
            )
        )

    # De-duplicate in case WebTrac renders a desktop and mobile copy of the same table.
    unique: list[Night] = []
    seen: set[tuple[str, str, str, str, str]] = set()
    for n in nights:
        key = (n.date, n.time.lower(), n.location_label, n.away_team, n.home_team)
        if key not in seen:
            seen.add(key)
            unique.append(n)

    unique.sort(key=lambda n: datetime.strptime(f"{n.date} {n.time.upper()}", "%m/%d/%Y %I:%M %p"))
    return unique


def parse_start(night: Night) -> datetime:
    dt = datetime.strptime(f"{night.date} {night.time.upper()}", "%m/%d/%Y %I:%M %p")
    return dt.replace(tzinfo=LOCAL_TZ)


def build_games(nights: list[Night]) -> list[Game]:
    meeting_counts: defaultdict[str, int] = defaultdict(int)
    games: list[Game] = []

    for night in nights:
        if night.home_team.casefold() == TEAM_NAME.casefold():
            opponent = night.away_team
            first_relation = "Home"
        else:
            opponent = night.home_team
            first_relation = "Away"

        meeting_counts[opponent.casefold()] += 1
        meeting_number = meeting_counts[opponent.casefold()]
        first_start = parse_start(night)
        location_parts = [night.location_label]
        if night.location_address and night.location_address.casefold() not in night.location_label.casefold():
            location_parts.append(night.location_address)
        location = ", ".join(p for p in location_parts if p)

        for game_number in (1, 2):
            start = first_start + timedelta(minutes=(game_number - 1) * DOUBLEHEADER_GAP_MINUTES)
            end = start + timedelta(minutes=GAME_DURATION_MINUTES)
            if game_number == 1:
                relation = first_relation
            else:
                relation = "Away" if first_relation == "Home" else "Home"

            # Keep the UID independent of time/location so ordinary schedule changes update
            # the existing subscribed event rather than creating a duplicate.
            uid_seed = f"{LEAGUE_ID}|{TEAM_NAME}|{opponent}|meeting-{meeting_number}|game-{game_number}"
            uid_hash = hashlib.sha256(uid_seed.encode("utf-8")).hexdigest()[:24]
            uid = f"{uid_hash}@sultans-softball-calendar"
            games.append(
                Game(
                    start_local=start,
                    end_local=end,
                    opponent=opponent,
                    location=location,
                    home_away=relation,
                    game_number=game_number,
                    meeting_number=meeting_number,
                    uid=uid,
                )
            )

    games.sort(key=lambda g: g.start_local)
    return games


def ics_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_ics(line: str, limit: int = 73) -> str:
    # Folding by Python characters is sufficient here because our generated text is mostly ASCII.
    if len(line) <= limit:
        return line
    chunks = [line[:limit]]
    rest = line[limit:]
    while rest:
        chunks.append(" " + rest[: limit - 1])
        rest = rest[limit - 1 :]
    return "\r\n".join(chunks)


def event_summary(game: Game) -> str:
    relation = "vs" if game.home_away == "Home" else "@"
    return f"Sultans {relation} {game.opponent} — Game {game.game_number}"


def build_ics(games: list[Game]) -> str:
    now_stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//Sultans Softball Calendar//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "X-WR-CALNAME:Sultans Men's Softball",
        f"X-WR-TIMEZONE:{LOCAL_TZ_NAME}",
        "X-PUBLISHED-TTL:PT12H",
        "REFRESH-INTERVAL;VALUE=DURATION:PT12H",
    ]

    for g in games:
        start_utc = g.start_local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        end_utc = g.end_local.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        description = (
            f"Sultans men's softball — Game {g.game_number} of the doubleheader. "
            f"Sultans are {g.home_away.lower()} for this game. "
            f"Game length: {GAME_DURATION_MINUTES} minutes. Source: {SOURCE_URL}"
        )
        lines.extend(
            [
                "BEGIN:VEVENT",
                f"UID:{g.uid}",
                f"DTSTAMP:{now_stamp}",
                f"DTSTART:{start_utc}",
                f"DTEND:{end_utc}",
                f"SUMMARY:{ics_escape(event_summary(g))}",
                f"LOCATION:{ics_escape(g.location)}",
                f"DESCRIPTION:{ics_escape(description)}",
                f"URL:{SOURCE_URL}",
                "STATUS:CONFIRMED",
                "TRANSP:OPAQUE",
                "END:VEVENT",
            ]
        )

    lines.append("END:VCALENDAR")
    return "\r\n".join(fold_ics(line) for line in lines) + "\r\n"


def build_index(games: list[Game], refreshed_at: datetime) -> str:
    rows = []
    for g in games:
        relation = "vs" if g.home_away == "Home" else "@"
        rows.append(
            "<tr>"
            f"<td>{html.escape(g.start_local.strftime('%a, %b %-d, %Y'))}</td>"
            f"<td>{html.escape(g.start_local.strftime('%-I:%M %p'))}</td>"
            f"<td>Game {g.game_number}</td>"
            f"<td>Sultans {relation} {html.escape(g.opponent)}</td>"
            f"<td>{html.escape(g.home_away)}</td>"
            f"<td>{html.escape(g.location)}</td>"
            "</tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Sultans Men's Softball Calendar</title>
<style>
body{{font-family:system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;max-width:1100px;margin:2rem auto;padding:0 1rem;color:#1f2937}}
h1{{margin-bottom:.35rem}} .muted{{color:#6b7280}} .button{{display:inline-block;padding:.75rem 1rem;background:#111827;color:white;text-decoration:none;border-radius:.5rem;font-weight:600;margin:.5rem 0 1.5rem}}
table{{border-collapse:collapse;width:100%;font-size:.95rem}} th,td{{text-align:left;padding:.7rem;border-bottom:1px solid #e5e7eb;vertical-align:top}} th{{background:#f9fafb}}
.notice{{background:#f3f4f6;padding:1rem;border-radius:.5rem;margin:1rem 0 1.5rem}} code{{word-break:break-all}} @media(max-width:700px){{table{{font-size:.82rem}} th,td{{padding:.45rem}}}}
</style>
</head>
<body>
<h1>Sultans Men's Softball</h1>
<p class="muted">Arlington, Virginia · Automatically refreshed from Arlington WebTrac</p>
<a class="button" href="{html.escape(CALENDAR_FILENAME)}">Subscribe / download calendar</a>
<div class="notice"><strong>Doubleheaders:</strong> Arlington lists only the first game time for each night. This feed creates Game 1 at the listed time and Game 2 one hour later. Each game is scheduled for 55 minutes, and home/away reverses for Game 2.</div>
<table>
<thead><tr><th>Date</th><th>Time</th><th>Game</th><th>Matchup</th><th>H/A</th><th>Location</th></tr></thead>
<tbody>{''.join(rows)}</tbody>
</table>
<p class="muted">Last successful refresh: {html.escape(refreshed_at.astimezone(LOCAL_TZ).strftime('%B %-d, %Y at %-I:%M %p %Z'))}</p>
<p class="muted">Source: <a href="{html.escape(SOURCE_URL)}">Arlington WebTrac schedule</a></p>
</body></html>"""


def save_debug(name: str, content: str) -> None:
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)
    (DEBUG_DIR / name).write_text(content, encoding="utf-8")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    try:
        response = requests.get(
            SOURCE_URL,
            timeout=30,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; SultansCalendarBot/1.0; +https://github.com/)",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        response.raise_for_status()
        save_debug("source.html", response.text)
        save_debug("http.txt", f"status={response.status_code}\nurl={response.url}\n")

        nights = parse_nights(response.text)
        save_debug("parsed-nights.json", json.dumps([asdict(n) for n in nights], indent=2))

        if len(nights) < MIN_NIGHTS:
            raise RuntimeError(
                f"Safety check failed: found only {len(nights)} Sultans schedule nights; expected at least {MIN_NIGHTS}. "
                "The source page may have changed, so the existing published calendar was not overwritten."
            )

        games = build_games(nights)
        save_debug(
            "parsed-games.json",
            json.dumps(
                [
                    {
                        **asdict(g),
                        "start_local": g.start_local.isoformat(),
                        "end_local": g.end_local.isoformat(),
                        "summary": event_summary(g),
                    }
                    for g in games
                ],
                indent=2,
            ),
        )

        refreshed = datetime.now(timezone.utc)
        (OUTPUT_DIR / CALENDAR_FILENAME).write_text(build_ics(games), encoding="utf-8", newline="")
        (OUTPUT_DIR / "index.html").write_text(build_index(games, refreshed), encoding="utf-8")
        (OUTPUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

        print(f"Parsed {len(nights)} doubleheader nights and generated {len(games)} calendar events.")
        for g in games:
            print(f"- {g.start_local:%Y-%m-%d %I:%M %p}: {event_summary(g)} @ {g.location}")

    except Exception:
        save_debug("error.txt", traceback.format_exc())
        raise


if __name__ == "__main__":
    main()
