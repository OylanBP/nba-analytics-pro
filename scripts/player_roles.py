"""ESPN completed box scores; use only prior UTC dates to measure player roles."""
import argparse
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
import gzip
import json
from pathlib import Path
import re
import unicodedata
from urllib.request import urlopen

DATA = Path(__file__).resolve().parents[1] / "data"
BOX = DATA / "model/player_box.json.gz"
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/summary?event="


def name_key(name):
    if "," in name:
        last, first = name.split(",", 1)
        name = first + " " + last
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    return re.sub("[^a-z0-9]", "", text)


def parse_box(payload, game):
    if str(payload["header"]["id"]) != str(game["id"]):
        raise ValueError("Mismatched event ID")
    if not payload["header"]["competitions"][0]["status"]["type"]["completed"]:
        raise ValueError("Game is not final")
    result = {}
    for team in payload["boxscore"]["players"]:
        team_id = str(team["team"]["id"])
        rows = {}
        for group in team["statistics"]:
            keys = group["keys"]
            if not {"minutes","points"} <= set(keys):
                continue
            for player in group["athletes"]:
                values = dict(zip(keys, player.get("stats", [])))
                if player.get("didNotPlay") or not values.get("minutes","").isdigit():
                    continue
                minutes = int(values["minutes"])
                if minutes > 0:
                    rows[player["athlete"]["displayName"]] = [minutes,int(values["points"])]
        if len(rows) < 5:
            raise ValueError("Incomplete player box")
        result[team_id] = rows
    if set(result) != {str(game["home"]),str(game["away"])}:
        raise ValueError("Mismatched teams")
    return result


def load_boxes():
    if not BOX.exists():
        return {}
    return json.loads(gzip.decompress(BOX.read_bytes()))


def update(cache=None):
    archive = load_boxes()
    games = json.loads((DATA / "games.json").read_text())["games"]
    pending = [g for g in games if "h" in g and g["id"] not in archive]
    def get(game):
        try:
            path = cache / (game["id"]+".json") if cache else None
            if path and path.exists():
                payload=json.loads(path.read_bytes())
            else:
                with urlopen(SUMMARY+game["id"],timeout=20) as response:
                    payload=json.load(response)
            return game["id"],parse_box(payload,game)
        except (ValueError, KeyError, OSError) as err:
            print("Skipped",game["id"],str(err)[:100])
            return game["id"],None
    with ThreadPoolExecutor(max_workers=5) as pool:
        for game_id,box in pool.map(get,pending):
            if box:
                archive[game_id]=box
    if not archive:
        raise ValueError("No verified box scores")
    data=json.dumps(archive,sort_keys=True,separators=(",",":")).encode()
    BOX.write_bytes(gzip.compress(data,mtime=0))
    print("Verified ESPN box scores:",len(archive))


def role_history(games,boxes):
    history=defaultdict(list)
    for game in sorted(games,key=lambda g:g["date"]):
        for team,players in boxes.get(game["id"],{}).items():
            for name,stats in players.items():
                history[(game["season"],team,name_key(name))].append((game["date"][:10],stats))
    return history


def role_features(reports,game,history):
    minutes=[0.0]*4
    points=[0.0]*4
    statuses=("Out","Doubtful","Questionable","Probable")
    matched=0
    for side,sign in (("away",1),("home",-1)):
        for player in reports[side]["players"]:
            player.pop("role",None)
            records=history.get((game["season"],str(game[side]),name_key(player["name"])),[])
            sample=[v for date,v in records if date<game["date"][:10]][-10:]
            if len(sample)<3:
                continue
            mpg=sum(v[0] for v in sample)/len(sample)
            ppg=sum(v[1] for v in sample)/len(sample)
            player["role"]={"games":len(sample),"minutes":round(mpg,1),"points":round(ppg,1)}
            if player["status"] in statuses:
                i=statuses.index(player["status"])
                minutes[i]+=sign*mpg/30
                points[i]+=sign*ppg/20
                matched+=1
    return minutes+points,matched

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--cache",type=Path)
    update(parser.parse_args().cache)
