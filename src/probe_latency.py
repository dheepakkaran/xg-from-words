"""Measure how stale ESPN's commentary is during a live match.

This is the last unanswered question in the project. Everything about the live
product assumes the words arrive in time to be worth reading, and that has
never been checked -- FINDINGS 4.3, AUDIT check 5. It can only be checked while
a match is running, and it needs to run somewhere that is awake when one is.

Each poll records the gap between now and the wallclock stamp on the newest
commentary line. The stamp is ESPN's own, so the number is the age of the most
recent event they have published, not network time.
"""
import argparse, datetime as dt, json, os, sys, time
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ROOT = os.path.join(os.path.dirname(__file__), "..")
LIVE = {"STATUS_FIRST_HALF", "STATUS_SECOND_HALF", "STATUS_IN_PROGRESS",
        "STATUS_HALFTIME", "STATUS_END_PERIOD"}
session = requests.Session()      # no custom User-Agent; see collect.py


def newest_event(summary):
    """(wallclock, minute, text) of the latest stamped commentary line."""
    best = None
    for e in summary.get("commentary", []):
        wc = (e.get("play") or {}).get("wallclock")
        if not wc:
            continue
        t = dt.datetime.fromisoformat(wc.replace("Z", "+00:00"))
        if best is None or t > best[0]:
            best = (t, (e.get("time") or {}).get("displayValue", ""),
                    (e.get("text") or "")[:90])
    return best


def poll(league, out):
    now = dt.datetime.now(dt.timezone.utc)
    sb = session.get(f"{BASE}/{league}/scoreboard", timeout=30).json()
    live = [e for e in sb.get("events", [])
            if e["status"]["type"]["name"] in LIVE]
    if not live:
        print(f"{now:%H:%M:%S}  nothing in progress", flush=True)
        return 0

    for ev in live:
        sm = session.get(f"{BASE}/{league}/summary",
                         params={"event": ev["id"]}, timeout=30).json()
        newest = newest_event(sm)
        n_shots = sum(1 for e in sm.get("commentary", [])
                      if "Shot" in ((e.get("play") or {}).get("type") or {})
                      .get("text", ""))
        row = {"polled_at": now.isoformat(), "event_id": ev["id"],
               "name": ev["name"], "clock": ev["status"].get("displayClock"),
               "status": ev["status"]["type"]["name"],
               "n_commentary": len(sm.get("commentary", [])),
               "n_shots": n_shots}
        if newest:
            lag = (now - newest[0]).total_seconds()
            row.update(newest_wallclock=newest[0].isoformat(),
                       lag_seconds=round(lag, 1),
                       newest_minute=newest[1], newest_text=newest[2])
            print(f"{now:%H:%M:%S}  {ev['name'][:38]:38s} {ev['status'].get('displayClock',''):>7s}"
                  f"  lag {lag:6.0f}s  \"{newest[2][:44]}\"", flush=True)
        else:
            row.update(lag_seconds=None)
            print(f"{now:%H:%M:%S}  {ev['name'][:38]:38s} no stamped commentary",
                  flush=True)
        with open(out, "a") as f:
            f.write(json.dumps(row) + "\n")
    return len(live)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="eng.1")
    ap.add_argument("--every", type=float, default=60.0, help="seconds")
    ap.add_argument("--minutes", type=float, default=150.0, help="how long")
    ap.add_argument("--out", default=os.path.join(ROOT, "reports",
                                                  "latency.jsonl"))
    ap.add_argument("--quit-after-idle", type=int, default=20,
                    help="stop after this many consecutive empty polls")
    args = ap.parse_args()

    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    deadline = time.time() + args.minutes * 60
    idle = 0
    while time.time() < deadline:
        try:
            found = poll(args.league, args.out)
            idle = 0 if found else idle + 1
        except Exception as e:                    # a poll failing is not fatal
            print(f"poll failed: {e}", flush=True)
            idle += 1
        if idle >= args.quit_after_idle:
            print(f"no live match for {idle} polls; stopping", flush=True)
            break
        time.sleep(args.every)
    summarise(args.out)


def summarise(path):
    if not os.path.exists(path):
        print("no samples")
        return
    lags = [json.loads(l).get("lag_seconds") for l in open(path)]
    lags = sorted(x for x in lags if x is not None)
    if not lags:
        print("no stamped commentary in any sample")
        return
    q = lambda p: lags[min(len(lags) - 1, int(len(lags) * p))]
    print(f"\n{len(lags)} samples")
    print(f"  median {q(.5):6.0f}s   p90 {q(.9):6.0f}s   "
          f"p99 {q(.99):6.0f}s   max {lags[-1]:6.0f}s")


if __name__ == "__main__":
    main()
