# MomentumRadar — findings

Stages 1–4 of [PROPOSAL.md](../PROPOSAL.md), run end to end on four completed
Premier League seasons, plus three follow-up experiments that bound the result.

**Answer to the research question:** at minute *M*, the **numbers** win.
Counted events discriminate better than the words that describe them, in every
fold and at every horizon tested.

**And the more useful answer:** the problem is close to unpredictable, and we
can say how close. A deliberately leaky model that has already *watched* the
next fifteen minutes reaches only **0.60 AUC**. Track A reaches 0.54. So the
in-match state is not being modelled badly — there is very little there to
model. Meanwhile **knowing which two teams are playing beats every in-match
feature combined.**

**And the answer that kills the product:** the skill splits cleanly in two.
*Who* scores, given that someone does, is mildly predictable (0.64 AUC).
*Whether* anyone scores in the next fifteen minutes is not (0.52 AUC, and even
the crystal ball only manages 0.56). The live worklist asks exactly the second
question. See §3.6.

---

## 1. What was built

| | |
|---|---|
| Seasons | 2022-23, 2023-24, 2024-25, 2025-26 |
| Fixtures fetched | 1,520 (380 per season, all completed) |
| Matches usable | 1,491 |
| Snapshots | 22,147 — every 5 minutes from minute 10 to 80 |
| Labels | which side scores first in (*M*, *M*+h] for h ∈ {5, 10, 15, 30} |
| Base rates (h=15) | `NONE` 60.9%, `HOME` 21.3%, `AWAY` 17.8% |
| Raw archive | 54 MB of gzipped ESPN JSON, one file per match |

Both tracks are derived from the **same commentary stream**, so the only
variable in the core comparison is the representation:

* **Track A — numbers.** Typed commentary events counted up to *M* (shots on /
  off / blocked, woodwork, corners, fouls, offsides, cards, subs, goals), per
  side and as home−away differences.
* **Track B — words.** The raw text of the last 3 / 10 / 20 commentary lines.

Three further models exist to interpret those two:

* **E — Elo.** A team strength rating built from our own fixture list,
  chronologically, read *before* each match. Nothing in-match.
* **C — the ceiling.** Given the counted events from *inside the label window*
  (excluding the goals themselves). Not a competitor. An upper bound.

## 2. Method

* **Time-based folds only.** Expanding window: train on all earlier seasons,
  test on the next. Tested on 2023-24, 2024-25, 2025-26.
* **Grouping by match, never by row.** Snapshots five minutes apart in the same
  match are heavily correlated.
* **Every model is calibrated** on the most recent 20% of training matches, by
  date. This matters more than it sounds: uncalibrated, the boosted trees lose
  to the base rate on log loss despite ranking better than it. Isotonic
  calibration was tried first and was worse — with three classes it pushes
  probabilities to the bin edges. Platt scaling is what the numbers below use.
* **Significance by paired bootstrap over matches**, 2,000 resamples on the
  most recent season.

## 3. Results

Mean over the three folds, 15-minute horizon.

`auc_any` asks *is a goal coming?* — the product's question. `auc_side` asks
*given one is coming, whose?* — computed on goal rows only.

| Model | log loss | Brier | AUC (OvR) | auc_any | auc_side |
|---|---|---|---|---|---|
| 0. majority class | 0.9439 | 0.5552 | 0.5000 | 0.5000 | 0.5000 |
| 1. clock + scoreline only | 0.9435 | 0.5550 | 0.5233 | 0.5205 | 0.5278 |
| A. cumulative event counts | 0.9409 | 0.5543 | 0.5405 | 0.5076 | 0.5944 |
| A-rec. last-10-min counts | 0.9435 | 0.5556 | 0.5237 | 0.5028 | 0.5612 |
| A+rec. cumulative + recent | 0.9409 | 0.5545 | 0.5362 | 0.5062 | 0.5908 |
| B-tfidf. last 3 lines | 0.9436 | 0.5549 | 0.5122 | 0.5129 | 0.5090 |
| B-tfidf. last 10 lines | 0.9440 | 0.5552 | 0.5132 | 0.5078 | 0.5192 |
| B-tfidf. last 20 lines | 0.9438 | 0.5552 | 0.5067 | 0.5007 | 0.5212 |
| B. last 20 lines, frozen embeddings | 0.9451 | 0.5558 | 0.4974 | 0.5016 | 0.4884 |
| B-mlp. embeddings + PyTorch head | 0.9444 | 0.5555 | 0.5013 | 0.4966 | 0.5046 |
| A+B. counts + embeddings | 0.9441 | 0.5555 | 0.5085 | 0.4995 | 0.5160 |
| E. Elo only | 0.9368 | 0.5524 | 0.5585 | 0.5148 | 0.6268 |
| **A+E. counts + Elo** | **0.9343** | **0.5514** | **0.5647** | 0.5183 | **0.6413** |
| *C. ceiling — sees the window* | *0.9231* | *0.5447* | *0.5970* | *0.5720* | *0.6509* |
| *C+. ceiling + counts + Elo* | *0.9203* | *0.5443* | *0.6016* | *0.5572* | *0.6871* |

Italic rows are diagnostics, not candidates. They use future information by
design.

Per-fold and calibration data: `results_per_fold.csv`, `calibration.png`,
`discrimination.png`, `horizons.png`.

### 3.1 Numbers beat words, and it is not fold noise

Track A's AUC is above chance in **all three folds** (0.540 / 0.548 / 0.533).
No text variant reaches 0.52 in any fold, and the frozen-embedding models sit
at or below chance.

Head to head on the held-out 2025-26 season, bootstrapped over matches:

| Track A minus | AUC gap | 95% CI | numbers win |
|---|---|---|---|
| B-tfidf, last 3 lines | +0.0215 | [−0.0009, +0.0437] | 97% |
| B-tfidf, last 10 lines | +0.0197 | [−0.0045, +0.0440] | 95% |
| B-tfidf, last 20 lines | +0.0393 | [+0.0101, +0.0676] | 100% |
| B, frozen embeddings | +0.0454 | [+0.0197, +0.0697] | 100% |
| B-mlp, PyTorch head | +0.0383 | [+0.0117, +0.0646] | 100% |

The proposal's second outcome row is the one that fired: **commentary is
descriptive, not predictive.** It narrates what the event counts already
capture, and the extra language costs discrimination rather than adding to it.

Two supporting details:

* Concatenating text with counts (`A+B`) is **worse** than counts alone —
  the text is adding variance, not information.
* More text is worse than less. Twenty lines does worse than three. If the
  words carried momentum signal, the opposite would hold.

### 3.2 Almost nothing beats the base rate

Paired bootstrap on 2025-26, log loss versus the majority-class model — lower
is better, so a negative difference means the model won:

| Model | Δ log loss | 95% CI | better in |
|---|---|---|---|
| A. cumulative counts | +0.0004 | [−0.0046, +0.0055] | 45% |
| B-tfidf. last 10 lines | −0.0004 | [−0.0014, +0.0005] | 77% |
| B-mlp. PyTorch head | +0.0003 | [−0.0002, +0.0007] | 13% |
| E. Elo only | −0.0013 | [−0.0093, +0.0065] | 63% |
| A+E. counts + Elo | −0.0026 | [−0.0103, +0.0048] | 75% |
| *C. ceiling* | *−0.0210* | *[−0.0300, −0.0120]* | *100%* |

Every real model's interval straddles zero. Only the diagnostic that cheats
separates cleanly from the base rate.

`calibration.png` shows why in one picture: across the whole held-out season
every model's predictions live inside a band roughly 0.55–0.67 wide, and the
observed rate inside that band is essentially flat. The models are calibrated —
they are just not *resolving*. They say "about 61%" to almost every situation
because, on this feature set, about 61% is almost always the right answer.

**So the third outcome row fired too**, and it is the one that governs the
product: next-goal timing at this horizon is, on this feature set, close to
unpredictable. The live worklist in `src/live.py` is built and it runs — but
its ranking is barely distinguishable from ordering the matches at random, and
it should be presented that way.

`P@10%` is the one metric where a text model leads (0.432 for last-3-lines
against a 0.399 base rate). It is not supported by that model's AUC (0.512), so
it is most likely noise in a 10%-tail statistic. It is reported rather than
promoted.

### 3.3 The ceiling: 0.60 AUC, and Track A is already two-thirds of the way there

The obvious objection to a negative result is *your model is bad*. So: how good
could any model on this data be?

Model **C** is given the counted events from **inside** the label window —
every shot, corner, foul and card in the next fifteen minutes, with only the
goals themselves removed. It has watched the future and is asked merely to say
who scored. It reaches **0.597 AUC**; adding counts and Elo takes it to 0.602.

| | AUC | share of the reachable gap |
|---|---|---|
| majority class | 0.500 | — |
| B. words | 0.513 | 13% |
| A. numbers | 0.541 | 40% |
| A+E. numbers + team strength | 0.565 | 64% |
| **C+. sees the whole window** | **0.602** | **100%** |

Track A is not a weak model of a rich signal. It captures 40% of everything a
crystal ball could capture, and the crystal ball itself is only 0.10 AUC above
chance. **The target is nearly noise.** Which fifteen-minute window contains a
goal, and which side scores it, is dominated by finishing — and finishing is
close to a coin flip that the preceding events do not predict.

This reframes the whole project. The right sentence is not "commentary does not
work"; it is "very little works, and here is the measurement that says so."

### 3.4 Shortening the horizon does not rescue the words

Fifteen minutes might simply be too long for pressure to survive. It is not the
explanation. Every horizon was labelled and the whole comparison rerun.

AUC (macro OvR):

| horizon | base rate `NONE` | B. words | A. numbers | A+E | ceiling |
|---|---|---|---|---|---|
| 5 min | 85.2% | 0.523 | 0.543 | 0.564 | 0.607 |
| 10 min | 72.3% | 0.512 | 0.541 | 0.564 | 0.608 |
| 15 min | 60.9% | 0.513 | 0.541 | 0.565 | 0.602 |
| 30 min | 39.0% | 0.518 | 0.559 | 0.586 | 0.600 |

The picture is flat (`horizons.png`). The ordering never changes, the ceiling
sits at 0.60 regardless, and nothing moves by more than about 0.04.

The one place the hypothesis shows a flicker: **words do best at the 5-minute
horizon** (0.523, their peak), which is the only result in this project
consistent with commentary describing pressure that is about to pay off
immediately. It is still below the numbers at the same horizon, and the effect
is small enough that it should be called a hint, not a finding.

### 3.5 Who is playing matters more than what is happening

Elo — which knows nothing about the match in progress, only which two teams
took the field — scores **0.5585**, above every in-match model including all of
Track A. Adding it to Track A gives the best model in the study, 0.5647.

Of the 0.102 AUC available between chance and the ceiling, roughly a quarter is
recovered by team identity alone. That is not a momentum signal; it is a
reminder that Arsenal at home are more likely to score in any given window than
Burnley away, whatever the last ten commentary lines say.

For the product this is the most actionable line in the report. A worklist that
ranked matches by *pre-match* team strength would beat the momentum model, and
would not need a live feed at all.

### 3.6 The skill is in *who*, not *whether* — and the product needed *whether*

Splitting the three-class problem into its two real questions is the single
most useful thing in this report.

| Model | *is a goal coming?* | *given one is, whose?* |
|---|---|---|
| majority class | 0.500 | 0.500 |
| B. words (last 10 lines) | 0.508 | 0.519 |
| A. numbers | 0.508 | 0.594 |
| E. Elo only | 0.515 | 0.627 |
| **A+E. numbers + Elo** | **0.518** | **0.641** |
| *C+. ceiling* | *0.557* | *0.687* |

Every model sits within 0.02 of chance on *whether*. Even the crystal ball —
which has counted the next fifteen minutes' shots and corners — reaches only
0.557. The timing of a goal is essentially not predictable from anything here.

*Who*, on the other hand, is genuinely predictable at 0.64 — and look at where
that comes from. Elo alone gets 0.627 of it. Almost all of the model's real
skill is "the better team is more likely to be the one that scores", which is
knowable at kickoff and needs no live feed at all.

Decile check on the held-out 2025-26 season, ranking snapshots by the shipping
model's P(goal in next 15 min):

| decile | model says | actually happened |
|---|---|---|
| lowest | 31.9% | 41.6% |
| middle | 37.7% | 37.2% |
| highest | 45.3% | 35.2% |

The base rate that season was 36.5%. The decile the model was *most* confident
about scored **below** the base rate, and the decile it was least confident
about scored highest. On *whether*, the ranking is not weak — over the most
recent season it is slightly inverted, which is what a 0.52 AUC looks like in
practice.

**This is the finding that decides the product.** "Five matches kick off at
3pm, which one do I watch?" is the *whether* question, and it is the one
question this data cannot answer.

## 4. What the data turned out to be

Three things were open questions in the proposal. Each was checked directly and
two of them changed the plan.

### 4.1 Commentary is partly templated — the shots are the exception

The proposal named this the single biggest threat to the premise. Measured by
stripping proper nouns and digits and counting distinct templates per event
type, over 400 matches (`commentary_check.txt`):

| Event type | Lines | Distinct templates | Most common template's share |
|---|---|---|---|
| Foul | 16,864 | 41 | 46% |
| Substitution | 3,229 | 16 | 83% |
| Corner Awarded | 3,174 | 16 | 60% |
| Yellow Card | 1,628 | 18 | 64% |
| Offside | 1,338 | 11 | 70% |
| **Shot Off Target** | **3,499** | **1,045** | **2.5%** |
| **Shot On Target** | **2,079** | **602** | **2.9%** |
| **Goal** | **726** | **435** | **3.7%** |

So the premise was **half right**. Fouls, corners, cards and substitutions are
pure templates and carry nothing the event counter does not already have. Shots
and goals are described in genuine detail — body part, position on the pitch,
how the chance was created:

```
Attempt missed. <player> (<team>) header from the centre of the box misses
to the left. Assisted by <player> with a cross.
```

That detail is real information absent from a shot count. It just does not
help: the text tracks had access to it and still lost. This is a stronger
negative result than a templating artefact would have been — the words were
richer than the numbers and were still worse.

Commentary depth is stable across all four seasons (median 104–110 lines per
match), so the 2022-23 rows are not systematically thinner than 2025-26.

### 4.2 ESPN's odds are settled, not pre-match — the bookmaker baseline is gone

The proposal listed Bet365 pre-match prices as an external reference baseline.
They are not pre-match. On a completed fixture the `odds[]` block returns
prices that pick the actual result with near-certainty:

```
final 1-2   implied P(H,D,A) = (0.01, 0.10, 0.90)  → predicted A, actual A
final 2-0   implied P(H,D,A) = (0.97, 0.02, 0.01)  → predicted H, actual H
final 2-2   implied P(H,D,A) = (0.06, 0.84, 0.10)  → predicted D, actual D
```

These are settled or late in-play prices. Using them as a baseline would have
been catastrophic leakage dressed up as a strong reference. **The bookmaker
baseline is dropped**, and the test suite zeroes the `odds` field so it cannot
come back in by accident. The Elo rating in §3.5 is the honest substitute: a
pre-match reference built from data we already hold.

`boxscore.teams[].statistics` was dropped for the same reason: it contains
full-match totals only, with no per-minute breakdown. It is not available at
minute *M* in any form.

### 4.3 Live commentary latency: still unmeasured

`src/live.py` measures the age of the newest commentary line on every poll.
There were no Premier League matches in progress while this was built, so the
number has not been observed under live conditions. The instrument exists; the
reading does not.

## 5. Leakage

Defended by tests rather than by care (`tests/test_leakage.py`, 9 tests). The
central one takes a real match, deletes every event after minute *M*, rebuilds
the features from the truncated data, and asserts each feature at minute *M* is
identical to the one built from the full match. Anything that can see forward
fails.

Three tests exist so that the central one cannot pass vacuously:

* the **label** must change under truncation;
* the **`fut_*` ceiling columns** must change under truncation — otherwise the
  ceiling in §3.3 would not actually be built from future events;
* the **Elo columns** must *not* change, since they are read before kickoff.

Offline and live share one feature function (`snapshots.features_at`), so
training and serving cannot drift apart.

One honest caveat the tests do not cover: matches are dropped from the dataset
when their commentary is too sparse or when the goals parsed from commentary do
not reconstruct the final scoreboard (29 of 1,520). That is a match-level
filter using end-of-match information. It affects which matches are included,
not any feature value, but it is a selection made with hindsight and is
recorded here rather than buried.

## 6. What would actually change the answer

The three obvious follow-ups were run and are in §3.3–3.5. What is left:

* **Live latency**, §4.3. Needs a run during a match. Everything else is built.
* **A different target.** Expected goals per window, rather than which side
  scored, removes the finishing coin flip that §3.3 shows is dominating. It is
  a different question, and probably the more answerable one.
* **A different text source.** ESPN's commentary is Opta event description, not
  a pundit talking. "Liverpool have all the momentum now" is the sentence the
  original hypothesis was about, and it never appears in this dataset. A
  broadcast transcript would test the actual claim; this tested the closest
  free proxy to it, and the proxy failed.
* **Whether the product should exist.** §3.5 and §3.6 together say no, at least
  not as specified: the model's real skill is *who scores*, it comes almost
  entirely from pre-match team strength, and the worklist asks the other
  question. If a worklist is still the goal, rank by *who is playing* and skip
  the live feed.
