"""Post-hoc ablation on the frozen test run: what does each part of TariffTrail contribute?

Run after the preregistered test evaluation (research/PREREGISTRATION.md); it changes no headline
number. Every arm re-uses the recorded Decider search for each product and the same Bedrock
shortlist prompt (adjudicator.ShortlistAdjudicator, temperature 0, same model as the test run),
so the arms differ only in which candidate codes Bedrock is shown.

  retrieval4    the 4 codes with the most similarity-weighted votes among the 20 nearest past
                rulings; no Decider (the "retrieval proposes, LLM picks" design)
  decider3      Decider's top 3 complete paths; no retrieval candidate
  decider3_knn  Decider's top 3 plus the nearest-ruling vote: the frozen TariffTrail shortlist,
                re-run to measure run-to-run noise against the recorded result
  decider3_retrieval4  Decider's top 3 plus retrieval's top 4 (up to 7 candidates): a wider
                shortlist suggested by this ablation; exploratory, not a preregistered result

    python eval/ablation.py --split test --arms retrieval4 decider3 decider3_knn   # Bedrock, ~$0.35 per arm
    python eval/ablation.py --split test --markdown eval/ABLATION.md                # tables only, no AWS calls
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Same model as the recorded test run, even if a different reasoner becomes invokable later.
os.environ.setdefault("TT_REASONER_MODEL", "us.amazon.nova-pro-v1:0")

from eval.report import mcnemar_p, pct, wilson  # noqa: E402

RESULTS = ROOT / "eval" / "results"
ARMS = ("retrieval4", "decider3", "decider3_knn", "decider3_retrieval4")
K_NEAREST = 20


def read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()] if path.exists() else []


def retrieval_candidates(split: str, tree, cases: list[dict]) -> dict[str, list[list]]:
    """Ranked 10-digit codes from the 20 nearest pre-2026 rulings (Titan embeddings only), cached."""
    from tariff_trail import precedents

    path = RESULTS / split / "retrieval.jsonl"
    cached = {r["id"]: r["codes"] for r in read_jsonl(path)}
    todo = [c for c in cases if c["id"] not in cached]

    def one(case: dict) -> dict:
        votes: dict[str, float] = {}
        for p in precedents.search(case["facts"], k=K_NEAREST):
            for code in p.codes:
                if code[:2] not in ("98", "99") and len(code) == 10 and tree.exists(code):
                    votes[code] = votes.get(code, 0.0) + p.score
        ranked = sorted(votes.items(), key=lambda kv: kv[1], reverse=True)[:10]
        return {"id": case["id"], "codes": [[code, round(w, 4)] for code, w in ranked]}

    if todo:
        with ThreadPoolExecutor(max_workers=4) as pool, path.open("a", encoding="utf-8") as out:
            for rec in pool.map(one, todo):
                out.write(json.dumps(rec) + "\n")
                cached[rec["id"]] = rec["codes"]
    return cached


def shortlist_for(arm: str, row: dict, retrieved: list[list]) -> list[tuple[str, float]]:
    decider = [(c["code"], c["p"]) for c in row.get("candidates", [])[:3]]
    if arm == "retrieval4":
        return [(code, 0.0) for code, _ in retrieved[:4]]
    if arm == "decider3":
        return decider
    out = list(decider)
    if arm == "decider3_retrieval4":
        for code, _ in retrieved[:4]:
            if code not in [c for c, _ in out]:
                out.append((code, 0.0))
        return out
    knn = row.get("precedent_code") or ""
    if knn and knn not in [c for c, _ in out]:
        out.append((knn, 0.0))
    return out


def run_arm(split: str, arm: str, tree, facts: dict[str, str], trail: list[dict], retrieved: dict[str, list]) -> None:
    from tariff_trail import bedrock
    from tariff_trail.adjudicator import ShortlistAdjudicator

    path = RESULTS / split / f"ablation_{arm}.jsonl"
    done = {r["id"] for r in read_jsonl(path)}
    todo = [r for r in trail if r["id"] not in done]
    print(f"{arm}: {len(done)} done, {len(todo)} to run (model {bedrock.model_for('reasoner')})", flush=True)

    def one(row: dict) -> dict:
        shortlist = [(tree.by_code[c], p) for c, p in shortlist_for(arm, row, retrieved.get(row["id"], [])) if c in tree.by_code]
        usage = bedrock.Usage()
        adjudicator = ShortlistAdjudicator(tree, usage=usage)
        picked = adjudicator(tree, shortlist, facts[row["id"]]) if len(shortlist) > 1 else (shortlist[0][0] if shortlist else None)
        fallback = shortlist[0][0] if shortlist else None  # the arm's own top candidate if the LLM call fails
        leaf = picked or fallback
        return {"id": row["id"], "gold": row["gold"], "code": tree.code_of(leaf) if leaf else "",
                "shortlist": [tree.code_of(l) for l, _ in shortlist], "llm_calls": len(adjudicator.log),
                "reason": adjudicator.log[-1].reason if adjudicator.log else "",
                "llm_in": usage.input_tokens, "llm_out": usage.output_tokens}

    with ThreadPoolExecutor(max_workers=4) as pool, path.open("a", encoding="utf-8") as out:
        for count, rec in enumerate(pool.map(one, todo), 1):
            out.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out.flush()
            if count % 50 == 0:
                print(f"  {count}/{len(todo)}", flush=True)


def depth(a: str | None, b: str) -> int:
    n = 0
    for x, y in zip(a or "", b):
        if x != y:
            break
        n += 1
    return n


def known_codes() -> set[str]:
    """Every code used by a ruling in the retrieval index (pre-2026): the only codes retrieval can propose."""
    codes: set[str] = set()
    for meta in read_jsonl(ROOT / "data" / "precedents" / "meta.jsonl"):
        codes.update(meta["codes"])
    return codes


def report(split: str, trail: list[dict], retrieved: dict[str, list]) -> list[str]:
    n = len(trail)
    by_id = {r["id"]: r for r in trail}
    lines = [f"## Ablation on the {split} split (post-hoc; n = {n})\n",
             "Each arm shows Bedrock (same prompt, same model, temperature 0) a different shortlist; Bedrock "
             "must pick from it, so it cannot invent a code. *Shortlist recall* is the share of products whose "
             "correct 10-digit code is on the shortlist: the best any picker could do.\n",
             "| System | Decider | Retrieval | Bedrock | shortlist recall | 4-digit | **10-digit** (95% CI) | Bedrock tokens / product | only TariffTrail right / only this right (exact McNemar) |",
             "|---|---|---|---|---|---|---|---|---|"]

    def row_line(label: str, flags: str, recall: float | None, codes: dict[str, str], tokens: float | None) -> None:
        acc4 = sum(depth(codes.get(i), by_id[i]["gold"]) >= 4 for i in by_id) / n
        k = sum(depth(codes.get(i), by_id[i]["gold"]) >= 10 for i in by_id)
        lo, hi = wilson(k, n)
        tok = "0" if tokens == 0 else ("-" if tokens is None else f"{tokens:,.0f}")
        if label.startswith("**TariffTrail"):
            versus = "-"
        else:
            b = sum(ours[i] and depth(codes.get(i), by_id[i]["gold"]) < 10 for i in by_id)
            c = sum(not ours[i] and depth(codes.get(i), by_id[i]["gold"]) >= 10 for i in by_id)
            versus = f"{b} / {c} (p = {mcnemar_p(b, c):.2g})"
        lines.append(f"| {label} | {flags} | {pct(recall) if recall is not None else '-'} | {pct(acc4)} | "
                     f"**{pct(k / n)}** ({pct(lo)}-{pct(hi)}) | {tok} | {versus} |")

    ours = {i: depth(r.get("code") or r.get("decider_code"), r["gold"]) >= 10 for i, r in by_id.items()}

    retr = {i: (retrieved.get(i) or [[""]])[0][0] for i in by_id}
    row_line("Nearest past rulings (vote)", "- | yes | -", None, retr, 0)
    row_line("Strands Decider only (best path)", "yes | seeds the walk | -", None, {i: r.get("decider_code") for i, r in by_id.items()}, 0)
    arms = {}
    for arm, label, flags in (("retrieval4", "Retrieval top 4 + Bedrock pick", "- | yes | yes"),
                              ("decider3", "Decider top 3 + Bedrock pick", "yes | seeds the walk | yes"),
                              ("decider3_knn", "Decider top 3 + nearest ruling + Bedrock pick (re-run)", "yes | yes | yes"),
                              ("decider3_retrieval4", "Decider top 3 + retrieval top 4 + Bedrock pick (exploratory)", "yes | yes | yes")):
        rows = {r["id"]: r for r in read_jsonl(RESULTS / split / f"ablation_{arm}.jsonl") if r["id"] in by_id}
        if len(rows) < n:
            if rows:
                lines.append(f"| {label} | {flags} | ({len(rows)}/{n} run) | | | | |")
            continue
        arms[arm] = rows
        recall = sum(r["gold"] in r["shortlist"] for r in rows.values()) / n
        tokens = sum(r["llm_in"] + r["llm_out"] for r in rows.values()) / n
        row_line(label, flags, recall, {i: r["code"] for i, r in rows.items()}, tokens)
    recorded_recall = sum(r["gold"] in [c["code"] for c in r.get("candidates", [])[:3]] + [r.get("precedent_code")] for r in trail) / n
    row_line("**TariffTrail as recorded** (frozen test run)", "yes | yes | yes", recorded_recall,
             {i: r.get("code") or r.get("decider_code") for i, r in by_id.items()},
             sum(r.get("llm_in", 0) + r.get("llm_out", 0) for r in trail) / n)

    lines += ["\n### Who found the right code (TariffTrail as recorded)\n",
              "| correct code was ... | products | TariffTrail got it right |", "|---|---|---|"]
    groups = {"in Decider's top 3 and was the nearest-ruling vote": [], "in Decider's top 3 only (retrieval vote missed it)": [],
              "the nearest-ruling vote only (Decider's top 3 missed it)": [], "on neither": []}
    for r in trail:
        in_d = r["gold"] in [c["code"] for c in r.get("candidates", [])[:3]]
        in_k = r["gold"] == r.get("precedent_code")
        key = list(groups)[0 if in_d and in_k else 1 if in_d else 2 if in_k else 3]
        groups[key].append(r)
    for key, rows in groups.items():
        right = sum((r.get("code") or r.get("decider_code")) == r["gold"] for r in rows)
        lines.append(f"| {key} | {len(rows)} ({pct(len(rows) / n)}) | {right} |")

    lines += ["\n### Recall of the candidate generators\n", "| generator | top 1 | top 3 | top 4 | top 8 |", "|---|---|---|---|---|"]
    rec = lambda codes_of, k: sum(by_id[i]["gold"] in codes_of(i)[:k] for i in by_id) / n  # noqa: E731
    lines.append("| Retrieval vote over 20 nearest rulings | " + " | ".join(pct(rec(lambda i: [c for c, _ in retrieved.get(i, [])], k)) for k in (1, 3, 4, 8)) + " |")
    lines.append("| Decider's best complete paths | " + " | ".join(pct(rec(lambda i: [c["code"] for c in by_id[i].get("candidates", [])], k)) for k in (1, 3)) + " | - | - |")

    if "retrieval4" in arms:
        h_ours = sum(depth(r.get("code") or r.get("decider_code"), r["gold"]) >= 4 for r in trail)
        h_theirs = sum(depth(arms["retrieval4"][i]["code"], by_id[i]["gold"]) >= 4 for i in by_id)
        b4 = sum(depth(by_id[i].get("code") or by_id[i].get("decider_code"), by_id[i]["gold"]) >= 4
                 and depth(arms["retrieval4"][i]["code"], by_id[i]["gold"]) < 4 for i in by_id)
        c4 = sum(depth(by_id[i].get("code") or by_id[i].get("decider_code"), by_id[i]["gold"]) < 4
                 and depth(arms["retrieval4"][i]["code"], by_id[i]["gold"]) >= 4 for i in by_id)
        lines.append(f"\nAt the heading (4 digits), TariffTrail {h_ours}/{n} vs retrieval top 4 + Bedrock {h_theirs}/{n}: "
                     f"only TariffTrail right {b4}, only retrieval right {c4}, exact McNemar p = {mcnemar_p(b4, c4):.2g}.")
    if "decider3_knn" in arms:
        same = sum(arms["decider3_knn"][i]["code"] == (by_id[i].get("code") or by_id[i].get("decider_code")) for i in by_id)
        lines.append(f"\nRe-running the frozen shortlist step gives the same final code for {same}/{n} products "
                     f"({pct(same / n)}): the run-to-run noise of the Bedrock pick at temperature 0.")
    known = known_codes()  # empty when the retrieval index has not been built locally
    unseen = [r for r in trail if r["gold"] not in known] if known else []
    if unseen:
        in_top3 = sum(r["gold"] in [c["code"] for c in r.get("candidates", [])[:3]] for r in unseen)
        right = sum(depth(r.get("code") or r.get("decider_code"), r["gold"]) >= 10 for r in unseen)
        lines.append(f"\n{len(unseen)} of {n} products ({pct(len(unseen) / n)}) have a correct code that no ruling in the "
                     f"retrieval index (pre-2026) uses, so retrieval can never propose it. Decider's top 3 held it for {in_top3} of them; "
                     f"TariffTrail classified {right} correctly.")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="test")
    parser.add_argument("--arms", nargs="*", default=[], choices=ARMS)
    parser.add_argument("--markdown", help="write the tables to this markdown file")
    args = parser.parse_args()

    from tariff_trail.hts.tree import load

    tree = load()
    cases = read_jsonl(ROOT / "data" / "eval" / f"{args.split}.jsonl")
    facts = {c["id"]: c["facts"] for c in cases}
    trail = [r for r in read_jsonl(RESULTS / args.split / "tariff_trail.jsonl") if r["id"] in facts]
    retrieved = retrieval_candidates(args.split, tree, cases)
    for arm in args.arms:
        run_arm(args.split, arm, tree, facts, trail, retrieved)
    text = "\n".join(report(args.split, trail, retrieved))
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
