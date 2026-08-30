"""Train the model that ships, on every season, and write it to disk with the
metadata needed to reproduce it.

What ships is Track A + Elo (`A+E`): cumulative event counts plus a team
strength rating read before kickoff. It is the best model in the comparison,
and most of what makes it the best is the Elo -- knowing who is playing beats
everything happening inside the match. See reports/FINDINGS.md, including the
ceiling: no model here, not even one shown the next fifteen minutes, gets past
about 0.60 AUC.
"""
import json, os, subprocess, sys
import numpy as np
import pandas as pd
from joblib import dump
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator

sys.path.insert(0, os.path.dirname(__file__))
from evaluate import CLASSES
from run_experiment import CONTEXT, CAL_FRAC, xgb_model

ROOT = os.path.join(os.path.dirname(__file__), "..")
MODELS = os.path.join(ROOT, "models")


def git_sha():
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                       stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "not-a-git-repo"


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "snapshots.parquet"))
    df = df.sort_values(["date", "event_id", "minute"]).reset_index(drop=True)
    y = df.label.map({c: i for i, c in enumerate(CLASSES)}).values
    feats = (CONTEXT + [c for c in df.columns if c.startswith("cum_")]
             + ["elo_home", "elo_away", "elo_diff"])

    matches = df[["event_id", "date"]].drop_duplicates().sort_values("date")
    cut = int(len(matches) * (1 - CAL_FRAC))
    cal_ids = set(matches.event_id.iloc[cut:])
    cal = df.index[df.event_id.isin(cal_ids)]
    tr = df.index[~df.event_id.isin(cal_ids)]

    est = xgb_model().fit(df.loc[tr, feats], y[tr])
    model = CalibratedClassifierCV(FrozenEstimator(est), method="sigmoid")
    model.fit(df.loc[cal, feats], y[cal])

    os.makedirs(MODELS, exist_ok=True)
    dump({"model": model, "features": feats, "classes": CLASSES,
          "horizon_min": 15},
         os.path.join(MODELS, "track_a.joblib"))
    meta = {
        "features": feats,
        "classes": CLASSES,
        "data_window": [str(df.date.min()), str(df.date.max())],
        "seasons": sorted(df.season.unique().tolist()),
        "n_matches": int(df.event_id.nunique()),
        "n_snapshots_fit": int(len(tr)),
        "n_snapshots_calibration": int(len(cal)),
        "base_rates": df.label.value_counts(normalize=True).round(4).to_dict(),
        "git_sha": git_sha(),
    }
    json.dump(meta, open(os.path.join(MODELS, "track_a.meta.json"), "w"), indent=1)
    print(json.dumps(meta, indent=1))


if __name__ == "__main__":
    main()
