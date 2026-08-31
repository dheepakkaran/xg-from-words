"""The cover image, drawn from the results rather than typed.

Medium shows a cover at wildly different sizes -- full width on a laptop, a
thumbnail in a feed -- so it carries one number and one sentence, and both stay
legible small. Everything on it comes from docs/data.json, the same file the
site reads, so it cannot end up claiming a figure the project no longer has.
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrow, Rectangle

ROOT = os.path.join(os.path.dirname(__file__), "..")
OUT = os.path.join(os.path.dirname(__file__), "cover.png")

# The site's dark palette, unchanged.
SURFACE, INK, MUTED, DIM = "#1a1a19", "#ffffff", "#c3c2b7", "#78776f"
BLUE, ORANGE = "#3987e5", "#d95926"

W, H, DPI = 1500, 750, 150
SENTENCE = ('"right footed shot from the centre of the box,\n'
            ' assisted by Bruno Fernandes with a cross"')

for family in ("Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"):
    if any(family.lower() in f.name.lower()
           for f in matplotlib.font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = family
        break


def width_of(fig, txt):
    """Rendered width of a text object, as a fraction of the figure."""
    fig.canvas.draw()
    bb = txt.get_window_extent(renderer=fig.canvas.get_renderer())
    return bb.width / fig.bbox.width


def main():
    d = json.load(open(os.path.join(ROOT, "docs", "data.json")))
    v = d["validation"]
    pct = v["recovered"] * 100

    fig = plt.figure(figsize=(W / DPI, H / DPI), dpi=DPI, facecolor=SURFACE)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_axis_off()
    ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    t = lambda *a, **k: ax.text(*a, transform=ax.transAxes, **k)

    L = 0.065                      # left column starts here
    R = 0.615                      # right column starts here

    # matplotlib has no letter-spacing, so the eyebrow is spaced by hand
    t(L, 0.905, "\u2009".join("A FOOTBALL DATA EXPERIMENT"),
      color=DIM, fontsize=9, fontweight="bold")

    t(L, 0.83, SENTENCE, color=MUTED, fontsize=12.5, va="top",
      family="monospace", linespacing=1.7)

    # the headline, with the per-cent sign placed against the measured width
    num = t(L, 0.545, f"{pct:.1f}", color=BLUE, fontsize=104,
            fontweight="bold", va="center", ha="left")
    t(L + width_of(fig, num) + 0.008, 0.625, "%", color=BLUE, fontsize=40,
      fontweight="bold", va="center")

    for n, line in enumerate(["of what a camera-based",
                              "expected-goals model can tell",
                              "apart \u2014 from one English sentence."]):
        t(L, 0.305 - n * 0.075, line, color=INK, fontsize=21,
          fontweight="demibold", va="center")

    # the comparison, small, on the right and clear of the headline
    bw = 0.30
    rows = [("From the words", v["ours"], BLUE),
            ("From cameras", v["theirs"], ORANGE)]
    lo, hi = 0.5, 0.85
    for i, (label, val, colour) in enumerate(rows):
        y = 0.505 - i * 0.135
        t(R, y + 0.058, label, color=MUTED, fontsize=12.5)
        ax.add_patch(Rectangle((R, y), bw, 0.036, transform=ax.transAxes,
                               facecolor="#2e2e2b", edgecolor="none", zorder=1))
        ax.add_patch(Rectangle((R, y), bw * (val - lo) / (hi - lo), 0.036,
                               transform=ax.transAxes, facecolor=colour,
                               edgecolor="none", zorder=2))
        t(R + bw + 0.014, y + 0.018, f"{val:.3f}", color=INK, fontsize=13.5,
          fontweight="bold", va="center")
    t(R, 0.265, f"the same {v['shots']:,} shots, scored by both,",
      color=DIM, fontsize=11.5, va="center")
    t(R, 0.215, "measured above a coin toss", color=DIM, fontsize=11.5,
      va="center")

    t(L, 0.048, "xg-from-words", color=DIM, fontsize=11.5, fontweight="bold")
    t(0.935, 0.048, "dheepakkaran.github.io/xg-from-words", color=DIM,
      fontsize=11.5, ha="right")

    fig.savefig(OUT, facecolor=SURFACE, dpi=DPI)
    print(f"wrote {os.path.relpath(OUT, ROOT)}  {W}x{H}")
    print(f"  headline {pct:.1f}%   ours {v['ours']}   theirs {v['theirs']}")


if __name__ == "__main__":
    main()
