# Has anyone done this already?

A search you can re-run, with its limits stated. Run on 2026-08-31 by
`writing/litreview.py`; raw results in `writing/litreview.json`.

---

## The short answer

**Nothing found does what this project does.** The nearest work is the same
idea pointed the other way.

But read the limits section before quoting that. A search is evidence that
something is *hard to find*, not proof that it does not exist.

---

## What was actually claimed, and how it was tested

The claim has three parts. A paper only scoops this project if it has all
three at once:

1. the **input is natural-language text** — commentary, a report, prose
2. the **output is shot quality** — expected goals, goal probability
3. the sport is **football**

So every result is scored on how many of the three its title and abstract
touch. Anything scoring 3 gets read in full. Nothing is judged by whether it
caught my eye.

## What was searched

Three open indexes, no paid databases:

```
arXiv     preprints, where sports-analytics ML appears first
OpenAlex  ~250M indexed works
Crossref  the DOI registry
```

Semantic Scholar is missing on purpose: it answered `429 Too Many Requests`
on every attempt.

**24 queries across four groups:** the contribution itself, adjacent work, the
framing about data cost, and — added after the first run came back too clean —
the vocabulary of papers I already knew existed.

```
802 distinct works
 12 touch all three parts of the claim
 93 touch two
395 touch one
302 touch none
```

## The limits — read this before quoting the answer

**Recall is about 5 out of 6, and it moves between runs.**

The search is checked against six works I knew about before starting. If it
cannot find those, it cannot support a claim about what does not exist. Across
runs it found five of six — but not always the same five. `MatchTime` was
found on one run and missed on the next, because these indexes do not return
identical results twice.

So: **this is a floor, not a proof of absence.** It is good enough to say "this
looks unexplored" and not good enough to say "nobody has done this".

Three specific gaps:

* **No paid databases.** Scopus, Web of Science and IEEE Xplore are not
  searched. A supervisor with institutional access should redo this.
* **No thesis or dissertation repositories.** A master's thesis doing exactly
  this would not appear.
* **No blogs.** Football analytics has a large, serious, unindexed blog
  literature — StatsBomb, American Soccer Analysis, Opta — and something like
  this could well live there without ever becoming a paper.

That last one is the most likely place to be scooped, and the hardest to check.

## What the twelve closest works actually are

Every work touching all three parts, read in full. **None of them takes
natural-language text as model input.**

| # | Work | What it actually does |
|---|---|---|
| 1 | Seq2Event (KDD 2022) | Treats structured event records as tokens. "Language" is a metaphor — the input is WyScout data, not prose |
| 2 | Comparative Analysis of xG Models (2024) | Compares Opta and Understat. Coordinates in |
| 3 | EPV vs xG in the Bundesliga (2025) | Which metric predicts results better. Event data |
| 4 | xG for 5-a-side blind football (2026) | An xG model for a Paralympic sport. Positional |
| 5 | Football analytics for betting (2021) | Pitch partitioning and possession sequences |
| 6 | xG and goal scoring across competitions (2026) | Correlation study. Data scraped from Sofascore |
| 7 | Temporal patterns of shot quality (2026) | How shot quality changes over 15-minute intervals |
| 8 | Adjusting xG for game context (2026) | Corrects xG for scoreline and red cards |
| 9 | GoalNet (2025) | A graph network for valuing players |
| 10 | Play detection from GPS (2025) | American football, GPS traces |
| 11 | **Automated Explanation of Footballing Actions in Words** (2025) | **The nearest work — and the reverse.** Takes an xG model's coefficients and writes sentences explaining them, so coaches can read the model |
| 12 | What If They Took the Shot? (2025) | Bayesian per-player finishing effects. **Uses 9,970 shots from StatsBomb 2015-16** — the same dataset used here, from the coordinates side |

The last two are the useful ones.

**#11 is this project in a mirror.** They turn a model into words. This turns
words into a model. Both directions being worked on is a good sign for the
question mattering; it does not make either one the other.

**#12 uses the same season and dataset from the other side.** They take
StatsBomb 2015-16's coordinates; this takes the same matches' commentary. That
makes it the natural comparison and an obvious citation.

## What is and is not novel

Being precise matters more than being encouraging.

**Not novel, and should not be claimed:**

* expected goals models — two decades of them
* NLP on football commentary — commentary generation, event detection, audio
  alignment all exist
* treating structured events as a language — Seq2Event and others

**Appears unexplored, on this evidence:**

* using **free commentary text as the input** to a shot-quality model
* **measuring how much of a commercial coordinate-based model is recoverable**
  from that text — the 90.6% figure. Nothing found puts a number on the gap
  between what the words carry and what the cameras carry
* **the ceiling method applied to momentum** — bounding a negative result by
  building a model that sees the future. The technique is not new; using it to
  say *how unpredictable* next-goal timing is appears to be

The second of those is the strongest. It is a measurement nobody seems to have
taken, it is falsifiable, and it matters to anyone who cannot afford the data.

## What to do with this

1. **Do not claim novelty from this document alone.** It is a good first pass
   with stated holes.
2. **Have someone redo it with Scopus and Web of Science.** A supervisor has
   the access; that closes the biggest gap.
3. **Search the blogs by hand.** StatsBomb's articles, American Soccer
   Analysis, Opta Analyst, and the r/soccernerd corners of the internet. An
   afternoon. This is where the risk is.
4. **Cite #11 and #12 whatever happens.** #11 is the mirror image and #12
   shares the dataset — a reviewer who knows the field will look for both.

---

*Re-run with `./run.sh writing/litreview.py`. The queries are at the top of
that file; add to them rather than replacing them, so the record grows.*
