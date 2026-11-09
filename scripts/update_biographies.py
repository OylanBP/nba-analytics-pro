"""Build sourced player background snapshots without inferring missing biographical facts."""
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/biographies.json"
BASE = "https://site.web.api.espn.com/apis/common/v3/sports/basketball/nba/athletes/"
ROSTER = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/teams/{}/roster"
from update_rosters import extract_athletes


def fetch(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url,headers={"User-Agent":"NBAAnalyticsPro/3.1","Accept":"application/json"})
            with urllib.request.urlopen(request,timeout=20) as response:
                return json.load(response)
        except (OSError,ValueError):
            if attempt == 2:
                raise
            time.sleep(1+attempt)


def draft_text(value):
    if not value:
        return None
    if value.lower().strip() == "undrafted":
        return "未經 NBA 選秀獲選"
    match=re.fullmatch(r"(\d{4}): Rd (\d+), Pk (\d+) \(([^)]+)\)",value)
    if match:
        year,round_,pick,team=match.groups()
        return dict(year=int(year),round=int(round_),pick=int(pick),team=team)
    return None


def parse(player, overview, bio, when):
    athlete=overview["athlete"]
    if str(athlete["id"]) != str(player["id"]):
        raise ValueError("Mismatched player ID")
    birth=player.get("birthPlace") or {}
    birthday=(player.get("dateOfBirth") or "")[:10] or None
    if not birthday and athlete.get("displayDOB"):
        try:
            birthday=dt.datetime.strptime(athlete["displayDOB"],"%d/%m/%Y").date().isoformat()
        except ValueError:
            pass
    history=[dict(team=t["displayName"],seasons=t["seasons"])
             for t in bio.get("teamHistory",[]) if t.get("displayName") and t.get("seasons")]
    awards=[dict(name=a["name"],seasons=a.get("seasons",[]))
            for a in bio.get("awards",[]) if a.get("name")]
    return dict(name=athlete["displayName"],birthday=birthday,
                birthplace={k:birth.get(k) for k in ("city","state","country") if birth.get(k)},
                birthplace_text=athlete.get("displayBirthPlace") if not birth else None,
                college=(player.get("college") or athlete.get("college") or {}).get("name"),
                debut_year=athlete.get("debutYear"),draft=draft_text(athlete.get("displayDraft","")),
                history=history,awards=awards,updated_at_utc=when,
                source_url="https://www.espn.com/nba/player/bio/_/id/"+str(player["id"]))


def main():
    teams=json.loads((ROOT/"data/rosters.json").read_text())["teams"]
    wanted={str(p["id"]) for t in teams for p in t["players"]}
    now=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    previous=json.loads(OUT.read_text()).get("players",{}) if OUT.exists() else {}
    raw={}
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as pool:
        for payload in pool.map(lambda t:fetch(ROSTER.format(t["id"])),teams):
            raw.update({str(p["id"]):p for p in extract_athletes(payload)})
    def collect(item):
        pid,player=item
        try:
            return pid,parse(player,fetch(BASE+pid),fetch(BASE+pid+"/bio"),now),None
        except Exception as exc:
            return pid,previous.get(pid),str(exc)
    players,failures={},[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        for pid,row,error in pool.map(collect,[(pid,raw.get(pid,{"id":pid})) for pid in sorted(wanted)]):
            if row:
                players[pid]=row
            if error:
                failures.append(pid)
            if len(players) % 50 == 0:
                print(f"Verified backgrounds: {len(players)}, source failures: {len(failures)}",flush=True)
    for pid in wanted - players.keys():
        if pid in previous:
            players[pid]=previous[pid]
    if len(players)<.9*len(wanted) or len(failures)>.1*len(wanted):
        raise ValueError(f"Insufficient verified biography coverage: {len(players)}/{len(wanted)}, failures {len(failures)}")
    doc=dict(source="ESPN 公開球員資料與生涯頁",updated_at_utc=now,roster_players=len(wanted),
             fetch_failures=len(failures),players=players)
    temp=OUT.with_suffix(".tmp")
    temp.write_text(json.dumps(doc,ensure_ascii=False,separators=(",",":"))+"\n")
    temp.replace(OUT)
    print(f"Biographies {len(players)}/{len(wanted)}, errors {len(failures)}")

if __name__=="__main__":
    main()
