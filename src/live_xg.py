"""Deliverable — what the words can actually tell you during a match.

The momentum work established what this must *not* claim: which match will
produce the next goal is not predictable (FINDINGS §3.6, 0.52 AUC). So this
does not forecast. It measures what has already happened, which the scoreboard
gets wrong all the time:

    Arsenal 1   chances worth 0.4
    Liverpool 0 chances worth 2.1

Same match, opposite readings. Three things are reported, all descriptive:

  chance quality  who has actually created something
  finishing form  goals minus chances -- who is converting, who is wasting
  best chance     the single moment that was worth the most

Ranking across matches is by chance quality in the last twenty minutes: where
the football is happening, not where a goal is coming.

Deliberately absent: how tonight compares with a side's usual shape. One match
is ten to seventeen shots, and a shot profile built on that is noise. That
comparison needs a run of matches, so it lives in `style.py --team` instead.
"""
import argparse, os, sys
import numpy as np, pandas as pd
import requests
from joblib import load

sys.path.insert(0, os.path.dirname(__file__))
import shots as SH

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1"
ROOT = os.path.join(os.path.dirname(__file__), "..")
LIVE = {"STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_IN_PROGRESS",
        "STATUS_HALFTIME", "STATUS_END_PERIOD"}
RECENT = 20        # minutes, for the "where is the action" ranking

session = requests.Session()      # no custom User-Agent; see collect.py


def model():
    path = os.path.join(ROOT, "models", "xg.joblib")
    if os.path.exists(path):
        return load(path)
    raise SystemExit("no models/xg.joblib -- run src/train_xg.py first")


def read_match(bundle, ev):
    sm = session.get(f"{BASE}/summary", params={"event": ev["id"]},
                     timeout=30).json()
    rows = SH.shots_from_summary(sm, event_id=ev["id"])
    if not rows:
        return None
    df = pd.DataFrame(rows)
    df["xg"] = bundle["model"].predict_proba(df[bundle["features"]])[:, 1]

    comp = ev["competitions"][0]
    teams = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
    score = {c["homeAway"]: int(c.get("score", 0)) for c in comp["competitors"]}
    clock = ev["status"].get("displayClock", "")
    minute = float(ev["status"].get("clock", 0) or 0) / 60.0

    out = {"match": f"{teams['home']} v {teams['away']}", "clock": clock,
           "score": f"{score['home']}-{score['away']}", "sides": []}
    for ha in ("home", "away"):
        t = teams[ha]
        s = df[df.team == t]
        recent = s[s.minute > minute - RECENT]
        out["sides"].append({
            "team": t, "goals": score[ha], "xg": float(s.xg.sum()),
            "recent_xg": float(recent.xg.sum()), "shots": len(s),
            "best": (_tidy(s.loc[s.xg.idxmax(), "text"]) if len(s) else ""),
            "best_xg": float(s.xg.max()) if len(s) else 0.0})
    out["recent_total"] = sum(x["recent_xg"] for x in out["sides"])
    return out


def _tidy(text):
    """The whitelist can leave a dangling "assisted by" when the assister's
    name did not match a known pattern. Drop it rather than print it."""
    t = " ".join(text.split())
    for tail in (" assisted by", "assisted by"):
        if t.endswith(tail):
            t = t[:-len(tail)].strip()
    return t or "shot"


def render(reports):
    if not reports:
        print("no matches in progress")
        return
    for r in sorted(reports, key=lambda x: -x["recent_total"]):
        print(f"\n{r['match']}   {r['score']}   {r['clock']}")
        for s in r["sides"]:
            form = s["goals"] - s["xg"]
            verdict = ("finishing well" if form > 0.7 else
                       "wasteful" if form < -0.7 else "about par")
            print(f"  {s['team']:26s} {s['goals']} goals   "
                  f"chances worth {s['xg']:.2f}   ({s['shots']} shots)")
            print(f"  {'':26s} {form:+.2f} vs expected -- {verdict}")
            if s["best"]:
                print(f"  {'':26s} best: {s['best_xg']:.0%}  \"{s['best']}\"")


def replay(bundle, event_id, step=15):
    """Step through a finished match the way the live view would see it.

    Nothing here is hindsight: at each checkpoint only the commentary up to
    that minute is used, which is exactly what would have been on the wire.
    """
    sm = session.get(f"{BASE}/summary", params={"event": event_id},
                     timeout=30).json()
    rows = SH.shots_from_summary(sm, event_id=event_id)
    if not rows:
        raise SystemExit("no shots parsed for that match")
    df = pd.DataFrame(rows)
    df["xg"] = bundle["model"].predict_proba(df[bundle["features"]])[:, 1]

    comp = sm["header"]["competitions"][0]
    teams = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
    h, a = teams["home"], teams["away"]
    print(f"{h} v {a}\n")
    print(f"  {'min':>4s}  {'score':^7s}  "
          f"{h[:16]:>16s}  {a[:16]:>16s}   what changed")
    prev = None
    for M in range(step, 96, step):
        seen = df[df.minute <= M]
        gh = int(seen[(seen.side == "home") & (seen.goal == 1)].shape[0])
        ga = int(seen[(seen.side == "away") & (seen.goal == 1)].shape[0])
        xh = seen[seen.side == "home"].xg.sum()
        xa = seen[seen.side == "away"].xg.sum()
        window = df[(df.minute > M - step) & (df.minute <= M)]
        best = (window.loc[window.xg.idxmax()] if len(window) else None)
        note = (f"{best.team[:14]} {best.xg:.0%} chance" if best is not None
                else "nothing")
        print(f"  {M:4d}  {gh}-{ga:^5d}  {xh:16.2f}  {xa:16.2f}   {note}")
        prev = (gh, ga)
    print(f"\n  final {prev[0]}-{prev[1]}   "
          f"chances {df[df.side=='home'].xg.sum():.2f} v "
          f"{df[df.side=='away'].xg.sum():.2f}")
    for side, name in (("home", h), ("away", a)):
        s_ = df[df.side == side]
        print(f"  {name:26s} {int(s_.goal.sum())} from {s_.xg.sum():.2f} "
              f"-- {s_.goal.sum()-s_.xg.sum():+.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--replay", help="ESPN event id, to step through a match")
    ap.add_argument("--date", help="YYYYMMDD, to replay a finished matchday")
    ap.add_argument("--finished", action="store_true",
                    help="include completed matches (for replay)")
    args = ap.parse_args()

    bundle = model()
    if args.replay:
        return replay(bundle, args.replay)
    p = {"dates": args.date} if args.date else {}
    evs = session.get(f"{BASE}/scoreboard", params=p, timeout=30).json().get("events", [])
    evs = [e for e in evs if e["status"]["type"]["name"] in LIVE
           or (args.finished and e["status"]["type"].get("completed"))]
    render([r for r in (read_match(bundle, e) for e in evs) if r])


if __name__ == "__main__":
    main()
