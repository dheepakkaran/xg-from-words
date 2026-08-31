"""A cover image for the write-up, generated from the result.

One comparison, stated once: what a sentence of English recovers of what a
stadium full of cameras can see. Drawn from reports/head_to_head_xg.json and
the validation parquet, so it cannot claim a number the project does not hold.

Sized for Medium's cover slot (1400x787, 16:9).
"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from platform_quirks import silence_accelerate_matmul

silence_accelerate_matmul()

# Reference data-viz palette, dark column. Two hues, validated all-pairs.
SURFACE, INK, MUTED = "#1a1a19", "#ffffff", "#9b9a91"
BLUE, ORANGE = "#3987e5", "#d95926"


def main():
    p = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    ours = round(float(roc_auc_score(p.sb_goal, p.our_xg)), 4)
    theirs = round(float(roc_auc_score(p.sb_goal, p.sb_xg)), 4)
    share = (ours - 0.5) / (theirs - 0.5)

    fig = plt.figure(figsize=(14, 7.87), dpi=100, facecolor=SURFACE)
    F = "DejaVu Sans"

    # Left half is type, right half is the chart. Nothing crosses the middle.
    fig.text(0.06, 0.86, "A N   E X P E C T E D - G O A L S   M O D E L\n"
                         "T H A T   R E A D S",
             color=MUTED, fontsize=13, weight="semibold", family=F,
             va="top", linespacing=1.9)
    fig.text(0.055, 0.60, f"{share:.1%}", color=BLUE, fontsize=112,
             weight="bold", va="center", family=F)
    fig.text(0.06, 0.36,
             "of what a camera-based model can tell\n"
             "apart, recovered from one English\n"
             "sentence per shot.",
             color=INK, fontsize=23, va="top", linespacing=1.5, family=F)
    fig.text(0.06, 0.10,
             f"Measured on {len(p):,} shots that both sources describe.",
             color=MUTED, fontsize=15, family=F)

    # The two bars, measured above a coin toss -- the real zero for this score.
    ax = fig.add_axes([0.60, 0.30, 0.33, 0.36])
    ax.set_facecolor(SURFACE)
    rows = [("one English\nsentence", ours, BLUE),
            ("coordinates and 16\nplayer positions", theirs, ORANGE)]
    hi = 0.36
    for i, (label, v, c) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.barh(y, hi, height=0.40, color=INK, alpha=0.07, zorder=1)
        ax.barh(y, v - 0.5, height=0.40, color=c, zorder=2)
        ax.text(v - 0.5 + 0.009, y, f"{v:.3f}", va="center", color=INK,
                fontsize=19, weight="bold", family=F)
        ax.text(-0.014, y, label, va="center", ha="right", color=MUTED,
                fontsize=14, linespacing=1.4, family=F)
    ax.set_xlim(0, hi + 0.055)
    ax.set_ylim(-0.62, len(rows) - 0.38)
    ax.axis("off")
    ax.text(hi / 2, -0.58, "skill above a coin toss", ha="center",
            color=MUTED, fontsize=12.5, family=F)

    out = os.path.join(ROOT, "reports", "cover.png")
    fig.savefig(out, facecolor=SURFACE)
    print(f"wrote {os.path.relpath(out, ROOT)}  —  {share:.1%} "
          f"({ours} vs {theirs}, {len(p):,} shots)")


if __name__ == "__main__":
    main()
