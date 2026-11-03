#!/usr/bin/env python3
"""Publish future probabilities only when a validated champion model exists."""
import datetime as dt
import json
import math
import pathlib
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
        results.append({"id":g["id"],"date":g["date"],"home":g["home"],"away":g["away"],"home_win_probability":round(p,4),"away_win_probability":round(1-p,4)})
    output={"generated_utc":now.isoformat(),"model_trained_utc":model["trained_utc"],"source":"approved model and archived ESPN games","predictions":results,"limitations":"Win percentage and rest only; no injuries or roster updates."}
    dest=DATA/"model/predictions.json"
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_text(json.dumps(output,indent=2)+"\n")
    print("Exported",len(results),"future predictions.")
if __name__=="__main__":
    main()
