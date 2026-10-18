"""How often do the nearest pre-2026 rulings already contain the right heading? (no Decider needed)

    python eval/knn_probe.py --split dev
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail import precedents  # noqa: E402


def ranked_prefixes(found, width: int) -> list[str]:
    out: list[str] = []
    for p in found:
        for code in p.codes:
            prefix = code[:width]
            if code[:2] in ("98", "99"):  # add-on numbers (e.g. 9903 Section 301), not product headings
                continue
            if len(prefix) == width and prefix not in out:
                out.append(prefix)
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    parser.add_argument("--k", type=int, default=20)
    args = parser.parse_args()
    cases = [json.loads(l) for l in (ROOT / "data" / "eval" / f"{args.split}.jsonl").open(encoding="utf-8")]
    hits = {w: {1: 0, 3: 0, 5: 0, 8: 0} for w in (2, 4, 6, 10)}
    misses = []
    for case in cases:
        found = precedents.search(case["facts"], k=args.k)
        for width in hits:
            ranked = ranked_prefixes(found, width)
            for top in hits[width]:
                hits[width][top] += case["gold"][:width] in ranked[:top]
        heads = ranked_prefixes(found, 4)
        if case["gold"][:4] not in heads[:5]:
            misses.append((case["id"], case["gold"][:4], heads[:5], case["title"]))
    n = len(cases)
    print(f"{n} cases, k={args.k} nearest pre-2026 rulings")
    for width, row in hits.items():
        print(f"  {width:2}-digit recall: " + "  ".join(f"top{t}={100 * v / n:.0f}%" for t, v in row.items()))
    print("\nheading not in top 5:")
    for miss in misses:
        print("  ", miss)


if __name__ == "__main__":
    main()
