"""Recent Premier League matches, scored by our model, marked against reality.

There is no free professional xG for the current season -- FBref returns 403,
Understat no longer inlines its data, and ESPN publish none at all -- so recent
matches cannot be put head to head with a commercial model. What they can be
marked against is the result, which is the harder marker anyway.

For each finished match: our expected goals for both sides, the score, and
whether the side we rated higher actually outscored the other. Matches inside
0.15 expected goals are recorded as too close to call rather than counted as
wrong, because a model that says "nothing between them" has not made a claim.

Runs on requests and the standard library, so the matchday job picks up
whatever has just finished without installing anything. Already-scored matches
are kept, so each run only fetches what is new.
"""
import argparse, datetime as dt, json, os, sys, time
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
import shots as SH
from score import Scorer

CLOSE = 0.15          # expected-goal gap below which no call is made
session = requests.Session()      # no custom User-Agent; see collect.py


def finished_fixtures(league="eng.1", since=None):
    """Completed fixtures from the calendar, newest last."""
    path = os.path.join(ROOT, "docs", "fixtures.json")
    if not os.path.exists(path):
        raise SystemExit("no docs/fixtures.json -- run src/fixtures.py first")
    fx = [f for f in json.load(open(path))["fixtures"] if f.get("completed")]
    if since:
        fx = [f for f in fx if f["kickoff"] >= since]
    return sorted(fx, key=lambda f: f["kickoff"])


def score_match(scorer, fx, league="eng.1"):
    sm = session.get(f"{BASE}/{league}/summary", params={"event": fx["event_id"]},
                     timeout=30).json()
    rows = SH.shots_from_summary(sm, event_id=fx["event_id"])
    if not rows:
        return None
    xg = {"home": 0.0, "away": 0.0}
    for r in rows:
        xg[r["side"]] += scorer(r)
    goals = [int(x) for x in (fx.get("score") or "0-0").split("-")]

    gap = xg["home"] - xg["away"]
    if abs(gap) < CLOSE:
        verdict = "too close to call"
    elif goals[0] == goals[1]:
        verdict = "drawn"
    elif (goals[0] > goals[1]) == (gap > 0):
        verdict = "right"
    else:
        verdict = "wrong"

    return {
        "event_id": fx["event_id"], "kickoff": fx["kickoff"],
        "home": fx["home"], "away": fx["away"],
        "score": fx["score"], "goals": goals,
        "our_home": round(xg["home"], 2), "our_away": round(xg["away"], 2),
        "favoured": None if verdict == "too close to call" else (
            fx["home"] if gap > 0 else fx["away"]),
        "verdict": verdict,
        "shots": len(rows),
    }


def tally(matches):
    counts = {k: sum(1 for m in matches if m["verdict"] == k)
              for k in ("right", "wrong", "drawn", "too close to call")}
    decisive = counts["right"] + counts["wrong"]
    return {"matches": len(matches), **counts, "decisive": decisive,
            "hit_rate": round(counts["right"] / decisive, 3) if decisive else None}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="2025-08-01",
                    help="ISO date; earlier fixtures are ignored")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "scorecard.json"))
    ap.add_argument("--refresh", action="store_true",
                    help="rescore everything instead of only what is new")
    args = ap.parse_args()

    have = {}
    if os.path.exists(args.out) and not args.refresh:
        have = {m["event_id"]: m
                for m in json.load(open(args.out)).get("matches", [])}

    scorer = Scorer()
    fx = finished_fixtures(since=args.since)
    added = 0
    for i, f in enumerate(fx, 1):
        if f["event_id"] in have:
            continue
        try:
            m = score_match(scorer, f)
        except Exception as e:
            print(f"  {f['home']} v {f['away']}: {e}", flush=True)
            continue
        if m:
            have[m["event_id"]] = m
            added += 1
        if added and added % 25 == 0:
            print(f"  scored {added} new matches", flush=True)
        time.sleep(0.25)

    matches = sorted(have.values(), key=lambda m: m["kickoff"])
    payload = {
        "refreshed": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "close_threshold": CLOSE,
        "tally": tally(matches),
        "matches": matches,
    }
    json.dump(payload, open(args.out, "w"), indent=1)

    t = payload["tally"]
    print(f"\n{t['matches']} matches scored ({added} new)")
    print(f"  right {t['right']}   wrong {t['wrong']}   drawn {t['drawn']}   "
          f"too close {t['too close to call']}")
    if t["hit_rate"] is not None:
        print(f"  of the {t['decisive']} it called and that had a winner: "
              f"{t['hit_rate']:.1%} right")
    print(f"\n  latest five")
    for m in matches[-5:]:
        print(f"    {m['home'][:17]:17s} v {m['away'][:17]:17s} {m['score']:>5s}  "
              f"ours {m['our_home']:.2f}-{m['our_away']:.2f}  {m['verdict']}")
    print(f"\n  wrote {os.path.relpath(args.out, ROOT)}")


if __name__ == "__main__":
    main()
