"""Stage 1 premise check - is the commentary written, or templated from events?

If it is templated, the words track is just a re-encoding of the numbers track
and the whole comparison is trivial. This measures how much the text varies
*within* a single event type.
"""
import gzip, glob, json, os, random, re
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..")
NAME = re.compile(r"\b[A-ZÁÉÍÓÚÄÖÜÑ][\w'\-]+(?:\s[A-ZÁÉÍÓÚÄÖÜÑ][\w'\-]+)*")


def skeleton(text):
    """Strip proper nouns and digits so only the template survives."""
    return re.sub(r"\d+", "#", NAME.sub("<N>", text)).strip()


def main(sample=400):
    files = sorted(glob.glob(os.path.join(ROOT, "data", "raw", "*.json.gz")))
    files = random.sample(files, min(sample, len(files)))
    by_type = defaultdict(Counter)
    per_season = defaultdict(list)
    for f in files:
        d = json.load(gzip.open(f, "rt"))
        yr = (d.get("header", {}).get("season", {}) or {}).get("year", "?")
        c = d.get("commentary", [])
        per_season[yr].append(len(c))
        for e in c:
            t = ((e.get("play") or {}).get("type") or {}).get("text", "none")
            by_type[t][skeleton(e.get("text", ""))] += 1

    print(f"{len(files)} matches sampled\n")
    print("commentary depth by season")
    for yr in sorted(per_season):
        v = per_season[yr]
        print(f"  {yr}: {len(v):4d} matches, median {sorted(v)[len(v)//2]:4d} lines, "
              f"min {min(v)}, max {max(v)}")

    print("\ntemplate variety within each event type")
    print(f"  {'event type':28s} {'lines':>7s} {'templates':>10s} {'top share':>10s}")
    for t, c in sorted(by_type.items(), key=lambda kv: -sum(kv[1].values()))[:14]:
        n = sum(c.values())
        print(f"  {t:28s} {n:7d} {len(c):10d} {c.most_common(1)[0][1]/n:10.2%}")

    shots = by_type.get("Shot Off Target", Counter())
    print("\nmost common 'Shot Off Target' templates")
    for s, n in shots.most_common(6):
        print(f"  {n:5d}  {s[:100]}")


if __name__ == "__main__":
    main()
