"""Re-run the Bedrock shortlist step offline on recorded TariffTrail rows (no Decider needed).

Tests shortlist variants on the dev split, e.g. adding the nearest past ruling's code as a 4th
candidate. Writes eval/results/<split>/readjudicate_<variant>.jsonl.

    python eval/readjudicate.py --split dev --variant top3_plus_knn
"""

from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail import bedrock  # noqa: E402
from tariff_trail.adjudicator import ShortlistAdjudicator  # noqa: E402
from tariff_trail.hts.tree import load  # noqa: E402

RESULTS = ROOT / "eval" / "results"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    parser.add_argument("--variant", default="top3_plus_knn", choices=("top3", "top3_plus_knn"))
    args = parser.parse_args()
    tree = load()
    facts = {json.loads(l)["id"]: json.loads(l)["facts"] for l in (ROOT / "data" / "eval" / f"{args.split}.jsonl").open(encoding="utf-8")}
    rows = [json.loads(l) for l in (RESULTS / args.split / "tariff_trail.jsonl").open(encoding="utf-8")]
    knn = {json.loads(l)["id"]: json.loads(l) for l in (RESULTS / args.split / "knn.jsonl").open(encoding="utf-8")}

    def one(row: dict) -> dict:
        shortlist = [(tree.by_code[c["code"]], c["p"]) for c in row["candidates"][:3] if c["code"] in tree.by_code]
        knn_code = knn.get(row["id"], {}).get("code")
        if args.variant == "top3_plus_knn" and knn_code in tree.by_code and knn_code not in [c["code"] for c in row["candidates"][:3]]:
            shortlist.append((tree.by_code[knn_code], 0.0))
        usage = bedrock.Usage()
        adjudicator = ShortlistAdjudicator(tree, usage=usage)
        picked = adjudicator(tree, shortlist, facts[row["id"]]) if len(shortlist) > 1 else (shortlist[0][0] if shortlist else None)
        code = tree.code_of(picked) if picked else row["decider_code"]
        return {"id": row["id"], "gold": row["gold"], "code": code, "decider_code": row["decider_code"], "knn_code": knn_code,
                "shortlist": [tree.code_of(l) for l, _ in shortlist], "reason": adjudicator.log[-1].reason if adjudicator.log else "",
                "llm_in": usage.input_tokens, "llm_out": usage.output_tokens}

    with ThreadPoolExecutor(max_workers=4) as pool:
        out = list(pool.map(one, rows))
    path = RESULTS / args.split / f"readjudicate_{args.variant}.jsonl"
    with path.open("w", encoding="utf-8") as handle:
        for rec in out:
            handle.write(json.dumps(rec) + "\n")

    n = len(out)
    right = sum(r["code"] == r["gold"] for r in out)
    ceiling = sum(r["gold"] in r["shortlist"] for r in out)
    agree = [r for r in out if r["code"] == r["decider_code"] == r["knn_code"]]
    agree2 = [r for r in out if r["code"] == r["knn_code"]]
    print(f"{args.variant}: {right}/{n} = {right / n:.1%} correct at 10 digits; gold on shortlist {ceiling}/{n}")
    print(f"  tokens/product {sum(r['llm_in'] + r['llm_out'] for r in out) / n:.0f}")
    print(f"  final == Decider == nearest: {len(agree)} cases, {sum(r['code'] == r['gold'] for r in agree)} correct")
    print(f"  final == nearest: {len(agree2)} cases, {sum(r['code'] == r['gold'] for r in agree2)} correct")


if __name__ == "__main__":
    main()
