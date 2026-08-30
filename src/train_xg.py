"""Ship the xG model, with the window it was trained on recorded beside it."""
import json, os, subprocess, sys
import pandas as pd
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS

ROOT = os.path.join(os.path.dirname(__file__), "..")


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    df = df[df.season >= 2022]          # 2015-16 is the StatsBomb holdout
    tr, te = df[df.season < 2025], df[df.season == 2025]
    m = LogisticRegression(max_iter=2000).fit(tr[FIELDS], tr.goal)
    p = m.predict_proba(te[FIELDS])[:, 1]

    os.makedirs(os.path.join(ROOT, "models"), exist_ok=True)
    dump({"model": m, "features": FIELDS},
         os.path.join(ROOT, "models", "xg.joblib"))
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
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
