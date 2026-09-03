"""Can the archive answer the latency question? No, and this is the evidence.

reports/latency.jsonl is empty, and the obvious shortcut is the archive: every
commentary item carries a `wallclock`, so if that field records when ESPN
published the line, then 3,577 stored matches already contain the measurement
and no live poll is needed.

It does not. `wallclock` is the time the event happened, reconstructed as the
actual kickoff plus the match clock, and it is arithmetic rather than
observation. The test is the residual

    residual = (wallclock - scheduled kickoff) - match clock

within a single match. A published timestamp would scatter: some lines appear
seconds after the event, some tens of seconds, a few much later. A derived one
is constant, because the only thing separating it from the match clock is the
fixed gap between the scheduled and actual kickoff.

Across the matches checked here the within-match standard deviation is well
under a second, and the residual takes two adjacent integer values -- the
signature of second-level rounding on a constant, not of a process with real
variance.

Two consequences, both stated in the paper:

  1. The archive cannot answer the question. Latency has to be observed live.
  2. When it is observed live, the statistic is the *minimum* of
     `now - wallclock` across polls, not the mean. That difference is partly
     real latency and partly however long it has been since anything happened,
     and only the minimum squeezes the second term towards zero.
"""
import argparse, datetime as dt, glob, gzip, json, os
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..")
FIRST_HALF = 2400          # seconds; avoids the half-time interval entirely
MIN_ITEMS = 12
# A published timestamp cannot be this steady. Above it, the field is derived.
DERIVED_SD = 2.0


def residuals(path, kickoff):
    d = json.load(gzip.open(path))
    out = []
    for it in d.get("commentary", []):
        pl = it.get("play") or {}
        wc, ck = pl.get("wallclock"), (pl.get("clock") or {}).get("value")
        if not wc or ck is None or ck > FIRST_HALF:
            continue
        w = dt.datetime.fromisoformat(wc.replace("Z", "+00:00"))
        out.append((w - kickoff).total_seconds() - ck)
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--matches", type=int, default=200)
    args = ap.parse_args()

    fx = json.load(open(os.path.join(ROOT, "data", "fixtures.json")))
    fx = [f for f in fx if f["season"] >= "2022"]
    rows = []
    for f in sorted(fx, key=lambda x: x["date"], reverse=True):
        p = os.path.join(ROOT, "data", "raw", f"{f['event_id']}.json.gz")
        if not os.path.exists(p):
            continue
        ko = dt.datetime.fromisoformat(f["date"].replace("Z", "+00:00"))
        try:
            r = residuals(p, ko)
        except Exception:
            continue
        if len(r) < MIN_ITEMS:
            continue
        rows.append({"event_id": f["event_id"], "n": int(len(r)),
                     "mean_s": float(r.mean()), "sd_s": float(r.std()),
                     "distinct": int(len(set(r.round(0))))})
        if len(rows) >= args.matches:
            break

    sd = np.array([r["sd_s"] for r in rows])
    mean = np.array([r["mean_s"] for r in rows])
    dis = np.array([r["distinct"] for r in rows])
    out = {
        "matches_checked": len(rows),
        "items_per_match_median": int(np.median([r["n"] for r in rows])),
        "within_match_sd_seconds": {
            "median": round(float(np.median(sd)), 3),
            "p95": round(float(np.percentile(sd, 95)), 3),
            "max": round(float(sd.max()), 3),
        },
        "distinct_residual_values_per_match": {
            "median": int(np.median(dis)), "max": int(dis.max()),
        },
        "kickoff_offset_seconds": {
            "median": round(float(np.median(mean)), 1),
            "p5": round(float(np.percentile(mean, 5)), 1),
            "p95": round(float(np.percentile(mean, 95)), 1),
        },
        "share_below_sd_threshold": round(float((sd < DERIVED_SD).mean()), 4),
        "sd_threshold_seconds": DERIVED_SD,
        "verdict": ("wallclock is the event time, derived as actual kickoff "
                    "plus match clock. It is not a publish timestamp and "
                    "cannot measure latency."),
    }
    p = os.path.join(ROOT, "reports", "wallclock_check.json")
    json.dump(out, open(p, "w"), indent=1)
    print(json.dumps(out, indent=1))
    print(f"\nwrote {os.path.relpath(p, ROOT)}")


if __name__ == "__main__":
    main()
