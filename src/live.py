"""Deliverable 1 - the live worklist.

Five matches kick off at once and you have one screen. This ranks the
in-progress fixtures by the model's probability that someone scores in the
next 15 minutes, and prints the recent commentary that drove the number so
the ranking can be argued with.

It also measures commentary latency -- the gap between the wallclock stamp on
the newest commentary line and now -- because that was an open question in the
proposal and it can only be answered while a match is actually running.
"""
import argparse, datetime as dt, json, os, sys, time
import pandas as pd
import requests
from joblib import load

sys.path.insert(0, os.path.dirname(__file__))
import snapshots as S
import strength

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1"
ROOT = os.path.join(os.path.dirname(__file__), "..")
LIVE_STATUSES = {"STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_IN_PROGRESS",
                 "STATUS_HALFTIME", "STATUS_END_PERIOD"}

session = requests.Session()   # no custom User-Agent; see collect.py


def scoreboard(date=None):
    p = {"dates": date} if date else {}
    return session.get(f"{BASE}/scoreboard", params=p, timeout=30).json()


def summary(event_id):
    return session.get(f"{BASE}/summary", params={"event": event_id},
                       timeout=30).json()


def latency_seconds(sm):
    """Age of the newest commentary line, in seconds. None if unstamped."""
    stamps = [(e.get("play") or {}).get("wallclock")
              for e in sm.get("commentary", [])]
    stamps = [s for s in stamps if s]
    if not stamps:
        return None
    newest = max(stamps)
    t = dt.datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc)
    return (dt.datetime.now(dt.timezone.utc) - t).total_seconds()


def elo_table():
    """Current ratings, from the collected fixture history."""
    path = os.path.join(ROOT, "data", "fixtures.json")
    if not os.path.exists(path):
        return {}
    return strength.current(json.load(open(path)))


def score_match(bundle, ev, elo=None):
    comp = ev["competitions"][0]
    teams = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
    home, away = teams["home"], teams["away"]
    sm = summary(ev["id"])
    lines = S.timeline(sm, home, away)
    if not lines:
        return None
    goals = S.goals_of(sm, home, away)
    M = max(l[0] for l in lines)
    row = S.features_at(lines, goals, M)
    if row is None:
        return None
    elo = elo or {}
    eh = elo.get(home, strength.INIT)
    ea = elo.get(away, strength.INIT)
    row.update(elo_home=eh, elo_away=ea, elo_diff=eh - ea)
    X = pd.DataFrame([row])[bundle["features"]]
    p = bundle["model"].predict_proba(X)[0]
    cls = bundle["classes"]
    return {
        "match": f"{home} v {away}",
        "score": f"{row['goals_home']}-{row['goals_away']}",
        "minute": int(M),
        "p_goal": float(1 - p[cls.index("NONE")]),
        "p_home": float(p[cls.index("HOME")]),
        "p_away": float(p[cls.index("AWAY")]),
        "latency_s": latency_seconds(sm),
        "recent": [t for _, _, _, t in lines[-3:]],
    }


def once(bundle, date=None, include_finished=False, elo=None):
    sb = scoreboard(date)
    evs = [e for e in sb.get("events", [])
           if include_finished or e["status"]["type"]["name"] in LIVE_STATUSES]
    if not evs:
        n = len(sb.get("events", []))
        print(f"no in-progress Premier League matches right now "
              f"({n} fixture(s) listed for this date)")
        return []
    out = [r for r in (score_match(bundle, e, elo) for e in evs) if r]
    out.sort(key=lambda r: -r["p_goal"])
    print(f"\n{dt.datetime.now():%H:%M:%S}  goal in next 15 min")
    for i, r in enumerate(out, 1):
        lat = f"{r['latency_s']:.0f}s" if r["latency_s"] is not None else "n/a"
        print(f"{i}. {r['p_goal']:5.1%}  {r['match']:42s} {r['score']}  "
              f"{r['minute']:>2}'  (home {r['p_home']:.0%} / away {r['p_away']:.0%})"
              f"  commentary lag {lat}")
        print(f"      {r['recent'][-1][:110]}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--interval", type=int, default=0,
                    help="seconds between polls; 0 runs once")
    ap.add_argument("--date", help="YYYYMMDD, for replaying a past matchday")
    ap.add_argument("--include-finished", action="store_true",
                    help="score completed fixtures too, for a dry run")
    args = ap.parse_args()

    bundle = load(os.path.join(ROOT, "models", "track_a.joblib"))
    elo = elo_table()
    while True:
        once(bundle, args.date, args.include_finished, elo)
        if not args.interval:
            return
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
