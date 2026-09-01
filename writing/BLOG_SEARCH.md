# Blog and grey-literature search

The API search in [LITERATURE_REVIEW.md](LITERATURE_REVIEW.md) covered arXiv,
OpenAlex and Crossref, and named three gaps. It said the third was the one that
mattered:

> No blogs. Football analytics has a large, serious blog literature —
> StatsBomb's own articles, American Soccer Analysis, Opta Analyst. Something
> like this is more likely to exist there than in a journal.

This is that search. It found something, and the finding changes what this
project may claim.

---

## What changed

**Retired.** "No published work uses natural-language commentary as the input
to a shot-quality model." A hobby project on GitHub does exactly that, and has
since 2020.

**Stands, and is now the whole claim.** Nobody has measured how much of a
coordinate xG model that recovers.

**New, and better than expected.** Agreement with StatsBomb per team-match sits
inside the band the commercial providers occupy against each other.

**New, and it needs a citation added.** Two of this project's side findings —
that the model survives a decade of staleness and travels between leagues — were
established in 2020 by Robberechts and Davis. They are confirmations, not
findings. What *is* new against that paper is check 12, and its own framing
makes it sharper.

---

## Method, and why it is weaker than the API search

`writing/litreview.py` is a script: fixed queries, three indexes, re-runnable,
and it reports its own recall. This search cannot be that. Web search has no
free API here, so it was run by hand.

What is kept instead is the audit trail: every query below was run, and every
one is recorded with what it returned, including the fourteen that returned
nothing. Anyone can repeat them.

**Recall probes first**, on the same principle as the API search — a search that
cannot find things known to exist cannot support a claim about what does not.

| Probe | Looking for | Result |
|---|---|---|
| Karun Singh, expected threat | The best-known xT blog post | ✅ found (`karun.in/blog/expected-threat.html`) |
| StatsBomb, explaining xG | Their own xG articles | ✅ found (blog archive, "The Dual Life of Expected Goals") |
| American Soccer Analysis, xG method | A public methodology writeup | ✅ found ("Expected Goals 3.0 Methodology") |
| opengoalapp, build your own xG | A named hobby-blog xG series | ⚠️ **not found by name** — the search returned the genre (Medium, R-bloggers, GitHub) but not the site asked for |

**Three of four by name.** The fourth is a real miss and it is the same
instability the API search reported. Read the negative result accordingly.

---

## Queries run

### The claim, four ways — nothing

| # | Query | Returned |
|---|---|---|
| C1 | expected goals model from text commentary NLP football no coordinates | coordinate xG papers; arXiv 2504.00767 again |
| C2 | build xG model from ESPN commentary text scraping football | scrapers for *numeric* xG (Understat, soccerdata); nothing text-derived |
| C3 | predict goal probability from match commentary sentence text football analytics | commentary *generation*, sentiment on results; nothing |
| C4 | expected goals without shot coordinates text description shot quality | arXiv 2402.06820 again; nothing |

### Platforms where a hobby project would live

| # | Restricted to | Returned |
|---|---|---|
| P1 | medium.com, towardsdatascience.com, substack.com | xG tutorials, all coordinate-based |
| P2 | kaggle.com, github.com | **one hit — see below** |
| P3 | reddit.com | ❌ **blocked** — the crawler is refused by reddit.com. A real gap; r/footballanalytics is exactly where this would be discussed |

### Blog domains, directly

| # | Restricted to | Returned |
|---|---|---|
| B1 | theanalyst.com, statsandsnakeoil.com, deepxg.com, americansocceranalysis.com | nothing text-derived. Deep xG is *human*-collected chance quality — 50 analysts watching 10,000 matches — which is the opposite trade: more expensive than coordinates, not cheaper |

### Follow-ups

| # | Query | Returned |
|---|---|---|
| F1 | infer shot position from Premier League commentary text expected goals project | nothing beyond P2's hit |
| F2 | text derived expected goals compared to StatsBomb Understat validation | the provider-disagreement literature — see below |
| F3 | commentary based expected goals github football text features | confirms P2; also `eddwebster/football_analytics`, the community's curated index |
| F4 | Robberechts Davis how data availability affects ability to learn good xG models | **must-cite — see below** |
| F5 | Opta Understat StatsBomb xG disagree average absolute difference per match | correlation figures at match level |
| F6 | how much of xG can you recover from words text only benchmark | nothing. The question appears not to have been asked |

Sixteen searches, three direct page fetches, fourteen returning nothing on the
claim.

---

## The hit: `calbal91/project-moneyballing-fpl`

Fetched and read directly rather than trusted from a snippet.

> "Scraping the Premier League website. We are able to scrape commentary (as
> well as some other aggregated data) straight from the Premier League website."

> "By instantiating each commentary text string as an 'Event' object, we were
> able to extract key information."

> "Note - we can infer the shot position from the text commentary."

So the input idea is not original to this project. Someone else read shot
features out of English match commentary, and did it first.

What that project does **not** do:

| | calbal91 | here |
|---|---|---|
| Commentary text as the source | ✅ | ✅ |
| Shot position inferred from words | ✅ | ✅ |
| Fitted probabilistic model | ✗ — conversion rates by category | ✅ logistic regression, 18 fields |
| Outcome-leak removal from the sentence | ✗ — not a concern in its framing | ✅ and it took four attempts |
| Held-out season, AUC / log loss / Brier | ✗ **none reported** | ✅ 0.7709 AUC on 2025-26 |
| Compared against a reference xG model | ✗ **none** | ✅ StatsBomb, 8,825 shared shots |
| A number for how much is recovered | ✗ | ✅ **90.6%** |

**The idea has been had. The measurement has not.** That is a narrower claim
than the one this project was carrying, and it is the claim the API search
already identified as the strongest one. It survives intact.

---

## Robberechts & Davis (2020) — the citation this project was missing

*How Data Availability Affects the Ability to Learn Good xG Models*, MLSA
workshop, ECML/PKDD. KU Leuven, the `soccer_xg` group.

Their findings, against this project's:

| They found (coordinates) | This project found (words) | Verdict |
|---|---|---|
| A basic logistic xG converges by ~6,000 shots, about ⅔ of a season | trained on 28,735 | ✅ comfortably above their threshold — **supports the design** |
| Training on less recent data costs "only a negligible performance hit" | a decade-stale model costs 0.0068 AUC | ⚠️ **same conclusion, six years earlier.** `src/drift.py` is a replication |
| League-specific, mixed, and other-league models "perform equally" | EPL 0.7709, five other leagues mean 0.7781, cost −0.0072 | ⚠️ **same conclusion.** `src/transfer.py` is a replication |
| "Mixing data from multiple data sources should be avoided" | every training path scoped to `eng.1` | ✅ independently arrived at the same rule |
| Brier as the primary metric, because "the primary objective of an expected goals model should be to produce calibrated probability estimates" | reports Brier and calibration deciles | ✅ aligned |

Two of this project's findings are replications. Say so.

### But this is where check 12 gets interesting

Robberechts and Davis put **calibration at the centre** — Brier score,
calibration curves, the stated position that calibrated probabilities are the
objective — and found staleness negligible.

This project, reading words instead of coordinates, found the ranking equally
stable (0.0068 AUC over ten years, agreeing with them) and the **level not
stable at all**: +11.9% on the held-out season, driven by "following a fast
break" going from 0.73% of shots at 49.3% conversion in 2015-16 to 3.30% at
28.4% in 2025-26.

Their result and this one do not conflict. They complete each other:

> A coordinate does not drift. A phrase does. Robberechts and Davis showed
> event-data xG is stable in exactly the sense — calibration — where a
> text-derived model is not, because the features of a text-derived model are
> written by people whose habits change.

That is a specific, falsifiable, small claim that stands on top of a 2020 result
rather than beside it, and it is much better than "we also measured drift."
`reports/AUDIT.md` check 12.

---

## The agreement band — the strongest thing this search turned up

The public comparisons of paid providers report **match-level correlations**
across five seasons and five leagues (~4,290 matches):

```
Opta      x Understat      0.96
Opta      x StatsBomb      0.92 - 0.93
StatsBomb x Understat      0.92 - 0.93
Wyscout   x the others     0.86 - 0.88
```

Computed here on the 8,825 shared shots, aggregated to 746 team-matches:

```
ours (commentary text) x StatsBomb      0.869
mean | ours - StatsBomb |               0.249 xG per team-match
median                                  0.198
max                                      1.54
mean xG: ours 1.150   StatsBomb 1.161   actual goals 1.202
```

**A model that reads only English sentences agrees with StatsBomb about as well
as a commercial provider does.** 0.869 sits inside the Wyscout band and below
the Opta/Understat/StatsBomb band. That is the sentence the abstract wants.

Two honesties attached to it:

1. **The aggregation levels are close but not identical.** Theirs is per match
   across five leagues and five seasons; this is per team-match on one league
   and one season, 373 matches. Comparable, not interchangeable.
2. **A widely repeated "~1 xG mean absolute difference between providers, max
   3.88 for Manchester City" figure was deliberately not used.** Its unit is
   unresolved — "Manchester City" and "3.88" together read as a season
   aggregate per team, which would make it far *tighter* per match than the
   0.249 here, not looser. The source paywalls. Until the unit is confirmed the
   figure is unusable, and quoting it would have been the kind of favourable
   misreading this document exists to prevent.

---

## What is still not searched

| Gap | Why it matters |
|---|---|
| **reddit.com — blocked** | r/footballanalytics is the single likeliest place for an unpublished version of this |
| **X / Twitter** | Where football analytics actually argues. Surfaced only indirectly |
| **Paid databases** | Scopus, Web of Science, IEEE. Needs institutional access |
| **Theses** | An MS thesis doing this would not appear anywhere searched |
| **Non-English** | Every query was English |
| **`eddwebster/football_analytics` not read in full** | The community's own curated index. Worth an hour with it directly |

Two of these — reddit and X — are where the calbal91 project's *discussion*
would live even though its code is on GitHub. The one hit found came from the
one platform pair that was searchable. That is not a comfortable ratio.

---

## Bottom line

- The **input idea** has been done, in a hobby project, without evaluation.
- The **measurement** — how much of a coordinate xG model words recover — has
  not been done, and F6 suggests the question has not been asked.
- **90.6% recovery**, and **0.869 correlation with StatsBomb**, is the
  contribution.
- Two side findings are **replications of Robberechts & Davis (2020)** and must
  be cited as such.
- **Check 12 is the genuinely new modelling result**, and it is new *because*
  that paper established the coordinate-side baseline.
- The negative result is weaker than the API search's, because reddit is
  blocked and one of four recall probes missed.

## To cite

1. Robberechts & Davis (2020), *How Data Availability Affects the Ability to
   Learn Good xG Models* — the staleness and transfer baselines, and the
   calibration-first position.
2. arXiv 2504.00767, *Automated Explanation of Machine Learning Models of
   Footballing Actions in Words* — this project's mirror image.
3. arXiv 2402.06820, *Forecasting Events in Soccer Matches Through Language* —
   already assessed in AUDIT check 1.
4. The Bayesian counterfactual-xG paper on StatsBomb 2015-16 — same shots,
   coordinate side.
5. `calbal91/project-moneyballing-fpl` — prior art on the input, cited as such.
6. American Soccer Analysis, *Expected Goals 3.0 Methodology* — their public
   feature set is nearly this project's field list (headed, from a cross or
   through ball, fast break, corner, penalty, logistic regression). Good
   corroboration that the phrase-derived fields are the right ones.
