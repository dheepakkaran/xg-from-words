"""Figures for the write-up: calibration on the most recent season, and the
head-to-head discrimination gap."""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
REPORTS = os.path.join(ROOT, "reports")

SHOW = ["0. majority class", "A. cumulative counts", "B-tfidf. last 10 lines",
        "B-mlp. embeddings, PyTorch head"]


def calibration():
    calib = json.load(open(os.path.join(REPORTS, "calibration.json")))
    fig, ax = plt.subplots(figsize=(5.5, 5.5))
    ax.plot([0, 1], [0, 1], "k--", lw=1, label="perfect")
    for name in SHOW:
        rows = calib.get(name) or []
        if not rows:
            continue
        ax.plot([r[0] for r in rows], [r[1] for r in rows], "o-", ms=4, label=name)
    ax.set_xlabel("predicted P(no goal in next 15 min)")
    ax.set_ylabel("observed rate")
    ax.set_title("Calibration, 2025-26 held out")
    ax.legend(fontsize=7, loc="upper left")
    lo = min(min(r[0] for r in (calib.get(n) or [(0.5, 0, 0)])) for n in SHOW)
    hi = max(max(r[0] for r in (calib.get(n) or [(0.5, 0, 0)])) for n in SHOW)
    pad = max(0.02, (hi - lo) * 0.6)
    ax.set_xlim(lo - pad, hi + pad); ax.set_ylim(lo - pad, hi + pad)
    ax.annotate("every model sits inside a narrow band around the\n"
                "base rate; the axes span less than 0.1 probability",
                xy=(0.02, 0.02), xycoords="axes fraction", fontsize=7)
    fig.tight_layout()
    fig.savefig(os.path.join(REPORTS, "calibration.png"), dpi=150)


def discrimination():
    d = pd.read_csv(os.path.join(REPORTS, "results_per_fold.csv"))
    p = d.pivot(index="model", columns="test_season", values="auc_ovr")
    p = p.loc[p.mean(1).sort_values().index]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    for c in p.columns:
        ax.plot(p[c].values, range(len(p)), "o", ms=5, label=c)
    ax.axvline(0.5, color="k", ls="--", lw=1)
    ax.set_yticks(range(len(p))); ax.set_yticklabels(p.index, fontsize=8)
    ax.set_xlabel("macro one-vs-rest AUC (0.5 = chance)")
    ax.set_title("Discrimination by fold")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(REPORTS, "discrimination.png"), dpi=150)


def horizons():
    """How the picture changes with the label window, against the ceiling."""
    want = {"0. majority class": "majority class",
            "B-tfidf. last 10 lines": "B: words",
            "A. cumulative counts": "A: numbers",
            "A+E. counts + Elo": "A + team strength",
            "C+. CEILING + counts + Elo": "ceiling (sees the window)"}
    hs, series = [5, 10, 15, 30], {v: [] for v in want.values()}
    for h in hs:
        tag = "" if h == 15 else f"_h{h}"
        d = pd.read_csv(os.path.join(REPORTS, f"results{tag}.csv")).set_index("name")
        for k, v in want.items():
            series[v].append(d.loc[k, "auc_ovr"] if k in d.index else float("nan"))

    fig, ax = plt.subplots(figsize=(6.5, 5.0))
    for label, ys in series.items():
        ls = "--" if "ceiling" in label else "-"
        c = "k" if "ceiling" in label else None
        ax.plot(hs, ys, marker="o", ms=5, ls=ls, color=c, label=label)
    ax.axhline(0.5, color="gray", lw=1, ls=":")
    ax.set_xticks(hs)
    ax.set_xlabel("label horizon (minutes)")
    ax.set_ylabel("macro one-vs-rest AUC")
    ax.set_title("Shortening the horizon does not rescue the words")
    ax.legend(fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.13),
              ncol=3, frameon=False)
    fig.tight_layout()
    fig.savefig(os.path.join(REPORTS, "horizons.png"), dpi=150)


if __name__ == "__main__":
    calibration()
    discrimination()
    horizons()
    print("wrote reports/calibration.png, discrimination.png, horizons.png")
