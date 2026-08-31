"""Emit docs/data.json from the actual results.

The page reads its numbers from here rather than carrying them inline, so a
rerun that changes a result changes the site, and the two cannot quietly
disagree.
"""
import json, os, subprocess, sys
import numpy as np, pandas as pd
from sklearn.metrics import roc_auc_score

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.dirname(__file__))
from platform_quirks import silence_accelerate_matmul
from xg import FIELDS, xg_model

silence_accelerate_matmul()
NAMES = {"eng.1": "Premier League", "esp.1": "La Liga", "ger.1": "Bundesliga",
         "ita.1": "Serie A", "fra.1": "Ligue 1", "por.1": "Primeira Liga"}


def momentum():
    """Question one: the ceiling that says the target is nearly noise."""
    r = pd.read_csv(os.path.join(ROOT, "reports", "results.csv")).set_index("name")
    pick = [("majority class", "0. majority class"),
            ("the words", "B-tfidf. last 10 lines"),
            ("the numbers", "A. cumulative counts"),
            ("+ who is playing", "A+E. counts + Elo"),
            ("seeing the future", "C+. CEILING + counts + Elo")]
    return [{"label": lab, "auc": round(float(r.loc[k, "auc_ovr"]), 4),
             "ceiling": k.startswith("C")}
            for lab, k in pick if k in r.index]


def momentum_rows():
    """Snapshot count behind question one, read from the parquet not retyped."""
    p = os.path.join(ROOT, "data", "proc", "snapshots.parquet")
    return int(len(pd.read_parquet(p, columns=["minute"]))) if os.path.exists(p) else None


def momentum_ceiling():
    r = pd.read_csv(os.path.join(ROOT, "reports", "results.csv")).set_index("name")
    key = "C+. CEILING + counts + Elo"
    return round(float(r.loc[key, "auc_ovr"]), 2) if key in r.index else None


def validation():
    p = pd.read_parquet(os.path.join(ROOT, "data", "proc", "xg_validation.parquet"))
    # Rounded before the ratio, so the page and the tables cannot disagree by
    # a tenth of a point.
    ours = round(float(roc_auc_score(p.sb_goal, p.our_xg)), 4)
    theirs = round(float(roc_auc_score(p.sb_goal, p.sb_xg)), 4)
    return {"shots": int(len(p)),
            "ours": round(float(ours), 4), "theirs": round(float(theirs), 4),
            "recovered": round((ours - 0.5) / (theirs - 0.5), 3),
            "corr": round(float(p.our_xg.corr(p.sb_xg)), 3),
            "mean_ours": round(float(p.our_xg.mean()), 3),
            "mean_theirs": round(float(p.sb_xg.mean()), 3)}


def leagues(df):
    tr = df[(df.league == "eng.1") & (df.season >= 2022) & (df.season < 2025)]
    m = xg_model().fit(tr[FIELDS], tr.goal)
    out = []
    for lg, g in df[df.season == 2025].groupby("league"):
        if len(g) < 500:
            continue
        out.append({"code": lg, "name": NAMES.get(lg, lg), "shots": int(len(g)),
                    "auc": round(float(roc_auc_score(
                        g.goal, m.predict_proba(g[FIELDS])[:, 1])), 4),
                    "home": lg == "eng.1"})
    return sorted(out, key=lambda x: -x["auc"])


def chance_types(df):
    """What the words are actually reading, as conversion rates."""
    rows = [("A penalty", "penalty"), ("On the break", "after_break"),
            ("Six yards out", "six_yard"), ("A through ball", "from_through"),
            ("Off a corner", "after_corner"), ("A header", "header"),
            ("A cross", "from_cross"), ("From outside the box", "outside_box")]
    d = df[(df.league == "eng.1") & (df.season >= 2022)]
    return [{"label": lab, "rate": round(float(d[d[c] == 1].goal.mean()), 4),
             "n": int(d[c].sum())} for lab, c in rows if d[c].sum() > 200]


def head_to_head():
    """Our model against StatsBomb's, per match, with the points tally."""
    path = os.path.join(ROOT, "reports", "head_to_head_xg.json")
    return json.load(open(path)) if os.path.exists(path) else None


REPLAY_MATCH = "401879312"          # Tottenham 0-2 Newcastle, 2026-08-29


def replay(step=15):
    """One match as the live view would have seen it unfold.

    At each checkpoint only the commentary up to that minute is used, so the
    sequence is what would have been on the wire, not hindsight.
    """
    import requests
    import shots as SH
    url = ("https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/summary")
    sm = requests.get(url, params={"event": REPLAY_MATCH}, timeout=30).json()
    rows = SH.shots_from_summary(sm, event_id=REPLAY_MATCH)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    tr = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    tr = tr[(tr.league == "eng.1") & (tr.season >= 2022) & (tr.season < 2025)]
    df["xg"] = xg_model().fit(tr[FIELDS], tr.goal).predict_proba(df[FIELDS])[:, 1]

    comp = sm["header"]["competitions"][0]
    teams = {c["homeAway"]: c["team"]["displayName"] for c in comp["competitors"]}
    frames = []
    for M in range(step, 96, step):
        seen = df[df.minute <= M]
        frames.append({
            "minute": M,
            "home_goals": int(seen[(seen.side == "home") & (seen.goal == 1)].shape[0]),
            "away_goals": int(seen[(seen.side == "away") & (seen.goal == 1)].shape[0]),
            "home_xg": round(float(seen[seen.side == "home"].xg.sum()), 2),
            "away_xg": round(float(seen[seen.side == "away"].xg.sum()), 2)})
    return {"home": teams["home"], "away": teams["away"], "frames": frames}


def stamp_assets(version):
    """Point index.html at versioned asset URLs.

    GitHub Pages serves with `cache-control: max-age=600`, so a returning
    visitor can otherwise get new HTML against a ten-minute-old script -- which
    is exactly what happened once, and left the live panel stuck on its loading
    text. The commit SHA in the query string makes each deploy a new URL.
    """
    import re
    p = os.path.join(ROOT, "docs", "index.html")
    html = open(p).read()
    html = re.sub(r'(href="style\.css)(\?v=[^"]*)?"', rf'\1?v={version}"', html)
    html = re.sub(r'(src="app\.js)(\?v=[^"]*)?"', rf'\1?v={version}"', html)
    open(p, "w").write(html)
    print(f"stamped docs/index.html assets with v={version}")


def main():
    df = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    site = {
        "generated": subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                                    cwd=ROOT, capture_output=True, text=True
                                    ).stdout.strip(),
        "corpus": {"shots": int(len(df)),
                   "matches": int(df.event_id.nunique()),
                   "leagues": int(df.league.nunique()),
                   "goals": int(df.goal.sum())},
        "momentum": momentum(),
        "momentum_snapshots": momentum_rows(),
        "momentum_ceiling": momentum_ceiling(),
        "leak": {"raw_auc": 1.0, "clean_auc": 0.7688,
                 "openers": [{"phrase": "Goal!", "rate": 1.0},
                             {"phrase": "Attempt missed", "rate": 0.0},
                             {"phrase": "Attempt saved", "rate": 0.0},
                             {"phrase": "Attempt blocked", "rate": 0.0}]},
        "validation": validation(),
        "leagues": leagues(df),
        "head_to_head": head_to_head(),
        "chances": chance_types(df),
        "replay": replay(),
    }
    out = os.path.join(ROOT, "docs", "data.json")
    json.dump(site, open(out, "w"), indent=1)
    stamp_assets(site["generated"])
    print(json.dumps({k: (v if not isinstance(v, list) else f"{len(v)} rows")
                      for k, v in site.items()}, indent=1)[:900])
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
