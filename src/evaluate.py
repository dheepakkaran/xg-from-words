"""Metrics and splits shared by every track, so the comparison is like-for-like."""
import numpy as np
from sklearn.metrics import log_loss, roc_auc_score

CLASSES = ["AWAY", "HOME", "NONE"]      # fixed order everywhere


def brier(y_true_idx, proba):
    """Multiclass Brier score: mean squared error against the one-hot target."""
    onehot = np.zeros_like(proba)
    onehot[np.arange(len(y_true_idx)), y_true_idx] = 1.0
    return float(np.mean(np.sum((proba - onehot) ** 2, axis=1)))


def precision_at_k(y_true_idx, proba, k_frac=0.10):
    """The product metric: rank snapshots by P(a goal is coming) and ask how
    many of the top k% actually saw one."""
    none_i = CLASSES.index("NONE")
    score = 1.0 - proba[:, none_i]
    k = max(1, int(len(score) * k_frac))
    top = np.argsort(-score)[:k]
    return float(np.mean(y_true_idx[top] != none_i))


def auc_any_goal(y_true_idx, proba):
    """The product question, stripped of which side scores: rank by
    P(a goal is coming) and score that ranking."""
    none_i = CLASSES.index("NONE")
    return float(roc_auc_score((y_true_idx != none_i).astype(int),
                               1.0 - proba[:, none_i]))


def auc_side(y_true_idx, proba):
    """The other half of the question: *given* a goal arrives in the window,
    which side scores it? Computed on goal rows only, so it cannot be inflated
    by knowing whether a goal comes at all."""
    none_i = CLASSES.index("NONE")
    m = y_true_idx != none_i
    if m.sum() < 2 or len(np.unique(y_true_idx[m])) < 2:
        return float("nan")
    home_i, away_i = CLASSES.index("HOME"), CLASSES.index("AWAY")
    return float(roc_auc_score((y_true_idx[m] == home_i).astype(int),
                               proba[m][:, home_i] - proba[m][:, away_i]))


def evaluate(y_idx, proba):
    out = {
        "log_loss": float(log_loss(y_idx, proba, labels=list(range(len(CLASSES))))),
        "brier": brier(y_idx, proba),
        "p@10%": precision_at_k(y_idx, proba, 0.10),
        "p@5%": precision_at_k(y_idx, proba, 0.05),
        "auc_any": auc_any_goal(y_idx, proba),
        "auc_side": auc_side(y_idx, proba),
    }
    try:
        out["auc_ovr"] = float(roc_auc_score(y_idx, proba, multi_class="ovr",
                                             average="macro",
                                             labels=list(range(len(CLASSES)))))
    except ValueError:
        out["auc_ovr"] = float("nan")
    return out


def season_folds(seasons):
    """Expanding-window folds: always train on the past, test on the next
    season. Random splits would put snapshots from the same match on both
    sides of the split."""
    s = sorted(set(seasons))
    return [(s[:i], s[i]) for i in range(1, len(s))]


def calibration_curve_multi(y_idx, proba, cls, bins=10):
    """Reliability of P(cls): (mean predicted, observed rate, count) per bin.

    Bins are quantiles of the predicted probability, not a fixed 0-1 grid.
    These models barely move off the base rate, so a fixed grid puts every
    prediction into two bins and shows nothing.
    """
    i = CLASSES.index(cls)
    p = proba[:, i]
    y = (y_idx == i).astype(float)
    edges = np.unique(np.quantile(p, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:
        return [(float(p.mean()), float(y.mean()), int(len(p)))]
    rows = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & (p < hi if hi < edges[-1] else p <= hi)
        if m.sum() >= 20:
            rows.append((float(p[m].mean()), float(y[m].mean()), int(m.sum())))
    return rows
