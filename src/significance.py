"""Is the gap between two models real, or fold noise?

Paired bootstrap over *matches*, not rows. Snapshots from one match are
correlated -- resampling rows would make every difference look significant.
"""
import numpy as np


def paired_bootstrap(groups, loss_a, loss_b, n=2000, seed=0):
    """P(model A has lower mean loss than B), resampling whole matches.

    Returns (mean difference a-b, 95% CI, share of resamples where a < b).
    """
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in uniq}
    diffs = np.empty(n)
    for i in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([index[g] for g in pick])
        diffs[i] = loss_a[rows].mean() - loss_b[rows].mean()
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(diffs.mean()), (float(lo), float(hi)), float((diffs < 0).mean())


def rowwise_log_loss(y_idx, proba, eps=1e-15):
    p = np.clip(proba[np.arange(len(y_idx)), y_idx], eps, 1.0)
    return -np.log(p)


def paired_bootstrap_auc(groups, y_idx, proba_a, proba_b, metric, n=2000, seed=0):
    """Same match-level resampling, but for a ranking metric that cannot be
    written as a per-row loss (AUC). Returns (mean a-b, 95% CI, P(a > b))."""
    rng = np.random.default_rng(seed)
    uniq = np.unique(groups)
    index = {g: np.flatnonzero(groups == g) for g in uniq}
    diffs = []
    for _ in range(n):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        rows = np.concatenate([index[g] for g in pick])
        try:
            diffs.append(metric(y_idx[rows], proba_a[rows])
                         - metric(y_idx[rows], proba_b[rows]))
        except ValueError:
            continue
    diffs = np.asarray(diffs)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return float(diffs.mean()), (float(lo), float(hi)), float((diffs > 0).mean())
