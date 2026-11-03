#!/usr/bin/env python3
"""Chronological NBA model training with champion/challenger protection.

Input: data/model/games_history.json, a list of completed games:
[{"date":"2026-10-22","home_team":"BOS","away_team":"NYK",
  "home_win":1,"home_win_pct_before":0.6,"away_win_pct_before":0.5,
  "home_rest_days":2,"away_rest_days":1}]
All features MUST be pregame observations. No synthetic games are allowed.
"""
import argparse
import datetime as dt
import json
import math
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data/model/games_history.json"
CHAMPION = ROOT / "data/model/champion.json"
REPORT = ROOT / "data/model/evaluation.json"
FEATURES = ("home_win_pct_before", "away_win_pct_before", "home_rest_days", "away_rest_days")
MIN_GAMES = 200
MIN_TEST = 40

def sigmoid(z):
    return 1 / (1 + math.exp(-max(-35, min(35, z))))

def predict(weights, x):
    return sigmoid(weights[0] + sum(a*b for a,b in zip(weights[1:],x)))

def read_games():
    if not SOURCE.exists():
        raise ValueError("Historical pregame dataset missing; no training performed.")
    rows = json.loads(SOURCE.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        raise ValueError("Historical dataset must be a JSON array.")
    seen = set()
    games = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed game record.")
        date = dt.date.fromisoformat(row["date"])
        if date > dt.date.today():
            raise ValueError("Future games are not valid training outcomes.")
        if row["home_win"] not in (0, 1, False, True):
            raise ValueError("Outcome must be binary.")
        if row["home_team"] == row["away_team"]:
            raise ValueError("Team cannot play itself.")
        key = str(row["id"]) if row.get("id") else (str(date), row["home_team"], row["away_team"])
        if key in seen:
            raise ValueError("Duplicate game: "+str(key))
        seen.add(key)
        values = [float(row[k]) for k in FEATURES]
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Non-finite pregame feature.")
        if not all(0 <= v <= 1 for v in values[:2]) or not all(0 <= v <= 14 for v in values[2:]):
            raise ValueError("Pregame feature outside expected range.")
        games.append((str(date), values, int(row["home_win"])))
    games.sort(key=lambda x:x[0])
    if len(games) < MIN_GAMES:
        raise ValueError(f"Insufficient real games: {len(games)}; need {MIN_GAMES}.")
    return games

def train(rows, steps=1500, rate=0.08):
    weights = [0.0] * (len(FEATURES)+1)
    for _ in range(steps):
        grad = [0.0] * len(weights)
        for _, x, y in rows:
            # Scale rest-day values to avoid numerical imbalance.
            scaled = [x[0], x[1], x[2]/7, x[3]/7]
            error = predict(weights, scaled) - y
            grad[0] += error
            for j, value in enumerate(scaled):
                grad[j+1] += error*value
        n = len(rows)
        for j in range(len(weights)):
            weights[j] -= rate*(grad[j]/n + (0.001*weights[j] if j else 0))
    return weights

def score(weights, rows):
    probs = [predict(weights,[x[0],x[1],x[2]/7,x[3]/7]) for _,x,_ in rows]
    outcomes = [y for _,_,y in rows]
    brier = sum((p-y)**2 for p,y in zip(probs,outcomes))/len(rows)
    logloss = -sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12)) for p,y in zip(probs,outcomes))/len(rows)
    accuracy = sum((p>=0.5)==bool(y) for p,y in zip(probs,outcomes))/len(rows)
    return {"brier":round(brier,6),"log_loss":round(logloss,6),"accuracy":round(accuracy,6),"n":len(rows)}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=["train","evaluate"],default="evaluate")
    args=parser.parse_args()
    games=read_games()
    # Hold out the newest 20% of games. Never shuffle time series.
    split=max(len(games)-max(MIN_TEST,len(games)//5),1)
    training,holdout=games[:split],games[split:]
    if len(training)<100 or len(holdout)<MIN_TEST:
        raise ValueError("Not enough chronological train/test games.")
    challenger=train(training)
    challenger_score=score(challenger,holdout)
    champion=None
    champion_score=None
    if CHAMPION.exists():
        champion=json.loads(CHAMPION.read_text(encoding="utf-8"))
        if champion.get("features")!=list(FEATURES):
            raise ValueError("Existing champion uses incompatible features.")
        champion_score=score(champion["weights"],holdout)
    # This is an evaluation gate, not a claim of independent unbiased test accuracy:
    # Repeated decisions on the same holdout can overfit. Production needs rolling backtests.
    improved=champion_score is None or (
        challenger_score["brier"] < champion_score["brier"]-0.001 and
        challenger_score["log_loss"] <= champion_score["log_loss"]+0.005
    )
    report={"generated_utc":dt.datetime.now(dt.timezone.utc).isoformat(),
            "source":"real completed games with pregame features",
            "train_games":len(training),"holdout_games":len(holdout),
            "challenger":challenger_score,"champion":champion_score,
            "challenger_passed_gate":improved,
            "note":"Chronological holdout; rolling out-of-sample backtesting required before production predictions."}
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    if args.mode=="train" and improved:
        CHAMPION.write_text(json.dumps({"features":list(FEATURES),"weights":challenger,
            "trained_utc":report["generated_utc"],"training_games":len(training),
            "holdout_brier":challenger_score["brier"]},indent=2)+"\n",encoding="utf-8")
        print("Challenger promoted after evaluation gate.")
    else:
        print("Evaluation only; champion unchanged.")
    print(json.dumps(report,ensure_ascii=False))

if __name__=="__main__":
    try:
        main()
    except (ValueError,KeyError,TypeError,FileNotFoundError) as exc:
        print("Model pipeline stopped safely: "+str(exc),file=sys.stderr)
        sys.exit(2)
