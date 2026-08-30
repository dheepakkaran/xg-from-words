"""The regression test the project actually depends on.

Leakage is the failure mode most likely to invalidate this work: a feature
computed over the full match encodes the answer, the offline score looks
excellent, and the live model is worthless. So it is defended by a test
rather than by care.

The test truncates a real match at minute M, rebuilds the features from the
truncated data, and asserts every feature at minute M is bit-identical to the
one built from the full match. Any feature that can see past M fails here.
"""
import glob, gzip, json, os, sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import snapshots as S

HERE = os.path.dirname(__file__)
# Prefer the full collected dataset; fall back to the handful of matches
# committed under tests/fixtures so these run in CI without a 900 MB download.
_full = os.path.join(HERE, "..", "data", "fixtures.json")
if os.path.exists(_full):
    RAW = os.path.join(HERE, "..", "data", "raw")
    FIXTURES = _full
else:
    RAW = FIXTURES_DIR = os.path.join(HERE, "fixtures")
    FIXTURES = os.path.join(HERE, "fixtures", "fixtures.json")
NON_FEATURE = ({"label", "event_id", "season", "date", "home", "away"} |
               {f"label_{h}" for h in S.HORIZONS})


def is_future_column(k):
    """`fut_*` is the ceiling diagnostic. It is deliberately made of future
    events and is never in a feature list -- see test_future_columns_do_move."""
    return k.startswith("fut_")


def sample_matches(n=5):
    fx = {f["event_id"]: f for f in json.load(open(FIXTURES))}
    out = []
    for p in sorted(glob.glob(os.path.join(RAW, "*.json.gz")))[:400]:
        eid = os.path.basename(p).split(".")[0]
        if eid not in fx:
            continue
        d = json.load(gzip.open(p, "rt"))
        if len(d.get("commentary", [])) > 60 and len(S.goals_of(
                d, fx[eid]["home"], fx[eid]["away"])) >= 2:
            out.append((fx[eid], d))
        if len(out) == n:
            break
    return out


def truncate(summary, M):
    """Everything the live system would not yet have seen at minute M."""
    keep = lambda mn: mn is not None and mn <= M
    out = dict(summary)
    out["commentary"] = [
        e for e in summary.get("commentary", [])
        if keep(S.minute_of(e.get("time", {}).get("displayValue"),
                            e.get("time", {}).get("value")))]
    out["keyEvents"] = [
        e for e in summary.get("keyEvents", [])
        if keep(S.minute_of(e.get("clock", {}).get("displayValue"),
                            e.get("clock", {}).get("value")))]
    out["boxscore"] = {}     # full-match totals; never available live
    out["odds"] = []         # settled odds; see reports/FINDINGS.md
    return out


@pytest.mark.parametrize("idx", range(5))
def test_features_do_not_see_the_future(idx):
    matches = sample_matches()
    if idx >= len(matches):
        pytest.skip("not enough collected matches")
    fx, full = matches[idx]
    rows_full = {r["minute"]: r for r in S.build_match(fx, full)}
    assert rows_full, "no snapshots built"

    compared = 0
    for M in S.MINUTES:
        if M not in rows_full:
            continue
        rows_trunc = {r["minute"]: r
                      for r in S.build_match(fx, truncate(full, M))}
        if M not in rows_trunc:
            continue          # early minutes can fall under the sparsity guard
        compared += 1
        a, b = rows_full[M], rows_trunc[M]
        for k in a:
            if k in NON_FEATURE or is_future_column(k):
                continue
            assert a[k] == b[k], (
                f"feature '{k}' at minute {M} changed when the future was "
                f"removed: {a[k]!r} (full) vs {b[k]!r} (truncated) -- leakage")
    assert compared >= 5, f"only {compared} minutes compared; test too weak"


def test_label_only_looks_forward():
    """The label must change when the future is removed. If it does not, the
    truncation above is not actually removing anything and the test is vacuous."""
    matches = sample_matches(1)
    if not matches:
        pytest.skip("no collected matches")
    fx, full = matches[0]
    rows_full = {r["minute"]: r for r in S.build_match(fx, full)}
    changed = False
    for M in S.MINUTES:
        if M not in rows_full:
            continue
        tr = {r["minute"]: r for r in S.build_match(fx, truncate(full, M))}
        if M in tr and tr[M]["label"] != rows_full[M]["label"]:
            changed = True
    assert changed, "labels never changed under truncation -- test is vacuous"


def test_horizon_and_sampling_are_disjoint_from_features():
    assert S.HORIZON == 15
    assert max(S.MINUTES) + S.HORIZON <= 95


def test_future_columns_do_move():
    """The `fut_*` diagnostic columns must change under truncation.

    If they did not, they would not actually be built from future events, and
    the ceiling number they produce would be meaningless.
    """
    matches = sample_matches(1)
    if not matches:
        pytest.skip("no collected matches")
    fx, full = matches[0]
    rows_full = {r["minute"]: r for r in S.build_match(fx, full)}
    moved = 0
    for M in S.MINUTES:
        if M not in rows_full:
            continue
        tr = {r["minute"]: r for r in S.build_match(fx, truncate(full, M))}
        if M not in tr:
            continue
        if any(rows_full[M][k] != tr[M][k]
               for k in rows_full[M] if is_future_column(k)):
            moved += 1
    assert moved >= 5, f"fut_* columns changed at only {moved} minutes"


def test_elo_is_not_a_future_column():
    """Elo is read before kickoff, so truncating the match must not move it."""
    matches = sample_matches(1)
    if not matches:
        pytest.skip("no collected matches")
    fx, full = matches[0]
    a = S.build_match(fx, full)[0]
    b = S.build_match(fx, truncate(full, S.MINUTES[-1]))[0]
    assert a["elo_home"] == b["elo_home"] and a["elo_away"] == b["elo_away"]
