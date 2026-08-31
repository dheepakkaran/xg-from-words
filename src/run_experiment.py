"""Stages 2-4 - the comparison.

Every model sees the same rows, the same folds and the same metrics. The only
thing that changes between Track A and Track B is how the state at minute M is
represented: counted events versus the raw words.

Two details that the headline numbers depend on:

* Every model is Platt-calibrated on a held-out slice of its own
  training data. The product needs probabilities that mean what they say, and
  an uncalibrated booster loses to the majority class on log loss no matter
  how much ranking signal it has.
* The calibration slice is the most recent 20% of training *matches*, taken by
  date. Splitting by row would put snapshots from one match on both sides.
"""
import argparse, json, os, sys, time
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, os.path.dirname(__file__))
from text_head import MLPHead
from significance import (paired_bootstrap, paired_bootstrap_auc,
                          rowwise_log_loss)
from evaluate import (CLASSES, evaluate, season_folds,
                      calibration_curve_multi)
from sklearn.metrics import roc_auc_score

ROOT = os.path.join(os.path.dirname(__file__), "..")
PROC = os.path.join(ROOT, "data", "proc")
REPORTS = os.path.join(ROOT, "reports")

CONTEXT = ["minute", "score_diff", "goals_home", "goals_away"]
SEP = " ||| "          # must match snapshots.py
CAL_FRAC = 0.20        # share of training matches held out for calibration


class PriorClassifier(ClassifierMixin, BaseEstimator):
    """Predicts the training base rate for every row. The floor."""

    def fit(self, X, y):
        self.classes_ = np.arange(len(CLASSES))
        self.prior_ = np.bincount(y, minlength=len(CLASSES)) / len(y)
        return self

    def predict_proba(self, X):
        return np.tile(self.prior_, (len(X), 1))

    def predict(self, X):
        return np.full(len(X), int(np.argmax(self.prior_)))


def xgb_model():
    from xgboost import XGBClassifier
    return XGBClassifier(
        n_estimators=300, max_depth=3, learning_rate=0.03,
        subsample=0.8, colsample_bytree=0.6, min_child_weight=20,
        reg_lambda=5.0, objective="multi:softprob", num_class=len(CLASSES),
        n_jobs=4, eval_metric="mlogloss", tree_method="hist", random_state=0,
    )


def embed_texts(texts, batch=256):
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return m.encode([t.replace(SEP, " ") for t in texts], batch_size=batch,
                    show_progress_bar=False, convert_to_numpy=True,
                    normalize_embeddings=True)


def last_k(text, k):
    """The stored text holds the last 20 commentary lines; ablations take the
    final k of them."""
    return " ".join(text.split(SEP)[-k:])


def tfidf_pipe():
    return make_pipeline(
        TfidfVectorizer(ngram_range=(1, 2), min_df=5, max_features=60000,
                        sublinear_tf=True),
        LogisticRegression(max_iter=2000, C=0.3))


def dense_pipe(C=1.0):
    return make_pipeline(StandardScaler(),
                         LogisticRegression(max_iter=3000, C=C))


def fit_predict(est, X, y, tr, cal, te):
    """Fit on `tr`, isotonically calibrate on `cal`, predict `te`."""
    Xtr = X.iloc[tr] if hasattr(X, "iloc") else X[tr]
    Xcal = X.iloc[cal] if hasattr(X, "iloc") else X[cal]
    Xte = X.iloc[te] if hasattr(X, "iloc") else X[te]
    est.fit(Xtr, y[tr])
    cc = CalibratedClassifierCV(FrozenEstimator(est), method="sigmoid")
    cc.fit(Xcal, y[cal])
    return cc.predict_proba(Xte)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-embeddings", action="store_true")
    ap.add_argument("--horizon", type=int, default=15,
                    help="label window in minutes; must exist in snapshots")
    ap.add_argument("--only", default="",
                    help="comma-separated name prefixes, to run a subset")
    ap.add_argument("--tag", default="",
                    help="suffix for the output filenames")
    args = ap.parse_args()

    df = pd.read_parquet(os.path.join(PROC, "snapshots.parquet"))
    # Premier League only. snapshots.py already restricts to it, but the
    # experiment states which football it is about rather than inheriting it.
    if "league" in df.columns:
        df = df[df.league == "eng.1"]
    df = df.sort_values(["date", "event_id", "minute"]).reset_index(drop=True)
    label_col = f"label_{args.horizon}"
    if label_col not in df.columns:
        raise SystemExit(f"{label_col} not in snapshots; rebuild with that "
                         f"horizon in snapshots.HORIZONS")
    y = df[label_col].map({c: i for i, c in enumerate(CLASSES)}).values

    elo_feats = ["elo_home", "elo_away", "elo_diff"]
    cum_feats = CONTEXT + [c for c in df.columns if c.startswith("cum_")]
    fut_feats = CONTEXT + [c for c in df.columns if c.startswith("fut_")]
    rec_feats = CONTEXT + [c for c in df.columns if c.startswith("rec_")] + ["n_lines_10min"]
    both_feats = cum_feats + rec_feats[len(CONTEXT):]

    emb = None
    if not args.skip_embeddings:
        cache = os.path.join(PROC, "embeddings.npy")
        if os.path.exists(cache) and len(np.load(cache, mmap_mode="r")) == len(df):
            emb = np.load(cache)
        else:
            t0 = time.time()
            emb = embed_texts(df.text.values)
            np.save(cache, emb)
            print(f"embedded {len(df)} snapshots in {time.time()-t0:.0f}s", flush=True)

    text_k = {k: df.text.map(lambda t: last_k(t, k)) for k in (3, 10, 20)}

    specs = [
        ("0. majority class",              lambda: PriorClassifier(), df[CONTEXT]),
        ("1. clock + scoreline only",      xgb_model, df[CONTEXT]),
        ("A. cumulative counts",           xgb_model, df[cum_feats]),
        ("A-rec. last-10min counts",       xgb_model, df[rec_feats]),
        ("A+rec. cumulative + recent",     xgb_model, df[both_feats]),
        ("E. Elo only",                    xgb_model, df[CONTEXT + elo_feats]),
        ("A+E. counts + Elo",              xgb_model, df[cum_feats + elo_feats]),
        ("B-tfidf. last 3 lines",          tfidf_pipe, text_k[3]),
        ("B-tfidf. last 10 lines",         tfidf_pipe, text_k[10]),
        ("B-tfidf. last 20 lines",         tfidf_pipe, text_k[20]),
    ]
    if emb is not None:
        specs += [
            ("B. last 20 lines, embeddings", lambda: dense_pipe(0.3),
             pd.DataFrame(emb, index=df.index)),
            ("B-mlp. embeddings, PyTorch head", lambda: MLPHead(),
             pd.DataFrame(emb, index=df.index)),
            ("A+B. counts + embeddings", lambda: dense_pipe(0.3),
             pd.concat([df[both_feats].reset_index(drop=True),
                        pd.DataFrame(emb)], axis=1).set_axis(
                 [f"f{i}" for i in range(len(both_feats) + emb.shape[1])], axis=1)),
        ]

    # Deliberately leaky. Not a competitor -- an upper bound. See FINDINGS.md.
    specs.append(("C. CEILING (sees future events)", xgb_model, df[fut_feats]))
    specs.append(("C+. CEILING + counts + Elo", xgb_model,
                  df[fut_feats + [c for c in cum_feats if c not in CONTEXT]
                     + elo_feats]))

    if args.only:
        want = tuple(p.strip() for p in args.only.split(",") if p.strip())
        specs = [s for s in specs if s[0].startswith(want)]

    folds = season_folds(df.season)
    print(f"\nhorizon {args.horizon} min, label column {label_col}")
    print(f"{len(df)} snapshots, {df.event_id.nunique()} matches, {len(folds)} folds")
    print(f"base rates: {df[label_col].value_counts(normalize=True).round(3).to_dict()}\n")

    rows, calib, per_fold_log, final_proba = [], {}, [], {}
    for name, factory, X in specs:
        folds_out = []
        for tr_seasons, te_season in folds:
            tr_all = df.index[df.season.isin(tr_seasons)]
            te = df.index[df.season == te_season]
            # calibration slice: latest 20% of training matches, by date
            m = (df.loc[tr_all, ["event_id", "date"]].drop_duplicates()
                   .sort_values("date"))
            cut = int(len(m) * (1 - CAL_FRAC))
            cal_ids = set(m.event_id.iloc[cut:])
            cal = tr_all[df.loc[tr_all, "event_id"].isin(cal_ids)]
            tr = tr_all[~df.loc[tr_all, "event_id"].isin(cal_ids)]

            p = fit_predict(factory(), X, y, tr, cal, te)
            r = evaluate(y[te], p)
            r.update(model=name, test_season=te_season)
            folds_out.append(r)
            per_fold_log.append(r)
            if te_season == folds[-1][1]:
                calib[name] = calibration_curve_multi(y[te], p, "NONE")
                final_proba[name] = p
        agg = {k: float(np.mean([f[k] for f in folds_out]))
               for k in ("log_loss", "brier", "auc_ovr", "auc_any", "auc_side",
                         "p@10%", "p@5%")}
        agg["name"] = name
        rows.append(agg)
        print(f"{name:32s} logloss {agg['log_loss']:.4f}  brier {agg['brier']:.4f}  "
              f"auc_ovr {agg['auc_ovr']:.4f}  auc_any {agg['auc_any']:.4f}  "
              f"auc_side {agg['auc_side']:.4f}", flush=True)

    # Is any of this distinguishable from the base rate? Paired bootstrap on
    # the most recent season, resampling matches rather than rows.
    te = df.index[df.season == folds[-1][1]]
    groups = df.loc[te, "event_id"].values
    if "0. majority class" not in final_proba:
        raise SystemExit("the majority-class baseline must be in every run")
    base = rowwise_log_loss(y[te], final_proba["0. majority class"])
    sig = []
    for name, p in final_proba.items():
        d, ci, win = paired_bootstrap(groups, rowwise_log_loss(y[te], p), base)
        sig.append({"model": name, "logloss_vs_majority": d,
                    "ci_low": ci[0], "ci_high": ci[1], "p_better": win})
        print(f"{name:32s} {d:+.4f} log loss vs majority "
              f"[{ci[0]:+.4f}, {ci[1]:+.4f}]  better in {win:.0%} of resamples",
              flush=True)

    # The research question itself: words versus numbers, head to head.
    auc_ovr = lambda yy, pp: roc_auc_score(yy, pp, multi_class="ovr",
                                           average="macro",
                                           labels=list(range(len(CLASSES))))
    head_to_head = []
    a_name = "A. cumulative counts"
    for b_name in ([n for n in final_proba if n.startswith("B")]
                   if a_name in final_proba else []):
        d, ci, win = paired_bootstrap_auc(groups, y[te], final_proba[a_name],
                                          final_proba[b_name], auc_ovr)
        head_to_head.append({"numbers": a_name, "words": b_name,
                             "auc_ovr_gap": d, "ci_low": ci[0],
                             "ci_high": ci[1], "p_numbers_win": win})
        print(f"{a_name} vs {b_name:32s} auc_ovr {d:+.4f} "
              f"[{ci[0]:+.4f}, {ci[1]:+.4f}]  numbers win {win:.0%}", flush=True)

    os.makedirs(REPORTS, exist_ok=True)
    tag = args.tag or ("" if args.horizon == 15 else f"_h{args.horizon}")
    out = lambda base, ext: os.path.join(REPORTS, f"{base}{tag}.{ext}")
    pd.DataFrame(head_to_head).to_csv(out("head_to_head", "csv"), index=False)
    pd.DataFrame(sig).to_csv(out("significance", "csv"), index=False)
    res = pd.DataFrame(rows).set_index("name")
    res.to_csv(out("results", "csv"))
    pd.DataFrame(per_fold_log).to_csv(out("results_per_fold", "csv"), index=False)
    json.dump(calib, open(out("calibration", "json"), "w"), indent=1)
    np.savez_compressed(out("final_fold_proba", "npz"),
                        y=y[te], groups=groups,
                        **{n: p for n, p in final_proba.items()})
    print(f"\nwrote reports/results{tag}.csv and friends")


if __name__ == "__main__":
    main()
