"""Our model against a professional one, match by match, and who was closer.

StatsBomb's xG is the benchmark: a commercial model built on tracking data,
published openly for the 2015-16 Premier League season. Both models are pointed
at the same 373 matches and asked the same question -- how many goals will this
side score? -- and reality answers it.

Scoring is deliberately simple, because a table nobody can read settles
nothing. For each side in each match, whichever model's xG lands closer to the
goals actually scored takes the point; inside 0.05 they split it. Mean absolute
error is reported beside it for anyone who would rather see the statistic than
the scoreboard.

Our model has never seen 2015-16 -- it is fitted on 2022-23 to 2024-25.
StatsBomb's was built with the season's own tracking data in hand.
"""
import json, os, sys
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from platform_quirks import silence_accelerate_matmul

silence_accelerate_matmul()
TIE = 0.05          # goals; inside this the point is shared


def per_side():
    """One row per side per match -- the unit the error is measured on."""
    p = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    g = (p.groupby(["event_id", "date", "home", "away", "team"])
           .agg(our_xg=("our_xg", "sum"), sb_xg=("sb_xg", "sum"),
                goals=("sb_goal", "sum"), shots=("sb_goal", "size"))
           .reset_index())
    g["our_err"] = (g.our_xg - g.goals).abs()
    g["sb_err"] = (g.sb_xg - g.goals).abs()
    g["margin"] = g.sb_err - g.our_err          # positive means we were closer
    g["point"] = g.margin.apply(
        lambda m: 0.5 if abs(m) <= TIE else (1.0 if m > 0 else 0.0))
    g["is_home"] = g.team == g.home
    return g


def per_match(g):
    """One row per match, both sides side by side.

    A table with each fixture twice reads like a mistake even when it is not,
    and the reader has to hold the first row in their head to make sense of the
    second. The unit of measurement is still the side; only the presentation
    changes.
    """
    rows = []
    for eid, m in g.groupby("event_id"):
        h = m[m.is_home]
        a = m[~m.is_home]
        if h.empty or a.empty:
            continue
        h, a = h.iloc[0], a.iloc[0]
        pts = float(h.point + a.point)
        rows.append({
            "event_id": eid, "date": h.date,
            "home": h.home, "away": h.away,
            "score": f"{int(h.goals)}-{int(a.goals)}",
            "our_home": round(float(h.our_xg), 2),
            "our_away": round(float(a.our_xg), 2),
            "sb_home": round(float(h.sb_xg), 2),
            "sb_away": round(float(a.sb_xg), 2),
            "points": pts,                     # out of 2, both sides
            "winner": "ours" if pts > 1 else "StatsBomb" if pts < 1 else "level",
        })
    return pd.DataFrame(rows).sort_values("date")


def main():
    g = per_side()
    matches = per_match(g)
    ours, theirs = g.point.sum(), len(g) - g.point.sum()
    print(f"{g.event_id.nunique()} matches, {len(g)} team-innings, "
          f"2015-16 Premier League\n")
    print(f"  {'':22s} {'mean error':>11s} {'points':>8s}")
    print(f"  {'ours (the words)':22s} {g.our_err.mean():11.3f} {ours:8.1f}")
    print(f"  {'StatsBomb (cameras)':22s} {g.sb_err.mean():11.3f} {theirs:8.1f}")
    print(f"\n  closer more often : "
          f"{'ours' if ours > theirs else 'StatsBomb'} "
          f"({max(ours, theirs)/len(g):.1%} of team-innings)")
    print(f"  our mean error is {g.our_err.mean()-g.sb_err.mean():+.3f} goals "
          f"against theirs")

    print("\n  where each model wins")
    for label, mask in (("we are closer", g.margin > TIE),
                        ("they are closer", g.margin < -TIE),
                        ("level", g.margin.abs() <= TIE)):
        sub = g[mask]
        print(f"    {label:16s} {len(sub):4d}  avg goals {sub.goals.mean():.2f}"
              f"  avg our xG {sub.our_xg.mean():.2f}"
              f"  avg their xG {sub.sb_xg.mean():.2f}")

    print("\n  six matches, one row each")
    print(f"    {'match':38s} {'score':>5s}  {'ours':>11s}  {'StatsBomb':>11s}  won by")
    for _, r in matches.head(6).iterrows():
        print(f"    {r.home[:17]:17s} v {r.away[:17]:17s} {r.score:>5s}  "
              f"{r.our_home:5.2f}-{r.our_away:<5.2f}  "
              f"{r.sb_home:5.2f}-{r.sb_away:<5.2f}  {r.winner}")

    out = {
        "season": "2015-16",
        "matches": int(g.event_id.nunique()),
        "innings": int(len(g)),
        "ours": {"points": round(float(ours), 1),
                 "mean_error": round(float(g.our_err.mean()), 3)},
        "theirs": {"points": round(float(theirs), 1),
                   "mean_error": round(float(g.sb_err.mean()), 3)},
        "split": {"ours_closer": int((g.margin > TIE).sum()),
                  "theirs_closer": int((g.margin < -TIE).sum()),
                  "level": int((g.margin.abs() <= TIE).sum())},
        "matches_won": {
            "ours": int((matches.winner == "ours").sum()),
            "theirs": int((matches.winner == "StatsBomb").sum()),
            "level": int((matches.winner == "level").sum())},
        "examples": [
            {k: (v.item() if hasattr(v, "item") else v)
             for k, v in r.items() if k not in ("event_id", "date")}
            for _, r in matches.head(8).iterrows()],
    }
    path = os.path.join(ROOT, "reports", "head_to_head_xg.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"\n  wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
