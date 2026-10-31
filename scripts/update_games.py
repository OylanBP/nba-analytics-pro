"""Archive ESPN regular-season schedules, retaining completed historical games."""
import datetime as dt
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{}/schedule?season={}&seasontype=2"


def download(url):
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "NBAAnalyticsPro/2.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                return json.load(response)
        except (OSError, ValueError):
            if attempt == 2:
                raise
            time.sleep(2 ** attempt)


# ESPN classifies the 2025 in-season cup final under regular-season schedules.
CUP_FINALS = {"401809839"}


def parse(event, season, teams):
    notes = " ".join(n.get("headline", "") for c in event["competitions"] for n in c.get("notes", [])).lower()
    if str(event["id"]) in CUP_FINALS or ("cup" in notes and ("championship" in notes or "cup final" in notes)):
        return None
    if int(event["season"]["year"]) != season or int(event["seasonType"]["type"]) != 2:
        return None
    comp = event["competitions"][0]
    sides = {c["homeAway"]: c for c in comp["competitors"]}
    home, away = (str(sides[k]["team"]["id"]) for k in ("home", "away"))
    if {home, away} - teams or home == away:
        return None
    status = comp["status"]["type"]
    if status["name"] not in ("STATUS_FINAL", "STATUS_SCHEDULED"):
        return None
    game = dict(id=str(event["id"]), date=event["date"], season=season, home=home, away=away)
    dt.datetime.fromisoformat(game["date"].replace("Z", "+00:00"))
    if status["name"] == "STATUS_FINAL":
        def points(side):
            score = sides[side]["score"]
            return int(float(score["value"] if isinstance(score, dict) else score))
        game.update(h=points("home"), a=points("away"))
        if min(game["h"], game["a"]) < 0 or game["h"] == game["a"]:
            raise ValueError(f"Invalid final score: {game}")
    return game


def main():
    now = dt.datetime.now(dt.timezone.utc)
    season = now.year + int(now.month >= 10)
    teams = {str(t["id"]) for t in json.loads((DATA / "standings.json").read_text())["teams"]}
    target = DATA / "games.json"
    previous = json.loads(target.read_text())["games"] if target.exists() else []
    games = {g["id"]: g for g in previous if "h" in g and g["id"] not in CUP_FINALS}
    for year in (season - 1, season):
        if year < season and sum(g["season"] == year for g in games.values()) >= 1230:
            continue
        found = set()
        for team in sorted(teams):
            payload = download(URL.format(team, year))
            for event in payload["events"]:
                game = parse(event, year, teams)
                if game:
                    found.add(game["id"])
                    if "h" in game or game["id"] not in games:
                        games[game["id"]] = game
        if len(found) < 30:
            raise ValueError(f"Incomplete season {year}: {len(found)} games")
    output = dict(updated=now.isoformat(), games=sorted(games.values(), key=lambda g: (g["date"], g["id"])))
    tmp = target.with_suffix(".tmp")
    tmp.write_text(json.dumps(output, separators=(",", ":")) + "\n")
    tmp.replace(target)


if __name__ == "__main__":
    main()
