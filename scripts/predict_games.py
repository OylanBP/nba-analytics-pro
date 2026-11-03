#!/usr/bin/env python3
"""Publish future probabilities only when a validated champion model exists."""
import datetime as dt
import json
import math
import pathlib
from zoneinfo import ZoneInfo
from injury_archive import injury_at, load_snapshots
from player_roles import role_features, role_history, load_boxes
from availability import MODEL, game_key, difference, adjust
from enhanced_features import build as build_enhanced
from enhanced_model import forecast as forecast_enhanced, FEATURES as ENHANCED_FEATURES
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/"data"
def main():
    path=DATA/"model/champion.json"
    if not path.exists():
        print("No approved model; predictions not published.")
        return
    model=json.loads(path.read_text())
    expected=["home_win_pct_before","away_win_pct_before","home_rest_days","away_rest_days"]
    weights=model.get("weights",[])
    if model.get("features")!=expected or len(weights)!=5:
        raise ValueError("Incompatible model.")
    games=json.loads((DATA/"games.json").read_text())["games"]
    now=dt.datetime.now(dt.timezone.utc)
    upcoming=[g for g in games if "h" not in g and dt.datetime.fromisoformat(g["date"].replace("Z","+00:00"))>now]
    done=[g for g in games if "h" in g and "a" in g]
    teams=json.loads((DATA/"standings.json").read_text())["teams"]
    abbrev={str(t["id"]):t["abbreviation"] for t in teams}
    enhanced_path=DATA/"model/enhanced_champion.json"
    enhanced=None
    enhanced_rows={}
    if enhanced_path.exists():
        candidate=json.loads(enhanced_path.read_text())
        if candidate.get("features")==list(ENHANCED_FEATURES) and len(candidate.get("weights",[]))==len(ENHANCED_FEATURES)+1:
            enhanced=candidate
            enhanced_rows={str(row["id"]):row for row in build_enhanced(games,include_upcoming=True) if "home_win" not in row}
    snapshots=[s for s in load_snapshots() if s.get("parser_version")==2]
    effect=json.loads(MODEL.read_text()) if MODEL.exists() else {}
    history=role_history(games,load_boxes())
    results=[]
    for g in sorted(upcoming,key=lambda g:g["date"])[:120]:
        before=g["date"][:10]
        past=[x for x in done if x["season"]==g["season"] and x["date"][:10]<before]
        records={}
        for x in sorted(past,key=lambda x:x["date"]):
            for team,won in ((x["home"],x["h"]>x["a"]),(x["away"],x["a"]>x["h"])):
                row=records.setdefault(str(team),[0,0,None])
                row[0]+=int(won)
                row[1]+=1
                row[2]=x["date"][:10]
        def features(team):
            row=records.get(str(team))
            if row is None:
                return .5,7
            rest=min(14,max(0,(dt.date.fromisoformat(before)-dt.date.fromisoformat(row[2])).days-1))
            return row[0]/row[1],rest
        hp,hr=features(g["home"])
        ap,ar=features(g["away"])
        z=weights[0]+sum(a*b for a,b in zip(weights[1:],[hp,ap,hr/7,ar/7]))
        p=1/(1+math.exp(-max(-35,min(35,z))))
        model_name="baseline"
        if enhanced is not None and str(g["id"]) in enhanced_rows:
            p=forecast_enhanced(enhanced["weights"],enhanced_rows[str(g["id"])],True)
            model_name="elo_recent_form"
        game_date,matchup=game_key(g,abbrev)
        reports={side:injury_at(now.isoformat(),g[side],snapshots,matchup=matchup,game_date=game_date) for side in ("home","away")}
        counts=difference(reports["home"],reports["away"])
        apply=bool(effect.get("approved") and counts is not None and model_name=="elo_recent_form")
        original=p
        role_values,matches=role_features(reports,g,history)
        role_applied=bool(counts is not None and matches and model_name=="elo_recent_form" and effect.get("player_role",{}).get("approved"))
        if role_applied:
            p=adjust(p,effect["player_role"]["weights"],counts+role_values)
        elif apply:
            p=adjust(p,effect["weights"],counts)
        results.append(dict(id=g["id"],date=g["date"],home=g["home"],away=g["away"],
                            home_win_probability=round(p,4),away_win_probability=round(1-p,4),
                            baseline_home_probability=round(original,4), injuries=reports,
                            injuries_in_model=apply or role_applied,player_roles_in_model=role_applied,model_name=model_name))
    output={"generated_utc":now.isoformat(),"model_trained_utc":(enhanced or model)["trained_utc"],"source":"approved model and archived ESPN games","predictions":results,"limitations":"Uses rolling-validated Elo and recent form when approved, otherwise baseline. Availability adjustment requires verified reports for both teams and a successful chronological evaluation."}
    output["availability_evaluation"]={k:effect[k] for k in ("approved","paired","train","test","test_from","baseline","adjusted","player_role") if k in effect}
    dest=DATA/"model/predictions.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists():
        previous=json.loads(dest.read_text())
        if {k:v for k,v in previous.items() if k!="generated_utc"} == {k:v for k,v in output.items() if k!="generated_utc"}:
            print("Prediction inputs and results unchanged.")
            return
    dest.write_text(json.dumps(output,indent=2)+"\n")
    print("Exported",len(results),"future predictions.")
if __name__=="__main__":
    main()
