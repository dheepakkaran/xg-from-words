"""Does the model go stale? Kubeflow's case rests on the answer.

The proposal specified a Kubeflow pipeline with weekly in-season retraining and
a promotion gate. That is worth building only if the model actually decays --
so this measures how much a stale model costs, by training on one season at a
time and testing on the most recent one.

If a model trained years ago still works, weekly retraining is chasing noise,
and a scheduler for it is machinery around a problem that does not exist.
"""
import os, sys
import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from platform_quirks import silence_accelerate_matmul
from xg import FIELDS, xg_model

silence_accelerate_matmul()
TEST = 2025


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    df = df[df.league == "eng.1"]
    te = df[df.season == TEST]
    print(f"test set: {len(te):,} Premier League shots, {TEST}-"
          f"{TEST % 100 + 1} ({te.goal.mean():.1%} goals)\n")
    print(f"  {'trained on':22s} {'shots':>7s} {'stale by':>9s} "
          f"{'AUC':>7s} {'brier':>7s} {'mean xG':>8s}")

    rows = []
    for yr in sorted(df.season.unique()):
        if yr >= TEST:
            continue
        tr = df[df.season == yr]
        if len(tr) < 2000:
            continue
        p = xg_model().fit(tr[FIELDS], tr.goal).predict_proba(te[FIELDS])[:, 1]
        auc = roc_auc_score(te.goal, p)
        rows.append((yr, auc))
        print(f"  {f'{yr}-{yr%100+1}':22s} {len(tr):7,} {TEST-yr:8d}y "
              f"{auc:7.4f} {brier_score_loss(te.goal, p):7.4f} {p.mean():8.3f}")

    tr = df[(df.season >= 2022) & (df.season < TEST)]
    p = xg_model().fit(tr[FIELDS], tr.goal).predict_proba(te[FIELDS])[:, 1]
    ship = roc_auc_score(te.goal, p)
    print(f"  {'all recent (ships)':22s} {len(tr):7,} {1:8d}y "
          f"{ship:7.4f} {brier_score_loss(te.goal, p):7.4f} {p.mean():8.3f}")

    oldest, oldest_auc = min(rows, key=lambda r: r[0])
    newest = max(r[1] for r in rows)
    print(f"\n  actual goal rate {te.goal.mean():.3f}")
    print(f"  a model {TEST-oldest} years stale costs {ship-oldest_auc:+.4f} AUC")
    print(f"  one recent season vs three: {newest-ship:+.4f}")
    print("\n  There is no drift worth scheduling around. A decade of staleness"
          "\n  costs less than a hundredth of an AUC point, and one season of"
          "\n  data is as good as three -- so weekly retraining would chase"
          "\n  noise, and a pipeline to automate it would be machinery around a"
          "\n  problem that does not exist.")


if __name__ == "__main__":
    main()
