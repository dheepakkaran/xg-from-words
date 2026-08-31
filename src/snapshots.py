"""Stage 1b - turn raw match JSON into training snapshots.

One row per (match, minute M). Everything in a row is derived from the same
commentary stream: the numbers track counts typed events up to M, the words
track keeps the raw text of the last K lines up to M. Only the label looks
forward.
"""
import gzip, json, os, re, sys
from collections import Counter
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
import strength

ROOT = os.path.join(os.path.dirname(__file__), "..")
RAW = os.path.join(ROOT, "data", "raw")
PROC = os.path.join(ROOT, "data", "proc")

# The four seasons the momentum experiment is defined over. fixtures.json also
# holds 2015-16, which exists only to validate the xG model against StatsBomb,
# and five other competitions, which exist only for the transfer test.
SEASONS = {"2022-23", "2023-24", "2024-25", "2025-26"}

MINUTES = list(range(10, 81, 5))   # snapshot every 5 minutes
HORIZON = 15                       # headline label window, in minutes
HORIZONS = [5, 10, 15, 30]         # every window labelled, for the sweep
MAX_LINES = 20                     # keep 20; ablations slice 3 / 10 / 20
SEP = " ||| "                      # line delimiter, so ablations can slice cleanly

# Commentary play types -> the feature counter they increment.
EVENT_MAP = {
    "Foul": "foul", "Handball": "foul", "Free Kick": "freekick",
    "Corner Awarded": "corner", "Offside": "offside",
    "Shot On Target": "shot_on", "Shot Off Target": "shot_off",
    "Shot Blocked": "shot_blocked", "Shot Hit Woodwork": "woodwork",
    "Yellow Card": "yellow", "Red Card": "red", "Substitution": "sub",
    "Goal": "goal", "Goal - Header": "goal", "Goal - Volley": "goal",
    "Goal - Free-kick": "goal", "Penalty - Scored": "goal",
    "Own Goal": "goal", "Penalty - Saved": "shot_on",
    "Penalty - Missed": "shot_off", "Penalty - Hit Woodwork": "woodwork",
}
COUNTERS = sorted(set(EVENT_MAP.values()))

_MIN_RE = re.compile(r"^(\d+)'(?:\+(\d+)')?$")
_SCORE_RE = re.compile(r"Goal!\s+.*?\s(\d+),\s+.*?\s(\d+)")


def minute_of(display, clock_value):
    """Monotone minute. Stoppage time becomes a fraction so 45'+2' (45.02)
    sorts before 46' rather than colliding with it."""
    m = _MIN_RE.match(display or "")
    if m:
        return int(m.group(1)) + (int(m.group(2) or 0) / 100.0)
    if clock_value:
        return clock_value / 60.0
    return None


def goals_of(summary, home_name, away_name):
    """(minute, 'HOME'|'AWAY') for each goal.

    Primary source is the scoreline embedded in the goal text, which handles
    own goals correctly; ESPN's `team` field on an own goal names the team
    that conceded it. Falls back to `team` when the text does not parse.
    """
    out, prev_h, prev_a = [], 0, 0
    for ev in summary.get("keyEvents", []):
        if not ev.get("scoringPlay"):
            continue
        mn = minute_of(ev.get("clock", {}).get("displayValue"),
                       ev.get("clock", {}).get("value"))
        if mn is None:
            continue
        side = None
        m = _SCORE_RE.search(ev.get("text", ""))
        if m:
            h, a = int(m.group(1)), int(m.group(2))
            if h > prev_h:
                side = "HOME"
            elif a > prev_a:
                side = "AWAY"
            prev_h, prev_a = max(h, prev_h), max(a, prev_a)
        if side is None:
            t = (ev.get("team") or {}).get("displayName")
            side = "HOME" if t == home_name else "AWAY" if t == away_name else None
        if side:
            out.append((mn, side))
    return sorted(out)


def timeline(summary, home_name, away_name):
    """Commentary lines as (minute, side, counter_key, text), time-ordered."""
    rows = []
    for e in summary.get("commentary", []):
        play = e.get("play") or {}
        mn = minute_of(e.get("time", {}).get("displayValue"),
                       e.get("time", {}).get("value"))
        if mn is None:
            continue
        team = (play.get("team") or {}).get("displayName")
        side = "HOME" if team == home_name else "AWAY" if team == away_name else None
        key = EVENT_MAP.get((play.get("type") or {}).get("text"))
        rows.append((mn, side, key, (e.get("text") or "").strip()))
    rows.sort(key=lambda r: r[0])
    return rows


def features_at(lines, goals, M, minute_now=None):
    """The feature row for minute M. Shared by the offline builder and the
    live scorer -- if these two ever drift apart, training and serving drift
    apart with them.

    `lines` and `goals` must already be filtered to events at or before M by
    the caller; this function additionally guards it.
    """
    past = [l for l in lines if l[0] <= M]
    if len(past) < 5:
        return None
    cum = Counter()                 # cumulative counts, minute 0..M
    rec = Counter()                 # same counts, last 10 minutes only
    for mn, side, key, _ in past:
        if key is None or side is None:
            continue
        cum[f"{side.lower()}_{key}"] += 1
        if mn > M - 10:
            rec[f"{side.lower()}_{key}"] += 1
    gh = sum(1 for mn, s in goals if mn <= M and s == "HOME")
    ga = sum(1 for mn, s in goals if mn <= M and s == "AWAY")

    row = {
        "minute": M, "goals_home": gh, "goals_away": ga, "score_diff": gh - ga,
        "text": SEP.join(t for _, _, _, t in past[-MAX_LINES:]),
        "n_lines_10min": sum(1 for mn, _, _, _ in past if mn > M - 10),
    }
    for c in COUNTERS:
        for s in ("home", "away"):
            row[f"cum_{s}_{c}"] = cum.get(f"{s}_{c}", 0)
            row[f"rec_{s}_{c}"] = rec.get(f"{s}_{c}", 0)
        row[f"cum_diff_{c}"] = row[f"cum_home_{c}"] - row[f"cum_away_{c}"]
        row[f"rec_diff_{c}"] = row[f"rec_home_{c}"] - row[f"rec_away_{c}"]
    return row


def future_counts(lines, M, horizon):
    """Events in (M, M+horizon] -- the FUTURE. Never a feature.

    Used only by the ceiling diagnostic in run_experiment.py, which asks how
    well the label can be predicted by something that has already watched the
    window. Every column is prefixed `fut_` so it cannot be picked up by a
    feature list built from `cum_` / `rec_`, and the leakage test asserts these
    columns *do* change under truncation.
    """
    out = {f"fut_{s}_{c}": 0 for c in COUNTERS for s in ("home", "away")}
    for mn, side, key, _ in lines:
        if key is None or side is None or key == "goal":
            continue          # the goal itself would make this a lookup, not a bound
        if M < mn <= M + horizon:
            out[f"fut_{side.lower()}_{key}"] += 1
    return out


def build_match(fx, summary, elo=None):
    home, away = fx["home"], fx["away"]
    lines = timeline(summary, home, away)
    if len(lines) < 20:
        return []                       # too sparse to be usable
    goals = goals_of(summary, home, away)
    eh, ea = (elo or {}).get(fx["event_id"], (strength.INIT, strength.INIT))
    rows = []
    for M in MINUTES:
        row = features_at(lines, goals, M)
        if row is None:
            continue
        row.update(event_id=fx["event_id"], season=fx["season"], date=fx["date"],
                   home=home, away=away,
                   elo_home=eh, elo_away=ea, elo_diff=eh - ea)
        for h in HORIZONS:
            nxt = [(mn, s) for mn, s in goals if M < mn <= M + h]
            row[f"label_{h}"] = nxt[0][1] if nxt else "NONE"
        row["label"] = row[f"label_{HORIZON}"]
        row.update(future_counts(lines, M, HORIZON))
        rows.append(row)
    return rows


def main():
    import argparse
    ap = argparse.ArgumentParser()
    # Premier League by default, and on purpose. fixtures.json grew to six
    # competitions for the transfer test in src/transfer.py; letting them into
    # the momentum experiment would silently change every number it produced,
    # and a rebuild would no longer reproduce the published result.
    ap.add_argument("--leagues", default="eng.1",
                    help="comma-separated ESPN league codes")
    args = ap.parse_args()
    wanted = {l.strip() for l in args.leagues.split(",") if l.strip()}

    os.makedirs(PROC, exist_ok=True)
    fixtures = json.load(open(os.path.join(ROOT, "data", "fixtures.json")))
    fixtures = [f for f in fixtures if f.get("league", "eng.1") in wanted
                and f["season"] in SEASONS]
    elo = strength.build(fixtures)
    rows, missing, sparse, bad_label = [], 0, 0, 0
    for fx in fixtures:
        path = os.path.join(RAW, f"{fx['event_id']}.json.gz")
        if not os.path.exists(path):
            missing += 1
            continue
        summary = json.load(gzip.open(path, "rt"))
        # Label sanity: goals parsed from commentary must reconstruct the
        # final score reported on the scoreboard. A mismatch means the label
        # is wrong, so the match is dropped rather than silently trusted.
        g = goals_of(summary, fx["home"], fx["away"])
        if (sum(1 for _, s in g if s == "HOME") != fx["home_score"] or
                sum(1 for _, s in g if s == "AWAY") != fx["away_score"]):
            bad_label += 1
            continue
        out = build_match(fx, summary, elo)
        for r in out:
            r["league"] = fx.get("league", "eng.1")
        if not out:
            sparse += 1
        rows += out

    df = pd.DataFrame(rows)
    df.to_parquet(os.path.join(PROC, "snapshots.parquet"), index=False)
    print(f"matches used : {df.event_id.nunique()}")
    print(f"snapshots    : {len(df)}")
    print(f"dropped      : {missing} missing, {sparse} sparse, {bad_label} score-mismatch")
    for h in HORIZONS:
        v = df[f"label_{h}"].value_counts(normalize=True).round(3)
        print(f"  {h:2d} min horizon: " +
              "  ".join(f"{k} {v[k]:.3f}" for k in ("NONE", "HOME", "AWAY")))
    print(df.groupby('season').event_id.nunique().to_string())


if __name__ == "__main__":
    main()
