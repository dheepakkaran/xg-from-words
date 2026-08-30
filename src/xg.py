"""Audit prototype - does the text actually rate a chance?

Time-based split, same discipline as the momentum work: train on earlier
seasons, test on the most recent one. Three models:

  fields  - the regex columns only
  text    - tf-idf over the stripped sentence
  RAW     - tf-idf over the unstripped sentence, included only to show how
            large the leak is if the outcome clause is left in
"""
import os, sys
import numpy as np, pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss
from sklearn.pipeline import make_pipeline

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIELDS = ["six_yard", "centre_box", "side_box", "outside_box", "long_range",
          "difficult_ang", "header", "left_foot", "right_foot", "from_cross",
          "from_through", "after_corner", "after_break", "after_setpiece",
          "assisted", "penalty", "minute"]


def report(name, y, p):
    print(f"  {name:34s} AUC {roc_auc_score(y, p):.4f}   "
          f"logloss {log_loss(y, p):.4f}   brier {brier_score_loss(y, p):.4f}")
    return roc_auc_score(y, p)


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    # 2015-16 is collected only to validate against StatsBomb; it is held out
    # of the modelling seasons so this comparison stays reproducible.
    df = df[df.season >= 2022]
    tr, te = df[df.season < 2025], df[df.season == 2025]
    y_tr, y_te = tr.goal.values, te.goal.values
    print(f"train {len(tr):,} shots ({y_tr.mean():.1%} goals)  |  "
          f"test {len(te):,} shots ({y_te.mean():.1%} goals)\n")

    print("held-out season 2025-26")
    report("0. base rate", y_te, np.full(len(te), y_tr.mean()))

    m = LogisticRegression(max_iter=2000, C=1.0).fit(tr[FIELDS], y_tr)
    p_fields = m.predict_proba(te[FIELDS])[:, 1]
    report("1. regex fields", y_te, p_fields)

    tf = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=5,
                                       sublinear_tf=True),
                       LogisticRegression(max_iter=2000, C=1.0))
    tf.fit(tr.text, y_tr)
    report("2. stripped text, tf-idf", y_te, tf.predict_proba(te.text)[:, 1])

    tf2 = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=5,
                                        sublinear_tf=True),
                        LogisticRegression(max_iter=2000, C=1.0))
    tf2.fit(tr.text_raw, y_tr)
    report("3. RAW text (LEAKING, not a result)", y_te,
           tf2.predict_proba(te.text_raw)[:, 1])

    print("\ncalibration of model 1, held-out season")
    q = pd.qcut(p_fields, 8, labels=False, duplicates="drop")
    g = pd.DataFrame({"q": q, "p": p_fields, "y": y_te}).groupby("q").agg(
        predicted=("p", "mean"), actual=("y", "mean"), n=("y", "size"))
    for _, r in g.iterrows():
        print(f"  says {r.predicted:6.1%}   actually {r.actual:6.1%}   "
              f"n={int(r.n):5,}")

    te = te.assign(xg=p_fields)
    per = te.groupby(["event_id", "side"]).agg(xg=("xg", "sum"),
                                               goals=("goal", "sum"))
    print(f"\nper-team-per-match xG vs goals, {len(per):,} team-matches")
    print(f"  correlation      {per.xg.corr(per.goals):.3f}")
    print(f"  mean xG {per.xg.mean():.2f}   mean goals {per.goals.mean():.2f}")


if __name__ == "__main__":
    main()
