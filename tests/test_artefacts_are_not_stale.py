"""Does anything in the pipeline predate what it was built from?

The pipeline has an order, and nothing was enforcing it. Three things broke in
one day for exactly that reason: a committed test fixture predated the leagues
that had been added, so CI passed while the suite failed locally; an embeddings
cache predated a parser change, so retrieval ran on stale vectors; and
docs/data.json predated a refit, so the page showed 90.1% when the result was
90.6%.

None of those raised an error. Each one silently served an old number.

This declares the graph once and checks the timestamps. It is not a build
system -- it will not rebuild anything -- it just refuses to let a stale
artefact pass unnoticed.
"""
import os
import subprocess

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

# artefact -> what it is built from. Scripts count as inputs: editing the
# parser makes everything downstream of it stale.
GRAPH = {
    "data/proc/shots.parquet": ["src/shots.py", "data/fixtures.json"],
    "data/proc/snapshots.parquet": ["src/snapshots.py", "src/strength.py",
                                    "data/fixtures.json"],
    "data/proc/shot_embeddings.npy": ["data/proc/shots.parquet"],
    "data/proc/xg_validation.parquet": ["src/validate_xg.py", "src/xg.py",
                                        "data/proc/shots.parquet"],
    "models/xg.json": ["src/train_xg.py", "src/xg.py",
                       "data/proc/shots.parquet"],
    "models/xg.joblib": ["src/train_xg.py", "data/proc/shots.parquet"],
    "models/xg.shift.json": ["src/recalibrate.py", "src/xg.py",
                             "data/proc/shots.parquet", "data/fixtures.json"],
    "reports/results.csv": ["src/run_experiment.py", "src/evaluate.py",
                            "data/proc/snapshots.parquet"],
    "reports/head_to_head_xg.json": ["src/head_to_head.py",
                                     "data/proc/xg_validation.parquet"],
    "tests/fixtures/shots_sample.parquet": ["data/proc/shots.parquet"],
    "docs/data.json": ["src/site_data.py", "data/proc/shots.parquet",
                       "reports/results.csv",
                       "data/proc/xg_validation.parquet",
                       "reports/head_to_head_xg.json"],
    "docs/scorecard.json": ["src/scorecard.py", "models/xg.json",
                            "models/xg.shift.json"],
    "writing/cover.png": ["writing/cover.py", "docs/data.json"],
    "reports/recovery_ci.json": ["src/recovery_ci.py",
                                 "data/proc/xg_validation.parquet"],
    "reports/error_analysis.json": ["src/error_analysis.py", "src/xg.py",
                                    "data/proc/xg_validation.parquet"],
    "paper/fig1_schematic.pdf": ["paper/figures.py",
                                 "data/proc/xg_validation.parquet"],
    "paper/fig2_reliability.pdf": ["paper/figures.py",
                                   "data/proc/xg_validation.parquet"],
    "paper/fig3_drift.pdf": ["paper/figures.py", "data/proc/shots.parquet"],
}

# Enough slack that a rebuild finishing seconds apart is not flagged, and that
# a fresh git clone -- which writes every file at once -- does not fail.
SLACK_SECONDS = 120


def mtime(rel):
    p = os.path.join(ROOT, rel)
    return os.path.getmtime(p) if os.path.exists(p) else None


def in_git_checkout_only():
    """A clone has no data/, so there is nothing meaningful to compare."""
    return not os.path.isdir(os.path.join(ROOT, "data", "proc"))


@pytest.mark.parametrize("artefact", sorted(GRAPH))
def test_artefact_is_newer_than_its_inputs(artefact):
    if in_git_checkout_only():
        pytest.skip("no built data in this checkout")
    made = mtime(artefact)
    if made is None:
        pytest.skip(f"{artefact} has not been built")

    stale = [(src, mtime(src)) for src in GRAPH[artefact]
             if mtime(src) is not None and mtime(src) - made > SLACK_SECONDS]
    assert not stale, (
        f"{artefact} is older than "
        + ", ".join(f"{s} (by {(t - made) / 60:.0f} min)" for s, t in stale)
        + ". Rebuild it -- see ./rebuild.sh -- or the number it serves is a "
          "number from before the change.")


def test_the_graph_names_files_that_exist_in_the_repo():
    """A path that has been renamed makes its edge silently unenforced."""
    tracked = set(subprocess.run(["git", "ls-files"], cwd=ROOT,
                                 capture_output=True, text=True
                                 ).stdout.split())
    if not tracked:
        pytest.skip("not a git checkout")
    missing = [p for deps in GRAPH.values() for p in deps
               if p.startswith("src/") and p not in tracked]
    assert not missing, f"the graph refers to scripts that no longer exist: {missing}"
