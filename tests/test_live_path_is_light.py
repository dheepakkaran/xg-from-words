"""The live path must run on requests and nothing else.

The matchday job installs one dependency, which is only true because the
shipped model is plain numbers in models/xg.json and is scored in pure Python
rather than unpickled through sklearn. That is a claim about the code, so it is
checked rather than asserted in a commit message.

An accidental `import pandas` at the top of shots.py would not fail any other
test -- it would fail the job, at kickoff, in three weeks.

The check runs in a subprocess. Hiding pandas by editing sys.modules inside
pytest poisons every other test in the session, which is exactly what happened
on the first attempt.
"""
import os
import subprocess
import sys
import textwrap

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
HEAVY = ["pandas", "numpy", "sklearn", "scipy", "joblib", "torch",
         "sentence_transformers", "qdrant_client", "matplotlib"]

PREAMBLE = f"""
import sys
HEAVY = {HEAVY!r}


class Blocker:
    def find_module(self, name, path=None):
        return self if name.split(".")[0] in HEAVY else None

    def load_module(self, name):
        raise ImportError(name + " is not installed on the matchday runner")


sys.meta_path.insert(0, Blocker())
sys.path.insert(0, {os.path.join(ROOT, 'src')!r})
"""


def run_isolated(body):
    """Run body in a fresh interpreter with the heavy libraries hidden."""
    code = PREAMBLE + textwrap.dedent(body)
    return subprocess.run([sys.executable, "-c", code], capture_output=True,
                          text=True, cwd=ROOT, timeout=120)


def test_publish_imports_without_the_heavy_stack():
    r = run_isolated("import publish; print('ok')")
    assert r.returncode == 0, (
        f"src/publish.py needs more than requests:\n{r.stderr[-900:]}")


def test_the_parser_needs_nothing_heavy_either():
    r = run_isolated("""
        import shots
        rows = shots.shots_from_summary({
            "header": {"competitions": [{"competitors": [
                {"homeAway": "home", "team": {"displayName": "A"}},
                {"homeAway": "away", "team": {"displayName": "B"}}]}]},
            "commentary": [{
                "time": {"value": 1500.0, "displayValue": "25'"},
                "text": ("Goal! A 1, B 0. Someone (A) header from the centre "
                         "of the box. Assisted by Another with a cross."),
                "play": {"type": {"text": "Goal - Header"},
                         "team": {"displayName": "A"}}}]})
        assert len(rows) == 1, rows
        r = rows[0]
        assert r["goal"] == 1, "goal not detected"
        assert r["header"] == 1, "header not detected"
        assert r["centre_box"] == 1, "location not detected"
        assert r["from_cross"] == 1, "assist type not detected"
        assert "goal" not in r["text"].lower(), r["text"]
        print("ok")
    """)
    assert r.returncode == 0, f"src/shots.py:\n{r.stderr[-900:]}"


def test_a_shot_can_be_scored_without_the_heavy_stack():
    if not os.path.exists(os.path.join(ROOT, "models", "xg.json")):
        pytest.skip("run src/train_xg.py first")
    r = run_isolated("""
        from score import Scorer
        sc = Scorer()
        close = sc({"six_yard": 1, "minute": 60})
        far = sc({"outside_box": 1, "minute": 60})
        assert 0 < far < close < 1, (close, far)
        print(f"{close:.3f} {far:.3f}")
    """)
    assert r.returncode == 0, f"src/score.py:\n{r.stderr[-900:]}"
    close, far = (float(x) for x in r.stdout.split())
    assert close > far, (
        f"a six-yard chance scored {close:.3f} against {far:.3f} from outside "
        f"the box; the model has come out the wrong way round")
