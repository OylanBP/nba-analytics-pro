#!/usr/bin/env python3
"""Build leak-free pregame training rows and optional daily predictions from archived ESPN games."""
import datetime as dt
import json
import pathlib

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
OUT=DATA/"model"
OUT.mkdir(parents=True,exist_ok=True)
FEATURES=("home_win_pct_before","away_win_pct_before","home_rest_days","away_rest_days")

def make_features(games):
    rows=[]
    completed={}
    last_played={}
    # Group by UTC calendar day. Freeze features for all games on a given date.
    days={}
    for game in games:
        if not isinstance(game,dict) or not all(k in game for k in ("id","date","home","away","season")):
            continue
        date=dt.datetime.fromisoformat(game["date"].replace("Z","+00:00")).date()
        days.setdefault(str(date),[]).append(game)
    season=None
    for day,group in sorted(days.items()):
        if season!=group[0]["season"]:
            completed={}
            last_played={}
            season=group[0]["season"]
        snapshots={}
        for game in group:
            h,a=str(game["home"]),str(game["away"])
            if h==a:
                continue
            def stats(team):
                wins,played=completed.get(team,(0,0))
                last=last_played.get(team)
                rest=min(14,max(0,(dt.date.fromisoformat(day)-last).days-1)) if last else 7
                return wins/played if played else 0.5,rest
            hp,hr=stats(h)
            ap,ar=stats(a)
            row={"id":str(game["id"]),"date":day,"season":season,
                 "home_team":h,"away_team":a,
                 "home_win_pct_before":hp,"away_win_pct_before":ap,
                 "home_rest_days":hr,"away_rest_days":ar}
            snapshots[str(game["id"])]=row
        for game in group:
            row=snapshots.get(str(game["id"]))
            if not row:
                continue
            if "h" in game and "a" in game:
                if not all(isinstance(game[k],int) and not isinstance(game[k],bool) for k in ("h","a")):
                    continue
                if game["h"]==game["a"]:
                    continue
                rows.append({**row,"home_win":int(game["h"]>game["a"])})
        # Update records only after all same-day features were frozen.
        for game in group:
            if str(game["id"]) not in snapshots or "h" not in game or "a" not in game:
                continue
            h,a=str(game["home"]),str(game["away"])
            for team,win in ((h,game["h"]>game["a"]),(a,game["a"]>game["h"])):
                w,n=completed.get(team,(0,0))
                completed[team]=(w+int(win),n+1)
                last_played[team]=dt.date.fromisoformat(day)
    return rows

def main():
    source=DATA/"games.json"
    if not source.exists():
        raise SystemExit("Missing real ESPN game archive.")
    doc=json.loads(source.read_text(encoding="utf-8"))
    games=doc["games"]
    if not isinstance(games,list):
        raise ValueError("Invalid game archive.")
    rows=make_features(games)
    if len(rows)<200:
        raise ValueError(f"Only {len(rows)} completed games; at least 200 required.")
    (OUT/"games_history.json").write_text(json.dumps(rows,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(f"Built {len(rows)} completed-game pregame records from archived ESPN games.")

if __name__=="__main__":
    main()
