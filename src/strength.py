"""Team strength, computed from our own fixture list and nothing else.

Both tracks are blind to who is playing. A model that knew Liverpool were at
home would beat everything in the comparison while saying nothing at all about
momentum -- which is exactly why it is worth adding: it bounds how much of the
remaining headroom is team quality rather than in-match state.

Elo is built chronologically and read *before* each match is played, so a
match never contributes to its own rating. Ratings regress toward the mean
between seasons, because squads change.
"""
import json, os
from collections import defaultdict

INIT = 1500.0
K = 20.0
HOME_ADV = 60.0        # rating points, roughly the league-wide home edge
SEASON_REGRESSION = 0.75   # pull toward INIT at each season boundary


def expected(ra, rb):
    return 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))


def build(fixtures):
    """-> {event_id: (home_elo, away_elo)} as they stood at kickoff."""
    fixtures = sorted(fixtures, key=lambda f: f["date"])
    rating = defaultdict(lambda: INIT)
    out = {}
    season = None
    for f in fixtures:
        if f["season"] != season:
            season = f["season"]
            for t in list(rating):
                rating[t] = INIT + (rating[t] - INIT) * SEASON_REGRESSION
        h, a = f["home"], f["away"]
        rh, ra = rating[h], rating[a]
        out[f["event_id"]] = (rh, ra)          # read before the update

        e = expected(rh + HOME_ADV, ra)
        s = (1.0 if f["home_score"] > f["away_score"]
             else 0.5 if f["home_score"] == f["away_score"] else 0.0)
        rating[h] = rh + K * (s - e)
        rating[a] = ra + K * ((1 - s) - (1 - e))
    return out


def current(fixtures):
    """Ratings after every fixture in the list -- what a live match starts from."""
    fixtures = sorted(fixtures, key=lambda f: f["date"])
    at_kickoff = build(fixtures)
    rating = {}
    for f in fixtures:
        rating[f["home"]], rating[f["away"]] = at_kickoff[f["event_id"]]
    # roll the last match of each team forward one update
    for f in fixtures:
        h, a = f["home"], f["away"]
        rh, ra = at_kickoff[f["event_id"]]
        e = expected(rh + HOME_ADV, ra)
        s = (1.0 if f["home_score"] > f["away_score"]
             else 0.5 if f["home_score"] == f["away_score"] else 0.0)
        rating[h] = rh + K * (s - e)
        rating[a] = ra + K * ((1 - s) - (1 - e))
    return rating


def main():
    root = os.path.join(os.path.dirname(__file__), "..")
    fx = json.load(open(os.path.join(root, "data", "fixtures.json")))
    elo = build(fx)
    last = current(fx)
    print("final Elo, strongest first")
    for t, r in sorted(last.items(), key=lambda kv: -kv[1])[:10]:
        print(f"  {r:7.0f}  {t}")


if __name__ == "__main__":
    main()
