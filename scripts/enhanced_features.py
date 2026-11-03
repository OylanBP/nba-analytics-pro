"""Leak-free historical Elo, last-ten form and point differential features.

Each game's features are frozen before updating results for that UTC date.
This is a research challenger and never silently replaces the approved champion.
"""
import datetime as dt
import json
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FEATURES = ("home_win_pct_before", "away_win_pct_before",
            "home_rest_days", "away_rest_days",
            "home_elo", "away_elo", "home_last10_win_pct",
            "away_last10_win_pct", "home_last10_margin",
            "away_last10_margin")

def build(games):
    dates = defaultdict(list)
    for game in games:
        if all(k in game for k in ("id", "date", "season", "home", "away")):
            date = dt.datetime.fromisoformat(game["date"].replace("Z", "+00:00")).date()
            dates[date].append(game)
    rows = []
    elo, record, recent, last = {}, {}, {}, {}
    season = None
    for day, group in sorted(dates.items()):
        current_season = group[0]["season"]
        if current_season != season:
            # Regress prior-season strength toward league average; reset season record.
            elo = {k: 1500 + (v - 1500) * 0.65 for k, v in elo.items()}
            record, recent, last = {}, {}, {}
            season = current_season
        frozen = {}
        for g in group:
            h, a = str(g["home"]), str(g["away"])
            if h == a:
                continue
            def state(team):
                w, n = record.get(team, (0, 0))
                history = list(recent.get(team, ()))
                previous = last.get(team)
                rest = min(14, max(0, (day - previous).days - 1)) if previous else 7
                return (w / n if n else .5, rest, elo.get(team, 1500),
                        sum(v[0] for v in history)/len(history) if history else .5,
                        sum(v[1] for v in history)/len(history) if history else 0)
            hp, hr, he, hf, hm = state(h)
            ap, ar, ae, af, am = state(a)
            frozen[str(g["id"])] = {
                "id": str(g["id"]), "date": day.isoformat(), "season": season,
                "home_team": h, "away_team": a,
                "home_win_pct_before": hp, "away_win_pct_before": ap,
                "home_rest_days": hr, "away_rest_days": ar,
                "home_elo": he, "away_elo": ae,
                "home_last10_win_pct": hf, "away_last10_win_pct": af,
                "home_last10_margin": hm, "away_last10_margin": am}
        for g in group:
            row = frozen.get(str(g["id"]))
            if row and type(g.get("h")) is int and type(g.get("a")) is int and g["h"] != g["a"]:
                rows.append({**row, "home_win": int(g["h"] > g["a"])})
        for g in group:
            if str(g["id"]) not in frozen or type(g.get("h")) is not int or type(g.get("a")) is not int or g["h"] == g["a"]:
                continue
            h, a = str(g["home"]), str(g["away"])
            hw = int(g["h"] > g["a"])
            ha, aa = elo.get(h, 1500), elo.get(a, 1500)
            expected = 1 / (1 + 10 ** ((aa - ha - 65) / 400))
            elo[h] = ha + 20 * (hw - expected)
            elo[a] = aa - 20 * (hw - expected)
            for team, won, margin in ((h, hw, g["h"] - g["a"]),
                                      (a, 1-hw, g["a"] - g["h"])):
                w, n = record.get(team, (0, 0))
                record[team] = w + won, n + 1
                recent.setdefault(team, deque(maxlen=10)).append((won, margin))
                last[team] = day
    return rows

def main():
    archive = json.loads((ROOT / "data/games.json").read_text(encoding="utf-8"))["games"]
    rows = build(archive)
    if len(rows) < 200:
        raise ValueError("Not enough completed games")
    target = ROOT / "data/model/enhanced_history.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Built", len(rows), "pregame enhanced samples")

if __name__ == "__main__":
    main()
