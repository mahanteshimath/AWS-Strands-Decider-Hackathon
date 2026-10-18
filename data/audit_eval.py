"""Audit the evaluation set for answer leakage and print a few random cases.

    python data/audit_eval.py
"""

from __future__ import annotations

import collections
import json
import random
import re
from pathlib import Path

EVAL = Path(__file__).resolve().parent / "eval"
CODE_LIKE = re.compile(r"\d{4}\.\d{2}|\b\d{6,10}\b")
LEGAL = re.compile(r"(?i)\b(heading|subheading|chapter|classif\w*|tariff|hts\w*|duty|customs|ruling|regarded|considered)\b")


def main() -> None:
    rows = [json.loads(line) for name in ("dev", "test") for line in (EVAL / f"{name}.jsonl").open(encoding="utf-8")]
    print(f"cases: {len(rows)}")
    code_like = [r["id"] for r in rows if CODE_LIKE.search(r["facts"] + " " + r["title"])]
    own_digits = [r["id"] for r in rows if r["gold"][:6] in re.sub(r"\D", "", r["facts"])]
    words = collections.Counter(m.group(1).lower() for r in rows for m in LEGAL.finditer(r["facts"]))
    print(f"code-like strings in facts: {len(code_like)} {code_like[:8]}")
    print(f"gold 6-digit prefix appears in facts digits: {len(own_digits)} {own_digits[:8]}")
    print(f"legal words in facts: {dict(words) or 'none'}")
    lengths = sorted(len(r["facts"]) for r in rows)
    print(f"facts length p10/p50/p90: {lengths[len(lengths) // 10]} / {lengths[len(lengths) // 2]} / {lengths[9 * len(lengths) // 10]} chars")
    print(f"distinct chapters: {len({r['gold'][:2] for r in rows})}, headings: {len({r['gold'][:4] for r in rows})}, codes: {len({r['gold'] for r in rows})}")
    top = collections.Counter(r["gold"][:2] for r in rows).most_common(8)
    print(f"top chapters: {top}")
    rejected = [json.loads(line) for line in (EVAL / "rejected.jsonl").open(encoding="utf-8")]
    print(f"rejected: {len(rejected)}; reasons: {[x['reason'][:80] for x in rejected[:3]]}")
    random.seed(7)
    for r in random.sample(rows, 3):
        print(f"\n{r['id']} gold {r['gold']} | {r['title']}\n  {r['facts'][:420]}")


if __name__ == "__main__":
    main()
