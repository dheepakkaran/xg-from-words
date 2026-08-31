"""Qdrant — "this shot is like these ones, and here is what happened to them."

Two jobs, and the second is what earns the dependency:

1. **Explanation.** A logistic model says 0.31 and cannot say why. Neighbour
   retrieval says "the 40 closest past shots produced 12 goals", which is the
   same number with its evidence attached.
2. **A second opinion.** The neighbour goal rate is itself an xG estimate. If
   it tracks the trained model, the retrieval is faithful; if it does not, one
   of the two is wrong and worth knowing about.

Leak discipline, same as everywhere else in this repo: a shot may only be
matched against shots from *earlier seasons*. Neighbours from the same season
would let a shot see its own match.

Qdrant runs embedded here (`QdrantClient(path=...)`), because the Docker
daemon on this machine belongs to another account. The client code is the same
either way; only the constructor changes.
"""
import os, sys
import numpy as np, pandas as pd
from qdrant_client import QdrantClient
from qdrant_client.models import (Distance, VectorParams, PointStruct,
                                  Filter, FieldCondition, Range)
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, brier_score_loss

ROOT = os.path.join(os.path.dirname(__file__), "..")
PROC = os.path.join(ROOT, "data", "proc")
STORE = os.path.join(ROOT, "data", "qdrant")
COLL = "shots"
TRAIN_MAX, TEST = 2024, 2025
sys.path.insert(0, os.path.dirname(__file__))
from xg import FIELDS, xg_model


def embeddings(texts):
    cache = os.path.join(PROC, "shot_embeddings.npy")
    if os.path.exists(cache) and len(np.load(cache, mmap_mode="r")) == len(texts):
        return np.load(cache)
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    v = m.encode(list(texts), batch_size=256, convert_to_numpy=True,
                 normalize_embeddings=True, show_progress_bar=True)
    np.save(cache, v)
    return v


def build(client, df, vecs):
    """Index only the seasons a test shot is allowed to see."""
    idx = df.index[df.season <= TRAIN_MAX]
    client.recreate_collection(
        COLL, vectors_config=VectorParams(size=vecs.shape[1],
                                          distance=Distance.COSINE))
    B = 2000
    for i in range(0, len(idx), B):
        chunk = idx[i:i + B]
        client.upsert(COLL, points=[
            PointStruct(id=int(j), vector=vecs[j].tolist(),
                        payload={"season": int(df.at[j, "season"]),
                                 "goal": int(df.at[j, "goal"]),
                                 "text": df.at[j, "text"][:160]})
            for j in chunk])
    print(f"indexed {len(idx):,} shots from seasons <= {TRAIN_MAX}")
    return idx


def main(k=40):
    df = pd.read_parquet(os.path.join(PROC, "shots.parquet"))
    # Premier League only. The other five leagues exist to test whether the
    # model travels (src/transfer.py); mixing them in here would change what
    # "similar past shots" means and make the number incomparable with the
    # trained model it is being checked against.
    df = df[(df.league == "eng.1") & (df.season >= 2022)].reset_index(drop=True)
    vecs = embeddings(df.text.values)

    os.makedirs(STORE, exist_ok=True)
    client = QdrantClient(path=STORE)
    build(client, df, vecs)

    te = df.index[df.season == TEST]
    knn_xg = []
    for n, j in enumerate(te, 1):
        res = client.query_points(COLL, query=vecs[j].tolist(), limit=k,
                                  with_payload=True).points
        goals = sum(p.payload["goal"] for p in res)
        knn_xg.append(goals / max(len(res), 1))
        if n % 2000 == 0:
            print(f"  queried {n:,}/{len(te):,}", flush=True)
    knn_xg = np.array(knn_xg)

    y = df.loc[te, "goal"].values
    tr = df[df.season <= TRAIN_MAX]
    lr = xg_model().fit(tr[FIELDS], tr.goal)
    model_xg = lr.predict_proba(df.loc[te, FIELDS])[:, 1]

    print(f"\nheld-out {TEST}-26, {len(te):,} shots, k={k}")
    for nm, p in (("trained model (regex fields)", model_xg),
                  ("neighbour goal rate (Qdrant)", knn_xg),
                  ("average of the two", (model_xg + knn_xg) / 2)):
        print(f"  {nm:30s} AUC {roc_auc_score(y, p):.4f}   "
              f"brier {brier_score_loss(y, p):.4f}   mean {p.mean():.3f}")
    print(f"  {'(actual goal rate)':30s} {'':22s}       {y.mean():.3f}")
    print(f"\n  agreement between the two: r={np.corrcoef(model_xg, knn_xg)[0,1]:.3f}")

    # what an explanation looks like
    print("\nexample — the highest-rated chance in the held-out season")
    j = te[int(np.argmax(model_xg))]
    res = client.query_points(COLL, query=vecs[j].tolist(), limit=k,
                              with_payload=True).points
    g = sum(p.payload["goal"] for p in res)
    print(f'  shot : "{df.at[j, "text"][:100]}"')
    print(f"  model says {model_xg[int(np.argmax(model_xg))]:.0%}, "
          f"{g}/{len(res)} similar past shots were goals "
          f"({g/len(res):.0%}); this one "
          f"{'was' if df.at[j,'goal'] else 'was not'} a goal")
    print("  closest three:")
    for p in res[:3]:
        print(f'    {p.score:.3f}  {"GOAL" if p.payload["goal"] else "  no"}  '
              f'{p.payload["text"][:78]}')


if __name__ == "__main__":
    main()
