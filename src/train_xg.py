"""Ship the xG model, with the window it was trained on recorded beside it."""
import json, os, subprocess, sys
import pandas as pd
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS, xg_model

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    # 2015-16 is the StatsBomb holdout; the other leagues are the transfer test.
    df = df[(df.league == "eng.1") & (df.season >= 2022)]
    tr, te = df[df.season < 2025], df[df.season == 2025]
    m = xg_model().fit(tr[FIELDS], tr.goal)
    p = m.predict_proba(te[FIELDS])[:, 1]

    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    dump({"model": m, "features": FIELDS},
         os.path.join(ROOT, "models", "xg.joblib"))

    # The same model as plain numbers. A scaler and a logistic regression over
    # seventeen fields is a dot product, so serving it needs no pickle, no
    # sklearn, and no version agreement -- and anyone can read what it believes.
    scaler, lr = m.named_steps["standardscaler"], m.named_steps["logisticregression"]
    json.dump({
        "kind": "standardised logistic regression",
        "features": FIELDS,
        "mean": [round(float(x), 6) for x in scaler.mean_],
        "scale": [round(float(x), 6) for x in scaler.scale_],
        "coef": [round(float(x), 6) for x in lr.coef_[0]],
        "intercept": round(float(lr.intercept_[0]), 6),
    }, open(os.path.join(ROOT, "models", "xg.json"), "w"), indent=1)
    meta = {
        "trained_on": sorted(tr.season.unique().tolist()),
        "n_train": len(tr), "held_out_season": 2025, "n_test": len(te),
        "auc": round(float(roc_auc_score(te.goal, p)), 4),
        "brier": round(float(brier_score_loss(te.goal, p)), 4),
        "base_rate": round(float(te.goal.mean()), 4),
        "features": FIELDS,
        "git_sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                  capture_output=True, text=True
                                  ).stdout.strip() or "unknown",
    }
    json.dump(meta, open(os.path.join(ROOT, "models", "xg.meta.json"), "w"),
              indent=1)
    print("wrote models/xg.joblib, models/xg.json, models/xg.meta.json")
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
