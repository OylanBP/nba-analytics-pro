#!/usr/bin/env python3
"""Archive official NBA pregame injury reports, with timestamps and matchup scope.

Reports are sourced directly from official.nba.com links to NBA-hosted PDFs.
Never infer a historical status from a newer report or treat missing as healthy.
"""
import datetime as dt
import io
import json
import pathlib
import re
import urllib.request
from urllib.parse import urljoin
from html.parser import HTMLParser
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
PAGE = "https://official.nba.com/nba-injury-report-2026-27-season/"
OUT = ROOT / "data/injuries/snapshots.json"
PDF_PATTERN = re.compile(r"Injury-Report_(\d{4}-\d{2}-\d{2})_(\d{2})_(\d{2})(AM|PM)\.pdf", re.I)
STATUS = {"Out", "Doubtful", "Questionable", "Probable", "Available"}
MATCHUP = re.compile(r"\b([A-Z]{3})@([A-Z]{3})\b")
DATE = re.compile(r"\b(\d{2}/\d{2}/\d{4})\b")

class ReportLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag == "a":
            href = dict(attrs).get("href", "")
            if PDF_PATTERN.search(href):
                url = urljoin(PAGE, href)
                if url.startswith("https://ak-static.cms.nba.com/"):
                    self.urls.append(url)

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 NBAAnalyticsPro/3.0"})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()

def published_utc(url):
    match = PDF_PATTERN.search(url)
    if not match:
        raise ValueError("Invalid official NBA report URL")
    day, hh, mm, period = match.groups()
    hour = int(hh) % 12 + (12 if period.upper() == "PM" else 0)
    return dt.datetime.strptime(day, "%Y-%m-%d").replace(
        hour=hour, minute=int(mm), tzinfo=ZoneInfo("America/New_York")
    ).astimezone(dt.timezone.utc)

def parse_pdf(data, url, teams):
    import pdfplumber
    when = published_utc(url)
    # NBA reports contain rows: Game Date | Game | Team | Player | Status | Reason.
    # The report is a full snapshot, but only reported teams are marked covered.
    records = []
    active_date = None
    active_matchup = None
    active_team = None
    covered = set()
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            for line in (page.extract_text() or "").splitlines():
                date_match = DATE.search(line)
                if date_match:
                    active_date = dt.datetime.strptime(date_match.group(1), "%m/%d/%Y").date().isoformat()
                matchup = MATCHUP.search(line)
                if matchup:
                    active_matchup = matchup.group(0)
                    active_team = None
                if not active_matchup or not active_date:
                    continue
                compact = re.sub(r"\s+", "", line).lower()
                for name, info in teams.items():
                    token = re.sub(r"\s+", "", name).lower()
                    if token in compact:
                        active_team = info
                        break
                if not active_team:
                    continue
                submitted = "NOTYETSUBMITTED" not in compact
                covered.add((active_date, active_matchup, str(active_team["id"]), submitted))
                status_match = re.search(r"\b(Out|Doubtful|Questionable|Probable|Available)\b", line)
                if not status_match:
                    continue
                before = line[:status_match.start()]
                name = re.sub(r"^.*?"+re.escape(active_team["name"].replace(" ", "")), "", before, flags=re.I).strip()
                if not name:
                    continue
                records.append({"game_date": active_date, "matchup": active_matchup,
                                "team_id": str(active_team["id"]), "name": name,
                                "status": status_match.group(1), "reason": line[status_match.end():].strip()})
    return {"observed_utc": when.isoformat(), "source_url": url,
            "covered_games": [{"game_date": d, "matchup": m, "team_id": t, "submitted": submitted}
                              for d,m,t,submitted in sorted(covered) if d and m],
            "players": records}

def main():
    from injury_archive import validate_snapshot
    html = fetch(PAGE).decode("utf-8", errors="replace")
    links = ReportLinks()
    links.feed(html)
    urls = sorted(set(links.urls), key=published_utc, reverse=True)
    now = dt.datetime.now(dt.timezone.utc)
    # Keep only latest available NBA-hosted report from the past 36 hours.
    urls = [u for u in urls if dt.timedelta(0) <= now-published_utc(u) <= dt.timedelta(hours=36)]
    if not urls:
        raise RuntimeError("No current official NBA PDF report found; no invented data")
    standings = json.loads((ROOT/"data/standings.json").read_text())
    teams = {t["name"]: t for t in standings["teams"]}
    if OUT.exists():
        snapshots = json.loads(OUT.read_text())
    else:
        snapshots = []
    known = {s["source_url"] for s in snapshots}
    added = 0
    for url in urls[:3]:
        if url in known:
            continue
        try:
            snapshot = parse_pdf(fetch(url), url, teams)
            if not snapshot["covered_games"]:
                import pdfplumber
                with pdfplumber.open(io.BytesIO(fetch(url))) as debug_pdf:
                    print("NBA PDF extraction sample:", repr((debug_pdf.pages[0].extract_text() or "")[:2200]))
                    print("NBA PDF first table:", repr((debug_pdf.pages[0].extract_tables() or [])[:1])[:2200])
                raise ValueError("No verified team/game rows parsed")
            validate_snapshot(snapshot)
        except Exception as exc:
            print("Rejected unreadable official report:", type(exc).__name__, str(exc))
            continue
        snapshots.append(snapshot)
        added += 1
    if not added and not any(s["source_url"] in urls[:3] for s in snapshots):
        raise RuntimeError("No official report could be parsed")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshots, ensure_ascii=False, separators=(",", ":"))+"\n")
    print("Archived", added, "new official reports; total", len(snapshots))

if __name__ == "__main__":
    main()
