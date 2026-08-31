"""No result may be typed into the page.

The headline sat at 90.1% for two commits after the result moved to 90.6%,
because it was a literal in the markup: `data-count="0.901"`. Nothing failed --
the page was simply wrong, and stayed wrong until someone read it.

So every figure on the page has to come from docs/data.json, which
src/site_data.py generates from the results. This checks two things: that the
paths the markup asks for actually exist in the data, and that no
result-shaped number is sitting loose in the prose where it can rot.
"""
import json
import os
import re

import pytest

HERE = os.path.dirname(__file__)
HTML = os.path.join(HERE, "..", "docs", "index.html")
DATA = os.path.join(HERE, "..", "docs", "data.json")

# Prose legitimately contains these: they are definitions, not measurements.
# 0.50 is what a coin toss scores and 1.00 what a perfect model would; 0.05 is
# the tie threshold in the scoring; 0.15 the gap below which a match is too
# close to call. None of them move when a model is refitted.
ALLOWED = {"0.50", "1.00", "0.05", "0.15"}


@pytest.fixture(scope="module")
def page():
    if not (os.path.exists(HTML) and os.path.exists(DATA)):
        pytest.skip("no built page")
    return open(HTML).read(), json.load(open(DATA))


def resolve(data, path):
    cur = data
    for key in path.split("."):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def test_every_requested_path_exists_in_the_data(page):
    html, data = page
    paths = set(re.findall(r'data-(?:fill|count)="([a-z_.]+)"', html))
    assert paths, "no data-driven figures found; has the markup changed?"
    missing = sorted(p for p in paths if resolve(data, p) is None)
    assert not missing, (
        f"the page asks for {missing}, which site_data.py does not produce")


def test_no_loose_result_numbers_in_the_prose(page):
    html, _ = page
    # Strip the elements that are meant to hold a figure, and every attribute,
    # then look for what is left in the visible text.
    body = re.sub(r'<(strong|b|span|div)[^>]*data-(fill|count)="[^"]*"[^>]*>'
                  r'.*?</\1>', "", html, flags=re.S)
    body = re.sub(r"<[^>]+>", " ", body)
    loose = {n for n in re.findall(r"\b\d\.\d{2,4}\b", body)} - ALLOWED
    assert not loose, (
        f"result-shaped numbers typed into the prose: {sorted(loose)}. "
        f"Move them into docs/data.json and reference them with data-fill, or "
        f"add them to ALLOWED if they are definitions rather than results.")


def test_the_headline_matches_the_validation_it_claims(page):
    html, data = page
    m = re.search(r'data-count="([a-z_.]+)"', html)
    assert m, "the hero figure is not data-driven"
    v = resolve(data, m.group(1))
    ours, theirs = data["validation"]["ours"], data["validation"]["theirs"]
    expected = round((ours - 0.5) / (theirs - 0.5), 3)
    assert abs(v - expected) < 1e-9, (
        f"the page shows {v:.1%} but {ours} against {theirs} is {expected:.1%}")
