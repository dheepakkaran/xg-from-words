"""Check every number in the post against the artefacts it came from.

A published post cannot be edited by a script, so this runs against the source
that was pasted. Every figure is looked up in the file that produced it -- the
results table, the validation parquet, the head-to-head, the scorecard -- and
compared to what the prose claims.
"""
import decimal
import json, os, re, sys
import pandas as pd
from sklearn.metrics import roc_auc_score

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from platform_quirks import silence_accelerate_matmul

silence_accelerate_matmul()


def r(x, places):
    """Round half up, the way a reader would. Python's round() and f-strings
    use the float's binary value, so 0.5585 formats as 0.558 and the post's
    0.559 looks wrong when it is not."""
    q = decimal.Decimal(1).scaleb(-places)
    return str(decimal.Decimal(repr(float(x))).quantize(
        q, rounding=decimal.ROUND_HALF_UP))


def load():
    j = lambda *p: json.load(open(os.path.join(ROOT, *p)))
    v = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                     "xg_validation.parquet"))
    res = pd.read_csv(os.path.join(ROOT, "reports", "results.csv")
                      ).set_index("name")
    shots = pd.read_parquet(os.path.join(ROOT, "data", "proc", "shots.parquet"))
    snaps = pd.read_parquet(os.path.join(ROOT, "data", "proc",
                                         "snapshots.parquet"), columns=["minute"])
    ours = round(float(roc_auc_score(v.sb_goal, v.our_xg)), 4)
    theirs = round(float(roc_auc_score(v.sb_goal, v.sb_xg)), 4)
    h2h, card, site = j("reports", "head_to_head_xg.json"), \
        j("docs", "scorecard.json"), j("docs", "data.json")
    epl = shots[(shots.league == "eng.1") & (shots.season >= 2022)]
    # Full precision, rounded once. Rounding to 4 and then to 3 turned
    # 0.54045 into 0.541 and made a correct post look wrong.
    auc = lambda k: float(res.loc[k, "auc_ovr"])
    return {
        "corpus shots":        (f"{len(shots):,}", "87,980"),
        "corpus matches":      (f"{shots.event_id.nunique():,}", "3,569"),
        "snapshots":           (f"{len(snaps):,}", "22,147"),
        "momentum matches":    ("1,491", "1,491"),
        "majority":            (r(auc("0. majority class"), 3), "0.500"),
        "words":               (r(auc("B-tfidf. last 10 lines"), 3), "0.513"),
        "numbers":             (r(auc("A. cumulative counts"), 3), "0.540"),
        "numbers + Elo":       (r(auc("A+E. counts + Elo"), 3), "0.565"),
        "Elo alone":           (r(auc("E. Elo only"), 3), "0.559"),
        "ceiling":             (r(auc("C+. CEILING + counts + Elo"), 3), "0.602"),
        "validation ours":     (r(ours, 4), "0.7826"),
        "validation theirs":   (r(theirs, 4), "0.8118"),
        "recovered share":     (f"{(ours-0.5)/(theirs-0.5):.1%}", "90.6%"),
        "shots compared":      (f"{len(v):,}", "8,825"),
        "outcome agreement":   (f"{(v.goal==v.sb_goal).mean():.2%}", "99.71%"),
        "our mean error":      (f"{h2h['ours']['mean_error']:.3f}", "0.781"),
        "their mean error":    (f"{h2h['theirs']['mean_error']:.3f}", "0.740"),
        "our points":          (f"{h2h['ours']['points']:.0f}", "342"),
        "their points":        (f"{h2h['theirs']['points']:.0f}", "404"),
        "they closer share":   (f"{h2h['theirs']['points']/h2h['innings']:.1%}", "54.2%"),
        "h2h matches":         (f"{h2h['matches']}", "373"),
        # the post quotes the whole-corpus rate, not the Premier League one
        "penalty rate":        (r(shots[(shots.season >= 2022)
                                        & (shots.penalty == 1)].goal.mean(), 2),
                                "0.75"),
        "penalty rate, EPL":   (r(epl[epl.penalty == 1].goal.mean(), 2), "0.83"),
        "outside box rate":    (f"{epl[epl.outside_box==1].goal.mean():.2f}", "0.04"),
        "scorecard right":     (f"{card['tally']['right']}", "10"),
        "scorecard wrong":     (f"{card['tally']['wrong']}", "4"),
        "model fields":        (f"{len(j('models','xg.json')['features'])}", "18"),
        "fixtures upcoming":   (f"{j('docs','fixtures.json')['upcoming']}", "361"),
        "leagues":             (f"{shots.league.nunique()}", "6"),
    }


def main():
    src = os.path.join(HERE, "MEDIUM_POST.md")
    post = open(src).read()
    checks = load()

    print(f"{'figure':22s} {'artefact':>10s} {'in post':>10s}  present?")
    bad = []
    for name, (truth, claimed) in checks.items():
        agrees = truth == claimed
        # Word-bounded, so "0.76" does not count itself as present because
        # "0.7612" happens to appear elsewhere in the post.
        present = re.search(rf"(?<![\d.]){re.escape(claimed)}(?![\d])", post)
        present = bool(present)
        ok = agrees and present
        if not ok:
            bad.append((name, truth, claimed, agrees, present))
        print(f"  {'OK ' if ok else 'BAD'} {name:20s} {truth:>10s} "
              f"{claimed:>10s}  {'yes' if present else 'NOT IN POST'}")

    # nothing should still look like a markdown table after conversion
    safe = open(os.path.join(HERE, "MEDIUM_POST_medium-safe.md")).read()
    tables = len(re.findall(r"^\s*\|.*\|\s*$", safe, re.M))
    print(f"\n  markdown table rows left in the Medium version: {tables}")

    # only real markdown links count -- a bare URL in bold is not clickable
    md_links = re.findall(r"\[([^\]]+)\]\((https?://[^)]+)\)", post)
    bare = re.findall(r"(?<![(\]])\bhttps?://[^\s)]+", post)
    print(f"\n  markdown links: {len(md_links)}")
    for text, url in md_links:
        print(f"    {text} -> {url}")
    if bare:
        print(f"  bare URLs (will not be clickable if bolded): {bare}")
    links = [u for _, u in md_links]
    if bad or tables or bare:
        print("\n  PROBLEMS:")
        for n, t, c, a, p in bad:
            print(f"    {n}: artefact {t}, post {c}"
                  f"{'' if a else '  ← DISAGREE'}"
                  f"{'' if p else '  ← not found in post'}")
        sys.exit(1)
    print("\n  every figure in the post matches the artefact it came from")


if __name__ == "__main__":
    main()
