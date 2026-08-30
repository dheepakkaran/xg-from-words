# MomentumRadar

**Can the language of live football commentary predict the next goal better than the box score can?**

> This is the original design document, kept unedited. Stages 1–4 have since
> been built and run; three of the assumptions below did not survive contact
> with the data. The results, and what changed, are in
> [reports/FINDINGS.md](reports/FINDINGS.md).

Train on three completed Premier League seasons. Serve live, during matches in progress.

---

## 1. Aim

Build a system that, at any minute of a live Premier League match, estimates the probability that each side scores within the next 15 minutes — and answer whether that estimate is better made from **commentary text** or from **match statistics**.

Two deliverables:

1. **A product.** A live worklist that ranks simultaneous matches by "where is a goal about to happen" — the answer to *five matches kick off at 3pm, which one do I watch?*
2. **A finding.** A controlled comparison of two representations of the same match state: words versus numbers. The finding stands on its own regardless of which side wins.

---

## 2. Problem

Football pundits assert momentum constantly — *"Liverpool have all the momentum now"* — and analysts routinely dismiss it as narrative rather than signal. The disagreement persists because the two camps look at different data. Pundits are reacting to what they see and say; analysts are looking at shot counts and possession percentages.

Commentary is where momentum is actually *expressed in language*. It is also, conveniently, a structured, timestamped, free data stream that almost nobody in football ML uses. Existing work overwhelmingly models the box score.

That gap is the opportunity. If momentum is real, it should be detectable in the words before it is visible in the numbers.

### The practical problem

On a Saturday at 15:00 UK time, five Premier League matches run concurrently. A viewer has one screen. A broadcast producer has one output feed. Both need the same thing: a ranked answer to *which match is about to produce a goal?*

This is the same shape as a triage problem — limited attention, many candidates, rank by expected payoff.

---

## 3. Proposal

### Research question

> At minute *M* of a match, does a model built on the **last 10 commentary lines** predict the next 15 minutes of scoring better than a model built on the **cumulative match statistics** at minute *M*?

### Hypothesis

Commentary carries information that lags in the box score. A sequence like

```
11'  Corner, Chelsea. Conceded by Nathan Patterson.
12'  Corner, Chelsea. Conceded by Nathan Patterson.
14'  Attempt saved. Noni Madueke (Chelsea) shot from outside the box.
14'  Corner, Chelsea.
```

reads as sustained pressure to a human. The cumulative stat line at minute 14 reads "possession 54%, shots 3, corners 4" — balanced and unremarkable. Chelsea scored in the 27th minute.

The hypothesis is that the *density and phrasing* of recent events discriminates better than the *totals*.

### Why the result is useful either way

| Outcome | Interpretation |
|---|---|
| Text model wins | Momentum has measurable signal, and it lives in language before it lives in the box score |
| Stats model wins | Commentary is descriptive, not predictive — it narrates what the numbers already show |
| Neither beats the majority-class baseline | Next-goal timing at this horizon is close to unpredictable; a negative result worth stating plainly |

The project is designed so that a negative result is still a completed project. This is deliberate.

---

## 4. Data

**Source:** ESPN public soccer API. No API key, no registration.

```
GET https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/scoreboard?dates=YYYYMMDD
GET https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/summary?event=<event_id>
```

### Verified available

Each field below was confirmed by querying the API directly against a completed 2025 fixture (Chelsea 1–0 Everton, event `704611`) before writing this document.

| Field | Path | Detail |
|---|---|---|
| Commentary | `commentary[]` | 97 timestamped entries for that match; structured natural language |
| Goal events + minutes | `keyEvents[]` | includes explicit `Halftime` entry carrying the half-time score |
| Team statistics | `boxscore.teams[].statistics[]` | 28 stats per team — possession, shots, corners, cards, fouls, saves, offsides |
| Recent form | `lastFiveGames` | both teams |
| Bookmaker odds | `odds[]` | Bet365 pre-match prices |
| Historical backfill | `scoreboard?dates=` | confirmed working on a 2025-04-26 query |

### Scale estimate

| Quantity | Value |
|---|---|
| Seasons collected | 3 (plus current season, live) |
| Matches | ~1,140 |
| Commentary lines | ~110,000 |
| Training snapshots (5-min sampling, minutes 10–80) | ~17,000 |

### Known unknowns — to resolve in Stage 1

These are stated as open rather than assumed:

- **Live commentary latency.** Whether `commentary[]` populates during an in-progress match, and with what delay, has not been verified. All verification so far used completed fixtures. If live commentary lags by more than ~60 seconds the real-time product weakens (the research question is unaffected).
- **Historical commentary consistency.** Whether commentary depth and phrasing are stable across all three seasons, or whether older fixtures are sparser.
- **Rate limits.** The endpoint is public but undocumented. Throttling behaviour is unknown; the collector must assume limits exist and back off politely.

---

## 5. Architecture

```
                       ESPN public API
                              |
              +---------------+---------------+
              |                               |
      [ C++ live poller ]              [ Python backfill ]
       in-progress match                3 completed seasons
              |                               |
              +---------------+---------------+
                              |
                      raw commentary + events
                        (object storage)
                              |
                    [ Apache Spark ]
              windowing / feature engineering
                              |
              +---------------+---------------+
              |                               |
      Track A: numbers                Track B: words
   cumulative match stats        last 10 commentary lines
              |                               |
        [ XGBoost ]              [ Transformers -> PyTorch ]
              |                               |
              +---------------+---------------+
                              |
                     [ Comparison harness ]
                  time-based CV, calibrated
                              |
                       model registry
                              |
              +---------------+---------------+
              |                               |
      [ vLLM ] explanation          [ Qdrant ] similar
              |                        past moments
              +---------------+---------------+
                              |
                       [ LangGraph ]
                     inference orchestration
                              |
                      live ranked worklist
```

### Two paths, one source

Both feature tracks are derived from the **same commentary stream** — the numbers track counts events (`Corner, Chelsea` → corner += 1), the words track embeds the raw text. This matters: it isolates *representation* as the only variable. A comparison that drew numbers from the box score and words from commentary would confound representation with data source.

---

## 6. Stack flow

| Layer | Tool | Role | Honest assessment |
|---|---|---|---|
| Live ingest | **C++** | SSE/poll consumer for in-progress matches; parse, filter, enqueue | Justified only at multi-match concurrency. At one match Python suffices — the C++ rewrite must be motivated by a measured Python bottleneck, with before/after benchmarks |
| Batch preprocessing | **Apache Spark** | Window 110k commentary lines into ~17k training snapshots | Justified at 3+ seasons. At one season pandas is honestly enough |
| Tabular model | **XGBoost** | Track A — cumulative stats → next-goal probability | Correct tool, no reservations |
| Text encoder | **Transformers** | Sentence embeddings over the last 10 commentary lines | Off-the-shelf `sentence-transformers` first; fine-tuning only if the frozen encoder underperforms |
| Text model | **PyTorch** | Classification head over embeddings | Small model — the dataset does not support large capacity |
| Vector store | **Qdrant** | Retrieve historically similar momentum windows | Powers "this pattern occurred 14 times before; a goal followed in 9" |
| Serving | **vLLM** | Generate the plain-English reason attached to each ranked match | Explanation only. It must not score — scoring stays with the trained models |
| Orchestration | **LangGraph** | Inference flow: score → threshold → retrieve → explain | Correct fit |
| Agents | **AutoGen** | *Optional.* Weekly matchday report agent | **Redundant with LangGraph.** Included because it appears in the target stack; it earns no place in the core inference path and should be dropped unless it does independent work |
| MLOps | **Kubeflow** | Pipeline orchestration, model registry, scheduled retraining | Justified once retraining is weekly and in-season |
| CI/CD | **GitLab** | Test, build, push images, deploy | Correct fit |
| Data | **Live public API** | ESPN Premier League feed | Verified, free, key-less |

---

## 7. Procedures

Each stage produces something that runs. The project is complete and presentable at the end of Stage 4; Stages 5–9 are scale and production hardening.

### Stage 1 — Collection and labelling
Fetch three seasons of fixtures and match summaries. Store raw JSON. Build the label: from minute *M*, which side scores first within the following 15 minutes → `HOME` / `AWAY` / `NONE`.

**The critical constraint.** Features at minute *M* may use only events up to minute *M*. The label alone looks forward. This is the single easiest way to destroy the project: a feature computed over the full match will encode the answer, producing an excellent offline score and a worthless live model.

Deliverable: `snapshots.parquet`, ~17k rows.
Stack: `Python · SQLite/Parquet`

### Stage 2 — Baselines before models
Establish, in order: majority-class rate, bookmaker-implied rate, and a cumulative-stats XGBoost model.

Baselines come first on purpose. A model reported without them is uninterpretable.

Deliverable: Track A results, calibrated.
Stack: `XGBoost · scikit-learn`

### Stage 3 — Text track
Embed the last 10 commentary lines per snapshot. Train a small PyTorch head.

Deliverable: Track B results.
Stack: `Transformers · PyTorch`

### Stage 4 — The comparison
Time-based cross-validation. Same folds, same metrics, both tracks. Ablations: last-3 vs last-10 vs last-20 lines; text-only vs stats-only vs concatenated.

**This is the project.** Stages 1–3 exist to make this comparison trustworthy.

Deliverable: results table, calibration curves, written finding.
Stack: `scikit-learn`

### Stage 5 — Scale
Move feature engineering to Spark once pandas becomes the bottleneck.
Stack: `Apache Spark`

### Stage 6 — Retrieval
Index historical momentum windows in Qdrant. Given the current window, return the *k* most similar past windows and what followed.
Stack: `Qdrant`

### Stage 7 — Explanation and orchestration
LangGraph flow: score → if above threshold, retrieve similar windows → vLLM writes the reason.
Stack: `vLLM · LangGraph`

### Stage 8 — Live path
C++ poller for in-progress matches. Benchmark against the Python collector and report the delta.
Stack: `C++ · libcurl · nlohmann/json`

### Stage 9 — Production
Kubeflow pipeline with scheduled weekly retraining during the season. GitLab CI.
Stack: `Kubeflow · GitLab CI`

---

## 8. Techniques used

### Evaluation

- **Time-based splits only.** Train on earlier seasons, test on later. Random splits leak: snapshots from the same match land on both sides.
- **Overlapping-window correction.** Snapshots sampled every 5 minutes from the same match are correlated. Grouping is by match, never by row.
- **Multiclass log loss and Brier score** as headline metrics. The product needs *calibrated probabilities*, not labels — "62%" must mean 62%.
- **Calibration curves**, reported per track.
- **Precision@k** for the product framing: of the top-*k* ranked matches, how many produced a goal in the window.

### Baselines

| Baseline | Purpose |
|---|---|
| Majority class (`NONE`) | The floor. Goals are rare per 15-minute window; a model can score well while being useless |
| Bookmaker-implied rate | An external, strongly-informed reference. **This will likely not be beaten.** Reporting the gap honestly is the point |
| Cumulative stats (Track A) | The comparison target for Track B |

### Modelling

- Frozen sentence embeddings before any fine-tuning
- Class imbalance handled by weighting, with the effect on calibration measured rather than assumed
- Feature ablation to identify which commentary phrasing carries signal
- Model capacity matched to dataset size — 17k rows with a frozen encoder does not support a large head

---

## 9. ML operations

| Concern | Approach |
|---|---|
| **Orchestration** | Kubeflow pipeline: ingest → validate → featurise → train → evaluate → register. Each step containerised |
| **Data validation** | Schema and range checks between featurise and train. A commentary field that silently empties because ESPN renamed a key raises no exception anywhere else — it just quietly ruins the model. Validation failure fails the pipeline and blocks the bad model |
| **Drift** | Commentary style and squad names change across seasons. Compare each run's feature distribution against the training baseline; alert on divergence |
| **Registry** | Every trained model versioned with its data window, metrics, and git SHA |
| **Retraining** | Weekly during the season, after the last fixture of each matchweek |
| **Gating** | A new model is promoted only if it beats the incumbent on the held-out most-recent matchweek. No automatic promotion on training metrics |
| **Serving** | Trained models score; vLLM only explains. Keeping the LLM out of the scoring path means the ranking cannot silently disagree with the evaluated model |
| **Monitoring** | Live prediction logging with delayed outcome join — the same 15-minute wait as the label. Enables measuring live accuracy against offline accuracy |
| **CI/CD** | GitLab: unit tests, feature-leakage regression test, image build, deploy |

### The leakage regression test

A dedicated test asserts that no feature at minute *M* is affected by events after minute *M*. It runs in CI on every commit. Leakage is the failure mode most likely to invalidate this project, so it is defended in the test suite rather than by care alone.

---

## 10. Pipeline setup

### Offline — weekly, scheduled

```
[ ingest ]        fetch completed matchweek           -> object storage
     |
[ validate ]      schema + range checks               -> fail fast
     |
[ featurise ]     Spark windowing, both tracks        -> snapshots.parquet
     |
[ train ]         XGBoost (A) + PyTorch head (B)      -> model artifacts
     |
[ evaluate ]      time-based CV, all baselines        -> metrics.json
     |
[ gate ]          beat incumbent on latest week?      -> promote or stop
     |
[ register ]      version + metrics + data window     -> registry
```

### Online — during a live match

```
[ C++ poller ]      poll in-progress fixtures, ~15s cadence
     |
[ window ]          assemble last 10 commentary lines + running stats
     |
[ score ]           both models, from registry
     |
[ LangGraph ]       above threshold? -> Qdrant retrieve -> vLLM explain
     |
[ rank ]            order concurrent matches by goal probability
     |
[ log ]             persist prediction; join outcome after 15 min
```

The offline and online paths share feature code. They must, or training and serving drift apart — the classic training/serving skew failure.

---

## 11. Risks and honest limits

| Risk | Assessment |
|---|---|
| **The result is negative** | Entirely possible. Next-goal timing may be near-unpredictable at this horizon. The comparison is still the deliverable; the finding is reported either way |
| **Bookmaker odds are not beaten** | Expected. Odds aggregate injuries, lineups, and market information the model never sees. The gap is reported, not hidden |
| **Live commentary is too slow** | Unverified. If latency is high, the product degrades to post-match analysis. The research question survives intact |
| **Commentary is auto-generated** | If ESPN's commentary is templated from event data rather than written, the text track reduces to a re-encoding of the numbers track — and the comparison becomes trivial. **This must be checked in Stage 1**, by inspecting phrasing variety across matches. It is the single biggest threat to the premise |
| **Undocumented API** | ESPN could change or restrict the endpoint without notice. Raw responses are archived on collection so the dataset survives the source |
| **Stack is oversized for the data** | Acknowledged. Spark, Kubeflow, and C++ are justified at 3+ seasons and live multi-match serving, not at Stage 1. Each is introduced only when a measured limit demands it |

---

## 12. Timeline

| Stages | Work | Estimate |
|---|---|---|
| 1–4 | Collection, both tracks, the comparison | ~3 weekends |
| 5–7 | Spark, Qdrant, vLLM, LangGraph | ~4 weekends |
| 8–9 | C++ live path, Kubeflow, GitLab CI | ~5 weekends |

**Total ~12 weekends (3 months).** The project is complete and defensible at the end of Stage 4; everything after is production engineering.

---

## Appendix — worked example

Chelsea vs Everton, 26 April 2025. Real commentary, retrieved from the API.

**State at minute 14:**

| Track | What the model sees |
|---|---|
| A — numbers | possession 54%, shots 3, corners 4, cards 0 |
| B — words | `Corner, Chelsea.` / `Corner, Chelsea.` / `Attempt saved. Noni Madueke, shot from outside the box.` / `Corner, Chelsea.` |

**What happened:** Chelsea scored in the 27th minute.

Track A sees a broadly balanced match. Track B sees four attacking events in three minutes.

One worked example proves nothing. Seventeen thousand of them are the project.
