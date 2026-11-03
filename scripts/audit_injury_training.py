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
    from zoneinfo import ZoneInfo
    teams=json.loads((ROOT/"data/standings.json").read_text())["teams"]
    abbrev={str(t["id"]):t["abbreviation"] for t in teams}
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
                tip=datetime.fromisoformat(g["date"].replace("Z","+00:00"))
                local_day=tip.astimezone(ZoneInfo("America/New_York")).date().isoformat()
                if local_day!=coverage.get("game_date"):
                    continue
                matchup=abbrev.get(str(g["away"]),"")+"@"+abbrev.get(str(g["home"]),"")
                if matchup!=coverage.get("matchup"):
                    continue
                if str(coverage.get("team_id")) not in (str(g.get("home")),str(g.get("away"))):
                    continue
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
    from availability import HISTORY
    if HISTORY.exists():
        labeled=json.loads(HISTORY.read_text())
        report["matched_labeled_games"]=len({r["id"] for r in labeled})
        report["ready_to_train"]=report["matched_labeled_games"]>=MIN_LABELED_GAMES
        report["reason"]="Paired historical labels from both teams in timestamp-verified official PDFs. Snapshot player_rows refers to the live archive only."
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
    print(json.dumps(report,ensure_ascii=False))
    if not report["ready_to_train"]:
        print("Injury-adjusted training blocked; existing verified Elo model unchanged.")

if __name__=="__main__":
    main()
