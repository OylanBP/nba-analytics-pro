"""Recover signed-time reports directly from the NBA host, even after index rollover."""
import argparse
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from availability import DATA,HISTORY,game_key,difference
from fetch_official_injuries import fetch,parse_pdf
from injury_archive import injury_at,parse_time

BASE='https://ak-static.cms.nba.com/referee/injury/Injury-Report_'

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--cache',type=Path)
    parser.add_argument('--offline',action='store_true')
    args=parser.parse_args()
    games=json.loads((DATA/'games.json').read_text())['games']
    teams=json.loads((DATA/'standings.json').read_text())['teams']
    names={t['name']:t for t in teams}
    teams={str(t['id']):t['abbreviation'] for t in teams}
    by_day={}
    for g in games:
        if 'h' in g and 'a' in g:
            day,match=game_key(g,teams)
            by_day.setdefault(day,[]).append((g,match))
    existing={r['id']:r for r in json.loads(HISTORY.read_text())} if HISTORY.exists() else {}
    def extract(day):
        url=BASE+day+'_05_00PM.pdf'
        path=args.cache/(day+'.pdf') if args.cache else None
        if args.offline and (not path or not path.exists()):
            return []
        try:
            data=path.read_bytes() if path and path.exists() else fetch(url)
            snapshot=parse_pdf(data,url,names)
        except Exception as exc:
            print(day,'report unavailable:',str(exc)[:120],flush=True)
            return []
        found=[]
        for g,match in by_day[day]:
            if parse_time(snapshot['observed_utc'])>=parse_time(g['date']):
                continue
            def team(side):
                return injury_at(g['date'],g[side],[snapshot],matchup=match,game_date=day)
            x=difference(team('home'),team('away'))
            if x is not None:
                found.append(dict(id=str(g['id']),counts=x,source_url=url,observed_utc=snapshot['observed_utc']))
        return found
    with ThreadPoolExecutor(max_workers=4) as pool:
        for batch in pool.map(extract,sorted(by_day)):
            existing.update({r['id']:r for r in batch})
    HISTORY.write_text(json.dumps(list(existing.values()),separators=(',',':'))+'\n')
    print('Paired pre-tipoff reports:',len(existing))

if __name__=='__main__':
    main()
