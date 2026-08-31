#!/bin/sh
# Rebuild every artefact in dependency order.
#
# The pipeline has an order and three things broke in one day for want of
# enforcing it: a test fixture that predated the leagues added to the corpus,
# an embeddings cache that predated a parser change, and a docs/data.json that
# predated a refit and left 90.1% on the page after the result moved to 90.6%.
# None of them raised an error; each served an old number.
#
# tests/test_artefacts_are_not_stale.py declares the same graph and fails when
# an artefact is older than what it was built from. This is how you fix it.
#
# Collection is deliberately not here. It is slow, resumable, and only needed
# when a season ends -- run it yourself:
#
#   ./run.sh src/collect.py                       # historical seasons
#   ./run.sh src/collect.py --leagues esp.1,ger.1,ita.1,fra.1,por.1 \
#       --seasons 2025-26                         # the transfer-test leagues
#   ./run.sh src/fixtures.py                      # the current calendar

set -e
cd "$(dirname "$0")"
step() { printf '\n=== %s\n' "$1"; }

step "shots and snapshots, from the raw archive"
./run.sh src/shots.py
./run.sh src/snapshots.py

step "the momentum experiment, and its horizon sweep"
./run.sh src/run_experiment.py
for h in 5 10 30; do
  ./run.sh src/run_experiment.py --horizon "$h" \
    --only "0.,1.,A.,A+E,E.,B-tfidf. last 10,C.,C+."
done
./run.sh src/plots.py

step "the xG model"
./run.sh src/train_xg.py
./run.sh src/xg.py

step "validation against StatsBomb, and the head to head"
./run.sh src/validate_xg.py
./run.sh src/head_to_head.py

step "retrieval, which also builds the embeddings the ceiling needs"
rm -f data/proc/shot_embeddings.npy
./run.sh src/retrieve.py
./run.sh src/extraction_ceiling.py

step "this season, marked against the result"
./run.sh src/scorecard.py --since 2026-08-01

step "the site, and the committed test fixture"
./run.sh src/site_data.py
./run.sh -c "import pandas as pd; d = pd.read_parquet('data/proc/shots.parquet'); \
d = d[d.season >= 2022]; \
d.drop(columns=[c for c in ('event_id','team','side') if c in d]) \
 .to_parquet('tests/fixtures/shots_sample.parquet', index=False, compression='zstd'); \
print(f'{len(d):,} rows')"

step "tests"
./run.sh -m pytest tests/ -q

printf '\nrebuilt. commit docs/, reports/, models/*.json and tests/fixtures/.\n'
