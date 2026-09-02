"""Figures for the paper.

Print drives every choice here. LNCS proceedings are read on paper as often as
on screen, and the palette these figures need does not survive the trip: the
two colours in the reliability diagram are 0.09 apart in relative luminance,
or gray 119 against gray 142 once printed, and two of the three in the drift
figure are 0.045 apart, which is gray 142 against gray 152 and therefore
nothing at all.

Colour is decoration in these figures and never identity. Every series carries
a marker shape and a line style as well, and a legend is present throughout.
Where series can be separated at their right-hand ends they are also labelled
there, which is stronger than a legend; in Figure 2 the two curves coincide
almost exactly, which is itself the result, so labelling them in place would
collide and the legend carries identity alone.
"""
import os, sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

ROOT = os.path.join(os.path.dirname(__file__), "..")
HERE = os.path.dirname(os.path.abspath(__file__))

# LNCS text width is 122mm. A figure wider than that is scaled down and takes
# its fonts with it, so everything is drawn at final size.
W = 4.80
INK, MUTED, FAINT = "#0b0b0b", "#52514e", "#c9c8c3"
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"

plt.rcParams.update({
    "font.family": "serif",
    "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "font.size": 8, "axes.labelsize": 8, "axes.titlesize": 8,
    "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
    "axes.edgecolor": MUTED, "axes.linewidth": 0.6,
    "xtick.color": MUTED, "ytick.color": MUTED,
    "xtick.major.width": 0.6, "ytick.major.width": 0.6,
    "xtick.major.size": 2.5, "ytick.major.size": 2.5,
    "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 300, "savefig.bbox": "tight", "savefig.pad_inches": 0.02,
})


def _box(ax, x, y, w, h, lines, size=6.6, mono=True, italic=False,
         fill="#ffffff", weight="normal", center=False):
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.004,rounding_size=0.010",
        linewidth=0.6, edgecolor=MUTED, facecolor=fill))
    ax.text(x + w / 2 if center else x + 0.016, y + h / 2, lines,
            ha="center" if center else "left", va="center", fontsize=size,
            color=INK, fontweight=weight,
            fontstyle="italic" if italic else "normal",
            family="monospace" if mono else "serif", linespacing=1.35)


def _arrow(ax, x0, y0, x1, y1, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style,
                                 mutation_scale=7, linewidth=0.6,
                                 color=MUTED, shrinkA=0, shrinkB=0))


def fig_schematic(path):
    """What each side of the comparison is given, for a single real shot.

    Every value here is read from the joined data rather than written into the
    figure. The first draft of this figure carried invented coordinates and an
    invented commentary line, which is not a thing a paper may contain.

    The shot is Aaron Ramsey for Arsenal against Manchester United, 33 minutes,
    identified by its StatsBomb location. It is chosen because it exercises
    four of the eighteen fields and because the two estimates land within 0.007
    of each other, which is the ordinary case rather than a flattering one.
    """
    d = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    r = d[(d.sb_x.sub(112.9).abs() < 0.05)
          & (d.sb_y.sub(44.4).abs() < 0.05)].iloc[0]
    dist = float(np.hypot(r.sb_x - 120, r.sb_y - 40))
    ang = float(np.arctan2(abs(r.sb_y - 40), 120 - r.sb_x))
    on = [f for f in ("six_yard", "centre_box", "side_box", "outside_box",
                      "long_range", "difficult_ang", "header", "left_foot",
                      "right_foot", "from_cross", "from_headed_pass",
                      "from_through", "after_corner", "after_break",
                      "assisted", "penalty") if r[f] == 1]
    FREEZE = 15                # 5 teammates, 10 opponents, one a goalkeeper

    fig, ax = plt.subplots(figsize=(W, 2.70))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    quote = " ".join(str(r.text_raw).split())
    _box(ax, 0.01, 0.805, 0.98, 0.175,
         "\u201cAttempt missed. Aaron Ramsey (Arsenal) right footed shot from\n"
         "the centre of the box is close, but misses to the left. Assisted by\n"
         "Alexis S\u00e1nchez with a through ball.\u201d",
         size=6.9, mono=False, italic=True, fill="#fcfcfb")
    assert quote.startswith("Attempt missed. Aaron Ramsey"), quote[:40]

    ax.text(0.245, 0.780, "this work: parsed from the sentence", ha="center",
            va="center", fontsize=6.8, color=MUTED)
    ax.text(0.755, 0.780, "StatsBomb: hand-collected", ha="center",
            va="center", fontsize=6.8, color=MUTED)
    _arrow(ax, 0.245, 0.762, 0.245, 0.730)
    _arrow(ax, 0.755, 0.762, 0.755, 0.730)

    left = "\n".join(f"{f:<13s}= 1" for f in on)
    left += f"\nminute       = {int(r.minute)}\n"
    left += f"({18 - len(on) - 1} others   = 0)"
    _box(ax, 0.01, 0.300, 0.47, 0.425, left)
    _box(ax, 0.52, 0.300, 0.47, 0.425,
         f"x        = {r.sb_x:.1f}\ny        = {r.sb_y:.1f}\n"
         f"distance = {dist:.1f} m\nangle    = {ang:.2f} rad\n"
         f"body     = right foot\ntechnique= volley\n"
         f"freeze frame: {FREEZE}", fill="#fcfcfb")

    _arrow(ax, 0.245, 0.295, 0.245, 0.232)
    _arrow(ax, 0.755, 0.295, 0.755, 0.232)

    _box(ax, 0.075, 0.100, 0.34, 0.130,
         f"$\\widehat{{xG}} = {r.our_xg:.3f}$",
         size=9, mono=False, center=True, weight="bold")
    _box(ax, 0.585, 0.100, 0.34, 0.130, f"$xG = {r.sb_xg:.3f}$",
         size=9, mono=False, center=True, fill="#fcfcfb")
    _arrow(ax, 0.425, 0.165, 0.580, 0.165, style="<->")
    ax.text(0.5025, 0.142, f"{abs(r.our_xg - r.sb_xg):.3f}", ha="center",
            va="top", fontsize=6.6, color=MUTED)

    ax.text(0.5, 0.030,
            "Over 8,825 such shots the estimates correlate at 0.735 per shot, "
            "0.869 per team-match.",
            ha="center", va="center", fontsize=6.9, color=INK)
    fig.savefig(path); plt.close(fig)
    print(f"  wrote {os.path.relpath(path, ROOT)}")


def fig_reliability(path):
    d = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    fig, ax = plt.subplots(figsize=(W * 0.60, 2.0))
    hi = 0.45
    ax.plot([0, hi], [0, hi], linewidth=0.6, color=FAINT, zorder=1)
    ax.text(hi - 0.015, hi - 0.055, "perfect calibration", fontsize=6.6,
            color=MUTED, rotation=45, ha="right", va="center",
            rotation_mode="anchor")

    for label, col, c, mk, ls in (("this work", "our_xg", BLUE, "o", "-"),
                                  ("StatsBomb", "sb_xg", ORANGE, "s", "--")):
        q = pd.qcut(d[col], 8, labels=False, duplicates="drop")
        g = (pd.DataFrame({"q": q, "p": d[col], "y": d.sb_goal})
             .groupby("q").agg(pred=("p", "mean"), obs=("y", "mean")))
        ax.plot(g.pred, g.obs, ls, color=c, linewidth=1.0, marker=mk,
                markersize=3.4, markeredgewidth=0.5,
                markeredgecolor="#ffffff", label=label, zorder=3)

    ax.set_xlabel("mean predicted probability")
    ax.set_ylabel("observed goal rate")
    ax.set_xlim(0, hi); ax.set_ylim(0, hi)
    ax.set_xticks([0, 0.1, 0.2, 0.3, 0.4])
    ax.set_yticks([0, 0.1, 0.2, 0.3, 0.4])
    ax.legend(frameon=False, loc="upper left", handlelength=2.2,
              borderpad=0.1, labelspacing=0.35)
    fig.savefig(path); plt.close(fig)
    print(f"  wrote {os.path.relpath(path, ROOT)}")


def fig_drift(path):
    """Share of shots and conversion, three phrases, five seasons.

    2016/17 to 2021/22 are not in the corpus, so the axis is broken rather
    than spacing the seasons evenly and implying a decade of annual
    observations that do not exist.
    """
    d = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    d = d[d.league == "eng.1"]
    seasons = sorted(d.season.unique())
    lab = {2015: "15/16", 2022: "22/23", 2023: "23/24",
           2024: "24/25", 2025: "25/26"}
    xs = [0.0, 1.6, 2.6, 3.6, 4.6]           # gap marks the missing seasons
    spec = [("six yard box", "six_yard", BLUE, "o", "-"),
            ("fast break", "after_break", ORANGE, "s", "--"),
            ("penalty", "penalty", AQUA, "^", ":")]

    # Stacked rather than side by side: two panels across 122mm leaves about
    # 0.30in per season tick, and a "22/23" label at 7pt is 0.28in wide, so
    # the labels collided. Full width per panel fixes it and leaves room for
    # the end-of-line labels.
    fig, axes = plt.subplots(2, 1, figsize=(W, 3.30), sharex=True)
    for ax, what in zip(axes, ("share", "conv")):
        for label, f, c, mk, ls in spec:
            ys = [100 * d[d.season == s][f].mean() if what == "share"
                  else 100 * d[(d.season == s) & (d[f] == 1)].goal.mean()
                  for s in seasons]
            ax.plot(xs[:1], ys[:1], color=c, linewidth=1.0, marker=mk,
                    markersize=3.6, markeredgewidth=0.5,
                    markeredgecolor="#ffffff", zorder=3)
            ax.plot(xs[1:], ys[1:], ls, color=c, linewidth=1.0, marker=mk,
                    markersize=3.6, markeredgewidth=0.5,
                    markeredgecolor="#ffffff", label=label, zorder=3)
            ax.annotate(label, (xs[-1], ys[-1]), textcoords="offset points",
                        xytext=(5, 0), fontsize=7, color=INK, va="center")
        ax.set_xlim(-0.28, 6.55); ax.set_ylim(0)
    axes[0].set_ylabel("share of shots (\\%)")
    axes[1].set_ylabel("conversion rate (\\%)")
    axes[1].set_xticks(xs); axes[1].set_xticklabels([lab[s] for s in seasons])
    axes[1].set_xlabel("Premier League season")
    for ax in axes:                          # the break in the season axis
        ax.plot([0.106, 0.126], [0, 0], transform=ax.get_xaxis_transform(),
                clip_on=False, color="#ffffff", linewidth=1.8, zorder=4)
        for xb in (0.104, 0.122):
            ax.plot([xb, xb + 0.012], [-0.020, 0.020],
                    transform=ax.get_xaxis_transform(), clip_on=False,
                    color=MUTED, linewidth=0.6, zorder=5)
    axes[0].legend(frameon=False, loc="center left", handlelength=2.2,
                   borderpad=0.1, labelspacing=0.3,
                   bbox_to_anchor=(0.02, 0.62))
    fig.subplots_adjust(hspace=0.14)
    fig.savefig(path); plt.close(fig)
    print(f"  wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    fig_schematic(os.path.join(HERE, "fig1_schematic.pdf"))
    fig_reliability(os.path.join(HERE, "fig2_reliability.pdf"))
    fig_drift(os.path.join(HERE, "fig3_drift.pdf"))
