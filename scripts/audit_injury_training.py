"""Audit whether sourced injury snapshots can support historical injury-effect training.

A snapshot alone is not a training label. Every row must precede tipoff,
identify an actual unavailable player, and be matched to a completed game.
"""
import json
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/injuries/snapshots.json"
REPORT=ROOT/"data/model/injury_readiness.json"
MIN_LABELED_GAMES=200

def audit(snapshots, games):
    from datetime import datetime
    completed={str(g["id"]):g for g in games if type(g.get("h")) is int and type(g.get("a")) is int}
    matched=set()
    invalid=0
    usable_players=0
    for snapshot in snapshots:
        observed=datetime.fromisoformat(snapshot["observed_utc"].replace("Z","+00:00"))
        players=snapshot.get("players",[])
        usable_players+=len(players)
        for coverage in snapshot.get("covered_games",[]):
            if not coverage.get("submitted",True):
                continue
            for game_id,g in completed.items():
                if str(g.get("date",""))[:10]!=coverage.get("game_date"):
                    continue
                if str(coverage.get("team_id")) not in (str(g.get("home")),str(g.get("away"))):
                    continue
                tip=datetime.fromisoformat(g["date"].replace("Z","+00:00"))
                if observed>=tip:
                    invalid+=1
                    continue
                if any(str(p.get("team_id"))==str(coverage["team_id"]) and
                       p.get("game_date")==coverage.get("game_date") and
                       p.get("matchup")==coverage.get("matchup") and
                       p.get("status") in ("Out","Doubtful","Questionable","Probable")
                       for p in players):
                    matched.add(game_id)
    return {"snapshots":len(snapshots),"player_rows":usable_players,
            "historical_completed_games":len(completed),
            "matched_labeled_games":len(matched),
            "invalid_post_tipoff_rows":invalid,
            "minimum_labeled_games":MIN_LABELED_GAMES,
            "ready_to_train":len(matched)>=MIN_LABELED_GAMES,
            "reason":"Need historical pre-tipoff player availability joined to completed game outcomes; no fabricated injury coefficients."}

def main():
    snapshots=json.loads(SOURCE.read_text()) if SOURCE.exists() else []
    games=json.loads((ROOT/"data/games.json").read_text())["games"]
    report=audit(snapshots,games)
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    if not report["ready_to_train"]:
        print("Injury-adjusted training blocked; existing verified Elo model unchanged.")

if __name__=="__main__":
    main()
