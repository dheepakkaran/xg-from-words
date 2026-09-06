"""Every headline number in the paper must still be the number in the artefact.

docs/ already has this guard: test_page_numbers_are_not_hardcoded.py exists
because the site once displayed 90.1% for three days after a refit produced
90.6%. The paper had no equivalent, and a paper is worse to get wrong than a
web page -- it is a fixed version with a DOI on it, and a reader has no way to
tell that a figure has drifted from the pipeline that produced it.

This checks in both directions: the artefact still holds the value, and the
paper still contains it. A refit that changes a number now fails here rather
than being noticed by a reader.

Values are compared as the formatted strings the paper prints, because that is
what a reader sees; comparing floats would pass on a number the paper rounds
differently.
"""
import json
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
TEX = os.path.join(ROOT, "paper", "paper.tex")


def load(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        pytest.skip(f"{rel} not built")
    return json.load(open(p))


@pytest.fixture(scope="module")
def tex():
    if not os.path.exists(TEX):
        pytest.skip("paper not present")
    return open(TEX, encoding="utf-8").read()


def cases():
    """(label, printed form, artefact, path through it, format)."""
    return [
        ("auc ours",        "reports/recovery_ci.json", ["auc_ours"], "{:.4f}"),
        ("auc statsbomb",   "reports/recovery_ci.json", ["auc_statsbomb"], "{:.4f}"),
        ("auc gap",         "reports/recovery_ci.json", ["auc_gap"], "{:.4f}"),
        ("held-out auc",    "models/xg.meta.json", ["auc"], "{:.4f}"),
        ("held-out brier",  "models/xg.meta.json", ["brier"], "{:.4f}"),
        ("n train",         "models/xg.meta.json", ["n_train"], "{:,}"),
        ("n test",          "models/xg.meta.json", ["n_test"], "{:,}"),
        ("joined shots",    "reports/recovery_ci.json", ["n_shots"], "{:,}"),
        ("joined matches",  "reports/recovery_ci.json", ["n_matches"], "{}"),
        ("agreement r",     "reports/head_to_head_xg.json",
                            ["agreement", "correlation"], "{:.3f}"),
        ("mean abs diff",   "reports/head_to_head_xg.json",
                            ["agreement", "mean_abs_diff"], "{:.3f}"),
        ("recalibrated %",  "models/xg.shift.json",
                            ["evidence", "recalibrated_over_pct"], "{:.1f}"),
        ("shots evaluated", "models/xg.shift.json",
                            ["evidence", "n_evaluated"], "{:,}"),
        ("wallclock sd",    "reports/wallclock_check.json",
                            ["within_match_sd_seconds", "median"], "{:.2f}"),
    ]


@pytest.mark.parametrize("label,rel,path,fmt",
                         cases(), ids=[c[0] for c in cases()])
def test_paper_number_matches_artefact(tex, label, rel, path, fmt):
    v = load(rel)
    for k in path:
        v = v[k]
    printed = fmt.format(v)
    assert printed in tex, (
        f"the paper does not contain {printed} for '{label}'. The artefact "
        f"{rel} says {printed}; either the pipeline was re-run and the paper "
        f"was not updated, or the paper rounds it differently.")


def test_recovery_and_interval_are_in_the_paper(tex):
    """The headline, which is a ratio and a bootstrap interval rather than a
    field lifted straight out of a JSON file."""
    c = load("reports/recovery_ci.json")
    lo, hi = c["recovery_ci95"]
    for s in (f"{100*c['recovery']:.1f}", f"{100*lo:.1f}", f"{100*hi:.1f}"):
        assert s in tex, f"headline component {s} missing from the paper"
