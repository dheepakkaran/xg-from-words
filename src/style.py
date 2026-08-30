"""How a team plays, read off the shots they take.

A fingerprint is the share of a team's shots that come from each situation --
crossed, through-balled, headed, from outside the box. It needs proportions,
not precision, which is why commentary can produce it while it cannot produce a
shot map: to know City cross less than Wolves you have to count crosses, not
measure where the cross came from.

Two uses:

* the season baseline, for describing a team;
* the gap between tonight and that baseline, which is the interesting one --
  a side playing unlike itself is either changing plan or being forced to.
"""
import os
import numpy as np, pandas as pd

DIMENSIONS = ["outside_box", "centre_box", "six_yard", "header", "from_cross",
              "from_through", "after_corner", "after_break"]
MIN_SHOTS = 60          # below this a profile is noise


def fingerprint(shots):
    """Share of these shots showing each trait. NaN if there are too few."""
    if len(shots) < MIN_SHOTS:
        return pd.Series({d: np.nan for d in DIMENSIONS}, dtype=float)
    return pd.Series({d: shots[d].mean() for d in DIMENSIONS})


def baselines(df, season=None):
    """{team: fingerprint} over a season, or over everything given."""
    d = df if season is None else df[df.season == season]
    return {t: fingerprint(g) for t, g in d.groupby("team")}


def deviation(today, baseline):
    """Per-trait difference, and one number for how unlike itself a side is.

    The summary is the mean absolute difference in percentage points, which
    keeps it readable -- "8 points off their usual shape" -- rather than a
    distance nobody can picture.
    """
    if today.isna().any() or baseline.isna().any():
        return None, None
    diff = (today - baseline)
    return diff, float(diff.abs().mean())


def describe(fp, top=3):
    """The traits that most distinguish this side, in plain words."""
    if fp.isna().any():
        return "not enough shots yet"
    words = {"outside_box": "shoots from distance", "centre_box": "gets central",
             "six_yard": "works it very close", "header": "heads it",
             "from_cross": "crosses", "from_through": "plays through balls",
             "after_corner": "scores off corners", "after_break": "counters"}
    order = fp.sort_values(ascending=False)
    return ", ".join(f"{words[k]} {v:.0%}" for k, v in order.head(top).items())


def recent_shape(df, team, n_matches=5):
    """A side's last n matches against their season -- the smallest window
    where a shot profile means anything. One match is far too few."""
    d = df[df.team == team]
    if d.empty:
        return None
    order = d.event_id.dropna().unique().tolist()[-n_matches:]
    recent = d[d.event_id.isin(order)]
    return fingerprint(recent), fingerprint(d), len(recent)


def main():
    root = os.path.join(os.path.dirname(__file__), "..")
    df = pd.read_parquet(os.path.join(root, "data", "proc", "shots.parquet"))
    df = df[df.season == df.season.max()]
    fps = baselines(df)
    fps = {t: f for t, f in fps.items() if not f.isna().any()}
    tbl = pd.DataFrame(fps).T.sort_values("from_cross", ascending=False)
    print(f"{int(df.season.max())}-{int(df.season.max())%100+1} shot profiles, "
          f"share of each team's shots\n")
    print((tbl * 100).round(1).to_string())
    print("\nmost and least like the rest of the league")
    league = tbl.mean()
    odd = (tbl - league).abs().mean(axis=1).sort_values(ascending=False)
    for t in list(odd.index[:3]) + list(odd.index[-2:]):
        print(f"  {t:26s} {odd[t]*100:4.1f} pts off league average -- "
              f"{describe(tbl.loc[t])}")


def team_view(team):
    import sys
    root = os.path.join(os.path.dirname(__file__), "..")
    df = pd.read_parquet(os.path.join(root, "data", "proc", "shots.parquet"))
    df = df[df.season == df.season.max()]
    got = recent_shape(df, team)
    if got is None:
        raise SystemExit(f"no shots for {team!r}")
    recent, season, n = got
    diff, gap = deviation(recent, season)
    print(f"{team} -- last 5 matches ({n} shots) against the season\n")
    if diff is None:
        print("  not enough shots for a profile")
        return
    for k in diff.abs().sort_values(ascending=False).index:
        print(f"  {k:14s} {recent[k]:6.1%} recent   {season[k]:6.1%} season   "
              f"{diff[k]*100:+5.1f} pts")
    print(f"\n  {gap*100:.1f} points off their own season shape")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 2 and sys.argv[1] == "--team":
        team_view(" ".join(sys.argv[2:]))
    else:
        main()
