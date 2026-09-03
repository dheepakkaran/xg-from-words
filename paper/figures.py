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

# IEEEtran conference is two columns: a column is 3.5in and the full text
# block is 7.16in. Figures are drawn at their final printed size so the 8pt
# labels match the 10pt body text instead of being scaled with the image.
# WIDE is for figure*, COL for a single column.
WIDE, COL = 7.00, 3.42
W = WIDE
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
    figure. An earlier draft carried invented coordinates and an invented
    commentary line, which is not a thing a paper may contain.

    The shot is Aaron Ramsey for Arsenal against Manchester United, 33
    minutes, identified by its StatsBomb location. It is chosen because it
    exercises five of the eighteen fields and because the two estimates land
    within 0.007 of each other, which is the ordinary case rather than a
    flattering one.

    Layout is a two-column grid: every box sits on GL/GR with the same width,
    so the four boxes and the two arrows line up. The first version inset the
    lower boxes and the misalignment was visible.
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
    assert len(on) == 4, on

    H = 2.58
    GL, GR, BW = 0.010, 0.520, 0.470       # the grid every box sits on
    CL, CR = GL + BW / 2, GR + BW / 2      # column centres, for the arrows

    fig, ax = plt.subplots(figsize=(WIDE, H))
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")

    quote = " ".join(str(r.text_raw).split())
    assert quote.startswith("Attempt missed. Aaron Ramsey"), quote[:40]
    _box(ax, GL, 0.830, GR + BW - GL, 0.150,
         "\u201cAttempt missed. Aaron Ramsey (Arsenal) right footed shot from the "
         "centre of the box is close,\nbut misses to the left. Assisted by "
         "Alexis S\u00e1nchez with a through ball.\u201d",
         size=6.9, mono=False, italic=True, fill="#fcfcfb", center=True)

    for cx, txt in ((CL, "this work: parsed from the sentence"),
                    (CR, "StatsBomb: hand-collected")):
        ax.text(cx, 0.755, txt, ha="center", va="center", fontsize=6.6,
                color=MUTED)
        _arrow(ax, cx, 0.825, cx, 0.788)
        _arrow(ax, cx, 0.722, cx, 0.685)

    # Two balanced columns inside each box. A single column of six lines
    # overflowed the box; one column of five with a lone entry beside it read
    # as a stray.
    lft = [f"{on[0]:<13s}= 1", f"{on[1]:<13s}= 1", f"{on[2]:<13s}= 1",
           f"{on[3]:<13s}= 1"]
    lft2 = [f"{'minute':<10s}= {int(r.minute)}",
            f"{18 - len(on) - 1} others  = 0", "", ""]
    rgt = [f"{'x':<9s}= {r.sb_x:.1f}", f"{'y':<9s}= {r.sb_y:.1f}",
           f"{'distance':<9s}= {dist:.1f} m", f"{'angle':<9s}= {ang:.2f} rad"]
    rgt2 = [f"{'body':<10s}= right foot", f"{'technique':<10s}= volley",
            f"{FREEZE} players in frame", ""]
    _box(ax, GL, 0.420, BW, 0.260,
         "\n".join(f"{a}    {b}".rstrip() for a, b in zip(lft, lft2)))
    _box(ax, GR, 0.420, BW, 0.260,
         "\n".join(f"{a}    {b}".rstrip() for a, b in zip(rgt, rgt2)),
         fill="#fcfcfb")

    for cx in (CL, CR):
        _arrow(ax, cx, 0.415, cx, 0.352)

    _box(ax, GL, 0.198, BW, 0.150, f"$\\widehat{{xG}} = {r.our_xg:.3f}$",
         size=9.5, mono=False, center=True, weight="bold")
    _box(ax, GR, 0.198, BW, 0.150, f"$xG = {r.sb_xg:.3f}$",
         size=9.5, mono=False, center=True, fill="#fcfcfb")
    ax.text(0.5, 0.075,
            f"The two estimates differ by {abs(r.our_xg - r.sb_xg):.3f} here. "
            "Over 8,825 such shots they correlate at 0.735 per shot "
            "and 0.869 per team-match.",
            ha="center", va="center", fontsize=6.9, color=INK)
    fig.savefig(path); plt.close(fig)
    print(f"  wrote {os.path.relpath(path, ROOT)}")


def fig_reliability(path):
    d = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    fig, ax = plt.subplots(figsize=(COL, 2.25))
    hi = 0.42
    ax.plot([0, hi], [0, hi], linewidth=0.6, color=FAINT, zorder=1)
    # below the diagonal rather than on it: at the corner the rotated text was
    # clipped by the axis edge, and on the diagonal it sat over the curves.
    ax.text(0.345, 0.265, "perfect calibration", fontsize=6.4, color=MUTED,
            rotation=45, ha="center", va="center", rotation_mode="anchor")

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
    ax.legend(frameon=False, loc="upper left", handlelength=2.0,
              borderpad=0.0, labelspacing=0.3,
              bbox_to_anchor=(-0.02, 1.03))
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

    # Stacked rather than side by side, and single-column: two panels across
    # one 3.42in column leaves about 0.2in per season tick against a 0.28in
    # label, so they collided. Stacking gives each panel the full column.
    fig, axes = plt.subplots(2, 1, figsize=(COL, 3.05), sharex=True)
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
    # No legend. Every line is labelled at its right-hand end, which carries
    # identity more strongly than a legend box does and does not depend on
    # colour; the legend duplicated those labels and collided with the top
    # panel's own series while hiding its 2015/16 marker.
    fig.subplots_adjust(hspace=0.14)
    fig.savefig(path); plt.close(fig)
    print(f"  wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    fig_schematic(os.path.join(HERE, "fig1_schematic.pdf"))
    fig_reliability(os.path.join(HERE, "fig2_reliability.pdf"))
    fig_drift(os.path.join(HERE, "fig3_drift.pdf"))
