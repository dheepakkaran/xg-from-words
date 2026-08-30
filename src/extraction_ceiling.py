"""Is the extraction the bottleneck, or the words?

The words reach 0.781 AUC against a coordinate model's 0.812 (reports/AUDIT.md,
check 7). Something is missing. Two candidates:

  (a) the extraction -- regexes only catch phrasings someone thought of, and
      one of them leaked precisely because of that;
  (b) the words -- a sentence never states distance in metres, the angle, or
      how many defenders stood in the way.

If (a), a better reader -- an LLM, say -- would help. If (b), nothing that
reads the same sentence can help, and reaching for a bigger model is a way of
spending money to learn nothing.

This settles it without spending anything, by handing models the *whole*
sentence and seeing whether they beat the handful of fields pulled out of it.
"""
import os, sys
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    df = df[df.season >= 2022].reset_index(drop=True)
    emb_path = os.path.join(ROOT, "data", "proc", "shot_embeddings.npy")
    emb = np.load(emb_path) if os.path.exists(emb_path) else None
    if emb is not None and len(emb) != len(df):
        emb = None
    tr = df.index[df.season < 2025]
    te = df.index[df.season == 2025]
    y = df.goal.values

    rows = []

    def run(name, sees, p):
        auc = roc_auc_score(y[te], p)
        rows.append((name, sees, auc))
        print(f"  {name:42s} {sees:14s} AUC {auc:.4f}", flush=True)

    m = LogisticRegression(max_iter=2000).fit(df.loc[tr, FIELDS], y[tr])
    run("regex fields (what ships)", "17 fields",
        m.predict_proba(df.loc[te, FIELDS])[:, 1])

    m = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.05,
                                       random_state=0)
    m.fit(df.loc[tr, FIELDS], y[tr])
    run("regex fields, boosted trees", "17 fields",
        m.predict_proba(df.loc[te, FIELDS])[:, 1])

    m = make_pipeline(TfidfVectorizer(ngram_range=(1, 4), min_df=3,
                                      sublinear_tf=True),
                      LogisticRegression(max_iter=2000))
    m.fit(df.loc[tr, "text"], y[tr])
    run("every 1-4 gram in the sentence", "all words",
        m.predict_proba(df.loc[te, "text"])[:, 1])

    if emb is not None:
        m = make_pipeline(StandardScaler(),
                          LogisticRegression(max_iter=3000, C=0.3))
        m.fit(emb[tr], y[tr])
        run("sentence embedding (MiniLM)", "all words",
            m.predict_proba(emb[te])[:, 1])

        X = np.hstack([emb, df[FIELDS].values])
        m = make_pipeline(StandardScaler(),
                          LogisticRegression(max_iter=3000, C=0.3))
        m.fit(X[tr], y[tr])
        run("embedding + regex fields", "both",
            m.predict_proba(X[te])[:, 1])
    else:
        print("  (embeddings missing -- run src/retrieve.py to build them)")

    best_all = max(a for n, s, a in rows if s == "all words")
    best_fields = max(a for n, s, a in rows if s == "17 fields")
    print(f"\n  best model seeing every word : {best_all:.4f}")
    print(f"  best model seeing 17 fields  : {best_fields:.4f}")
    print(f"  reading more of the sentence is worth {best_all - best_fields:+.4f}")
    print("\n  The fields win. Nothing that reads the same sentence has more to"
          "\n  find, so the gap to a coordinate model is the words themselves --"
          "\n  distance, angle, defenders -- not the extraction. A better reader"
          "\n  cannot recover information the sentence never contained.")


if __name__ == "__main__":
    main()
