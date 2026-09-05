"""Every JSON file in the repository must parse.

This exists because one did not. A workflow step stashed the live files,
pulled with `--autostash`, and popped; `git pull ... || true` swallowed a
failed rebase, so the autostash was never restored and the explicit pop
applied the wrong one. Git wrote conflict markers into docs/scorecard.json,
the next run's `git add docs/scorecard.json` committed them, and the workflow
then failed on every subsequent run because scorecard.py reads that file back.

Nothing caught it. The file is not imported by any test, CI does not parse the
site's data, and the failure surfaced only as a red badge on a workflow nobody
was watching. A machine-written file committed by a robot is exactly the kind
that no human reads before it lands.

The check is trivial and would have failed on the commit that introduced it.
"""
import json
import os
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

# Conflict markers at the start of a line. `=======` alone appears in ordinary
# text, so it is only a marker in the company of the other two.
MARKERS = ("<<<<<<< ", ">>>>>>> ")


def tracked_json():
    try:
        out = subprocess.check_output(["git", "ls-files", "*.json"], cwd=ROOT,
                                      stderr=subprocess.DEVNULL).decode()
    except Exception:
        pytest.skip("not a git checkout")
    return sorted(p for p in out.split("\n") if p.strip())


@pytest.mark.parametrize("rel", tracked_json())
def test_committed_json_parses(rel):
    p = os.path.join(ROOT, rel)
    if not os.path.exists(p):
        pytest.skip(f"{rel} not present")
    raw = open(p, encoding="utf-8").read()
    for m in MARKERS:
        assert m not in raw, (
            f"{rel} contains a git conflict marker. A merge or stash was "
            f"resolved by committing the conflict.")
    try:
        json.loads(raw)
    except json.JSONDecodeError as e:
        pytest.fail(f"{rel} is not valid JSON: {e}")


def test_jsonl_lines_parse():
    """The latency log is one JSON object per line, not a JSON document."""
    p = os.path.join(ROOT, "reports", "latency.jsonl")
    if not os.path.exists(p):
        pytest.skip("no latency log yet")
    for i, line in enumerate(open(p), 1):
        if line.strip():
            json.loads(line)          # raises with the line number in context
