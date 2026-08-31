"""The headline measurement: how much of a coordinate xG model do the words
recover?

StatsBomb release Premier League 2015/16 openly, with a true shot location, a
freeze frame of every player, and their own xG for each shot. ESPN publish a
commentary sentence for the same shots. Joining them is the only way to answer
the question this project exists for.

The join is deliberately conservative -- a shot pairs only when the match, the
team and the minute all agree. An unmatched shot is dropped rather than
guessed at.
"""
import difflib, json, os, sys, urllib.request
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, log_loss, brier_score_loss

ROOT = os.path.join(os.path.dirname(__file__), "..")
SB = "https://raw.githubusercontent.com/statsbomb/open-data/master/data/"
CACHE = os.path.join(ROOT, "data", "statsbomb")
SEASON = "2015-16"
sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS, xg_model


def fetch(path):
    local = os.path.join(CACHE, path.replace("/", "_"))
    if os.path.exists(local):
        return json.load(open(local))
    os.makedirs(CACHE, exist_ok=True)
    d = json.load(urllib.request.urlopen(SB + path, timeout=90))
    json.dump(d, open(local, "w"))
    return d


def statsbomb_shots():
    """Every shot StatsBomb record for PL 2015/16."""
    comps = fetch("competitions.json")
    c = [x for x in comps if x["competition_name"] == "Premier League"
         and x["season_name"] == "2015/2016"][0]
    matches = fetch(f"matches/{c['competition_id']}/{c['season_id']}.json")
    rows = []
    for i, m in enumerate(matches, 1):
        try:
            ev = fetch(f"events/{m['match_id']}.json")
        except Exception as e:
            print(f"  skip {m['match_id']}: {e}", flush=True)
            continue
        for e in ev:
            if e["type"]["name"] != "Shot":
                continue
            s = e["shot"]
            rows.append({
                "sb_match": m["match_id"],
                "date": m["match_date"],
                "home": m["home_team"]["home_team_name"],
                "away": m["away_team"]["away_team_name"],
                "team": e["team"]["name"],
                "minute": e["minute"] + 1,   # ESPN rounds up; StatsBomb floors
                "sb_xg": s["statsbomb_xg"],
                "sb_goal": int(s["outcome"]["name"] == "Goal"),
                "sb_body": s["body_part"]["name"],
                "sb_x": e["location"][0], "sb_y": e["location"][1],
            })
        if i % 60 == 0:
            print(f"  statsbomb {i}/{len(matches)} matches", flush=True)
    return pd.DataFrame(rows)


def main():
    ours = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    fx = {f["event_id"]: f for f in
          json.load(open(os.path.join(ROOT, "data", "fixtures.json")))}
    ours = ours[ours.event_id.map(lambda e: fx.get(e, {}).get("season")) == SEASON]
    if ours.empty:
        raise SystemExit(f"no {SEASON} shots parsed; collect that season first")
    ours = ours.assign(
        date=ours.event_id.map(lambda e: fx[e]["date"][:10]),
        home=ours.event_id.map(lambda e: fx[e]["home"]),
        away=ours.event_id.map(lambda e: fx[e]["away"]))
    print(f"ours      : {len(ours):,} shots over "
          f"{ours.event_id.nunique()} matches")

    sb = statsbomb_shots()
    print(f"statsbomb : {len(sb):,} shots over {sb.sb_match.nunique()} matches")

    # team names differ between the two sources; map once, by closest match
    names = sorted(set(sb.home) | set(sb.away))
    tmap = {n: (difflib.get_close_matches(n, names, 1, 0.55) or [None])[0]
            for n in sorted(set(ours.home) | set(ours.away))}
    unmapped = [k for k, v in tmap.items() if v is None]
    if unmapped:
        print(f"  unmapped team names: {unmapped}")
    for c in ("home", "away", "team"):
        ours[c + "_m"] = ours[c].map(tmap)

    # match-level join on date + both teams
    key = lambda d, h, a: d + "|" + str(h) + "|" + str(a)
    sb["mk"] = [key(d, h, a) for d, h, a in zip(sb.date, sb.home, sb.away)]
    ours["mk"] = [key(d, h, a) for d, h, a in
                  zip(ours.date, ours.home_m, ours.away_m)]
    common = set(sb.mk) & set(ours.mk)
    print(f"matches joined : {len(common)}")

    # shot-level join on match + team + minute (+/- 1)
    pairs = []
    for mk in common:
        o = ours[ours.mk == mk]
        s = sb[sb.mk == mk]
        used = set()
        for _, r in o.iterrows():
            cand = s[(s.team == r.team_m) & (abs(s.minute - r.minute) <= 1)]
            cand = cand[~cand.index.isin(used)]
            if cand.empty:
                continue
            j = (cand.minute - r.minute).abs().idxmin()
            used.add(j)
            pairs.append({**r.to_dict(), **s.loc[j, ["sb_xg", "sb_goal",
                                                    "sb_body", "sb_x", "sb_y"]]})
    p = pd.DataFrame(pairs)
    print(f"shots joined   : {len(p):,} "
          f"({len(p)/min(len(ours), len(sb)):.1%} of the smaller side)")
    print(f"outcome agreement (our goal flag vs StatsBomb's): "
          f"{(p.goal == p.sb_goal).mean():.2%}")

    # our model, trained only on other seasons, scored on these shots
    train = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                         "shots.parquet"))
    train = train[(train.league == "eng.1") & (train.season >= 2022)]
    m = xg_model().fit(train[FIELDS], train.goal)
    p["our_xg"] = m.predict_proba(p[FIELDS])[:, 1]

    print("\n=== the number this project exists for ===")
    print(f"  shots compared            : {len(p):,}")
    print(f"  correlation (our vs their): {p.our_xg.corr(p.sb_xg):.3f}")
    print(f"  rank correlation          : {p.our_xg.corr(p.sb_xg, method='spearman'):.3f}")
    print(f"  mean  ours {p.our_xg.mean():.3f}   theirs {p.sb_xg.mean():.3f}")
    print(f"  MAE                       : {(p.our_xg - p.sb_xg).abs().mean():.3f}")

    print("\n  predicting the same goals, on the same shots")
    for nm, col in (("ours (words)", "our_xg"), ("StatsBomb (coordinates)", "sb_xg")):
        print(f"    {nm:26s} AUC {roc_auc_score(p.sb_goal, p[col]):.4f}   "
              f"logloss {log_loss(p.sb_goal, p[col].clip(1e-6, 1-1e-6)):.4f}   "
              f"brier {brier_score_loss(p.sb_goal, p[col]):.4f}")

    # Rounded to the four decimals actually published, so a reader dividing the
    # two numbers in the table gets the same share printed here.
    a = round(float(roc_auc_score(p.sb_goal, p.our_xg)), 4)
    b = round(float(roc_auc_score(p.sb_goal, p.sb_xg)), 4)
    print(f"\n  words recover {(a-0.5)/(b-0.5):.1%} of the coordinate model's "
          f"discrimination above chance")

    out = os.path.join(ROOT, "data", "proc", "xg_validation.parquet")
    p.to_parquet(out, index=False)
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
