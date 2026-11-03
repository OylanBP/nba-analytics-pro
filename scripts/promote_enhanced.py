"""Promote enhanced Elo model only after genuine chronological out-of-sample gains.

No injury adjustment is trained here. Do not claim otherwise.
"""
import datetime as dt
import json
from pathlib import Path
from enhanced_model import fit, evaluate
from enhanced_features import FEATURES

ROOT = Path(__file__).resolve().parents[1]
HISTORY = ROOT/"data/model/enhanced_history.json"
REPORT = ROOT/"data/model/enhanced_evaluation.json"
CHAMPION = ROOT/"data/model/enhanced_champion.json"

def main():
    rows = json.loads(HISTORY.read_text())
    result = evaluate(rows)
    REPORT.write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n")
    baseline = result["models"]["baseline"]
    enhanced = result["models"]["enhanced"]
    if not result["enhanced_outperformed_baseline"] or enhanced["n"] < 200:
        print("Enhanced model failed rolling gate; production baseline retained", baseline, enhanced)
        return
    # Train on all completed pregame rows only after the separate rolling gate.
    weights = fit(rows, True)
    artifact = {"features": list(FEATURES), "weights": weights,
                "trained_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
                "training_games": len(rows), "rolling_brier": enhanced["brier"],
                "baseline_rolling_brier": baseline["brier"],
                "rolling_log_loss": enhanced["log_loss"],
                "injuries_in_model": False,
                "model_type": "logistic_regression_elo_recent_form"}
    CHAMPION.write_text(json.dumps(artifact, indent=2)+"\n")
    print("Enhanced Elo model promoted", enhanced)

if __name__ == "__main__":
    main()
