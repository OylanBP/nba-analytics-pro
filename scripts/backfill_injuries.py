#!/usr/bin/env python3
"""Backfill timestamped NBA official injury PDFs for historical pregame research.

Archives source timestamps and matchup-specific submission status. No postgame
information is used to infer pregame availability.
"""
import argparse
import datetime as dt
import json
import pathlib
import sys
from collections import defaultdict
from html.parser import HTMLParser
from urllib.parse import urljoin

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from fetch_official_injuries import PDF_PATTERN, fetch, parse_pdf, published_utc
from injury_archive import validate_snapshot

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data/injuries/snapshots.json"
PAGES = [
    "https://official.nba.com/nba-injury-report-2025-26-season/",
    "https://official.nba.com/nba-injury-report-2026-27-season/",
]

class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls = []
    def handle_starttag(self, tag, attrs):
        if tag != "a":
            return
        href = dict(attrs).get("href", "")
        if PDF_PATTERN.search(href):
            url = urljoin("https://official.nba.com/", href)
            if url.startswith("https://ak-static.cms.nba.com/"):
                self.urls.append(url)

def select_urls(urls, per_day):
    # Prefer reports at multiple times, to cover early and late tipoffs.
    days = defaultdict(list)
    for url in set(urls):
        days[published_utc(url).date().isoformat()].append(url)
    selected = []
    for day, candidates in sorted(days.items()):
        ordered = sorted(candidates, key=published_utc)
        if len(ordered) <= per_day:
            selected.extend(ordered)
        else:
            indices = sorted({round(i * (len(ordered)-1) / (per_day-1))
                              for i in range(per_day)})
            selected.extend(ordered[i] for i in indices)
    return selected

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--per-day", type=int, default=4)
    parser.add_argument("--max-new", type=int, default=150)
    args = parser.parse_args()
    if args.per_day < 2 or args.max_new < 1:
        parser.error("per-day must be >=2 and max-new >=1")
    links = Links()
    for page in PAGES:
        try:
            links.feed(fetch(page).decode("utf-8", "replace"))
        except Exception as exc:
            print("Could not read", page, str(exc))
    urls = select_urls(links.urls, args.per_day)
    if not urls:
        raise RuntimeError("No official historical report links found")
    teams = json.loads((ROOT / "data/standings.json").read_text())["teams"]
    team_map = {t["name"]: t for t in teams}
    snapshots = json.loads(OUT.read_text()) if OUT.exists() else []
    known = {s["source_url"] for s in snapshots if s.get("players")}
    count, failed = 0, 0
    for url in urls:
        if url in known:
            continue
        try:
            snapshot = parse_pdf(fetch(url), url, team_map)
            validate_snapshot(snapshot)
            if not snapshot["covered_games"]:
                raise ValueError("No matchup coverage")
            snapshots = [s for s in snapshots if s["source_url"] != url]
            snapshots.append(snapshot)
            count += 1
        except Exception as exc:
            failed += 1
            print("Skipped", url, str(exc))
        if count >= args.max_new:
            break
    snapshots.sort(key=lambda s: s["observed_utc"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(snapshots, ensure_ascii=False, separators=(",", ":")) + "\n")
    print("Official reports:", len(urls), "new:", count, "failed:", failed,
          "archived:", len(snapshots), "player rows:",
          sum(len(s.get("players", [])) for s in snapshots))
    if not count and not snapshots:
        raise RuntimeError("No valid historical snapshots available")

if __name__ == "__main__":
    main()
