# MomentumRadar

Does the language of live football commentary predict the next goal better than
the event counts do?

**No** — and the more interesting part is *how little* anything predicts it.

Over four Premier League seasons and 22,147 snapshots:

* the **numbers beat the words** in every fold and at every horizon (5/10/15/30 min);
* **neither beats simply quoting the base rate**;
* a model that has already **watched the next fifteen minutes** only reaches
  0.60 AUC — so the counted events, at 0.54, already capture 40% of everything
  a crystal ball could;
* **knowing which two teams are playing** (Elo, 0.559) beats every in-match
  feature combined;
* and the skill splits: *who* scores is predictable at 0.64 AUC, *whether*
  anyone scores is not (0.52) — and the live worklist asks the second question.

Read [reports/FINDINGS.md](reports/FINDINGS.md).

The design is in [PROPOSAL.md](PROPOSAL.md). Stages 1–4 of it are implemented
here; Stages 5–9 (Spark, Qdrant, vLLM, LangGraph, C++ poller, Kubeflow) are not,
and the result above is the reason to think hard before building them.

## Run it

```
python3 -m venv venv && ./venv/bin/pip install -r requirements.txt
./run.sh src/collect.py          # ~25 min, 54 MB, resumable
./run.sh src/snapshots.py        # -> data/proc/snapshots.parquet
./run.sh -m pytest tests/ -q     # leakage regression tests
./run.sh src/run_experiment.py   # -> reports/*.csv
for h in 5 10 30; do ./run.sh src/run_experiment.py --horizon $h \
  --only "0.,1.,A.,A+E,E.,B-tfidf. last 10,C.,C+."; done
./run.sh src/plots.py            # -> reports/*.png
./run.sh src/train_final.py      # -> models/track_a.joblib
./run.sh src/live.py             # the live worklist
```

`run.sh` exists because the macOS xgboost wheel hard-codes an rpath to
Homebrew's `libomp`, which is not installed on this machine; the wrapper puts a
copy from the torch wheel on the loader path. On a machine with
`brew install libomp`, `./venv/bin/python` works directly.

## Layout

| Path | What |
|---|---|
| `src/collect.py` | ESPN fixtures + match summaries, gzipped one file per match |
| `src/snapshots.py` | Raw JSON → labelled snapshots. `features_at` is shared with the live path |
| `src/check_commentary.py` | Is the commentary written or templated? |
| `src/strength.py` | Elo, built chronologically and read before kickoff |
| `src/evaluate.py` | Metrics and the time-based folds |
| `src/significance.py` | Paired bootstrap, resampling matches not rows |
| `src/text_head.py` | Track B's PyTorch head over frozen embeddings |
| `src/run_experiment.py` | The comparison |
| `src/train_final.py` | Ships `models/track_a.joblib` (counts + Elo) with its data window |
| `src/live.py` | The ranked worklist, and the commentary-latency probe |
| `tests/test_leakage.py` | Asserts no feature at minute *M* can see past *M*, and that the diagnostics that *should* see it do |

## The live worklist

```
./run.sh src/live.py --interval 60
```

```
19:48:27  goal in next 15 min
1. 39.6%  AFC Bournemouth v Everton              1-1  90'  (home 22% / away 17%)  commentary lag 28597s
      Second Half ends, Bournemouth 1, Everton 1.
```

It runs, it is calibrated, and — per the findings — its ranking is close to
indistinguishable from random. That is the result, not a bug.

## Things worth knowing about the data source

* ESPN returns **403 for browser-like User-Agent strings** on this host. The
  default `requests` UA works. Do not "fix" the collector by adding a Chrome UA.
* The `odds[]` block on a completed match is **settled**, not pre-match. It
  predicts the final result with ~100% confidence. It is leakage, and the
  leakage test zeroes it.
* `boxscore.teams[].statistics` is full-match totals only — no per-minute
  values, so nothing in it is available at minute *M*.
