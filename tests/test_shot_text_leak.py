"""The test that has to exist before any modelling.

Every shot's commentary line opens by stating what happened -- "Goal!",
"Attempt missed", "Attempt saved", "Attempt blocked" -- and often repeats it in
the verb ("is saved in the bottom left corner", "hits the left post"). That
text *is* the label. A model handed the raw sentence scores a perfect AUC and
has learned nothing.

Two blacklist attempts at removing it both passed inspection by eye and both
still leaked; the second was only caught by printing model coefficients and
finding `goal` weighted at +7.99. So the check that matters here is
behavioural, not cosmetic: train a model on the stripped text and assert it
*cannot* separate goals too well. That catches a regression no matter which
new phrasing sneaks the outcome back in.
"""
import os, sys
import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import shots as S

HERE = os.path.dirname(__file__)
_full = os.path.join(HERE, "..", "data", "proc", "shots.parquet")
# Same fallback as test_leakage: the committed sample keeps CI honest without
# requiring the collected corpus.
PROC = _full if os.path.exists(_full) else os.path.join(
    HERE, "fixtures", "shots_sample.parquet")

# Words that only ever appear because of how the shot ended.
FORBIDDEN = ["goal", "scored", "converts", "saved", "missed", "misses",
             "blocked", "woodwork", "crossbar", "hits the bar",
             "hits the post", "top left corner", "bottom right corner"]

# A clean model sits near 0.77. The leaking one sits at 1.00. Anything above
# this is the leak coming back, not a modelling breakthrough.
AUC_CEILING = 0.85

# Penalties are the best legitimate feature. They convert at 75% across the
# corpus and 83% in the Premier League alone, so this bar sits above both: a
# phrase confidently converting higher is naming the outcome, not the chance.
LOWER_BOUND = 0.85


def wilson_lower(successes, n, z=1.96):
    """Lower end of a Wilson score interval -- how high the true rate is
    confidently above, given this many observations."""
    import numpy as np
    p = successes / n
    d = 1 + z ** 2 / n
    centre = p + z ** 2 / (2 * n)
    margin = z * np.sqrt(p * (1 - p) / n + z ** 2 / (4 * n ** 2))
    return (centre - margin) / d


@pytest.fixture(scope="module")
def df():
    if not os.path.exists(PROC):
        pytest.skip("run src/shots.py first")
    import pandas as pd
    d = pd.read_parquet(PROC)
    return d[d.season >= 2022]


def test_openers_are_removed():
    cases = [
        ("Attempt missed. Luke Shaw (Manchester United) left footed shot from "
         "the left side of the box misses to the left.", "missed"),
        ("Goal!  Crystal Palace 0, Manchester United 1. Bruno Fernandes "
         "(Manchester United) right footed shot from the centre of the box to "
         "the top right corner.", "goal"),
        ("Attempt saved. Marcus Rashford (Manchester United) right footed shot "
         "from the centre of the box is saved in the bottom left corner.",
         "saved"),
    ]
    for raw, word in cases:
        out = S.strip_outcome(raw).lower()
        assert word not in out, f"'{word}' survived in: {out!r}"
        assert out, "stripping removed everything"


def test_no_forbidden_word_survives_anywhere(df):
    """Not one of 37,000 stripped sentences may contain an outcome word."""
    text = df.text.str.lower()
    offenders = {w: int(text.str.contains(w, regex=False).sum())
                 for w in FORBIDDEN}
    offenders = {w: n for w, n in offenders.items() if n}
    assert not offenders, f"outcome words present in stripped text: {offenders}"


def test_stripped_text_cannot_separate_goals(df):
    """The behavioural check. A clean text model lands near 0.77 AUC."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline

    tr, te = df[df.season < 2025], df[df.season == 2025]
    if len(te) < 500:
        pytest.skip("need a held-out season")
    m = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=5,
                                      sublinear_tf=True),
                      LogisticRegression(max_iter=1000))
    m.fit(tr.text, tr.goal)
    auc = roc_auc_score(te.goal, m.predict_proba(te.text)[:, 1])
    assert auc < AUC_CEILING, (
        f"stripped text reaches {auc:.4f} AUC, above the {AUC_CEILING} ceiling "
        f"-- the outcome has leaked back into the text")


def test_raw_text_does_leak(df):
    """Guards against the test above passing vacuously.

    If the raw sentence stopped leaking, the stripping would be untested and
    the ceiling check meaningless.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import roc_auc_score
    from sklearn.pipeline import make_pipeline

    tr, te = df[df.season < 2025], df[df.season == 2025]
    if len(te) < 500:
        pytest.skip("need a held-out season")
    m = make_pipeline(TfidfVectorizer(ngram_range=(1, 2), min_df=5,
                                      sublinear_tf=True),
                      LogisticRegression(max_iter=1000))
    m.fit(tr.text_raw, tr.goal)
    auc = roc_auc_score(te.goal, m.predict_proba(te.text_raw)[:, 1])
    assert auc > 0.99, (
        f"raw text only reaches {auc:.4f} -- if it no longer leaks, the "
        f"stripping is untested and test_stripped_text... proves nothing")


def test_no_extracted_phrase_is_an_outcome_in_disguise(df):
    """The check that does not rely on me guessing the words.

    A hand-written forbidden list only catches leaks already thought of. It
    missed one: ESPN word a scored direct free kick differently from a missed
    one, so the surviving phrase "from a free kick" appeared on 60 shots and
    every single one was a goal.

    So instead of listing words, this asks the data. Any n-gram converting far
    above the best legitimate feature is not describing a chance, it is naming
    the outcome.

    The bar is a Wilson lower bound rather than the raw rate, because a raw
    rate over a handful of shots is noise. "From very close range following a
    fast break" converts at 81% over 32 shots -- a genuinely excellent chance,
    a tap-in on the break -- and a fixed threshold flags it. Its lower bound is
    0.65, comfortably below a penalty. The free kick leak was 60 from 60, lower
    bound 0.94, and is flagged at any sample size.
    """
    from sklearn.feature_extraction.text import CountVectorizer
    import numpy as np

    v = CountVectorizer(ngram_range=(1, 4), min_df=25, binary=True)
    X = v.fit_transform(df.text)
    y = df.goal.values
    n = np.asarray(X.sum(axis=0)).ravel().astype(float)
    goals = np.asarray(X.T.dot(y)).ravel().astype(float)

    lower = wilson_lower(goals, n)
    names = v.get_feature_names_out()
    suspects = [(names[i], int(n[i]), round(float(goals[i] / n[i]), 3),
                 round(float(lower[i]), 3))
                for i in np.argsort(-lower)[:40]
                if lower[i] > LOWER_BOUND and "penalt" not in names[i]]
    assert not suspects, (
        f"phrases whose conversion is confidently above {LOWER_BOUND:.0%} -- "
        f"these name the outcome rather than describe the chance: "
        f"(phrase, n, rate, lower bound) {suspects[:5]}")


def test_penalties_come_from_the_event_type_not_the_text(df):
    """Penalty is knowable before the kick. It must not be inferred from
    wording that only a converted penalty produces."""
    pens = df[df.penalty == 1]
    assert len(pens) > 100, "too few penalties to check"
    rate = pens.goal.mean()
    assert 0.6 < rate < 0.9, (
        f"penalty conversion is {rate:.1%}; real is ~76%. A rate near 100% "
        f"means the flag is being set by goal-only wording")


def test_committed_fixture_is_not_stale():
    """CI runs against tests/fixtures, and a stale fixture gives a false green.

    That happened: adding five leagues introduced a phrase that failed the
    leak test locally, while CI stayed green because the committed sample
    predated those leagues. A fixture that does not resemble the corpus is not
    testing the corpus.

    This only runs where the full data exists -- in CI there is nothing to
    compare against, and the test skips.
    """
    import pandas as pd
    full = os.path.join(HERE, "..", "data", "proc", "shots.parquet")
    fixture = os.path.join(HERE, "fixtures", "shots_sample.parquet")
    if not (os.path.exists(full) and os.path.exists(fixture)):
        pytest.skip("needs both the corpus and the fixture")

    real = pd.read_parquet(full)
    real = real[real.season >= 2022]
    sample = pd.read_parquet(fixture)

    assert len(sample) == len(real), (
        f"fixture has {len(sample):,} rows, the corpus has {len(real):,}. "
        f"Regenerate it -- see README -- or CI is testing something else.")
    if "league" in real and "league" in sample:
        assert set(sample.league) == set(real.league), (
            "fixture and corpus cover different competitions")


def test_json_model_matches_the_pickled_one():
    """models/xg.json is what the live path scores with; models/xg.joblib is
    what training produced. If they drift, the site and the paper disagree.

    Skips where the pickle is absent -- it is not committed, only the JSON is.

    use_shift=False on purpose: this compares the *fitted* model in two
    formats. models/xg.shift.json is a separately fitted correction that
    the scorer applies on top by default, and it has its own tests in
    test_recalibration.py. Leaving it on here would compare a corrected
    score against an uncorrected one and fail for the wrong reason.
    """
    import numpy as np, pandas as pd
    sys.path.insert(0, os.path.join(HERE, "..", "src"))
    from score import Scorer
    jl = os.path.join(HERE, "..", "models", "xg.joblib")
    js = os.path.join(HERE, "..", "models", "xg.json")
    if not (os.path.exists(jl) and os.path.exists(js) and os.path.exists(PROC)):
        pytest.skip("needs both model files and a sample")
    from joblib import load
    b = load(jl)
    sc = Scorer(js, use_shift=False)
    d = pd.read_parquet(PROC).head(500)
    mine = np.array([sc(r) for r in d.to_dict("records")])
    theirs = b["model"].predict_proba(d[b["features"]])[:, 1]
    assert np.abs(mine - theirs).max() < 1e-4, (
        f"json and pickled model disagree by "
        f"{np.abs(mine - theirs).max():.2e}; rerun src/train_xg.py")


def test_shot_fields_are_not_read_out_of_the_assist(df):
    """How the shot was struck is described before "assisted by"; how the
    chance was made comes after.

    Matching "headed" across the whole sentence called 1,636 footed shots
    headers, because their assist was a headed pass -- and those convert at
    13.8% against a real header's 10.0%, so the flag was quietly carrying two
    different things. Found by tracing one real shot end to end, not by a test,
    which is why there is now a test.
    """
    text = df.text.str.lower()
    bad = text.str.contains("footed shot", regex=False) & (df.header == 1)
    assert bad.sum() == 0, (
        f"{bad.sum()} footed shots flagged as headers, e.g. "
        f"{df[bad].text.head(2).tolist()}")

    foot = df.left_foot.astype(bool) & df.right_foot.astype(bool)
    assert foot.sum() == 0, (
        f"{foot.sum()} shots struck with both feet, e.g. "
        f"{df[foot].text.head(2).tolist()}")
