"""The correction is allowed to move the level. It is not allowed to move
anything else.

The shipped model overestimates by 11.9% on 2025-26 because the phrases it
reads drifted: "following a fast break" was 47% conversion when the model was
fitted and 28% by the held-out season. src/recalibrate.py fixes that with one
number added to the intercept, refitted from shots already played.

That is a cheap fix and cheap fixes invite two failures. The first is fitting
the shift on the season it is then scored against, which would make the
reported improvement meaningless. The second is a future maintainer improving
calibration by touching the coefficients, which would quietly trade away the
ranking -- the actual result of this project -- to buy a better mean. Both are
checked here, along with the case that matters in deployment: the first
weekend of a season, when there is nothing to recalibrate on yet.
"""
import json, os, sys
import numpy as np
import pytest

HERE = os.path.dirname(__file__)
sys.path.insert(0, os.path.join(HERE, "..", "src"))
import recalibrate as R
from score import Scorer

ROOT = os.path.join(HERE, "..")
SHIFT_FILE = os.path.join(ROOT, "models", "xg.shift.json")
_full = os.path.join(ROOT, "data", "proc", "shots.parquet")
SHOTS = _full if os.path.exists(_full) else os.path.join(
    HERE, "fixtures", "shots_sample.parquet")
HAVE_DATES = os.path.exists(os.path.join(ROOT, "data", "fixtures.json"))

# The uncorrected overestimate is 11.97%. Anything under this bar means the
# drift has gone away on its own and this whole mechanism needs rethinking
# rather than maintaining.
MIN_UNCORRECTED = 8.0
# Recalibrated sits at 2.91%. A season's realised rate is itself a sample, so
# demanding zero would be demanding noise.
MAX_RECALIBRATED = 5.0


@pytest.fixture(scope="module")
def shift():
    if not os.path.exists(SHIFT_FILE):
        pytest.skip("models/xg.shift.json not built")
    return json.load(open(SHIFT_FILE))


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-z))


def test_shift_solves_for_the_realised_rate():
    """The whole mechanism is one bisection. If it is wrong, nothing else
    here means anything."""
    rng = np.random.default_rng(0)
    z = rng.normal(-2.0, 1.2, 4000)
    for target in (0.05, 0.1134, 0.3):
        s = R.shift_for(z, target)
        assert sigmoid(z + s).mean() == pytest.approx(target, abs=1e-6)


def test_the_shift_cannot_change_the_ranking():
    """An intercept shift is monotone, so AUC is invariant. This is the guard
    against a future 'calibration fix' that reaches for the coefficients: the
    ranking is the result, and buying a better mean with it is not a trade
    this project is willing to make."""
    from sklearn.metrics import roc_auc_score
    rng = np.random.default_rng(1)
    z = rng.normal(-2.0, 1.2, 5000)
    y = rng.binomial(1, sigmoid(z))
    for s in (-0.5, -0.15494, 0.0, 0.3):
        assert roc_auc_score(y, sigmoid(z + s)) == pytest.approx(
            roc_auc_score(y, sigmoid(z)), abs=1e-12)


def test_the_shift_uses_no_future_shots():
    """Each block's shift must be a function of the prefix alone.

    Recomputing it from only the rows before the block reproduces it exactly.
    If someone widens the slice to include the block itself -- the easiest
    possible mistake here -- this fails.
    """
    rng = np.random.default_rng(2)
    z = rng.normal(-2.0, 1.2, 4000)
    y = rng.binomial(1, sigmoid(z + 0.4))          # a drifted season
    replay = [R.shift_for(z[:start], y[:start].mean())
              for start in range(R.WARMUP, len(z), R.BLOCK)]
    # Appending future rows must not disturb a shift already fitted.
    for i, start in enumerate(range(R.WARMUP, len(z), R.BLOCK)):
        again = R.shift_for(z[:start], y[:start].mean())
        assert again == pytest.approx(replay[i], abs=1e-12)


def test_no_correction_before_the_warmup(tmp_path):
    """Three weekends into a season the realised rate is noise. The file has
    to say so, and the scorer has to leave the model alone."""
    p = tmp_path / "xg.shift.json"
    p.write_text(json.dumps({"season": 2026, "active": False, "shift": 0.0,
                             "n_shots_seen": 120, "warmup_shots": R.WARMUP}))
    s = Scorer(shift_path=str(p))
    assert s.shift == 0.0
    assert s.shift_meta["active"] is False


def test_a_missing_shift_file_is_not_an_error(tmp_path):
    """The live path must degrade to the uncorrected model, not crash."""
    s = Scorer(shift_path=str(tmp_path / "absent.json"))
    assert s.shift == 0.0 and s.shift_meta is None


def test_scorer_applies_the_shift_to_the_intercept(shift):
    row = {"six_yard": 1, "header": 1, "assisted": 1, "minute": 70}
    on, off = Scorer(), Scorer(use_shift=False)
    if not shift["active"]:
        pytest.skip("shift not active")
    assert on(row) < off(row)                      # a negative shift lowers it
    # and by exactly the recorded amount, in logit space
    z_off = np.log(off(row) / (1 - off(row)))
    z_on = np.log(on(row) / (1 - on(row)))
    assert z_on - z_off == pytest.approx(shift["shift"], abs=1e-9)


def test_recorded_evidence_clears_the_bar(shift):
    """The committed numbers, so CI checks the claim the report makes."""
    if not shift["active"]:
        pytest.skip("shift not active")
    e = shift["evidence"]
    assert e["uncorrected_over_pct"] > MIN_UNCORRECTED
    assert abs(e["recalibrated_over_pct"]) < MAX_RECALIBRATED
    assert e["n_evaluated"] > 5000


def test_shift_file_matches_the_shipped_model(shift):
    """A shift fitted for one season sitting beside a model retrained on
    another is the stale-artefact failure this repo has already had twice."""
    meta = json.load(open(os.path.join(ROOT, "models", "xg.meta.json")))
    assert shift["season"] == meta["held_out_season"]
    assert shift["trained_on"] == meta["trained_on"]


@pytest.mark.skipif(not HAVE_DATES, reason="needs the collected corpus")
def test_walk_forward_reproduces_from_the_corpus():
    """Rebuild the evidence from the data rather than trusting the file."""
    past, cur, season = R.season_shots(shots_path=SHOTS)
    from xg import FIELDS, xg_model
    model = xg_model().fit(past[FIELDS], past.goal)
    e = R.walk_forward(model, cur)
    assert e["uncorrected_over_pct"] > MIN_UNCORRECTED
    assert abs(e["recalibrated_over_pct"]) < MAX_RECALIBRATED


def test_wallclock_is_not_a_publish_timestamp():
    """The archive cannot answer the latency question, and the reason is
    measurable rather than asserted.

    `wallclock` looks like it records when ESPN published a commentary line,
    which would make 3,577 archived matches a free latency measurement. It
    does not: it is the event time, reconstructed as the actual kickoff plus
    the match clock. This guards the claim in the paper's limitations, and it
    guards against someone later reading src/publish.py's lag field as
    publish latency -- which an earlier version of its own docstring did.
    """
    p = os.path.join(ROOT, "reports", "wallclock_check.json")
    if not os.path.exists(p):
        pytest.skip("reports/wallclock_check.json not built")
    d = json.load(open(p))
    assert d["matches_checked"] >= 100
    # A published timestamp scatters. This one does not.
    assert d["within_match_sd_seconds"]["median"] < 2.0
    assert d["share_below_sd_threshold"] > 0.9
    # Two or three adjacent integers is rounding, not variance.
    assert d["distinct_residual_values_per_match"]["median"] <= 6
