"""A confidence interval on the headline, and a significance test on the gap.

The recovery figure -- what share of a coordinate model's discrimination above
chance the words reproduce -- has been reported as a point estimate. It is a
ratio of two AUCs estimated on the same 8,825 shots, so it carries sampling
error, and a reader cannot tell from 90.6% alone whether the true value is
nearer 85% or 95%.

Resampling is over *matches*, not shots. Shots within a match share a fixture,
a pair of teams and a commentator, so resampling shots independently would
understate the variance and narrow the interval spuriously.

Two quantities are reported:

  1. a percentile bootstrap interval on the recovery ratio;
  2. a paired test on the AUC gap itself, which is the quantity a reader
     wanting to know whether coordinates beat words should look at.
"""
import json, os, sys
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss

ROOT = os.path.join(os.path.dirname(__file__), "..")
N_BOOT = 2000


def recovery(y, ours, theirs):
    a, b = roc_auc_score(y, ours), roc_auc_score(y, theirs)
    return (a - 0.5) / (b - 0.5), a, b


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                      "xg_validation.parquet"))
    y = df.sb_goal.values.astype(int)
    ours, theirs = df.our_xg.values, df.sb_xg.values
    match = df.event_id.values

    point, a, b = recovery(y, ours, theirs)
    print(f"shots {len(df):,} in {df.event_id.nunique()} matches")
    print(f"  ours {a:.4f}   StatsBomb {b:.4f}   recovery {point:.4f}\n")

    uniq = np.unique(match)
    index = {g: np.flatnonzero(match == g) for g in uniq}
    rng = np.random.default_rng(0)
    recs, gaps = [], []
    for _ in range(N_BOOT):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([index[g] for g in pick])
        yy = y[rows]
        if yy.min() == yy.max():          # a resample with no goals is useless
            continue
        r, aa, bb = recovery(yy, ours[rows], theirs[rows])
        recs.append(r)
        gaps.append(bb - aa)
    recs, gaps = np.array(recs), np.array(gaps)

    lo, hi = np.percentile(recs, [2.5, 97.5])
    glo, ghi = np.percentile(gaps, [2.5, 97.5])
    out = {
        "n_shots": int(len(df)),
        "n_matches": int(df.event_id.nunique()),
        "n_bootstrap": int(len(recs)),
        "auc_ours": round(float(a), 4),
        "auc_statsbomb": round(float(b), 4),
        "recovery": round(float(point), 4),
        "recovery_ci95": [round(float(lo), 4), round(float(hi), 4)],
        "auc_gap": round(float(b - a), 4),
        "auc_gap_ci95": [round(float(glo), 4), round(float(ghi), 4)],
        "p_gap_favours_statsbomb": round(float((gaps > 0).mean()), 4),
        "logloss_ours": round(float(log_loss(y, np.clip(ours, 1e-6, 1-1e-6))), 4),
        "logloss_statsbomb": round(float(log_loss(y, np.clip(theirs, 1e-6, 1-1e-6))), 4),
        "brier_ours": round(float(brier_score_loss(y, ours)), 4),
        "brier_statsbomb": round(float(brier_score_loss(y, theirs)), 4),
        "resampled_over": "matches",
    }
    print(f"recovery      {point:.3f}   95% CI [{lo:.3f}, {hi:.3f}]")
    print(f"AUC gap       {b-a:.4f}  95% CI [{glo:.4f}, {ghi:.4f}]")
    print(f"share of resamples where StatsBomb is ahead: "
          f"{(gaps > 0).mean():.3f}")
    p = os.path.join(ROOT, "reports", "recovery_ci.json")
    json.dump(out, open(p, "w"), indent=1)
    print(f"\nwrote {os.path.relpath(p, ROOT)}")


if __name__ == "__main__":
    main()
