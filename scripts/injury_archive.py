"""Verified pregame injury snapshots. No retroactive inference from current status."""
import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data/injuries/snapshots.json"
OUT = {"Out", "Doubtful", "Questionable", "Probable", "Available"}

def parse_time(value):
    instant = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if instant.tzinfo is None:
        raise ValueError("Injury timestamp must include a timezone")
    return instant.astimezone(dt.timezone.utc)

def validate_snapshot(snapshot):
    if not isinstance(snapshot, dict) or not snapshot.get("source_url"):
        raise ValueError("A verifiable source URL is required")
    observed = parse_time(snapshot["observed_utc"])
    if observed > dt.datetime.now(dt.timezone.utc) + dt.timedelta(minutes=5):
        raise ValueError("Future injury snapshot timestamp")
    for player in snapshot.get("players", []):
        if not player.get("name") or not player.get("team_id") or player.get("status") not in OUT:
            raise ValueError("Incomplete player/team/status")
    return observed

def load_snapshots():
    if not PATH.exists():
        return []
    data = json.loads(PATH.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("Injury archive must be a list")
    for item in data:
        validate_snapshot(item)
    return data

def injury_at(game_utc, team_id, snapshots=None, matchup=None, game_date=None):
    """Latest verifiable pre-tipoff report for this matchup/team; otherwise unknown.

    The report must explicitly cover the game's team, matchup and local NBA game
    date. Missing or not-yet-submitted reports are never treated as healthy.
    """
    game = parse_time(game_utc)
    candidates = []
    for snapshot in (load_snapshots() if snapshots is None else snapshots):
        observed = validate_snapshot(snapshot)
        if not (observed <= game and game - observed <= dt.timedelta(hours=48)):
            continue
        if not matchup or not game_date:
            # Legacy archives lack game-specific provenance and cannot be trusted.
            continue
        covered = snapshot.get("covered_games", [])
        if not any(str(c.get("team_id")) == str(team_id) and
                   c.get("matchup") == matchup and
                   c.get("game_date") == game_date and c.get("submitted", True) for c in covered):
            continue
        candidates.append((observed, snapshot))
    if not candidates:
        return {"status": "unknown", "players": [], "observed_utc": None}
    observed, latest = max(candidates, key=lambda row: row[0])
    players = [p for p in latest.get("players", [])
               if str(p["team_id"]) == str(team_id) and
               p.get("matchup") == matchup and p.get("game_date") == game_date]
    return {"status": "verified", "players": players, "observed_utc": latest["observed_utc"],
            "source_url": latest["source_url"]}

if __name__ == "__main__":
    print(json.dumps({"snapshots": len(load_snapshots())}))
