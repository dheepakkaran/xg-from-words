"""One poll of the live matches, scored and written out for the page.

What it does not do is predict. Question one settled that: which match produces
the next goal is not knowable from this data (FINDINGS 3.6). So each match is
described, not forecast -- chances created, whether the finishing has been
better or worse than the chances deserved, and the best moment so far.

Every poll also records how stale ESPN's newest commentary line is, which is
the one number the project still has no evidence for.
"""
import argparse, datetime as dt, json, os, sys, time
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
import shots as SH
from score import Scorer
LIVE = {"STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_IN_PROGRESS",
        "STATUS_HALFTIME", "STATUS_END_PERIOD"}
RECENT = 20                       # minutes, for the "where is the action" sort
CHECKPOINT = 15                   # minutes between timeline entries
KICKOFF_WINDOW = 45               # minutes ahead worth waiting for
# 45 rather than 30 because kickoffs sit on :00 and :30 while the schedule
# fires on :50 -- a 15:30 kickoff is 40 minutes after the 14:50 firing, and a
# 30-minute window would let that job go back to sleep 40 minutes early.
POLL_SECONDS = 60                 # written out so the page can say it
session = requests.Session()      # no custom User-Agent; see collect.py


def timeline(rows, minute, step=CHECKPOINT):
    """Running totals at each quarter hour reached so far.

    A single pair of numbers says who is on top; the sequence says when it
    turned. Only checkpoints the match has actually passed are included, and
    each one uses only the shots up to it -- the same rule the model is held to
    everywhere else.
    """
    out = []
    for m in range(step, int(minute) + 1, step):
        seen = [r for r in rows if r["minute"] <= m]
        out.append({
            "minute": m,
            "home_xg": round(sum(r["xg"] for r in seen if r["side"] == "home"), 2),
            "away_xg": round(sum(r["xg"] for r in seen if r["side"] == "away"), 2),
            "home_goals": sum(r["goal"] for r in seen if r["side"] == "home"),
            "away_goals": sum(r["goal"] for r in seen if r["side"] == "away"),
        })
    return out


def kickoff_soon(now, minutes=KICKOFF_WINDOW):
    """Is a fixture about to start?

    The schedule cannot know when matches are -- GitHub cron times are fixed
    strings in the workflow file. So the schedule fires hourly through the
    football window and this decides whether to stay awake: if a kickoff is
    inside the next half hour, keep polling rather than exiting on an empty
    scoreboard.

    That matters more than it sounds. Premier League kickoffs land on ten
    different UTC times across a season, because the UK moves off BST in
    October -- Saturday 3pm is 14:00 UTC in August and 15:00 UTC in November.
    Four hardcoded slots covered 119 of 361 remaining fixtures.
    """
    path = os.path.join(ROOT, "docs", "fixtures.json")
    if not os.path.exists(path):
        return None
    for f in json.load(open(path)).get("fixtures", []):
        if f.get("completed"):
            continue
        t = dt.datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00"))
        if 0 <= (t - now).total_seconds() <= minutes * 60:
            return f
    return None


def newest_lag(summary, now):
    """Seconds since ESPN stamped their most recent commentary line."""
    stamps = [(e.get("play") or {}).get("wallclock")
              for e in summary.get("commentary", [])]
    stamps = [dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
              for s in stamps if s]
    return round((now - max(stamps)).total_seconds(), 1) if stamps else None


def describe(score, ev, now):
    sm = session.get(f"{BASE}/eng.1/summary", params={"event": ev["id"]},
                     timeout=30).json()
    rows = SH.shots_from_summary(sm, event_id=ev["id"])
    comp = ev["competitions"][0]
    teams = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
    scores = {c["homeAway"]: int(c.get("score", 0)) for c in comp["competitors"]}
    minute = float(ev["status"].get("clock", 0) or 0) / 60.0

    out = {"event_id": ev["id"], "home": teams["home"], "away": teams["away"],
           "score": [scores["home"], scores["away"]],
           "clock": ev["status"].get("displayClock"),
           "status": ev["status"]["type"]["name"],
           "commentary_lag_seconds": newest_lag(sm, now),
           "sides": []}
    if not rows:
        out["recent_xg"] = 0.0
        return out

    for r in rows:
        r["xg"] = score(r)
    for ha in ("home", "away"):
        mine = [r for r in rows if r["team"] == teams[ha]]
        total = sum(r["xg"] for r in mine)
        recent = sum(r["xg"] for r in mine if r["minute"] > minute - RECENT)
        best = max(mine, key=lambda r: r["xg"], default=None)
        out["sides"].append({
            "team": teams[ha], "goals": scores[ha], "shots": len(mine),
            "xg": round(total, 2), "recent_xg": round(recent, 2),
            "form": round(scores[ha] - total, 2),
            "best_xg": round(best["xg"], 3) if best else None,
            "best_text": " ".join(best["text"].split()) if best else None,
        })
    out["recent_xg"] = round(sum(x["recent_xg"] for x in out["sides"]), 2)
    out["timeline"] = timeline(rows, minute)
    out["minute"] = round(minute, 1)
    return out


def one_cycle(score, out_path, latency_path):
    now = dt.datetime.now(dt.timezone.utc)
    evs = session.get(f"{BASE}/eng.1/scoreboard", timeout=30).json().get("events", [])
    live = [e for e in evs if e["status"]["type"]["name"] in LIVE]
    matches = sorted((describe(score, e, now) for e in live),
                     key=lambda m: -m.get("recent_xg", 0))

    payload = {"generated": now.isoformat(timespec="seconds"),
               "poll_seconds": POLL_SECONDS,
               "live": len(matches), "matches": matches}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    json.dump(payload, open(out_path, "w"), indent=1)

    with open(latency_path, "a") as f:
        for m in matches:
            f.write(json.dumps({
                "polled_at": payload["generated"], "event_id": m["event_id"],
                "name": f"{m['home']} v {m['away']}", "clock": m["clock"],
                "status": m["status"],
                "lag_seconds": m["commentary_lag_seconds"]}) + "\n")

    for m in matches:
        lag = m["commentary_lag_seconds"]
        print(f"{now:%H:%M:%S}  {m['home'][:20]:20s} {m['score'][0]}-{m['score'][1]} "
              f"{m['away'][:20]:20s} {str(m['clock']):>7s}  "
              f"lag {lag if lag is None else f'{lag:5.0f}s'}", flush=True)
    if not matches:
        soon = kickoff_soon(now)
        if soon:
            t = dt.datetime.fromisoformat(soon["kickoff"].replace("Z", "+00:00"))
            mins = (t - now).total_seconds() / 60
            print(f"{now:%H:%M:%S}  nothing yet -- {soon['home']} v "
                  f"{soon['away']} in {mins:.0f} min, staying awake", flush=True)
            return -1            # awake, but with nothing to score
        print(f"{now:%H:%M:%S}  nothing in progress", flush=True)
    return len(matches)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true", help="keep polling")
    ap.add_argument("--every", type=float, default=60.0)
    ap.add_argument("--minutes", type=float, default=165.0)
    ap.add_argument("--quit-after-idle", type=int, default=3)
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "live.json"))
    ap.add_argument("--latency",
                    default=os.path.join(ROOT, "reports", "latency.jsonl"))
    args = ap.parse_args()

    score = Scorer()
    os.makedirs(os.path.dirname(args.latency), exist_ok=True)
    if not args.watch:
        one_cycle(score, args.out, args.latency)
        return

    deadline, idle = time.time() + args.minutes * 60, 0
    while time.time() < deadline:
        try:
            found = one_cycle(score, args.out, args.latency)
            # -1 means nothing live but a kickoff is imminent: not idle.
            idle = 0 if found != 0 else idle + 1
        except Exception as e:                     # one bad poll is not fatal
            print(f"poll failed: {e}", flush=True)
            idle += 1
        if idle >= args.quit_after_idle:
            print(f"no live match for {idle} polls; stopping", flush=True)
            break
        time.sleep(args.every)


if __name__ == "__main__":
    main()
