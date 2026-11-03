"""Expanding-window chronological evaluation of the existing approved baseline.
No shuffled games, no invented injury labels, no re-use of evaluation outcomes as features.
"""
import datetime as dt
import json
from pathlib import Path
from model_lifecycle import read_games, train, score, predict

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data/model/rolling_backtest.json"

def evaluate(rows, initial=600, step=120):
    if len(rows) < initial + step:
        raise ValueError("Insufficient historical games for rolling backtest")
    folds = []
    observations = []
    for stop in range(initial, len(rows), step):
        test = rows[stop:min(stop + step, len(rows))]
        if not test:
            break
        weights = train(rows[:stop])
        metrics = score(weights, test)
        folds.append({"train_games": stop, "test_games": len(test),
                      "test_start": test[0][0], "test_end": test[-1][0], **metrics})
        for _, x, y in test:
            p = predict(weights, [x[0], x[1], x[2]/7, x[3]/7])
            observations.append((p, y))
    buckets = []
    for lower in range(0, 10):
        subset = [(p, y) for p, y in observations if lower/10 <= p < (lower+1)/10 or (lower == 9 and p == 1)]
        if subset:
            buckets.append({"probability_bin": f"{lower*10}-{(lower+1)*10}%",
                            "games": len(subset),
                            "mean_prediction": round(sum(p for p, _ in subset)/len(subset), 4),
                            "actual_win_rate": round(sum(y for _, y in subset)/len(subset), 4)})
    return {"generated_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
            "method": "expanding-window out-of-sample, baseline logistic regression",
            "folds": folds, "evaluated_games": len(observations),
            "brier": round(sum((p-y)**2 for p,y in observations)/len(observations), 6),
            "accuracy": round(sum((p>=0.5)==bool(y) for p,y in observations)/len(observations), 6),
            "calibration": buckets,
            "injury_coverage": "not available historically; excluded rather than backfilled"}

if __name__ == "__main__":
    result = evaluate(read_games())
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"folds": len(result["folds"]), "games": result["evaluated_games"],
                      "brier": result["brier"], "accuracy": result["accuracy"]}))
