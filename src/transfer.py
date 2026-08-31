"""Does a model trained on English commentary work anywhere else?

The claim this project rests on is that xG becomes available wherever
commentary exists. That has only ever been tested on the Premier League, which
is also where the model was trained -- so it is a claim, not a result.

ESPN publish the same Opta-style English commentary for La Liga, the
Bundesliga, Serie A, Ligue 1 and the Primeira Liga. Nothing is retrained here:
the Premier League model is pointed at each of them, cold.

A drop would mean the phrasing, or the football, differs enough that the model
has to be refitted per competition -- worth knowing. No drop would mean one
model covers every league ESPN describe, which is the useful version of the
claim.
"""
import os, sys
import numpy as np, pandas as pd
from joblib import load
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS, xg_model

NAMES = {"eng.1": "Premier League", "esp.1": "La Liga", "ger.1": "Bundesliga",
         "ita.1": "Serie A", "fra.1": "Ligue 1", "por.1": "Primeira Liga"}


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    if "league" not in df:
        raise SystemExit("no league column -- rerun src/shots.py")

    tr = df[(df.league == "eng.1") & (df.season >= 2022) & (df.season < 2025)]
    m = xg_model().fit(tr[FIELDS], tr.goal)
    print(f"trained on {len(tr):,} Premier League shots, 2022-23 to 2024-25\n")

    print(f"  {'competition':18s} {'shots':>7s} {'goal rate':>10s} "
          f"{'AUC':>7s} {'brier':>7s} {'mean xG':>8s}")
    rows = []
    for lg, g in df[df.season == 2025].groupby("league"):
        if len(g) < 500:
            continue
        p = m.predict_proba(g[FIELDS])[:, 1]
        auc = roc_auc_score(g.goal, p)
        rows.append((lg, len(g), g.goal.mean(), auc,
                     brier_score_loss(g.goal, p), p.mean()))
        print(f"  {NAMES.get(lg, lg):18s} {len(g):7,} {g.goal.mean():9.1%} "
              f"{auc:7.4f} {brier_score_loss(g.goal, p):7.4f} {p.mean():8.3f}")

    home = next((r for r in rows if r[0] == "eng.1"), None)
    away = [r for r in rows if r[0] != "eng.1"]
    if home and away:
        drop = home[3] - np.mean([r[3] for r in away])
        print(f"\n  trained-on league   {home[3]:.4f}")
        print(f"  other leagues, mean {np.mean([r[3] for r in away]):.4f}")
        print(f"  cost of transfer    {drop:+.4f}")
        bias = np.mean([r[5] - r[2] for r in away])
        print(f"  mean calibration bias abroad {bias:+.3f} "
              f"(predicted minus actual)")

    print("\n  refitting per competition, for comparison")
    for lg, g in df[df.season == 2025].groupby("league"):
        if len(g) < 500 or lg == "eng.1":
            continue
        own = df[(df.league == lg) & (df.season < 2025)]
        if len(own) < 2000:
            print(f"  {NAMES.get(lg, lg):18s} not enough history to refit")
            continue
        m2 = xg_model().fit(own[FIELDS], own.goal)
        print(f"  {NAMES.get(lg, lg):18s} own model "
              f"{roc_auc_score(g.goal, m2.predict_proba(g[FIELDS])[:, 1]):.4f}")


if __name__ == "__main__":
    main()
