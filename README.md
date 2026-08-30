# Reading the game

**Two questions about football commentary, asked in order. The first one
failed, and the failure is what pointed at the second.**

---

## 1. Does commentary predict the *next goal*? — No.

Four Premier League seasons, 22,147 snapshots, time-based folds:

* the **numbers beat the words** in every fold and at every horizon (5/10/15/30 min);
* **neither beats simply quoting the base rate**;
* a model already **shown the next fifteen minutes** reaches only 0.60 AUC — so
  the counted events, at 0.54, capture 40% of everything a crystal ball could;
* **knowing which two teams are playing** (Elo, 0.559) beats every in-match
  feature combined;
* the skill splits — *who* scores is predictable at 0.64, *whether* anyone
  scores is not (0.52), and the live worklist asks the second question.

**The target is nearly noise.** Not a weak model of a rich signal — a good
model of almost nothing. [reports/FINDINGS.md](reports/FINDINGS.md).

## 2. Does it say how good a *chance* was? — Yes, to within 9%.

Measuring the first question turned up something else: foul and corner
commentary is templated (41 templates across 16,864 lines), but shot commentary
is not (1,045 across 3,499). The words describe body part, zone and build-up —
which is what an expected-goals model is made of.

So: rate a shot from its sentence, and check it against a model built on real
coordinates.

| Model | Input | AUC |
|---|---|---|
| **ours** | one English sentence | **0.7810** |
| StatsBomb | shot coordinates, 16 player positions, freeze frames | 0.8118 |

```
8,825 shots, both sources describing the same events
words recover 90.1% of the coordinate model's discrimination above chance
means agree to 0.001: ours 0.097, theirs 0.098
```

Trained on 2022-25, evaluated on **2015-16** — a decade outside the training
window, a different era and a different commentary team.

**Why it matters:** coordinate data is commercial. StatsBomb's open Premier
League coverage is two seasons ten years apart. Commentary is free, keyless,
and published for far more competitions than coordinates are.

### It nearly didn't work

Every shot line opens by stating the outcome — `Goal!` is 100% goals,
`Attempt missed/saved/blocked` is 0%. Raw text scores **1.0000 AUC** and has
learned nothing. Three rounds of filtering read correctly by eye and **all three still
leaked** — the second was caught by printing coefficients and finding `goal`
weighted at +7.99; the third by noticing that a retrieved shot's forty nearest
neighbours were all goals, because ESPN word a scored free kick differently
from a missed one.

That is why the leak test is behavioural rather than cosmetic, why a companion
test asserts the raw text *still* leaks so the ceiling cannot pass vacuously,
and why the third check asks the data — flagging any phrase that converts above
80% — instead of trusting a list of words someone thought of in advance. Full working: [reports/AUDIT.md](reports/AUDIT.md).

### Retrieval: the same number with its evidence attached

`src/retrieve.py` indexes every shot's sentence in Qdrant and answers a new
shot with its forty nearest neighbours from *earlier seasons only*.

```
trained model (regex fields)   AUC 0.7688   brier 0.0846
neighbour goal rate (Qdrant)   AUC 0.7603   brier 0.0859
average of the two             AUC 0.7724   brier 0.0832
agreement between the two      r = 0.810
```

A faithful second opinion, and a small ensemble gain. It also pays for itself
in a way a metric does not show: **the fourth leak above was found by reading a
retrieval example**, not by a test.

```
shot : "right footed shot from very close range following a fast break"
model says 84%, 26/40 similar past shots were goals (65%)
```

Qdrant runs embedded (`QdrantClient(path=...)`) because the Docker daemon here
belongs to another account. Only the constructor changes for a server.

---

The design for question 1 is in [PROPOSAL.md](PROPOSAL.md). Stages 1–4 are
implemented; Stages 5–9 (Spark, Qdrant, vLLM, LangGraph, C++ poller, Kubeflow)
are not, and the result above is the reason to think hard before building them.

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

./run.sh src/shots.py            # -> data/proc/shots.parquet, 47k shots
./run.sh src/xg.py               # xG from the words, held-out season
./run.sh src/validate_xg.py      # the join against StatsBomb -> 90.1%
./run.sh src/retrieve.py         # Qdrant neighbours + second opinion
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
| `src/shots.py` | Shots parsed out of commentary; whitelists the safe spans |
| `src/xg.py` | The xG model, and the size of the leak if the text is left raw |
| `src/validate_xg.py` | Joins ESPN 2015/16 to StatsBomb, shot by shot |
| `src/retrieve.py` | Qdrant neighbours: the estimate with its evidence |
| `tests/test_leakage.py` | Asserts no feature at minute *M* can see past *M*, and that the diagnostics that *should* see it do |
| `tests/test_shot_text_leak.py` | Asserts the shot outcome never returns to the text |

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
