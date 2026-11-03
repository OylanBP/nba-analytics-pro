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
    import subprocess
    result = subprocess.run(["pdftotext", "-layout", "-", "-"], input=data,
                            capture_output=True, check=True, timeout=30)
    raw = result.stdout.decode("utf8")
    stamp = published_utc(url)
    expected = stamp.astimezone(ZoneInfo("America/New_York")).strftime("%m/%d/%y %I:%M %p")
    if not re.search(r"Injury Report:\s*" + re.escape(expected), raw, re.I):
        raise ValueError("PDF header and publication time disagree")
    return parse_lines(raw, url, teams)


def parse_lines(raw, url, teams):
    records, covered = {}, {}
    day = matchup = team = None
    names = {k.lower(): str(v["id"]) for k,v in teams.items()}
    if "la clippers" in names:
        names["los angeles clippers"] = names["la clippers"]
    for line in raw.splitlines():
        if "Injury Report:" in line or "Current Status" in line:
            continue
        cells = re.split(r"\s{2,}", line.strip())
        for cell in cells:
            if DATE.fullmatch(cell):
                day = dt.datetime.strptime(cell, "%m/%d/%Y").date().isoformat()
                matchup = team = None
            elif MATCHUP.fullmatch(cell):
                matchup, team = cell, None
            elif cell.lower() in names:
                team = names[cell.lower()]
        if not (team and matchup and day):
            continue
        key = (day, matchup, team)
        if "NOT YET SUBMITTED" in line.upper():
            covered[key] = False
            continue
        for i, cell in enumerate(cells):
            if cell in STATUS and i and "," in cells[i-1]:
                name = cells[i-1]
                covered[key] = True
                records[key+(name,)] = dict(game_date=day, matchup=matchup, team_id=team,
                                             name=name,status=cell,reason=" ".join(cells[i+1:]))
    return dict(parser_version=2, observed_utc=published_utc(url).isoformat(), source_url=url,
                covered_games=[dict(game_date=d,matchup=m,team_id=t,submitted=v)
                               for (d,m,t),v in covered.items()], players=list(records.values()))
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
    snapshots = [s for s in snapshots if s.get("parser_version") == 2]
    known = {s["source_url"] for s in snapshots}

    added = 0
    for url in urls[:3]:
        if url in known:
            continue
        try:
            snapshot = parse_pdf(fetch(url), url, teams)
            if not snapshot["covered_games"]:
                raise ValueError("No verified team/game rows parsed")
            validate_snapshot(snapshot)
        except Exception as exc:
            print("Rejected unreadable official report:", type(exc).__name__, str(exc))
            continue
        snapshots = [old for old in snapshots if old["source_url"] != url]
        snapshots.append(snapshot)
        added += 1
    if not added and not any(s["source_url"] in urls[:3] for s in snapshots):
        raise RuntimeError("No official report could be parsed")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshots, ensure_ascii=False, separators=(",", ":"))+"\n")
    print("Archived", added, "new official reports; total", len(snapshots))

if __name__ == "__main__":
    main()
