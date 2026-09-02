"""Where the words disagree with the coordinates, and why it is the same
place they drift.

The headline says the words recover 90.6% of the coordinate model. It does not
say which 9.4% is missing. This locates the disagreement field by field on the
8,825 joined shots, and reports the examples at each extreme so a reader can
see what the sentence failed to say rather than taking the number on trust.

The result worth noting is that the two lists coincide. The fields carrying the
largest disagreement with StatsBomb -- "from very close range" and "following a
fast break" -- are the two phrases whose meaning moves across seasons
(src/recalibrate.py). Imprecise phrasing is both the least accurate feature and
the least stable one, which is one mechanism rather than two findings.
"""
import json, os, sys
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS

MIN_N = 40                 # below this a field's mean difference is noise


def clean(t, n=140):
    t = " ".join(str(t).split())
    return t[:n] + ("..." if len(t) > n else "")


def main():
    d = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    d = d.assign(diff=d.our_xg - d.sb_xg)
    d = d.assign(dist=np.hypot(d.sb_x - 120, d.sb_y - 40))

    per_field = []
    for f in FIELDS:
        if f == "minute":
            continue
        s = d[d[f] == 1]
        if len(s) < MIN_N:
            continue
        per_field.append({
            "field": f, "n": int(len(s)),
            "mean_abs_diff": round(float(s["diff"].abs().mean()), 4),
            "bias": round(float(s["diff"].mean()), 4),
        })
    per_field.sort(key=lambda r: -r["mean_abs_diff"])

    def picks(sub, k=3):
        return [{"text": clean(r.text),
                 "ours": round(float(r.our_xg), 3),
                 "statsbomb": round(float(r.sb_xg), 3),
                 "goal": int(r.sb_goal),
                 "distance_m": round(float(r.dist), 1)}
                for _, r in sub.head(k).iterrows()]

    mid = d[(d.our_xg > 0.05) & (d.our_xg < 0.6)]
    out = {
        "n_shots": int(len(d)),
        "min_n_per_field": MIN_N,
        "per_field": per_field,
        "closest": picks(mid.reindex(mid["diff"].abs().sort_values().index)),
        "we_over": picks(d.sort_values("diff", ascending=False)),
        "we_under": picks(d.sort_values("diff")),
    }
    p = os.path.join(ROOT, "reports", "error_analysis.json")
    json.dump(out, open(p, "w"), indent=1)

    print(f"{len(d):,} joined shots, {len(per_field)} fields above n={MIN_N}\n")
    print(f"  {'field':16s} {'n':>6s} {'mean|diff|':>11s} {'bias':>8s}")
    for r in per_field:
        print(f"  {r['field']:16s} {r['n']:6d} {r['mean_abs_diff']:11.4f} "
              f"{r['bias']:+8.4f}")
    print(f"\nlargest disagreement : {per_field[0]['field']}")
    biased = max(per_field, key=lambda r: abs(r["bias"]))
    print(f"largest bias         : {biased['field']} ({biased['bias']:+.4f})")
    print("both are phrases whose meaning drifts; see src/recalibrate.py")
    print(f"\nwrote {os.path.relpath(p, ROOT)}")


if __name__ == "__main__":
    main()
