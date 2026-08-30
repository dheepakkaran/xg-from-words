"""Stage 1a - collect EPL fixtures + match summaries from ESPN's public API.

Raw summary JSON is archived gzipped, one file per match, so the dataset
survives the source changing or disappearing.
"""
import gzip, json, os, random, sys, time
from datetime import date, timedelta
import requests

BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1"
ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")

# Completed Premier League seasons. Ranges are deliberately wide.
SEASONS = {
    # 2015-16 is here for one reason: it is the only recent Premier League
    # season StatsBomb release openly, so it is the only place where a
    # commentary sentence and a true shot coordinate describe the same shot.
    "2015-16": ("2015-08-01", "2016-06-05"),
    "2022-23": ("2022-08-01", "2023-06-05"),
    "2023-24": ("2023-08-01", "2024-06-05"),
    "2024-25": ("2024-08-01", "2025-06-05"),
    "2025-26": ("2025-08-01", "2026-06-05"),
}

session = requests.Session()
# Do NOT set a browser-like User-Agent. Verified against the live endpoint:
# a Chrome UA string returns 403, while the default requests UA and curl's UA
# both return 200. ESPN appears to block browser UAs on this host.


def get(url, params, tries=5):
    """GET with polite exponential backoff. The endpoint is undocumented,
    so we assume rate limits exist even though none are published."""
    delay = 1.0
    for attempt in range(tries):
        try:
            r = session.get(url, params=params, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(delay + random.random())
                delay *= 2
                continue
            r.raise_for_status()
        except requests.RequestException as e:
            if attempt == tries - 1:
                raise
            time.sleep(delay + random.random())
            delay *= 2
    raise RuntimeError(f"failed after {tries} tries: {url} {params}")


def month_chunks(start, end):
    d = date.fromisoformat(start)
    last = date.fromisoformat(end)
    while d <= last:
        nxt = min(d + timedelta(days=30), last)
        yield d.strftime("%Y%m%d"), nxt.strftime("%Y%m%d")
        d = nxt + timedelta(days=1)


def fixtures(season):
    start, end = SEASONS[season]
    out = {}
    for a, b in month_chunks(start, end):
        data = get(f"{BASE}/scoreboard", {"dates": f"{a}-{b}", "limit": 400})
        for ev in data.get("events", []):
            st = ev["status"]["type"]
            if not st.get("completed"):
                continue
            comp = ev["competitions"][0]
            teams = {c["homeAway"]: c for c in comp["competitors"]}
            out[ev["id"]] = {
                "event_id": ev["id"],
                "season": season,
                "date": ev["date"],
                "home": teams["home"]["team"]["displayName"],
                "away": teams["away"]["team"]["displayName"],
                "home_score": int(teams["home"].get("score", 0)),
                "away_score": int(teams["away"].get("score", 0)),
            }
        time.sleep(0.3)
    return list(out.values())


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seasons", default="",
                    help="comma-separated subset; default is all of them")
    args = ap.parse_args()
    wanted = ([s.strip() for s in args.seasons.split(",") if s.strip()]
              or list(SEASONS))

    os.makedirs(RAW, exist_ok=True)
    all_fx = []
    for s in wanted:
        fx = fixtures(s)
        print(f"{s}: {len(fx)} completed fixtures", flush=True)
        all_fx += fx
    # merge rather than overwrite, so collecting one season keeps the rest
    path = os.path.join(ROOT, "data", "fixtures.json")
    merged = {}
    if os.path.exists(path):
        merged = {f["event_id"]: f for f in json.load(open(path))}
    merged.update({f["event_id"]: f for f in all_fx})
    with open(path, "w") as f:
        json.dump(sorted(merged.values(), key=lambda x: x["date"]), f, indent=1)
    print(f"fixtures.json now holds {len(merged)} matches", flush=True)

    done = skipped = 0
    for i, fx in enumerate(all_fx, 1):
        path = os.path.join(RAW, f"{fx['event_id']}.json.gz")
        if os.path.exists(path):
            skipped += 1
            continue
        data = get(f"{BASE}/summary", {"event": fx["event_id"]})
        with gzip.open(path, "wt") as f:
            json.dump(data, f)
        done += 1
        if i % 25 == 0:
            print(f"  {i}/{len(all_fx)} fetched={done} cached={skipped}", flush=True)
        time.sleep(0.25)
    print(f"done: {done} fetched, {skipped} already cached, total {len(all_fx)}")


if __name__ == "__main__":
    main()
