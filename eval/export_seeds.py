"""Export the retrieval seed for every evaluation ruling, so the seeded search can run without AWS.

    python eval/export_seeds.py          # needs Bedrock (Titan embeddings) and the precedents index

Writes data/eval/seeds.jsonl: for each ruling id, the 8 candidate headings that the 20 most similar
pre-2026 rulings propose (what `HeadingSeed` gives the search) and their similarity-weighted vote
code. The notebook (notebooks/try_tarifftrail.ipynb) replays the real seeded Decider search on any
evaluation ruling from these, with only a Decider server.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail.hts.tree import load  # noqa: E402
from tariff_trail.precedents import HeadingSeed  # noqa: E402

OUT = ROOT / "data" / "eval" / "seeds.jsonl"


def main() -> None:
    tree = load()
    cases = [json.loads(line) for split in ("dev", "test") for line in (ROOT / "data" / "eval" / f"{split}.jsonl").open(encoding="utf-8")]

    def one(case: dict) -> dict:
        seed = HeadingSeed()
        headings = seed(tree, case["facts"])
        return {"id": case["id"], "headings": headings, "vote": seed.vote(tree)}

    with ThreadPoolExecutor(max_workers=4) as pool:
        rows = list(pool.map(one, cases))
    with OUT.open("w", encoding="utf-8", newline="\n") as out:
        for row in rows:
            out.write(json.dumps(row) + "\n")
    recall = sum("H:" + c["gold"][:4] in r["headings"] for c, r in zip(cases, rows)) / len(rows)
    print(f"wrote {len(rows)} seeds to {OUT} (correct heading among the 8: {recall:.1%})")


if __name__ == "__main__":
    main()
