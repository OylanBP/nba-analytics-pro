
#!/usr/bin/env python3
"""取得 NBA 30 隊球員陣容，儲存成網站可讀取的 JSON。"""

import datetime as dt
import json
import pathlib
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
STANDINGS = ROOT / "data" / "standings.json"
OUTPUT = ROOT / "data" / "rosters.json"

API = (
    "https://site.api.espn.com/apis/site/v2/"
    "sports/basketball/nba/teams/{team_id}/roster"
)


def download(url):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def extract_athletes(payload):
    athletes = payload.get("athletes", [])
    result = []

    for item in athletes:
        # ESPN 可能回傳球員物件，或依位置分組的球員清單
        if isinstance(item, dict) and "items" in item:
            result.extend(item["items"])
        elif isinstance(item, dict):
            result.append(item)

    return result


def parse_player(player):
    position = player.get("position") or {}

    return {
        "id": str(player.get("id", "")),
        "name": player.get("displayName", ""),
        "number": player.get("jersey", ""),
        "position": position.get("abbreviation", ""),
        "height": player.get("displayHeight", ""),
        "weight": player.get("displayWeight", ""),
        "age": player.get("age"),
        "headshot": (
            player.get("headshot") or {}
        ).get("href", ""),
    }


def main():
    standings = json.loads(
        STANDINGS.read_text(encoding="utf-8")
    )
    teams = standings.get("teams", [])

    if len(teams) != 30:
        raise ValueError("戰績資料不足 30 隊，停止更新陣容")

    result = []

    for team in teams:
        team_id = team["id"]
        url = API.format(team_id=team_id)

        payload = download(url)
        players = [
            parse_player(p)
            for p in extract_athletes(payload)
        ]

        players = [
            p for p in players
            if p["id"] and p["name"]
        ]

        if not players:
            raise ValueError(
                f"{team['name']} 沒有取得有效球員資料"
            )

        result.append({
            "id": team_id,
            "name": team["name"],
            "abbreviation": team["abbreviation"],
            "conference": team["conference"],
            "logo": team.get("logo", ""),
            "players": players,
        })

        print(f"{team['name']}: {len(players)} players")
        time.sleep(0.2)

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    document = {
        "source": "ESPN public API (unofficial)",
        "updated_at_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(timespec="seconds"),
        "teams": result,
    }

    temp = OUTPUT.with_suffix(".tmp")
    temp.write_text(
        json.dumps(document, ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    temp.replace(OUTPUT)

    print("Saved rosters for 30 NBA teams.")


if __name__ == "__main__":
    main()
