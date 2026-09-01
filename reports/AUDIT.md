# Audit — before committing to the xG-from-commentary project

Every claim below was checked against the live source or the collected data on
2026-08-30. Nothing here is recalled or assumed.

---

## Verdict first

**Words recover 90.6% of a coordinate model's discrimination.** Measured on
8,825 shots where a commentary sentence and a true StatsBomb shot location
describe the same event.

The idea works, and it nearly died in check 3.

* Rating a shot from its commentary text reaches **0.7727 AUC** on a held-out
  season, well calibrated. Published coordinate-based xG models sit at roughly
  0.78–0.82. **Words get within a few points of coordinates.**
* Getting there required catching a **complete label leak** that gives a naive
  model **1.0000 AUC**. Two rounds of blacklist filtering failed to remove it.
* The validation set that makes the headline claim measurable exists, but not
  where expected — it needs one more season collected.
* Prior art looks open, with one paper that must be read before any novelty
  claim is made.

---

## Check 1 — Has this been done? (prior art)

Searched for commentary-text xG and adjacent work.

| Line of work | Example | Does it do this? |
|---|---|---|
| xG from coordinates | [PLOS One](https://journals.plos.org/plosone/article?id=10.1371%2Fjournal.pone.0282295), [Frontiers](https://www.frontiersin.org/journals/sports-and-active-living/articles/10.3389/fspor.2021.624475/full) | No — positional and event data |
| xG from preceding events | [PMC11524524](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC11524524/) | No — structured event sequences |
| Explainable xG | [arXiv 2206.07212](https://arxiv.org/pdf/2206.07212) | No — coordinates, SHAP on top |
| Commentary **audio** datasets | [SoccerNet-Echoes](https://arxiv.org/html/2405.07354v1), [EchoNet++](https://www.nature.com/articles/s41598-026-39884-8) | No — ASR and alignment, not shot quality |
| Commentary **generation** | [MatchTime](https://arxiv.org/html/2406.18530v2) | No — opposite direction |
| Event extraction from commentary | [ResearchGate](https://www.researchgate.net/publication/372487453_Analyzing_sports_commentary_in_order_to_automatically_recognize_events_and_extract_insights) | Partly — detects *what* happened, does not rate chance quality |

### The one threat, resolved

[arXiv 2402.06820, "Forecasting Events in Soccer Matches Through
Language"](https://arxiv.org/html/2402.06820v2) was the only candidate that
looked like it might already be this idea, and a search-engine summary claimed
it computed xG "from language descriptions". **Read in full: it does not.**

* **Input is structured, not prose.** WyScout event records — eleven fields
  including type, coordinates, accuracy — ordinal-encoded into tokens. The
  paper's own framing: *"by tokenizing soccer event data, we enable a single
  model to learn the 'language' of soccer events"*. "Language" is a metaphor
  for event sequences, not natural language.
* **It does produce xG**, but by simulating a million shots from structured
  prior states ("after a pass at coordinates (80, 50)") — coordinates in,
  coordinates out.
* **Human-written commentary is never consumed anywhere in the paper.**
* Reported: 62.2% next-event-type accuracy, MAE 6.5 on X and 11.4 on Y.

**Verdict: not prior art for this.** The search summary was wrong; the abstract
was right.

**Overall:** the niche is open. Commentary NLP in football is about detecting,
summarising and generating. Nothing found rates *chance quality* from the
words.

## Check 2 — Data audit

| Source | HTTP | Contents | Verdict |
|---|---|---|---|
| ESPN summary/scoreboard | 200 | commentary, typed events, teams | **Core.** 1,520 matches already collected |
| StatsBomb open data | 200 | events + `statsbomb_xg` + `location` + 16-player freeze frames | **Core for validation** |
| football-data.co.uk | 200 | 380 rows × 132 cols per season | **QA only** |
| openfootball | 200 | fixtures | Redundant |
| Understat | 200 but `shotsData` absent on the match page tried | — | **Unverified. Do not depend on it** |
| FBref | **403** | — | **Blocked** |

### Resolved — the validation set was built

Both sides were collected and joined after this audit began. Result in
check 7.

### The problem, and the fix

StatsBomb's open Premier League coverage is **2003/04 and 2015/16 only**. Our
ESPN data is 2022-23 to 2025-26. **Zero overlap** — so the "how much of a
coordinate model can words recover?" comparison cannot be run on what we hold.

Checked whether ESPN goes back that far: **it does.** A 2016-02-13 fixture
returns 122 commentary lines, 110 of them typed. So the validation set is
buildable — collect ESPN 2015/16, join to StatsBomb 2015/16 on match and
minute. That is **380 matches, roughly 12,500 shots, each with both the
sentence and the true coordinates and xG.**

### A trap that is already familiar

`football-data.co.uk` gives `HS`/`AS` — shots per match. Those are **full-match
totals**, exactly like the ESPN boxscore dropped in the momentum work
(FINDINGS §4.2). They cannot be features. They are useful for one thing:
**checking the parser.**

Ran that check on 272 matched fixtures from 2025-26:

```
correlation with official shot counts : 0.986
mean difference                       : -0.4 shots
exact match                           : 64%
```

The parser is sound — and the check immediately found a match producing
nothing:

```
West Ham v Man Utd, 2026-02-10    ours: 0 shots    official: 7 and 9
```

Diagnosed: **not a parser bug.** ESPN returns that fixture with an empty
`commentary` array — 0 lines, while `keyEvents` still holds 16 entries. The
source simply has no commentary for it.

Counted across everything collected:

```
matches collected                  : 1,520
matches yielding 0 shots           : 1   (0.07%)
matches with 1-5 shots             : 0
parsed goals != final scoreline    : 1   (0.07%)
```

So the failure rate is one match in fifteen hundred, and its cause is upstream.
What is missing is not a fix but a **guard**: the pipeline should refuse a
match with empty commentary loudly instead of silently contributing nothing.

## Check 3 — The label leak (the one that nearly killed it)

**Every shot's commentary line opens by stating the outcome.**

```
Goal!             n= 4,322    goal rate 100.0%
Attempt missed    n=13,318    goal rate   0.0%
Attempt saved     n= 8,313    goal rate   0.0%
Attempt blocked   n=10,941    goal rate   0.0%
```

The first two words separate goals from non-goals **perfectly**. A tf-idf model
on the raw sentence scores:

```
3. RAW text (LEAKING)    AUC 1.0000   logloss 0.0104
```

A perfect model that has learned nothing. This is the same species of trap as
the settled ESPN odds — it looks like a triumph and is worthless.

**Removing it took three attempts, and the first two failed silently.**

| Attempt | Approach | Result |
|---|---|---|
| 1 | Strip the opening clause | Leaked — `penalty` field showed a 100% goal rate |
| 2 | Strip opener + a list of outcome verbs | Leaked — inspecting coefficients showed `goal` (+7.99), `own goal`, `converts the penalty`, `hits the post` had survived; AUC 0.8212 was fake |
| 3 | **Whitelist** — keep only spans matching known descriptive patterns | Leaked once more, found later. See below |
| 4 | Whitelist, minus free kicks | Clean |

### The fourth leak, and why the first test would not have caught it

Attempt 3 passed the leak test, passed inspection, and produced the headline
number. It was caught days later by looking at a retrieval example: the
highest-rated chance in the held-out season was *"from a free kick right footed
shot"*, and all forty of its nearest neighbours were goals.

ESPN word the two outcomes differently:

```
scored : "Olise (Crystal Palace) from a free kick with a left footed shot to..."
missed : "...right footed shot from outside the box ... from a direct free kick"
```

So the phrase surviving the whitelist, `from a free kick`, appeared on 60 shots
and **every one was a goal**. The event type leaks identically — scored ones are
typed `Goal - Free-kick`, missed ones `Shot Off Target`. A free kick cannot be
identified from this feed before its outcome is known, so it is no longer a
feature.

**The test was the problem, not just the parser.** It checked a hand-written
list of forbidden words, and `free kick` was not on it — because a free kick is
a legitimate thing to describe. A list only catches leaks already imagined.

The replacement asks the data instead: every n-gram appearing 25+ times is
checked, and any that converts above 80% — well clear of the penalty rate --
75% across the corpus, 83% in the Premier League alone — fails the suite. Run against the pre-fix data it
flags `('free kick', 60, 1.00)` immediately.

Cost of the fix at the time: 0.7727 → 0.7688 AUC. The leak was contributing almost nothing,
which is exactly why it survived so long.

Attempt 2 is the important one. It *looked* right, the text read correctly by
eye, and it was only caught by printing the model's top coefficients. **Free
text has too many ways to say what happened for a blacklist to work.**

Verification that attempt 3 is clean — the learned features, strongest first:

```
positive:  headed pass following corner,  through ball following,  free kick
negative:  with cross,  header,  footed shot following
```

That is correct football: through balls and set-piece headers produce better
chances than crossed balls. No outcome word survives.

**This must be permanent.** A test asserting the outcome clause never returns
belongs in CI beside the momentum project's leakage tests.

## Check 4 — Does it actually work?

Time-based split. Train 2022-23 → 2024-25 (28,735 shots), test 2025-26
(9,194 shots, 11.3% goals).

| Model | AUC | log loss | Brier |
|---|---|---|---|
| base rate | 0.5000 | 0.3539 | 0.1006 |
| **regex fields from the text** | **0.7709** | **0.2945** | **0.0840** |
| whitelisted text, tf-idf | 0.7628 | 0.3012 | 0.0861 |
| *raw text (leaking, not a result)* | *1.0000* | *0.0104* | *0.0004* |

That the two clean models land within 0.01 of each other is the sanity check
that the leak is gone — they are two different views of the same information.

Calibration on the held-out season:

```
says   3.5%   actually   2.8%      says  14.9%   actually  12.1%
says   3.9%   actually   3.7%      says  18.0%   actually  13.1%
says   4.6%   actually   3.8%      says  42.6%   actually  40.3%
says   5.6%   actually   5.7%
```

Honest across the range, mildly overconfident in the middle.

Aggregated to team-match level: correlation 0.490 with actual goals, mean xG
1.54 against mean goals 1.38 — a small systematic overestimate worth fixing.

**Where the signal comes from** (goal rate by parsed field, 37,929 shots):

```
penalty          82.9%          outside the box    4.2%
after fast break 37.3%          side of the box    5.7%
six yard box     27.1%          difficult angle    8.1%
through ball     25.7%          overall           11.8%
```

A twentyfold spread, recovered from English sentences alone.

## Check 5 — Live latency: still unmeasured

Polled six leagues at audit time. Every fixture `STATUS_FULL_TIME`; nothing in
progress. The instrument exists (`src/live.py` reports the age of the newest
commentary line on each poll) and has never been read under live conditions.

**Unchanged from FINDINGS §4.3.** Any claim about the live product remains
unsupported until a match is running.

## Check 6 — Why would anyone use this?

**Because coordinate data is not free and commentary is.**

StatsBomb's open Premier League coverage is two seasons, ten years apart. Opta
and StatsBomb's full feeds are commercial. Anyone outside a club or a paying
newsroom — a student, a lower-league analyst, a writer covering a competition
nobody sells data for — cannot build xG at all today.

ESPN publishes commentary, free and without a key, for far more competitions
than anyone publishes coordinates for. If 0.77 AUC is recoverable from the
words, then **xG becomes available wherever commentary exists**, which is a
much larger set of football than where tracking data exists.

The honest limits, stated up front:

* it will not beat a coordinate model, and is not meant to;
* it inherits whatever the commentary provider chooses to describe;
* it says nothing about *when* a goal arrives — the momentum work already
  measured that ceiling at 0.60 AUC and this does not move it.

## Check 7 — Words against coordinates, on the same shots

ESPN 2015/16 was collected (380 matches) and joined to StatsBomb's open
Premier League 2015/16. A shot pairs only when the match, the team and the
minute all agree; anything ambiguous is dropped rather than guessed.

```
ours        : 9,502 shots over 373 matches
statsbomb   : 9,908 shots over 380 matches
matches joined : 373
shots joined   : 8,825   (92.9% of the smaller side)
outcome agreement (our goal flag vs theirs) : 99.71%
```

The 99.71% agreement is the check that the join is real: two independent
sources agreeing on which shots were goals, shot by shot.

**Note the direction of the test.** The model is trained on 2022-23 → 2024-25
and evaluated on 2015-16 — a decade earlier, a different era of football and a
different commentary team. This is a harder test than a normal held-out split,
not an easier one.

### How close are the two numbers?

```
correlation (ours vs StatsBomb xG)  : 0.735
rank correlation                    : 0.628
mean   ours 0.097      theirs 0.098
MAE                                 : 0.052
```

The means agree to within 0.001. Whatever the words miss, they do
not miss it in a biased direction.

### Predicting the same goals, on the same shots

| Model | Input | AUC | log loss | Brier |
|---|---|---|---|---|
| **ours** | the commentary sentence | **0.7826** | 0.2711 | 0.0764 |
| StatsBomb | shot coordinates, freeze frames, 16 player positions | 0.8118 | 0.2555 | 0.0715 |

```
words recover 90.6% of the coordinate model's discrimination above chance
```

That is the number this project exists for. A sentence of English gets nine
tenths of the way to a model built on tracking data — using a source that is
free, keyless, and published for far more competitions than coordinates are.

The remaining 9.3% is what the words genuinely cannot say: exact distance
inside a zone, the angle, how many defenders stood in the way.

### Is that gap large? Compared to what the paid providers manage — no

"90.6% of a coordinate model" only means something against a scale, and the
obvious scale is how well the commercial providers agree with *each other*.
Public comparisons across five seasons and five leagues (~4,290 matches) report
match-level xG correlations:

```
Opta      x Understat      0.96
Opta      x StatsBomb      0.92 - 0.93
StatsBomb x Understat      0.92 - 0.93
Wyscout   x the others     0.86 - 0.88
```

On the 746 team-matches of the join (`src/head_to_head.py`):

```
ours (commentary text) x StatsBomb   0.869
mean | ours - StatsBomb |            0.249 xG per team-match
median                               0.198
max                                  1.54
mean xG: ours 1.150   StatsBomb 1.161   goals 1.202
```

**A model reading only English sentences agrees with StatsBomb about as closely
as a commercial provider does.** 0.869 lands inside the Wyscout band and below
the Opta/Understat/StatsBomb band — so the gap between words and coordinates is
of the same order as the gap between two companies both watching the video.

Caveats, because the comparison is close rather than exact:

* Theirs is per match across five leagues and five seasons; this is per
  team-match on one league and one season, 373 matches.
* A widely quoted "~1 xG mean absolute difference between providers, max 3.88
  for Manchester City" figure is **not used here**. Its unit is unresolved —
  naming a team alongside 3.88 reads as a season aggregate, which would make it
  much *tighter* per match than 0.249, not looser — and the source paywalls.
  Quoting it would have flattered this project on an unverified reading.

Source and search record: `writing/BLOG_SEARCH.md`.

## Check 8 — Would a better reader close the gap? No.

The words reach 0.781 against StatsBomb's 0.812. Something is missing, and
there are only two places it can be: the **extraction** (regexes catch only
phrasings someone thought of — and one of them leaked for exactly that reason),
or the **words** (a sentence never states distance in metres, the angle, or how
many defenders were in the way).

This decides which, at no cost, by handing models the *whole* sentence and
seeing whether they beat the eighteen fields pulled out of it.

| Model | Sees | AUC |
|---|---|---|
| **regex fields, logistic (what ships)** | 18 fields | **0.7709** |
| regex fields, boosted trees | 18 fields | 0.7695 |
| every 1–4 gram in the sentence | all words | 0.7612 |
| sentence embedding (MiniLM) | all words | 0.7584 |
| embedding + regex fields | both | 0.7589 |

**Reading more of the sentence is worth −0.010.** Every model given the full
text does *worse* than eighteen extracted fields, including a semantic
embedding and a bag of every 1–4 gram. Adding the embedding to the fields makes
them worse too — the rest of the sentence is player names, team names and
filler, and it is noise.

So the extraction is not the bottleneck. **The remaining 9.3% is information
the sentence never contained**, and no better reader can recover it. An LLM
extractor was considered and dropped on this evidence rather than on taste;
`src/extraction_ceiling.py` is the argument, and it reruns in seconds.

This is the same shape of answer as the momentum ceiling: rather than guessing
whether the model or the data is the limit, measure which.

## Check 9 — Does one model work in six leagues? Yes, at no cost.

The claim this project rests on is that xG becomes available *wherever
commentary exists*. Until now that had only been tested on the Premier League,
which is also where the model was trained — a claim, not a result.

ESPN publish the same Opta-style English commentary for five other
competitions. 1,677 further matches were collected, and the **Premier League
model was pointed at them cold — nothing retrained, nothing tuned**.

| Competition | Shots | Goal rate | AUC | Brier | Mean xG |
|---|---|---|---|---|---|
| Premier League *(trained on)* | 9,194 | 11.3% | 0.7709 | 0.0840 | 0.127 |
| La Liga | 9,240 | 11.1% | 0.7730 | 0.0823 | 0.119 |
| Ligue 1 | 7,391 | 11.7% | 0.7807 | 0.0859 | 0.122 |
| Bundesliga | 7,853 | 12.6% | 0.7795 | 0.0906 | 0.125 |
| Serie A | 9,065 | 10.2% | 0.7702 | 0.0771 | 0.115 |
| **Primeira Liga** | 7,000 | 11.7% | **0.7871** | 0.0851 | 0.122 |

```
trained-on league   0.7709
other leagues, mean 0.7781
cost of transfer    -0.0072     (a small gain, not a loss)
calibration bias abroad +0.006  (predicted minus actual)
```

**There is no transfer cost.** The model does marginally *better* abroad than
at home, and stays calibrated — mean prediction 0.115–0.125 against actual goal
rates of 10.2–12.6%, with the ordering preserved (Serie A both predicted and
observed lowest, the Bundesliga highest).

This is what makes the free-data argument real rather than rhetorical. One
model, fitted once on English football, reads Portuguese, German, Italian,
Spanish and French football without being told anything about them — because
what it reads is the sentence, and Opta build the sentence the same way
everywhere.

**Corpus after this check:** 87,980 shots across 3,569 matches and six
competitions.

### And Spark is still not justified — measured, not assumed

The obvious reason to expand was that more data would justify the distributed
tooling in the original proposal. It does not:

```
87,980 shots -> 4 MB parquet, 64 MB in memory
pandas load  0.04 s
full groupby 0.01 s
```

Raw JSON is 122 MB. Nothing here is close to a limit pandas cannot handle, so
Spark would be ceremony. It is left out, on the same grounds as vLLM and the
LLM extractor: the tool is introduced when a measured limit demands it, and no
limit has appeared.

## Check 10 — Does the live path need C++? No, and the reason is not close.

The proposal justified a C++ poller "at multi-match concurrency", with the
rewrite to be "motivated by a measured Python bottleneck, with before/after
benchmarks". `src/bench_live.py` is that measurement, taken before anything was
rewritten.

**How many matches actually run at once?** Across all six competitions, the
busiest 105-minute window in the collected fixtures holds **14**:

```
2025-09-13 14:30 UTC -- ger.1 5, eng.1 5, ita.1 2, por.1 2, esp.1 1, fra.1 1
```

**What does Python cost per match?**

```
json parse      1.40 ms
shot extract    0.72 ms
score           0.32 ms
total           2.44 ms      (p95 parse 1.2 ms)
```

**Against the proposal's own 15-second cadence:**

```
14 matches x 2.4 ms = 34 ms of cpu
0.23% of the budget
headroom before cpu is the limit: 438x  (6,136 concurrent matches)
```

And the part that settles it:

```
one summary fetch   147 ms
cpu is 60x cheaper than the round trip it waits on
```

**The bottleneck is the network, and no language changes that.** Even fetching
all fourteen matches one after another takes 2.1 s, comfortably inside fifteen.
If concurrency ever did become the constraint, the lever is asynchronous I/O —
overlapping those 147 ms waits — not a faster parser for the 2.4 ms that
follows them.

To be generous to the C++ case: a European Saturday with every league running
might reach a hundred concurrent matches. That is 244 ms of CPU, 1.6% of the
budget. The margin is not close at any plausible scale.

C++ joins vLLM, the LLM extractor and Spark: proposed, measured, declined.

## Check 11 — Kubeflow and LangGraph, the last two

### Kubeflow: there is no drift to schedule around

Kubeflow's case in the proposal was weekly in-season retraining with a
promotion gate. That is worth automating only if the model decays. Measured by
training on one season at a time and testing on the most recent
(`src/drift.py`):

| Trained on | Shots | Stale by | AUC | Mean xG |
|---|---|---|---|---|
| 2015-16 | 9,502 | **10 years** | 0.7641 | 0.138 |
| 2022-23 | 9,205 | 3 years | 0.7653 | 0.128 |
| 2023-24 | 10,022 | 2 years | 0.7714 | 0.130 |
| 2024-25 | 9,508 | 1 year | 0.7705 | 0.124 |
| all recent *(ships)* | 28,735 | 1 year | 0.7709 | 0.127 |

```
a model 10 years stale costs +0.0068 AUC
one recent season vs three:  +0.0005
```

**A decade of staleness costs well under a hundredth of an AUC point**, and one
season of data is indistinguishable from three. Weekly retraining would chase
noise; a scheduler to automate it is machinery around a problem that does not
exist. This is the same conclusion the transfer test reached from the other
direction.

**But read the last column too.** Mean xG falls from 0.138 to 0.124 across the
same rows — a 10% slide in the level while AUC does not move. When this table
was written only the AUC column was read, and the conclusion drawn from it —
"a model this stable across ten years is not drifting" — is half wrong. The
ranking does not drift. The level does, by roughly 10% a decade, and check 12
is what that turned out to be. Kubeflow is still not the answer; the answer is
one number, refitted in season.

What Kubeflow would genuinely have provided is already here in cheaper form:
provenance lives in `models/xg.meta.json` (data window, metrics, git SHA), and
the promotion gate is the test suite in CI.

### LangGraph: there is no flow to orchestrate

LangGraph earns its place where there are cycles, retries, human-in-the-loop
steps, or state that has to persist across several agents. The flow here, after
the LLM was dropped on the evidence in check 8, is:

```
score the shot  ->  above threshold?  ->  Qdrant lookup  ->  format a string
```

Four steps, one branch, no cycle, no state. That is an `if` and a function
call. Wrapping it in a graph framework would add a dependency, a runtime and a
vocabulary in exchange for nothing.

If an LLM ever does enter the picture — a different text source, a
conversational interface — LangGraph becomes reasonable, because retries and
branching on model output are real problems. It is not reasonable now.

## Check 12 — The over-estimate, and what it turned out to be

Check 4 left an unexplained residue: on the held-out 2025-26 season the model
predicts 1.54 goals per team-match against 1.38 actual, an 11.9% over-estimate
that does not appear in the 2015-16 comparison. Item 7 of the list below asked
why. This is the answer, and it is more interesting than a bug.

### It decomposes exactly

```
league goal rate, 2022-23 -> 2025-26      0.1199 -> 0.1134    x 1.057
mean prediction vs its own training rate  0.1199 -> 0.1270    x 1.059
                                                      product   1.119
```

Observed over-estimate: 11.9%. The two factors multiply to the whole of it,
with nothing left over. The first is the Premier League converting slightly
less often than it used to. The second is stranger: a logistic regression's
mean prediction on its training set equals the training base rate by
construction, so a mean of 0.1270 on 2025-26 means the *parsed features* of
those shots look better than the shots the model was fitted on — while
actually producing fewer goals.

### Two phrases account for it

```
                    share of shots            conversion
six yard box        4.2% -> 6.0%              39.1% -> 35.8%
following a fast    1.9% -> 3.3%              47.2% -> 28.4%
break
```

Both phrases became more common and less productive at the same time. A fast
break converting at 47% in 2022-23 and 28% in 2025-26 is not a change in
football; a 74% rise in how often the phrase appears is not one either. This is
ESPN's writers using the words more loosely. The model, which knows nothing
except the words, reads a better shot than the one that was taken.

### The decade confirms it

Scored with the shipped model, trained on 2022-24:

```
2015-16   mean xG 0.1023   actual 0.1052    -2.7%
2025-26   mean xG 0.1270   actual 0.1134   +11.9%
```

The sign flips. In 2015-16 "following a fast break" appeared on 0.73% of shots
and converted at 49.3%; by 2025-26 it appeared on 3.30% and converted at 28.4%
— four and a half times as common, at little more than half the conversion. The
model, fitted in the middle, under-reads the older season and over-reads the
newer one. That is a drift signature, not a defect in the parser.

### Retraining cannot fix it

```
trained on all three seasons (shipped)     +11.9%
trained on the last two                    +11.9%
trained on the last one only                +9.1%
recency weighted, half-life one season      +9.9%
```

None of it works, and the reason is not that the data is old. Next season's
conversion rate is not in this season's data at any weighting. The best of
these buys 2.8 points of the 11.9 and pays for it with two thirds of the
training set.

### Waiting does fix it

Once a few hundred shots of the new season have been played, their realised
rate is simply observable. One number added to the intercept pulls the level
back. Walking forward through 2025-26 and refitting that number only on shots
already played:

```
                  mean xG   actual   over     log loss
uncorrected        0.1267   0.1132   +12.0%    0.29523
recalibrated       0.1165   0.1132    +2.9%    0.29443
```

8,694 shots evaluated, after a 500-shot warm-up — about twenty matches, three
weekends — during which the model runs uncorrected because the realised rate is
still too noisy to correct towards. `src/recalibrate.py`, applied by
`src/score.py`, tested in `tests/test_recalibration.py`.

An intercept shift is monotone, so AUC is unchanged by construction, and a test
asserts it: the guard is against a future maintainer improving calibration by
reaching for the coefficients, which would trade the ranking — the result this
project exists for — to buy a better mean.

### What this adds to the finding

Check 11 measured drift and found it cheap: a ten-year-stale model costs 0.007
AUC. That measurement was correct and incomplete — and the missing half was
already printed in its own table, in the mean xG column, sliding from 0.138 to
0.124 while the AUC column stayed flat. Nobody read it, this one included,
because the question being asked was "does accuracy decay" and the answer was
no. Drift barely touches the ranking and badly damages the level.

> The words rank shots about as well as coordinates do, and go on doing so for
> a decade. It is the mapping from words to probabilities that moves, because
> the words themselves are written by people whose habits change.

Which is a limitation specific to text-derived features, worth stating plainly:
a coordinate does not drift, and a phrase does.

## What must happen before building

1. ~~Read arXiv 2402.06820 in full~~ — **done, check 1. Not prior art.**
2. ~~Collect ESPN 2015/16 and join to StatsBomb~~ — **done, check 7. 90.6%.**
3. ~~Write the leak test~~ — **done, then rewritten.** `tests/test_shot_text_leak.py`,
   six tests: a behavioural AUC ceiling, a companion test asserting the raw
   text still leaks so the ceiling cannot pass vacuously, and — after the free
   kick episode — a data-driven check that flags *any* n-gram converting above
   80%, rather than a list of words someone thought of in advance.
4. **Add the empty-commentary guard.** One match in 1,520 arrives with no
   commentary and currently contributes nothing, silently.
5. **Measure live latency** during an actual match. Still the only claim in
   this project with no evidence behind it.
6. ~~Ask whether a better reader would help~~ — **done, check 8. It would not.**
7. ~~Correct the small over-estimate~~ — **done, check 12.** It was phrase
   drift, not a parser defect, and it is not fixable by retraining. An
   in-season intercept refit takes it from +11.9% to +2.9% without touching
   the ranking. `src/recalibrate.py`.
