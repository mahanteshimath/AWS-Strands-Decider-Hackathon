"""Turn 2026 CBP rulings into a leak-checked evaluation set.

Each ruling becomes {id, date, gold code, title, facts}: the product as an importer would
describe it, with CBP's classification reasoning removed. Steps:

  1. select   2026 New York rulings with exactly one tariff number that exists in the current
              HTS (10 digits, or 8 digits whose "00" statistical line exists); chapters 1-97
  2. cut      the passage between the ruling request and "The applicable subheading ..."
  3. rewrite  Bedrock (fast model) restates the passage as product facts only
  4. check    reject any facts that still mention codes, headings, chapters, notes, GRIs or
              classification language; retry once with the offending terms named
  5. split    a fixed, seeded split: dev (thresholds and prompts) and test (reported once)

    python data/make_eval.py --limit 400        # writes data/eval/{dev,test,rejected}.jsonl
    python data/make_eval.py --dry-run          # selection and cut statistics only, no Bedrock
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail.hts.tree import digits, load  # noqa: E402

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "eval"
SEED = 20261018
DEV_SIZE = 60

START = re.compile(r"requested a (?:binding )?(?:tariff )?classification ruling[^.]*\.|requested a ruling[^.]*\.", re.I)
END = re.compile(r"The applicable (?:subheading|tariff provision|classification)", re.I)
TITLE = re.compile(r"RE:\s*(?:The\s+)?tariff classification of\s+(.*?)(?:\s+from\s+[A-Z][\w .,'()-]+?)?\s*\.?\s*Dear", re.I)

LEAK = re.compile(
    r"\b\d{4}\.\d{2}(?:\.\d{2,4})?\b|\bHTS\w*\b|\bheadings?\b|\bsub-?headings?\b|\bchapter\s+\d|"
    r"\bclassif\w*|\bGRI\b|General Rules? of Interpretation|Explanatory Notes?|\bSection [IVX]+\b|"
    r"\bNote\s+\d|\bstatistical\b|\brestraints?\b|tariff|duty|CBP|Customs|ruling",
    re.I,
)

SYSTEM = (
    "You prepare test cases for a customs classification benchmark. You restate product "
    "descriptions as plain facts, exactly as an importer would describe the goods, and you never "
    "reveal or hint at how the goods are classified."
)
PROMPT = """Below is the factual part of a US customs ruling letter.

Write the product description an importer would submit before any classification was known.
Keep every physical and commercial fact that matters: what the article is, materials and
fiber/ingredient content with percentages, how it is made (knitted, woven, molded, cast...),
components, function and how it works, intended user (men, women, children...), dimensions,
weight, power source, packaging, and how it is sold or used.

Do NOT include: any tariff number or code, the words heading, subheading, chapter, section,
HTS, HTSUS, tariff, duty, classification, classifiable, GRI, Explanatory Notes, legal notes,
CBP, customs, ruling, restraint categories, the requester's suggested classification, or any
statement of what the goods are "considered" or "regarded as" for tariff purposes.
{feedback}
Ruling subject: {subject}

Passage:
\"\"\"{passage}\"\"\"

Reply with JSON only: {{"title": "<short product name>", "facts": "<the description, 2-8 sentences>"}}"""


def load_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def gold_for(tariffs: str, tree) -> str | None:
    codes = [c for c in re.split(r"[;,\s]+", tariffs or "") if c]
    if len(codes) != 1:
        return None
    code = digits(codes[0])
    if code[:2] in ("98", "99"):
        return None
    if code in tree.by_code and len(code) == 10:
        return code
    if len(code) == 8 and code + "00" in tree.by_code:
        return code + "00"
    if len(code) == 8 and code in tree.by_code:
        return code  # an 8-digit line with statistical breakouts: scored to 8 digits
    return None


def cut(text: str) -> str | None:
    start = START.search(text)
    end = END.search(text, start.end() if start else 0)
    if not start or not end or end.start() - start.end() < 120:
        return None
    passage = text[start.end(): end.start()].strip()
    return passage[:6000]


def title_of(subject: str) -> str:
    match = re.search(r"classification of\s+(?:an?\s+|the\s+)?(.*?)(?:\s+from\s+[A-Z].*)?\.?$", subject or "", re.I)
    return (match.group(1) if match else subject or "").strip()


def select(tree) -> list[dict]:
    rows = load_jsonl(RAW / "cross_text.jsonl")
    picked = []
    for row in rows:
        if not row["rulingDate"].startswith("2026") or not row["rulingNumber"].startswith("N"):
            continue
        if row.get("revokedBy") or row.get("modifiedBy") or row.get("operationallyRevoked"):
            continue
        gold = gold_for(row.get("tariffs"), tree)
        passage = cut(row.get("text") or "")
        if gold and passage:
            picked.append({"id": row["rulingNumber"], "date": row["rulingDate"][:10], "gold": gold,
                           "subject": row.get("subject") or "", "passage": passage})
    picked.sort(key=lambda r: r["id"])
    return picked


def leaks(text: str) -> list[str]:
    return sorted({m.group(0) for m in LEAK.finditer(text)})


def rewrite(item: dict) -> dict:
    from tariff_trail import bedrock

    feedback = ""
    for attempt in range(2):
        data, reply = bedrock.converse_json(
            PROMPT.format(feedback=feedback, subject=item["subject"], passage=item["passage"]),
            role="fast", system=SYSTEM, max_tokens=700,
        )
        title, facts = str(data.get("title", "")).strip(), str(data.get("facts", "")).strip()
        bad = leaks(title + " " + facts)
        if facts and not bad:
            return {"id": item["id"], "date": item["date"], "gold": item["gold"], "title": title, "facts": facts,
                    "model": reply.model}
        feedback = f"\nYour previous answer used forbidden terms: {', '.join(bad) or 'empty facts'}. Remove them.\n"
    return {"id": item["id"], "rejected": True, "reason": feedback.strip(), "title": title, "facts": facts}


def split(items: list[dict]) -> tuple[list[dict], list[dict]]:
    rng = random.Random(SEED)
    order = sorted(items, key=lambda r: hashlib.sha256(r["id"].encode()).hexdigest())
    rng.shuffle(order)
    return order[:DEV_SIZE], order[DEV_SIZE:]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--limit", type=int, default=400, help="how many rulings to rewrite (seeded sample)")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    tree = load()
    picked = select(tree)
    depth = {}
    for item in picked:
        depth[len(item["gold"])] = depth.get(len(item["gold"]), 0) + 1
    chapters = {}
    for item in picked:
        chapters[item["gold"][:2]] = chapters.get(item["gold"][:2], 0) + 1
    print(f"selected {len(picked)} rulings; gold depth {depth}; {len(chapters)} chapters")

    rng = random.Random(SEED)
    sample = rng.sample(picked, min(args.limit, len(picked)))
    if args.dry_run:
        raw_leaks = sum(1 for item in sample if leaks(item["passage"]))
        print(f"sample {len(sample)}; passages that would leak without the rewrite: {raw_leaks}")
        return

    OUT.mkdir(parents=True, exist_ok=True)
    done, rejected = [], []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(rewrite, item) for item in sample]
        for count, future in enumerate(as_completed(futures), 1):
            try:
                record = future.result()
            except Exception as exc:
                print(f"  error: {exc}")
                continue
            (rejected if record.get("rejected") else done).append(record)
            if count % 50 == 0:
                print(f"  {count}/{len(sample)} rewritten, {len(rejected)} rejected")

    dev, test = split(done)
    for name, rows in (("dev", dev), ("test", test), ("rejected", rejected)):
        with (OUT / f"{name}.jsonl").open("w", encoding="utf-8") as out:
            for row in sorted(rows, key=lambda r: r["id"]):
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
    meta = {"hts_release": tree.release.get("name"), "seed": SEED, "selected": len(picked), "sampled": len(sample),
            "dev": len(dev), "test": len(test), "rejected": len(rejected)}
    (OUT / "meta.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    print(meta)


if __name__ == "__main__":
    main()
