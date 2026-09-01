"""A literature search you can re-run, argue with, and check.

Claiming novelty from a handful of web searches is how people get embarrassed
in review. This runs a fixed set of queries against three open indexes, keeps
every result with its identifiers, and scores each one against the specific
claim being made -- so the shortlist is produced by a rule rather than by
whichever paper happened to catch my eye.

It does not decide anything. It produces a shortlist short enough to read.

Sources
  arXiv     preprints, where sports-analytics ML mostly lives first
  OpenAlex  ~250M indexed works, free, no key
  Crossref  the DOI registry

Semantic Scholar is deliberately absent: it answered 429 on every attempt.
"""
import json, os, re, sys, time, urllib.parse, urllib.request
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "litreview.json")
OUT_MD = os.path.join(HERE, "LITERATURE_REVIEW.md")
UA = "xg-from-words/1.0 (research; mailto:elusanthi16@gmail.com)"

# The claim, split into the ideas a paper would have to combine to scoop it.
CLAIM = {
    "text_input": ["commentary", "text", "textual", "natural language",
                   "narrative", "description", "report", "nlp", "language model"],
    "shot_quality": ["expected goals", "xg", "shot quality", "goal probability",
                     "chance quality", "shot outcome", "scoring probability"],
    "football": ["football", "soccer"],
}

# Tier A is the contribution itself; B is next door; C is the framing.
QUERIES = {
    "A. the contribution": [
        "expected goals from text commentary",
        "commentary text expected goals model football",
        "natural language shot quality football",
        "text derived features expected goals soccer",
        "predicting shot outcome from match commentary",
    ],
    "B. adjacent work": [
        "football commentary natural language processing analytics",
        "soccer commentary text mining events",
        "expected goals model event data machine learning",
        "language model soccer event prediction",
        "explainable expected goals natural language",
    ],
    "C. the framing": [
        "low cost alternative to tracking data football analytics",
        "open data football analytics accessibility",
        "free data sources soccer analytics research",
        "event data extraction broadcast football",
    ],
    "D. vocabulary of the nearest work": [
        "soccer commentary generation dense video captioning",
        "automated explanation machine learning footballing actions words",
        "explaining expected goals model in words large language model",
        "expected goals bayesian hierarchical player",
        "SoccerNet commentary automatic description",
        "football tweets text prediction match",
        "sports news text mining match outcome prediction",
    ],
}

# Works I already knew about before running this. If the search cannot find
# them, its recall is too low to support a claim about what does not exist.
RECALL_PROBES = {
    "Forecasting Events in Soccer Matches Through Language": "arXiv:2402.06820",
    "MatchTime": "arXiv:2406.18530",
    "Automated Explanation of Machine Learning Models of Footballing Actions in Words":
        "arXiv:2504.00767 -- the nearest work, and the opposite direction",
    "Bayes-xG": "arXiv:2311.13707",
    "SoccerNet": "SoccerNet-Echoes / commentary datasets",
    "Seq2Event": "KDD 2022",
}


def fetch(url, parse="json"):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        raw = r.read().decode("utf-8", "replace")
    return json.loads(raw) if parse == "json" else raw


def from_arxiv(q, limit=30):
    # Unquoted terms. Wrapping the whole query in quotes asks arXiv for that
    # exact phrase, which found nothing for most queries and missed papers I
    # already knew existed.
    terms = " AND ".join(f"all:{w}" for w in q.split() if len(w) > 2)
    url = ("https://export.arxiv.org/api/query?search_query="
           + urllib.parse.quote(terms)
           + f"&max_results={limit}&sortBy=relevance")
    xml = fetch(url, parse="xml")
    out = []
    for entry in re.findall(r"<entry>(.*?)</entry>", xml, re.S):
        pick = lambda tag: (re.search(rf"<{tag}>(.*?)</{tag}>", entry, re.S)
                            or [None, ""])[1]
        out.append({
            "title": " ".join(pick("title").split()),
            "abstract": " ".join(pick("summary").split()),
            "year": pick("published")[:4],
            "url": " ".join(pick("id").split()),
            "source": "arXiv",
        })
    return out


def from_openalex(q, limit=25):
    url = ("https://api.openalex.org/works?search="
           + urllib.parse.quote(q) + f"&per-page={limit}")
    d = fetch(url)
    out = []
    for w in d.get("results", []):
        inv = w.get("abstract_inverted_index") or {}
        words = sorted(((i, t) for t, ii in inv.items() for i in ii))
        out.append({
            "title": w.get("display_name") or "",
            "abstract": " ".join(t for _, t in words),
            "year": str(w.get("publication_year") or ""),
            "url": w.get("doi") or w.get("id") or "",
            "venue": ((w.get("primary_location") or {}).get("source") or {}
                      ).get("display_name") or "",
            "cited_by": w.get("cited_by_count", 0),
            "source": "OpenAlex",
        })
    return out


def from_crossref(q, limit=25):
    url = ("https://api.crossref.org/works?query="
           + urllib.parse.quote(q) + f"&rows={limit}")
    d = fetch(url)
    out = []
    for w in d.get("message", {}).get("items", []):
        out.append({
            "title": " ".join(w.get("title") or [""]),
            "abstract": re.sub(r"<[^>]+>", " ", w.get("abstract") or ""),
            "year": str((w.get("issued", {}).get("date-parts") or [[""]])[0][0]),
            "url": w.get("URL", ""),
            "venue": " ".join(w.get("container-title") or []),
            "cited_by": w.get("is-referenced-by-count", 0),
            "source": "Crossref",
        })
    return out


def norm(title):
    return re.sub(r"[^a-z0-9]+", " ", title.lower()).strip()


def score(rec):
    """How many parts of the claim this paper's text touches."""
    blob = (rec["title"] + " " + rec.get("abstract", "")).lower()
    hits = {k: [w for w in ws if w in blob] for k, ws in CLAIM.items()}
    return sum(1 for v in hits.values() if v), hits


def main():
    seen, per_query = {}, defaultdict(list)
    for tier, queries in QUERIES.items():
        for q in queries:
            for name, fn in (("arXiv", from_arxiv), ("OpenAlex", from_openalex),
                             ("Crossref", from_crossref)):
                try:
                    got = fn(q)
                except Exception as e:
                    print(f"  {name:9s} {q[:44]:44s} FAILED {e}", flush=True)
                    continue
                print(f"  {name:9s} {q[:44]:44s} {len(got):3d}", flush=True)
                for r in got:
                    if not r["title"]:
                        continue
                    k = norm(r["title"])
                    r["tier"] = tier
                    r["query"] = q
                    if k not in seen:
                        seen[k] = r
                    per_query[q].append(k)
                time.sleep(1.2)          # be polite to free indexes

    for r in seen.values():
        r["score"], r["hits"] = score(r)

    ranked = sorted(seen.values(),
                    key=lambda r: (-r["score"], -int(r.get("cited_by", 0) or 0)))
    json.dump({"queries": QUERIES, "n": len(ranked), "results": ranked},
              open(OUT_JSON, "w"), indent=1)

    print(f"\n{len(ranked)} distinct works")
    for s in (3, 2, 1, 0):
        n = sum(1 for r in ranked if r["score"] == s)
        print(f"  touching {s}/3 parts of the claim: {n}")

    print("\nEverything touching all three -- the only ones that could scoop it:")
    for r in ranked:
        if r["score"] < 3:
            break
        print(f"\n  {r['year']}  {r['title'][:88]}")
        print(f"        {r['source']}  {r.get('venue','')[:50]}  "
              f"cited {r.get('cited_by','?')}")
        print(f"        {r['url']}")
    print("\nRecall check -- can this search find work I already knew about?")
    index = {norm(r["title"]): r for r in ranked}
    missed = []
    for probe, note in RECALL_PROBES.items():
        key = norm(probe)
        hit = next((t for t in index if key in t or t in key), None)
        if not hit:
            hit = next((t for t in index
                        if all(w in t for w in key.split() if len(w) > 3)), None)
        print(f"  {'FOUND ' if hit else 'MISSED'} {probe[:46]:46s} {note}")
        if not hit:
            missed.append(probe)
    if missed:
        print(f"\n  {len(missed)} known works not found. Recall is incomplete;"
              "\n  treat the shortlist as a floor, not a proof of absence.")
    else:
        print("\n  Every known work was found. The search reaches what it"
              "\n  claims to cover.")

    print(f"\nwrote {os.path.relpath(OUT_JSON, HERE)}")


if __name__ == "__main__":
    main()
