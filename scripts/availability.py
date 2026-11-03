"""Point-in-time NBA availability features and paired chronological evaluation."""
import datetime as dt
import json
import math
from pathlib import Path
from zoneinfo import ZoneInfo
from enhanced_features import build
from enhanced_model import fit, forecast, sigmoid
from injury_archive import injury_at

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MODEL = DATA / 'model/availability.json'
HISTORY = DATA / 'injuries/labeled_games.json'
STATUSES = ('Out', 'Doubtful', 'Questionable', 'Probable')
ALIASES = {'NY':'NYK','WSH':'WAS','SA':'SAS','NO':'NOP','GS':'GSW','UTAH':'UTA'}


def game_key(game, teams):
    def code(team):
        name = teams[str(team)]
        return ALIASES.get(name, name)
    tip = dt.datetime.fromisoformat(game['date'].replace('Z','+00:00'))
    return tip.astimezone(ZoneInfo('America/New_York')).date().isoformat(), code(game['away'])+'@'+code(game['home'])


def difference(home, away):
    if any(team['status'] != 'verified' for team in (home, away)):
        return None
    def count(team,status):
        return sum(p['status']==status for p in team['players'])
    return [count(away,s)-count(home,s) for s in STATUSES]


def adjust(p, weights, counts):
    return sigmoid(math.log(p/(1-p)) + sum(a*b for a,b in zip(weights,counts)))


def fit_effect(samples):
    weights=[0.0]*len(STATUSES)
    for _ in range(350):
        grad=[0.0]*len(weights)
        for p,x,y in samples:
            err=adjust(p,weights,x)-y
            for j,v in enumerate(x):
                grad[j]+=err*v
        for j in range(len(weights)):
            weights[j]-=.03*(grad[j]/len(samples)+.04*weights[j])
    return weights


def train():
    games=json.loads((DATA/'games.json').read_text())['games']
    rows=build(games)
    labels={r['id']:r for r in json.loads(HISTORY.read_text())}
    paired=sorted((r for r in rows if r['id'] in labels),key=lambda r:r['date'])
    report=dict(approved=False,paired=len(paired),statuses=list(STATUSES))
    if len(paired)>=200:
        cutoff=paired[int(.70*len(paired))]['date']
        train_rows=[r for r in paired if r['date']<cutoff]
        test_rows=[r for r in paired if r['date']>=cutoff]
        # Fit the same underlying Elo/form model on strictly earlier outcomes.
        base=fit([r for r in rows if r['date']<cutoff],True)
        def sample(r):
            return forecast(base,r,True),labels[r['id']]['counts'],r['home_win']
        weights=fit_effect(list(map(sample,train_rows)))
        pairs=[(p,adjust(p,weights,x),y) for p,x,y in map(sample,test_rows)]
        def metrics(k):
            n=len(pairs)
            return dict(brier=sum((r[k]-r[2])**2 for r in pairs)/n,
                        log_loss=-sum(math.log(r[k] if r[2] else 1-r[k]) for r in pairs)/n,
                        correct=sum((r[k]>=.5)==bool(r[2]) for r in pairs))
        before,after=metrics(0),metrics(1)
        report.update(train=len(train_rows),test=len(pairs),test_from=cutoff,baseline=before,
                      adjusted=after,weights=weights,approved=all(after[k]<before[k] for k in ('brier','log_loss')))
    MODEL.write_text(json.dumps(report,indent=2)+'\n')
    print(report)

if __name__=='__main__':
    train()
