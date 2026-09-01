"""Correct the one thing the shipped model gets wrong: the level.

The model reads phrases. Phrases drift. Between 2022-23 and 2025-26 the share
of shots ESPN describe as being from the six yard box rose from 4.2% to 6.0%
while their conversion fell from 39.1% to 35.8%, and "following a fast break"
went from 1.9% of shots at 47.2% to 3.3% at 28.4%. Both phrases became more
common and less productive at the same time, which is not a change in football
-- it is a change in how the sentence gets written.

The model cannot see that. It was fitted when "fast break" meant 47% and it
still believes so, so on 2025-26 it predicts 0.1270 per shot against a
realised 0.1134: an 11.9% overestimate. Exactly 5.7% of that is the league's
own goal rate falling and 5.9% is the phrase mix shifting -- 1.057 x 1.059 =
1.119, the whole of it.

Retraining does not help, because the problem is not old data, it is that next
season's rate is unknowable in advance. Weighting recent seasons more heavily
gets from +11.9% to +9.9% and costs training data to do it.

What does work is waiting. Once a few hundred shots of the new season have
been played, their realised conversion rate is observable, and one number --
a shift on the intercept -- pulls the level back into line. Walk forward
through 2025-26 recalibrating only on shots already played and the overestimate
falls from +11.7% to +2.6%.

An intercept shift is monotone, so it cannot change the ranking and cannot
change AUC. It only moves the level. That is the point: the words rank shots
about as well as coordinates do, and it is the words-to-probability mapping
that drifts.
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS, xg_model

ROOT = os.path.join(os.path.dirname(__file__), "..")

# Below this many shots the realised rate is too noisy to correct towards, and
# a shift fitted on it would be worse than no shift at all. 500 shots is about
# twenty Premier League matches -- three weekends. Until then the file says so
# and the scorer leaves the model alone.
WARMUP = 500

# Recalibrating after every shot would be pointless precision. Once per block
# is enough, and it makes the walk-forward evaluation honest about the fact
# that a deployed shift is always slightly out of date.
BLOCK = 500


def shift_for(logit, rate):
    """The intercept shift that makes the mean prediction equal `rate`.

    Bisection rather than algebra: the mean of a logistic has no closed form
    inverse, but it is monotone in the shift, so fifty halvings put it well
    inside float noise.
    """
    lo, hi = -5.0, 5.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if (1.0 / (1.0 + np.exp(-(logit + mid)))).mean() > rate:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2


def season_shots(season=None, shots_path=None, fixtures_path=None):
    """The shipped model's league and window, with a kickoff date attached."""
    df = pd.read_parquet(shots_path or os.path.join(ROOT, "data", "proc",
                                                    "shots.parquet"))
    df = df[(df.league == "eng.1") & (df.season >= 2022)]
    if season is None:
        season = int(df.season.max())
    dates = {f["event_id"]: f["date"]
             for f in json.load(open(fixtures_path or
                                     os.path.join(ROOT, "data",
                                                  "fixtures.json")))}
    cur = df[df.season == season].copy()
    cur["date"] = cur.event_id.map(dates)
    cur = cur.dropna(subset=["date"]).sort_values(["date", "minute"])
    return df[df.season < season], cur.reset_index(drop=True), season


def logits(model, rows):
    p = model.predict_proba(rows[FIELDS])[:, 1]
    return np.log(p / (1 - p))


def walk_forward(model, cur):
    """The evidence, with no future in it.

    Each block is scored with a shift fitted only on shots played before the
    block began. The first WARMUP shots are scored uncorrected and then
    excluded from the comparison, because in deployment they are what the
    correction is waiting for.
    """
    z = logits(model, cur)
    p_raw = 1.0 / (1.0 + np.exp(-z))
    p_cal = p_raw.copy()
    shifts = []
    for start in range(WARMUP, len(cur), BLOCK):
        past = slice(0, start)
        s = shift_for(z[past], cur.goal.values[past].mean())
        block = slice(start, min(start + BLOCK, len(cur)))
        p_cal[block] = 1.0 / (1.0 + np.exp(-(z[block] + s)))
        shifts.append(s)
    ev = slice(WARMUP, len(cur))
    y = cur.goal.values[ev]
    return {
        "n_evaluated": int(len(y)),
        "actual_rate": round(float(y.mean()), 5),
        "uncorrected_mean_xg": round(float(p_raw[ev].mean()), 5),
        "recalibrated_mean_xg": round(float(p_cal[ev].mean()), 5),
        "uncorrected_over_pct": round(100 * (p_raw[ev].mean() / y.mean() - 1), 2),
        "recalibrated_over_pct": round(100 * (p_cal[ev].mean() / y.mean() - 1), 2),
        "shifts_applied": [round(float(s), 5) for s in shifts],
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, default=None,
                    help="season to correct towards; default the newest held")
    ap.add_argument("--out", default=os.path.join(ROOT, "models",
                                                  "xg.shift.json"))
    args = ap.parse_args()

    past, cur, season = season_shots(args.season)
    model = xg_model().fit(past[FIELDS], past.goal)

    z = logits(model, cur)
    active = len(cur) >= WARMUP
    # Every shot here has already been played, so fitting on all of them is
    # what a deployment would legitimately know today. The walk-forward block
    # below is the part that has to prove there is no future in it.
    shift = shift_for(z, cur.goal.mean()) if active else 0.0

    out = {
        "season": season,
        "league": "eng.1",
        "trained_on": sorted(int(s) for s in past.season.unique()),
        "n_shots_seen": int(len(cur)),
        "warmup_shots": WARMUP,
        "active": bool(active),
        "realised_rate": round(float(cur.goal.mean()), 5),
        "uncorrected_mean_xg": round(float((1 / (1 + np.exp(-z))).mean()), 5),
        "shift": round(float(shift), 5),
        "evidence": walk_forward(model, cur) if active else None,
        "note": ("Added to the intercept in models/xg.json. Monotone, so it "
                 "moves the level and cannot move the ranking."),
    }
    json.dump(out, open(args.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
