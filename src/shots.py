"""Audit prototype - xG from the words alone.

Parses every shot out of the commentary text, turns the sentence into a
handful of binary fields with regular expressions, and fits the simplest
possible model. This exists to answer one question before any real work is
committed: does the text carry enough to rate a chance at all?
"""
import gzip, glob, json, os, re, sys

ROOT = os.path.join(os.path.dirname(__file__), "..")

# Each pattern is a column. Order matters only for readability.
PATTERNS = {
    "six_yard":      r"six yard box|very close range",
    "centre_box":    r"from the centre of the box",
    "side_box":      r"from the (left|right) side of the box",
    "outside_box":   r"from outside the box",
    "long_range":    r"from a difficult angle and long range|from long range",
    "difficult_ang": r"difficult angle",
    "header":        r"\bheader\b|\bheaded\b",
    "left_foot":     r"left footed",
    "right_foot":    r"right footed",
    "from_cross":    r"with a cross",
    "from_through":  r"with a through ball",
    "after_corner":  r"following a corner|corner kick",
    "after_break":   r"following a fast break",
    "after_setpiece": r"following a set piece routine",
    "assisted":      r"assisted by",
}

# ---------------------------------------------------------------------------
# Removing the outcome from the sentence.
#
# Every shot line has the same shape:
#
#   "Attempt saved. Rashford (Man Utd) right footed shot from the centre of
#    the box is saved in the bottom left corner. Assisted by Bruno Fernandes."
#    ^^^^^^^^^^^^^^ opener states the outcome    ^^^^^^^^ so does the verb
#
# Both halves give the label away. The opener separates goals from non-goals
# perfectly ("Goal!" -> 100%, "Attempt missed/saved/blocked" -> 0%), so a model
# handed the raw sentence scores a perfect AUC and has learned nothing at all.
#
# What is kept is the description that comes *before* the outcome verb, plus
# the assist clause, which is about how the chance was built rather than how it
# ended. tests/test_shot_text_leak.py asserts none of this comes back.
# Blacklisting outcome phrases was tried twice and leaked both times -- the
# words "goal", "converts the penalty" and "hits the left post" all survived
# and a tf-idf model scored 0.82 AUC by reading them. Free text has too many
# ways to say what happened to remove them all.
#
# So this whitelists instead. Only spans matching a known descriptive pattern
# are kept; everything else in the sentence is discarded. Nothing can leak
# that is not explicitly listed here, and each listed phrase is knowable
# before the ball is struck.
#
# Free kicks are deliberately absent. ESPN word a scored direct free kick as
# "X (Team) from a free kick with a right footed shot..." and a missed one as
# "...shot from outside the box ... from a direct free kick" -- different
# phrasing for the same situation, so the phrase that survives whitelisting
# appears only on goals (60 shots, 100% goal rate). The event type leaks the
# same way: scored ones are typed `Goal - Free-kick`, missed ones
# `Shot Off Target`. A free kick simply cannot be identified from this feed
# before its outcome is known, so it is not a feature.
SAFE_SPANS = [
    r"from (the )?(centre|left side|right side|outside) of the box",
    r"from outside the box",
    r"from the (six yard box|centre of the box)",
    r"from a difficult angle( and long range)?",
    r"from (very )?close range",
    r"from long range",
    r"(right|left) footed shot",
    r"\bheader\b",
    r"assisted by [a-zà-ÿ' .-]+? with (a cross|a through ball|a headed pass|"
    r"an aerial pass)",
    r"assisted by",
    r"following a (corner|fast break|set piece situation)",
    r"after a corner",
]
SAFE = re.compile("|".join(f"({p})" for p in SAFE_SPANS), re.I)


def strip_outcome(text):
    """Keep only whitelisted descriptive spans, in the order they appear."""
    if not text:
        return ""
    return " ".join(m.group(0).lower() for m in SAFE.finditer(text))


GOAL_TYPES = {"Goal", "Goal - Header", "Goal - Volley", "Goal - Free-kick",
              "Penalty - Scored", "Own Goal"}
SHOT_TYPES = {"Shot On Target", "Shot Off Target", "Shot Blocked",
              "Shot Hit Woodwork", "Penalty - Saved", "Penalty - Missed",
              "Penalty - Hit Woodwork"} | GOAL_TYPES


def shots_from_summary(summary, event_id=None, season=None):
    """Every shot in one match summary, as feature rows.

    Shared by the offline parser and the live path, for the same reason
    snapshots.features_at is shared: two copies of this drift, and then
    training and serving disagree about what a shot is.
    """
    head = summary.get("header", {}).get("competitions", [{}])[0]
    teams = {c["homeAway"]: c["team"]["displayName"]
             for c in head.get("competitors", [])}
    if len(teams) != 2:
        return []
    rows = []
    for e in summary.get("commentary", []):
        play = e.get("play") or {}
        ty = (play.get("type") or {}).get("text", "")
        if ty not in SHOT_TYPES:
            continue
        team = (play.get("team") or {}).get("displayName")
        if not team:
            continue
        txt = strip_outcome(e.get("text") or "").lower()
        row = {"event_id": event_id, "season": season, "team": team,
               "side": "home" if team == teams.get("home") else "away",
               "minute": (e.get("time") or {}).get("value", 0) / 60.0,
               "goal": int(ty in GOAL_TYPES),
               "text_raw": e.get("text", ""),
               "text": strip_outcome(e.get("text", ""))}
        for name, pat in PATTERNS.items():
            row[name] = int(bool(re.search(pat, txt)))
        # The event type carries this reliably; the text does not once the
        # outcome clause is gone.
        row["penalty"] = int("Penalty" in ty or "penalty" in txt)
        rows.append(row)
    return rows


def parse():
    import pandas as pd
    # fixtures.json is authoritative for which competition a match belongs to;
    # the summary payload does not carry it reliably.
    fx_path = os.path.join(ROOT, "data", "fixtures.json")
    leagues = {}
    if os.path.exists(fx_path):
        leagues = {f["event_id"]: f.get("league", "eng.1")
                   for f in json.load(open(fx_path))}
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*.json.gz"))):
        eid = os.path.basename(f).split(".")[0]
        d = json.load(gzip.open(f, "rt"))
        new = shots_from_summary(
            d, event_id=eid,
            season=(d.get("header", {}).get("season", {}) or {}).get("year"))
        for r in new:
            r["league"] = leagues.get(eid, "eng.1")
        rows += new
    return pd.DataFrame(rows)


def main():
    import pandas as pd
    df = parse()
    out = os.path.join(ROOT, "data", "proc", "shots.parquet")
    df.to_parquet(out, index=False)
    print(f"shots parsed : {len(df):,}")
    print(f"goals        : {df.goal.sum():,}  ({df.goal.mean():.1%})")
    print(f"seasons      : {sorted(df.season.dropna().unique().tolist())}")
    if "league" in df and df.league.nunique() > 1:
        print("by competition:")
        for lg, g in df.groupby("league"):
            print(f"  {lg:8s} {len(g):7,} shots  {g.goal.mean():5.1%} goals  "
                  f"{g.event_id.nunique():4d} matches")
    print()
    print("goal rate by parsed field")
    for c in PATTERNS:
        m = df[df[c] == 1]
        if len(m) > 100:
            print(f"  {c:15s} n={len(m):6,}  goal rate {m.goal.mean():6.1%}")
    print(f"  {'(overall)':15s} n={len(df):6,}  goal rate {df.goal.mean():6.1%}")
    print()
    print("outcome stripped from the text -- before and after")
    for a, b in zip(df.text_raw.head(3), df.text.head(3)):
        print(f"  raw  : {a[:88]}")
        print(f"  kept : {b[:88]}\n")


if __name__ == "__main__":
    main()
