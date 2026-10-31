#!/usr/bin/env python3
"""Fetch NBA regular-season player averages from ESPN's unofficial public API."""
import concurrent.futures as futures
import datetime as dt
import json
import os
import pathlib
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ROSTERS = ROOT / "data" / "rosters.json"
OUTPUT = ROOT / "data" / "player_stats.json"
URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{}/stats"

# ESPN season year is the calendar year in which the season ends.
NOW = dt.datetime.now(dt.timezone.utc)
SEASON_YEAR = NOW.year + 1 if NOW.month >= 10 else NOW.year
CODES = {"PTS": "pts", "REB": "reb", "AST": "ast", "STL": "stl",
         "BLK": "blk", "FG%": "fg_pct", "3P%": "three_pct", "FT%": "ft_pct"}


def fetch(athlete_id):
    request = urllib.request.Request(
        URL.format(athlete_id),
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def parse(payload):
    for category in payload.get("categories", []):
        if category.get("name") != "averages":
            continue
        labels = category.get("labels", [])
        names = category.get("names", [])
        for entry in category.get("statistics", []):
            season = entry.get("season") or {}
            if int(season.get("year") or 0) != SEASON_YEAR:
                continue
            # Use only regular-season rows when ESPN exposes a season type.
            st = entry.get("seasonType") or entry.get("type") or {}
            stid = st.get("id") if isinstance(st, dict) else st
            if stid is not None and str(stid) not in ("2", "regular"):
                continue
            values = entry.get("stats") or []
            if not isinstance(values, list):
                continue
            result = {}
            for label, name, value in zip(labels, names, values):
                key = CODES.get(label) or CODES.get(name)
                if key:
                    result[key] = value if value not in ("", "--", None) else None
            if result:
                return result
    return None


def worker(item):
    player_id, name = item
    try:
        return player_id, parse(fetch(player_id)), None
    except Exception as exc:
        return player_id, None, f"{name} ({player_id}): {exc}"


def main():
    rosters = json.loads(ROSTERS.read_text(encoding="utf-8"))
    athletes = {
        str(player["id"]): player.get("name", "")
        for team in rosters.get("teams", [])
        for player in team.get("players", [])
        if player.get("id")
    }
    if len(athletes) < 200:
        raise ValueError("Roster file has too few athletes; refusing to replace stats.")
    stats = {}
    errors = []
    with futures.ThreadPoolExecutor(max_workers=6) as executor:
        for athlete_id, row, error in executor.map(worker, athletes.items()):
            if row:
                stats[athlete_id] = row
            if error:
                errors.append(error)
    # Never overwrite good published data if the source is down.
    if len(errors) > max(30, len(athletes) // 4):
        raise RuntimeError(f"Too many ESPN failures ({len(errors)}); first: {errors[0]}")
    document = {
        "source": "ESPN unofficial public athlete statistics API",
        "season_year": SEASON_YEAR,
        "season_type": "regular",
        "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "players": stats,
        "missing_current_season": len(athletes) - len(stats) - len(errors),
        "fetch_errors": len(errors),
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, OUTPUT)
    print(f"Saved {len(stats)} player averages for season {SEASON_YEAR}; "
          f"{len(errors)} request failures; {len(athletes)} rostered players.")


if __name__ == "__main__":
    main()
