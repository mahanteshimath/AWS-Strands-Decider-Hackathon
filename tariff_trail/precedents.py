"""Nearest past CBP rulings for a product, as precedent for the fork adjudicator.

Built only from rulings dated before the evaluation window (2026), so no test answer can leak in.
Vectors are Titan Text Embeddings V2 (512 dims, normalised); search is a plain dot product.

    python -m tariff_trail.precedents build        # embeds pre-2026 rulings -> data/precedents/
    python -m tariff_trail.precedents search "women's knitted sweater, 44% polyamide"
"""

from __future__ import annotations

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import bedrock
from .hts.tree import digits

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw" / "cross_text.jsonl"
OUT = ROOT / "data" / "precedents"
CUTOFF = "2026-01-01"

_START = re.compile(r"requested a (?:binding )?(?:tariff )?classification ruling[^.]*\.", re.I)
_END = re.compile(r"The applicable (?:subheading|tariff provision)", re.I)


@dataclass
class Precedent:
    ruling: str
    date: str
    codes: list[str]
    subject: str
    summary: str
    score: float


def _summary(text: str) -> str:
    start = _START.search(text)
    end = _END.search(text, start.end() if start else 0)
    body = text[start.end(): end.start()] if start and end else text[:1500]
    return re.sub(r"\s+", " ", body).strip()[:1200]


def build(workers: int = 8) -> None:
    rows = []
    with RAW.open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["rulingDate"][:10] < CUTOFF and row.get("tariffs"):
                rows.append(row)
    rows.sort(key=lambda r: r["rulingNumber"])
    print(f"embedding {len(rows)} rulings dated before {CUTOFF}")

    def item(row: dict) -> tuple[dict, list[float]]:
        summary = _summary(row.get("text") or "")
        meta = {
            "ruling": row["rulingNumber"], "date": row["rulingDate"][:10], "subject": row.get("subject") or "",
            "codes": [digits(c) for c in re.split(r"[;,\s]+", row["tariffs"]) if c], "summary": summary,
        }
        return meta, bedrock.embed(f"{meta['subject']}\n{summary}")

    metas, vectors = [], []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for count, (meta, vector) in enumerate(pool.map(item, rows), 1):
            metas.append(meta)
            vectors.append(vector)
            if count % 500 == 0:
                print(f"  {count}/{len(rows)}")
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(OUT / "vectors.npy", np.asarray(vectors, dtype=np.float32))
    with (OUT / "meta.jsonl").open("w", encoding="utf-8") as out:
        for meta in metas:
            out.write(json.dumps(meta, ensure_ascii=False) + "\n")
    print(f"saved {len(metas)} precedents to {OUT}")


@lru_cache(maxsize=1)
def _index() -> tuple[np.ndarray, list[dict]]:
    vectors = np.load(OUT / "vectors.npy")
    with (OUT / "meta.jsonl").open(encoding="utf-8") as handle:
        metas = [json.loads(line) for line in handle]
    return vectors, metas


def available() -> bool:
    return (OUT / "vectors.npy").exists()


def search(facts: str, k: int = 3, prefix: str = "") -> list[Precedent]:
    """The k most similar past rulings; with `prefix`, only rulings whose code starts with it."""
    vectors, metas = _index()
    query = np.asarray(bedrock.embed(facts), dtype=np.float32)
    scores = vectors @ query
    order = np.argsort(-scores)
    out = []
    for i in order:
        meta = metas[int(i)]
        if prefix and not any(code.startswith(prefix) for code in meta["codes"]):
            continue
        out.append(Precedent(meta["ruling"], meta["date"], meta["codes"], meta["subject"], meta["summary"], float(scores[i])))
        if len(out) == k:
            break
    return out


class HeadingSeed:
    """`seed` hook for Calibrated Tree Descent: likely HTS headings from the nearest past rulings.

    Retrieval proposes, Decider decides: the descent asks Decider to choose among these headings
    (or "none of these", which falls back to the full walk from the top of the tree).
    Chapter 98/99 add-on numbers (e.g. 9903 Section 301 duties) are skipped: they are not headings
    a product is classified in. The last proposal is cached for the shortlist step and the UI.
    """

    def __init__(self, k: int = 20, n: int = 8) -> None:
        self.k, self.n = k, n
        self.last: list[Precedent] = []

    def __call__(self, tree, facts: str) -> list[str]:
        if not available():
            return []
        self.last = search(facts, k=self.k)
        weights: dict[str, float] = {}
        for p in self.last:
            for code in p.codes:
                heading = code[:4]
                if heading[:2] in ("98", "99") or f"H:{heading}" not in tree.nodes:
                    continue
                weights[heading] = weights.get(heading, 0.0) + p.score
        ranked = sorted(weights, key=weights.get, reverse=True)[: self.n]
        return [f"H:{h}" for h in ranked]

    def vote(self, tree) -> str:
        """The 10-digit code with the most similarity-weighted votes among the last search's rulings."""
        votes: dict[str, float] = {}
        for p in self.last:
            for code in p.codes:
                if code[:2] not in ("98", "99") and len(code) == 10 and code in tree.by_code:
                    votes[code] = votes.get(code, 0.0) + p.score
        return max(votes, key=votes.get) if votes else ""


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "build":
        build()
    elif len(sys.argv) >= 3 and sys.argv[1] == "search":
        for p in search(" ".join(sys.argv[2:]), k=5):
            print(f"{p.score:.3f} {p.ruling} {p.date} {p.codes} {p.subject[:80]}")
    else:
        print(__doc__)
