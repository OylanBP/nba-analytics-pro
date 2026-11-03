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
    weights=[0.0]*len(samples[0][1])
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
        def role_sample(r):
            p,counts,y=sample(r)
            return p,counts+labels[r["id"]].get("roles",[0.]*8),y
        role_weights=fit_effect(list(map(role_sample,train_rows)))
        role_pairs=[]
        count_approved=all(after[k]<before[k] for k in ("brier","log_loss"))
        for row in test_rows:
            p,x,y=role_sample(row)
            if labels[row["id"]].get("matched_players",0):
                corrected=adjust(p,role_weights,x)
            else:
                corrected=adjust(p,weights,x[:4]) if count_approved else p
            role_pairs.append((p,corrected,y))
        pairs=role_pairs
        role_metrics=metrics(1)
        covered=sum(labels[r["id"]].get("matched_players",0)>0 for r in test_rows)
        role_approved=covered>=40 and all(role_metrics[k]<min(before[k],after[k]) for k in ("brier","log_loss"))
        report.update(player_role=dict(approved=role_approved,weights=role_weights,
                      metrics=role_metrics,covered_test_games=covered))
        report.update(train=len(train_rows),test=len(pairs),test_from=cutoff,baseline=before,
                      adjusted=after,weights=weights,approved=all(after[k]<before[k] for k in ('brier','log_loss')))
    MODEL.write_text(json.dumps(report,indent=2)+'\n')
    print(report)

if __name__=='__main__':
    train()
