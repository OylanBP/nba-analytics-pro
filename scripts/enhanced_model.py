"""Research-only expanding-window comparison of baseline and enhanced logistic models."""
import datetime as dt
import json
import math
from pathlib import Path
from enhanced_features import FEATURES

ROOT = Path(__file__).resolve().parents[1]
BASE = FEATURES[:4]

def vector(row, enhanced):
    result = [row["home_win_pct_before"], row["away_win_pct_before"],
              row["home_rest_days"]/7, row["away_rest_days"]/7]
    if enhanced:
        result += [(row["home_elo"] - 1500)/400, (row["away_elo"] - 1500)/400,
                   row["home_last10_win_pct"], row["away_last10_win_pct"],
                   row["home_last10_margin"]/20, row["away_last10_margin"]/20]
    return result

def sigmoid(z):
    return 1/(1+math.exp(-max(-35, min(35, z))))

def fit(rows, enhanced, steps=900, rate=.12):
    width = len(FEATURES if enhanced else BASE)
    w = [0.] * (width+1)
    samples = [(vector(r, enhanced), int(r["home_win"])) for r in rows]
    for _ in range(steps):
        gradient = [0.] * len(w)
        for x, y in samples:
            err = sigmoid(w[0] + sum(a*b for a,b in zip(w[1:], x))) - y
            gradient[0] += err
            for j, value in enumerate(x):
                gradient[j+1] += err * value
        for j in range(len(w)):
            w[j] -= rate * (gradient[j]/len(samples) + (.001*w[j] if j else 0))
    return w

def forecast(weights, row, enhanced):
    return sigmoid(weights[0] + sum(a*b for a,b in zip(weights[1:], vector(row, enhanced))))

def evaluate(rows, initial=600, step=120):
    rows = sorted(rows, key=lambda r: (r["date"], str(r["id"])))
    if len(rows) < initial+step:
        raise ValueError("Insufficient games for rolling research")
    results = {}
    for label, enhanced in (("baseline", False), ("enhanced", True)):
        outcomes, folds = [], []
        for end in range(initial, len(rows), step):
            # No same-day games from test set are included in training.
            cutoff = rows[end]["date"]
            training = [r for r in rows if r["date"] < cutoff]
            testing = [r for r in rows if r["date"] >= cutoff][:step]
            if len(training) < initial or not testing:
                continue
            weights = fit(training, enhanced)
            fold = []
            for row in testing:
                p = forecast(weights, row, enhanced)
                fold.append((p, int(row["home_win"])))
            outcomes.extend(fold)
            folds.append({"start": testing[0]["date"], "end": testing[-1]["date"],
                          "train_games": len(training), "test_games": len(fold)})
        if not outcomes:
            raise ValueError("No valid chronological folds")
        brier = sum((p-y)**2 for p,y in outcomes)/len(outcomes)
        logloss = -sum(y*math.log(max(p,1e-12))+(1-y)*math.log(max(1-p,1e-12))
                       for p,y in outcomes)/len(outcomes)
        calibration = []
        for bucket in range(10):
            points = [(p,y) for p,y in outcomes if bucket/10 <= p < (bucket+1)/10 or (bucket==9 and p==1)]
            if points:
                calibration.append({"range": f"{bucket*10}-{(bucket+1)*10}%",
                                    "n": len(points),
                                    "predicted": round(sum(p for p,_ in points)/len(points), 4),
                                    "observed": round(sum(y for _,y in points)/len(points), 4)})
        results[label] = {"n": len(outcomes), "brier": round(brier, 6),
                          "log_loss": round(logloss, 6),
                          "accuracy": round(sum((p>=.5)==bool(y) for p,y in outcomes)/len(outcomes), 6),
                          "folds": folds, "calibration": calibration}
    b, e = results["baseline"], results["enhanced"]
    return {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "features": list(FEATURES), "methods": "expanding window, pregame features only",
            "models": results,
            "enhanced_outperformed_baseline": e["brier"] < b["brier"] and e["log_loss"] <= b["log_loss"],
            "production_model_changed": False,
            "injuries_included": False,
            "note": "No verified historical injury coverage yet. Research challenger only."}

if __name__ == "__main__":
    rows = json.loads((ROOT/"data/model/enhanced_history.json").read_text())
    result = evaluate(rows)
    (ROOT/"data/model/enhanced_evaluation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    print(json.dumps({k: {m: v[m] for m in ("n", "brier", "log_loss", "accuracy")}
                      for k,v in result["models"].items()}))
