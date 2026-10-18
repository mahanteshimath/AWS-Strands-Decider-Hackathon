"""Download US Customs and Border Protection classification rulings from CROSS.

CBP rulings are US government works (public domain). Two phases:
  index  the most recent rulings matching "classification" (the search API caps at 10,000),
         newest first                                          -> data/raw/cross_index.jsonl
  text   the full ruling letter for every Classification ruling that names a tariff number
         (resumable: rulings already saved are skipped)        -> data/raw/cross_text.jsonl

    python data/fetch_cross.py                    # both phases
    python data/fetch_cross.py --skip-index       # text only, from the saved index
    python data/fetch_cross.py --since 2026-01-01 # text only for rulings on or after a date
"""

from __future__ import annotations

import argparse
import json
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _http import get_json

SEARCH = "https://rulings.cbp.gov/api/search?term=classification&collection=ALL&pageSize=100&page={page}&sortBy=DATE_DESC"
RULING = "https://rulings.cbp.gov/api/ruling/{number}"
MAX_PAGES = 100  # 100 x 100 = the API's 10,000-hit cap

RAW = Path(__file__).resolve().parent / "raw"
INDEX = RAW / "cross_index.jsonl"
TEXT = RAW / "cross_text.jsonl"

INDEX_FIELDS = (
    "rulingNumber", "subject", "categories", "rulingDate", "collection", "tariffs",
    "relatedRulings", "modifiedBy", "modifies", "revokedBy", "revokes", "operationallyRevoked",
)


def fetch_index() -> list[dict]:
    seen: dict[str, dict] = {}
    for page in range(1, MAX_PAGES + 1):
        hits = get_json(SEARCH.format(page=page)).get("rulings", [])
        if not hits:
            break
        for hit in hits:
            seen.setdefault(hit["rulingNumber"], {key: hit.get(key) for key in INDEX_FIELDS})
        if page % 10 == 0:
            print(f"  index page {page}: {len(seen)} rulings, oldest {hits[-1]['rulingDate'][:10]}")
        time.sleep(0.2)
    rows = list(seen.values())
    with INDEX.open("w", encoding="utf-8") as out:
        for row in rows:
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
    return rows


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def wants_text(row: dict, since: str | None) -> bool:
    if (row.get("categories") or "").lower() != "classification" or not row.get("tariffs"):
        return False
    return since is None or row["rulingDate"][:10] >= since


def fetch_texts(rows: list[dict], workers: int) -> None:
    done = {row["rulingNumber"] for row in load_jsonl(TEXT)}
    todo = [row for row in rows if row["rulingNumber"] not in done]
    print(f"text: {len(done)} already saved, {len(todo)} to fetch with {workers} workers")
    lock = threading.Lock()

    def fetch(row: dict) -> dict:
        ruling = get_json(RULING.format(number=row["rulingNumber"]), timeout=60)
        return {**row, "text": ruling.get("text") or ""}

    started = time.time()
    with TEXT.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch, row): row["rulingNumber"] for row in todo}
        for count, future in enumerate(as_completed(futures), 1):
            try:
                record = future.result()
            except Exception as exc:  # keep going; a rerun retries what is missing
                print(f"  failed {futures[future]}: {exc}")
                continue
            with lock:
                out.write(json.dumps(record, ensure_ascii=False) + "\n")
            if count % 250 == 0:
                rate = count / (time.time() - started)
                print(f"  {count}/{len(todo)} texts ({rate:.1f}/s)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--skip-index", action="store_true", help="reuse data/raw/cross_index.jsonl")
    parser.add_argument("--since", help="only fetch text for rulings on or after YYYY-MM-DD")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    RAW.mkdir(parents=True, exist_ok=True)
    rows = load_jsonl(INDEX) if args.skip_index else fetch_index()
    print(f"index: {len(rows)} rulings, {rows[0]['rulingDate'][:10]} .. {rows[-1]['rulingDate'][:10]}")

    fetch_texts([row for row in rows if wants_text(row, args.since)], args.workers)
    print(f"text file: {len(load_jsonl(TEXT))} rulings")


if __name__ == "__main__":
    main()
