
#!/usr/bin/env python3
"""取得 ESPN NBA 戰績，驗證 30 隊後儲存為 JSON。"""

import datetime as dt
import json
import os
import pathlib
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]

URL = (
    "https://site.web.api.espn.com/apis/v2/sports/"
    "basketball/nba/standings"
    "?region=us&lang=en&contentorigin=espn"
)


def get_stat(stats, *keys):
    for stat in stats:
        if (
            stat.get("name") in keys
            or stat.get("abbreviation") in keys
            or stat.get("type") in keys
        ):
            value = stat.get("value", stat.get("displayValue"))
            if value is not None:
                return value
    return None


def walk_groups(obj, label=""):
    if not isinstance(obj, dict):
        return

    standings = obj.get("standings")

    if isinstance(standings, dict) and "entries" in standings:
        yield label or obj.get("name", ""), standings["entries"]

    for child in obj.get("children", []):
        name = child.get("name") or child.get("abbreviation") or label
        yield from walk_groups(child, name)


def conference(label, entry):
    team = entry.get("team", {})
    raw = f"{label} {team.get('conference', '')}".lower()

    if "east" in raw:
        return "East"
    if "west" in raw:
        return "West"

    return None


def parse(payload):
    rows = []

    for label, entries in walk_groups(payload):
        for entry in entries:
            team = entry.get("team") or {}
            stats = entry.get("stats") or []
            conf = conference(label, entry)

            if not conf:
                continue

            wins = get_stat(stats, "wins", "W")
            losses = get_stat(stats, "losses", "L")

            if wins is None or losses is None:
                raise ValueError(
                    f"Missing win/loss stats: {team.get('displayName')}"
                )

            wins = int(float(wins))
            losses = int(float(losses))

            pct = (
                wins / (wins + losses)
                if wins + losses
                else 0
            )

            rows.append({
                "id": str(team.get("id", "")),
                "name": team.get("displayName") or team.get("name"),
                "abbreviation": team.get("abbreviation", ""),
                "conference": conf,
                "wins": wins,
                "losses": losses,
                "win_pct": round(pct, 4),
                "logo": (
                    (team.get("logos") or [{}])[0].get("href", "")
                ),
            })

    unique = {
        row["id"]: row
        for row in rows
        if row["id"]
    }

    rows = list(unique.values())

    east = sum(r["conference"] == "East" for r in rows)
    west = sum(r["conference"] == "West" for r in rows)

    if len(rows) != 30 or east != 15 or west != 15:
        raise ValueError(
            f"Unexpected standings: {len(rows)} teams, "
            f"East={east}, West={west}"
        )

    rows.sort(
        key=lambda r: (
            r["conference"],
            -r["win_pct"],
            -r["wins"],
            r["name"],
        )
    )

    return rows


def main():
    request = urllib.request.Request(
        URL,
        headers={
            "User-Agent": "Mozilla/5.0 NBAAnalyticsPro/0.2",
            "Accept": "application/json",
        },
    )

    with urllib.request.urlopen(request, timeout=25) as response:
        payload = json.load(response)

    rows = parse(payload)

    output = {
        "source": "ESPN public standings endpoint (unofficial)",
        "source_url": URL,
        "updated_at_utc": dt.datetime.now(
            dt.timezone.utc
        ).isoformat(timespec="seconds"),
        "teams": rows,
    }

    target = ROOT / "data" / "standings.json"
    target.parent.mkdir(exist_ok=True)

    temp = target.with_suffix(".tmp")

    temp.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    os.replace(temp, target)

    print(f"Wrote {len(rows)} teams to {target}")


if __name__ == "__main__":
    main()
