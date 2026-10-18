"""Can one Decider call verify TariffTrail's shortlist? (offline probe over recorded dev rows)

One request per product. The state lists the top complete candidates with their full official
wording; the questions share that state (and the server's prefix cache):

    pick     choice  Which candidate is the correct classification? (+ none of these)
    ok_A..C  noul    Is candidate A the correct classification?

Writes eval/results/<split>/verify.jsonl and prints how well each answer separates right from wrong.

    python eval/verify_probe.py --split dev          # on the Decider host
"""

from __future__ import annotations

import argparse
import json
import string
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail.decider import Decider, choice, noul  # noqa: E402
from tariff_trail.hts.tree import load  # noqa: E402

RESULTS = ROOT / "eval" / "results"


def state_for(tree, facts: str, codes: list[str]) -> str:
    lines = [f"PRODUCT FACTS:\n{facts}\n", "CANDIDATE CLASSIFICATIONS (official tariff wording, most specific line last):"]
    for letter, code in zip(string.ascii_uppercase, codes):
        node = tree.by_code[code]
        path = " > ".join(n.text.rstrip(":") for n in tree.path(node) if n.kind in ("heading", "line"))
        lines.append(f"\n{letter}. {tree[node].htsno}: {path}")
    return "\n".join(lines)


def questions(n: int) -> dict:
    letters = string.ascii_uppercase[:n]
    out = {"pick": choice(
        "Which candidate is the correct US tariff classification for the product?",
        {**{l: f"candidate {l}" for l in letters}, "none": "none of the candidates is correct"},
    )}
    for l in letters:
        out[f"ok_{l}"] = noul(
            f"Is candidate {l} the correct and most specific US tariff classification for the product?",
            {"true": f"candidate {l} describes the product exactly", "false": f"candidate {l} is wrong or less specific than another line"},
        )
    return out


def auroc(scores, labels):
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    return sum((p > q) + 0.5 * (p == q) for p in pos for q in neg) / (len(pos) * len(neg))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()
    tree = load()
    facts = {json.loads(l)["id"]: json.loads(l)["facts"] for l in (ROOT / "data" / "eval" / f"{args.split}.jsonl").open(encoding="utf-8")}
    rows = [json.loads(l) for l in (RESULTS / args.split / "tariff_trail.jsonl").open(encoding="utf-8")]
    out_path = RESULTS / args.split / "verify.jsonl"
    done = {json.loads(l)["id"] for l in out_path.open(encoding="utf-8")} if out_path.exists() else set()
    decider = Decider()
    with out_path.open("a", encoding="utf-8") as out:
        for row in rows:
            if row["id"] in done:
                continue
            codes = []
            for c in [row.get("llm_code")] + [c["code"] for c in row.get("candidates", [])]:
                if c and c not in codes and c in tree.by_code:
                    codes.append(c)
            codes = codes[:3]
            if len(codes) < 1:
                continue
            answers = decider.ask(state_for(tree, facts[row["id"]], codes), questions(len(codes)))
            letters = string.ascii_uppercase[: len(codes)]
            record = {
                "id": row["id"], "gold": row["gold"], "codes": codes,
                "pick": answers["pick"]["choice"], "pick_probs": answers["pick"]["probabilities"],
                "pick_conf": answers["pick"]["confidence"],
                "ok": {code: answers[f"ok_{l}"]["noul"] for l, code in zip(letters, codes)},
                "latency_ms": decider.stats.latencies_ms[-1],
            }
            out.write(json.dumps(record) + "\n")
            out.flush()

    recs = [json.loads(l) for l in out_path.open(encoding="utf-8")]
    letters = string.ascii_uppercase
    pick_code = lambda r: r["codes"][letters.index(r["pick"])] if r["pick"] in letters[: len(r["codes"])] else None
    print(f"{len(recs)} products; mean latency {sum(r['latency_ms'] for r in recs) / len(recs):.0f} ms per verify call")
    print(f"gold among the verified candidates: {sum(r['gold'] in r['codes'] for r in recs)}")
    print(f"Decider pick correct: {sum(pick_code(r) == r['gold'] for r in recs)}")
    best_ok = lambda r: max(r["ok"], key=r["ok"].get)
    print(f"highest ok_* correct: {sum(best_ok(r) == r['gold'] for r in recs)}")
    for name, code_fn, score_fn in (
        ("pick confidence", pick_code, lambda r: r["pick_conf"]),
        ("pick probability", pick_code, lambda r: r["pick_probs"].get(r["pick"], 0)),
        ("ok of picked", pick_code, lambda r: r["ok"].get(pick_code(r) or "", 0)),
        ("max ok", best_ok, lambda r: max(r["ok"].values())),
    ):
        labels = [code_fn(r) == r["gold"] for r in recs]
        scores = [score_fn(r) for r in recs]
        a = auroc(scores, labels)
        order = sorted(range(len(recs)), key=lambda i: scores[i], reverse=True)
        cuts = []
        for frac in (0.2, 0.33, 0.5):
            top = order[: max(1, int(frac * len(recs)))]
            cuts.append(f"top{int(frac * 100)}% {sum(labels[i] for i in top)}/{len(top)}")
        print(f"  {name:18} AUROC {('-' if a is None else f'{a:.2f}')}  " + "  ".join(cuts))


if __name__ == "__main__":
    main()
