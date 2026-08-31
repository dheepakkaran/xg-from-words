"""The season's fixture list, so the schedule knows when to wake up.

ESPN publish the whole Premier League calendar, played and unplayed, for free.
Refreshing it daily gives two things: the page can say when the next match is,
and the matchday job can tell in one read whether today is worth polling.
"""
import argparse, datetime as dt, json, os, time
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ROOT = os.path.join(os.path.dirname(__file__), "..")
session = requests.Session()      # no custom User-Agent; see collect.py


def month_chunks(start, end):
    d = dt.date.fromisoformat(start)
    last = dt.date.fromisoformat(end)
    while d <= last:
        nxt = min(d + dt.timedelta(days=30), last)
        yield d.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")
        d = nxt + dt.timedelta(days=1)


def season(league="eng.1", start="2026-08-01", end="2027-06-05"):
    out = {}
    for a, b in month_chunks(start, end):
        d = session.get(f"{BASE}/{league}/scoreboard",
                        params={"dates": f"{a}-{b}", "limit": 400},
                        timeout=30).json()
        for ev in d.get("events", []):
            st, comp = ev["status"], ev["competitions"][0]
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            out[ev["id"]] = {
                "event_id": ev["id"], "kickoff": ev["date"],
                "home": teams["home"]["team"]["displayName"],
                "away": teams["away"]["team"]["displayName"],
                "home_short": teams["home"]["team"]["shortDisplayName"],
                "away_short": teams["away"]["team"]["shortDisplayName"],
                "completed": bool(st["type"].get("completed")),
                "score": (f"{teams['home'].get('score', 0)}-"
                          f"{teams['away'].get('score', 0)}")
                         if st["type"].get("completed") else None,
            }
        time.sleep(0.3)
    return sorted(out.values(), key=lambda f: f["kickoff"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="eng.1")
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "fixtures.json"))
    args = ap.parse_args()

    fx = season(args.league)
    now = dt.datetime.now(dt.timezone.utc)
    upcoming = [f for f in fx if not f["completed"]]
    payload = {
        "league": args.league,
        "refreshed": now.isoformat(timespec="seconds"),
        "played": sum(1 for f in fx if f["completed"]),
        "upcoming": len(upcoming),
        "next": upcoming[:6],
        "fixtures": fx,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(payload, open(args.out, "w"), indent=1)
    print(f"{len(fx)} fixtures, {payload['played']} played, "
          f"{payload['upcoming']} upcoming")
    for f in upcoming[:5]:
        t = dt.datetime.fromisoformat(f["kickoff"].replace("Z", "+00:00"))
        print(f"  {t:%a %d %b %H:%M} UTC  ({(t-now).total_seconds()/3600:6.1f}h)"
              f"  {f['home']} v {f['away']}")


if __name__ == "__main__":
    main()
