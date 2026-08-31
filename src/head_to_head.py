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


def per_match():
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
    return g


def main():
    g = per_match()
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

    print("\n  five matches, as an example")
    sample = g.sort_values("date").head(10)
    print(f"    {'match':38s} {'goals':>5s} {'ours':>6s} {'theirs':>7s} {'point':>6s}")
    for _, r in sample.iterrows():
        side = "H" if r.team == r.home else "A"
        print(f"    {r.home[:17]:17s} v {r.away[:17]:17s} ({side}) "
              f"{int(r.goals):5d} {r.our_xg:6.2f} {r.sb_xg:7.2f} "
              f"{r.point:6.1f}")

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
        "examples": [
            {"home": r.home, "away": r.away,
             "side": "home" if r.team == r.home else "away",
             "team": r.team, "goals": int(r.goals),
             "ours": round(float(r.our_xg), 2),
             "theirs": round(float(r.sb_xg), 2),
             "point": float(r.point)}
            for _, r in g.sort_values("date").head(12).iterrows()],
    }
    path = os.path.join(ROOT, "reports", "head_to_head_xg.json")
    json.dump(out, open(path, "w"), indent=1)
    print(f"\n  wrote {os.path.relpath(path, ROOT)}")


if __name__ == "__main__":
    main()
