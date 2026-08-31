"""Is the live path fast enough in Python, or does it need rewriting?

The proposal justified C++ for live ingest "at multi-match concurrency", with
the rewrite to be "motivated by a measured Python bottleneck, with before/after
benchmarks". This is that measurement, taken before anything is rewritten.

Three questions, in order:

1. How many matches actually run at once, across all six competitions?
2. How long does Python take to turn one match's JSON into scored shots?
3. Against a realistic polling cadence, is that anywhere near a limit?

Network time is measured separately, because it is not a language problem: a
rewrite cannot make ESPN answer faster, and whatever share of the budget the
round trip takes is fixed.
"""
import glob, gzip, json, os, statistics, sys, time
from collections import Counter

import pandas as pd
import requests

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
import shots as SH

CADENCE = 15.0        # seconds between polls, the proposal's figure
BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
session = requests.Session()


def peak_concurrency():
    """Most matches kicking off inside the same 105-minute window."""
    fx = json.load(open(os.path.join(ROOT, "data", "fixtures.json")))
    starts = pd.to_datetime([f["date"] for f in fx], utc=True, format="mixed")
    s = pd.Series(1, index=starts).sort_index()
    live = s.rolling("105min").sum()
    peak, when = int(live.max()), live.idxmax()
    by_league = Counter(
        f.get("league", "eng.1") for f in fx
        if abs((pd.Timestamp(f["date"]) - when).total_seconds()) < 105 * 60)
    return peak, when, by_league


def cpu_per_match(model, n=120):
    """Parse, extract and score one archived match. No network."""
    files = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*.json.gz")))[:n]
    blobs = [gzip.open(f, "rb").read() for f in files]
    parse, extract, score = [], [], []
    for b in blobs:
        t = time.perf_counter()
        d = json.loads(b)
        parse.append(time.perf_counter() - t)

        t = time.perf_counter()
        rows = SH.shots_from_summary(d, event_id="bench")
        extract.append(time.perf_counter() - t)

        if rows:
            df = pd.DataFrame(rows)
            t = time.perf_counter()
            model["model"].predict_proba(df[model["features"]])
            score.append(time.perf_counter() - t)
    return parse, extract, score


def network_sample(k=8):
    """Round-trip time for a summary fetch, which no rewrite can change."""
    fx = json.load(open(os.path.join(ROOT, "data", "fixtures.json")))[:k]
    out = []
    for f in fx:
        t = time.perf_counter()
        session.get(f"{BASE}/{f.get('league', 'eng.1')}/summary",
                    params={"event": f["event_id"]}, timeout=30)
        out.append(time.perf_counter() - t)
    return out


def main():
    from joblib import load
    model = load(os.path.join(ROOT, "models", "xg.joblib"))

    peak, when, by_league = peak_concurrency()
    print(f"peak concurrency : {peak} matches in one 105-minute window")
    print(f"  {when:%Y-%m-%d %H:%M UTC} -- "
          + ", ".join(f"{k} {v}" for k, v in by_league.most_common()))

    parse, extract, score = cpu_per_match(model)
    tot = (statistics.mean(parse) + statistics.mean(extract)
           + statistics.mean(score))
    print(f"\ncpu per match ({len(parse)} matches, no network)")
    print(f"  json parse     {statistics.mean(parse)*1000:7.2f} ms")
    print(f"  shot extract   {statistics.mean(extract)*1000:7.2f} ms")
    print(f"  score          {statistics.mean(score)*1000:7.2f} ms")
    print(f"  total          {tot*1000:7.2f} ms   "
          f"(p95 parse {sorted(parse)[int(len(parse)*.95)]*1000:.1f} ms)")

    budget = peak * tot
    print(f"\nagainst a {CADENCE:.0f}s polling cadence")
    print(f"  {peak} matches x {tot*1000:.1f} ms = {budget*1000:.0f} ms of cpu")
    print(f"  that is {budget/CADENCE:.2%} of the budget")
    print(f"  headroom before cpu is the limit: {CADENCE/budget:.0f}x "
          f"({int(CADENCE/tot):,} concurrent matches)")

    try:
        net = network_sample()
        mean_net = statistics.mean(net)
        print("\nnetwork, for scale")
        print(f"  one summary fetch  {mean_net*1000:7.0f} ms")
        print(f"  {peak} sequential   {peak*mean_net:7.1f} s -- "
              f"{'over' if peak*mean_net > CADENCE else 'under'} "
              f"the {CADENCE:.0f}s cadence")
        print(f"  cpu is {mean_net/tot:.0f}x cheaper than the round trip "
              f"it waits on")
    except Exception as e:
        print(f"\nnetwork sample skipped: {e}")


if __name__ == "__main__":
    main()
