#!/usr/bin/env python3
"""Fetch and validate NBA regular-season player averages from ESPN's unofficial API."""
import concurrent.futures as futures
import datetime as dt
import json
import math
import os
import pathlib
import re
import time
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
ROSTERS = ROOT / "data" / "rosters.json"
OUTPUT = ROOT / "data" / "player_stats.json"
URL = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/{}/stats"
NOW = dt.datetime.now(dt.timezone.utc)
SEASON_YEAR = NOW.year + 1 if NOW.month >= 10 else NOW.year

CODES = {
    "GP": "gp",
    "PTS": "pts",
    "REB": "reb",
    "AST": "ast",
    "STL": "stl",
    "BLK": "blk",
    "FG%": "fg_pct",
    "3P%": "three_pct",
    "FT%": "ft_pct",
}

SHOOTING = {"FG": ("fgm", "fga", "fg_pct"),
            "3PT": ("three_pm", "three_pa", "three_pct"),
            "FT": ("ftm", "fta", "ft_pct")}

RANGES = {
    "gp": (0, 100),
    "pts": (0, 100),
    "reb": (0, 60),
    "ast": (0, 40),
    "stl": (0, 20),
    "blk": (0, 20),
    "fg_pct": (0, 100),
    "three_pct": (0, 100),
    "ft_pct": (0, 100),
}

def fetch(athlete_id):
    request = urllib.request.Request(URL.format(athlete_id), headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    for attempt in range(3):
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))


def parse_pair(value):
    """ESPN average FG/3PT/FT strings are usually 'makes-attempts'."""
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*-\s*(\d+(?:\.\d+)?)\s*", value)
    if not match:
        return None
    makes, attempts = map(float, match.groups())
    return makes, attempts


def validate_row(row):
    for key, (low, high) in RANGES.items():
        value = row.get(key)
        if value is None:
            continue
        try:
            n = float(value)
        except (ValueError, TypeError):
            raise ValueError(f"{key} is not numeric: {value!r}")
        if not math.isfinite(n) or not low <= n <= high:
            raise ValueError(f"{key} outside [{low}, {high}]: {value!r}")
    for _, (makes_key, attempts_key, pct_key) in SHOOTING.items():
        makes = row.get(makes_key)
        attempts = row.get(attempts_key)
        if makes is None or attempts is None:
            continue
        if not all(math.isfinite(x) for x in (makes, attempts)):
            raise ValueError(f"Invalid {makes_key}/{attempts_key}")
        # Values are rounded *per-game* averages, so allow rounding tolerance.
        if makes < 0 or attempts < 0 or makes > attempts + 0.11:
            raise ValueError(f"Impossible {makes_key}/{attempts_key}: {makes}/{attempts}")
        if attempts == 0:
            # A 0.0 average can represent a very small nonzero season average;
            # never infer a genuine 0% from rounded per-game values alone.
            row[pct_key] = None
            row[pct_key + "_status"] = "no_recorded_attempts_in_rounded_average"
        elif row.get(pct_key) is not None:
            # With tiny per-game attempts, rounding can make derived percentages
            # diverge substantially. Do not overwrite ESPN's percentage.
            estimated = 100 * makes / attempts
            tolerance = min(50.0, 10.0 / attempts + 2.0)
            if abs(estimated - float(row[pct_key])) > tolerance:
                row[pct_key + "_status"] = "rounded_average_mismatch_review"
    return row


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
                pair_keys = SHOOTING.get(label) or SHOOTING.get(name)
                if pair_keys:
                    pair = parse_pair(value)
                    if pair is not None:
                        result[pair_keys[0]], result[pair_keys[1]] = pair
            if result:
                return validate_row(result)
    return None


def worker(item):
    athlete_id, name = item
    try:
        return athlete_id, parse(fetch(athlete_id)), None
    except Exception as exc:
        return athlete_id, None, f"{name} ({athlete_id}): {exc}"


def main():
    rosters = json.loads(ROSTERS.read_text(encoding="utf-8"))
    athletes = {str(p["id"]): p.get("name", "")
                for team in rosters.get("teams", [])
                for p in team.get("players", []) if p.get("id")}
    if len(athletes) < 200:
        raise ValueError("Roster file has too few athletes; refusing to replace stats.")
    stats, errors = {}, []
    with futures.ThreadPoolExecutor(max_workers=6) as executor:
        for athlete_id, row, error in executor.map(worker, athletes.items()):
            if row:
                stats[athlete_id] = row
            if error:
                errors.append(error)
    if len(errors) > max(30, len(athletes) // 4):
        raise RuntimeError(f"Too many ESPN failures ({len(errors)}); first: {errors[0]}")
    coverage = len(stats) / len(athletes)
    if coverage < 0.50:
        raise RuntimeError(f"Player statistics coverage too low: {coverage:.1%}")
    document = {
        "source": "ESPN unofficial public athlete statistics API",
        "season_year": SEASON_YEAR,
        "season_type": "regular",
        "updated_at_utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "players": stats,
        "missing_current_season": len(athletes) - len(stats) - len(errors),
        "fetch_errors": len(errors),
        "shooting_validation": "per-game makes/attempts parsed; rounded zero attempts shown as unavailable",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUTPUT.with_suffix(".tmp")
    tmp.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, OUTPUT)
    print(f"Data quality passed: {len(stats)}/{len(athletes)} ({coverage:.1%}); "
          f"{len(errors)} request failures; season {SEASON_YEAR}.")


if __name__ == "__main__":
    main()
