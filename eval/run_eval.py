"""Run one system over an evaluation split and write per-case results.

    python eval/run_eval.py --system llm_direct  --split dev
    python eval/run_eval.py --system llm_agent   --split dev --workers 3
    python eval/run_eval.py --system decider_only --split dev           # on the Decider host
    python eval/run_eval.py --system tariff_trail --split test          # Decider + Bedrock shortlist pick (both recorded)

Results: eval/results/<split>/<system>.jsonl (one line per case, resumable) and a printed summary.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail import bedrock  # noqa: E402
from tariff_trail.hts.tree import load  # noqa: E402

EVAL = ROOT / "data" / "eval"
RESULTS = ROOT / "eval" / "results"
SYSTEMS = ("knn", "llm_direct", "llm_agent", "decider_only", "tariff_trail")


def match_digits(predicted: str, gold: str) -> int:
    n = 0
    for a, b in zip(predicted, gold):
        if a != b:
            break
        n += 1
    return n


def runner(system: str, tree):
    if system == "knn":
        from tariff_trail import precedents

        def run(facts: str) -> dict:
            # Retrieval only: the code with the most similarity-weighted votes among the 20 nearest
            # pre-2026 rulings that still exists in the current HTS. No LLM, no Decider.
            started = time.perf_counter()
            votes: dict[str, float] = {}
            for p in precedents.search(facts, k=20):
                for code in p.codes:
                    if code[:2] not in ("98", "99") and len(code) == 10 and tree.exists(code):
                        votes[code] = votes.get(code, 0.0) + p.score
            code = max(votes, key=votes.get) if votes else ""
            return {"code": code, "valid": bool(code), "auto": None, "llm_calls": 0, "llm_in": 0, "llm_out": 0,
                    "wall_ms": (time.perf_counter() - started) * 1000}
        return run
    if system == "llm_direct":
        from tariff_trail.baselines import llm_direct

        def run(facts: str) -> dict:
            a = llm_direct(facts, tree)
            return {"code": a.code, "valid": a.valid, "auto": None, "llm_calls": a.llm_calls, "llm_in": a.llm_input_tokens,
                    "llm_out": a.llm_output_tokens, "wall_ms": a.wall_ms, "reason": a.reason, "model": bedrock.model_for("reasoner")}
        return run
    if system == "llm_agent":
        from tariff_trail.baselines import llm_agent

        def run(facts: str) -> dict:
            a = llm_agent(facts, tree)
            return {"code": a.code, "valid": a.valid, "auto": None, "llm_calls": a.llm_calls, "llm_in": a.llm_input_tokens,
                    "llm_out": a.llm_output_tokens, "wall_ms": a.wall_ms, "tool_calls": a.tool_calls, "reason": a.reason,
                    "model": bedrock.model_for("reasoner")}
        return run

    from tariff_trail.classify import TARIFF_POLICY, TariffTrail
    from tariff_trail.decider import Decider

    def run(facts: str) -> dict:
        # One client per call keeps the per-case Decider accounting exact under threads. Every row records
        # Decider's own best path and the final (Bedrock shortlist) pick, so eval/report.py can show both.
        adjudicate = system == "tariff_trail"
        trail = TariffTrail(tree=tree, decider=Decider(), policy=TARIFF_POLICY, adjudicate=adjudicate)
        c = trail.classify(facts)
        return {"code": c.code, "valid": bool(c.code) and tree.exists(c.code), "auto": c.auto, "fast_track": c.fast_track,
                "status": c.status, "route": c.route, "p": c.p, "p_best": c.candidates[0]["p"] if c.candidates else 0.0,
                "decider_code": c.decider_code, "llm_code": c.code if adjudicate else None,
                "precedent_code": c.precedent_code, "candidates": c.candidates,
                "min_confidence": c.min_confidence, "routes": c.routes, "steps": c.steps, "adjudications": c.adjudications,
                "off_path": c.off_path, "decider_calls": c.decider_calls, "decider_ms": c.decider_ms, "llm_calls": c.llm_calls,
                "llm_in": c.llm_input_tokens, "llm_out": c.llm_output_tokens, "wall_ms": c.wall_ms,
                "model": bedrock.model_for("reasoner") if c.llm_calls else None}
    return run


def summarize(rows: list[dict]) -> dict:
    n = len(rows)
    if not n:
        return {}
    out = {"n": n}
    for depth in (2, 4, 6, 8, 10):
        out[f"acc{depth}"] = round(sum(1 for r in rows if r["match"] >= depth) / n, 4)
    out["invalid_rate"] = round(sum(1 for r in rows if not r.get("valid")) / n, 4)
    autos = [r for r in rows if r.get("auto")]
    if any(r.get("auto") is not None for r in rows):
        out["auto_share"] = round(len(autos) / n, 4)
        out["auto_acc10"] = round(sum(1 for r in autos if r["match"] >= 10) / len(autos), 4) if autos else None
    out["llm_calls_per_case"] = round(sum(r.get("llm_calls", 0) for r in rows) / n, 3)
    out["llm_tokens_per_case"] = round(sum(r.get("llm_in", 0) + r.get("llm_out", 0) for r in rows) / n, 1)
    walls = sorted(r["wall_ms"] for r in rows)
    out["p50_ms"] = round(walls[n // 2])
    out["p95_ms"] = round(walls[min(n - 1, int(n * 0.95))])
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--system", choices=SYSTEMS, required=True)
    parser.add_argument("--split", choices=("dev", "test"), default="dev")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--out-dir", help="write under eval/results/<out-dir> instead of <split> (used for the GPU latency run)")
    args = parser.parse_args()

    tree = load()
    cases = [json.loads(line) for line in (EVAL / f"{args.split}.jsonl").open(encoding="utf-8")]
    if args.limit:
        cases = cases[: args.limit]
    out_dir = RESULTS / (args.out_dir or args.split)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{args.system}.jsonl"
    done = {}
    if out_path.exists():
        for line in out_path.open(encoding="utf-8"):
            row = json.loads(line)
            done[row["id"]] = row
    todo = [c for c in cases if c["id"] not in done]
    print(f"{args.system} on {args.split}: {len(done)} done, {len(todo)} to run", flush=True)

    run = runner(args.system, tree)
    lock = threading.Lock()

    def one(case: dict) -> dict:
        started = time.perf_counter()
        try:
            got = run(case["facts"])
        except Exception as exc:
            got = {"code": "", "valid": False, "error": str(exc)[:300], "wall_ms": (time.perf_counter() - started) * 1000}
        return {"id": case["id"], "gold": case["gold"], "match": match_digits(got.get("code", ""), case["gold"]), **got}

    with out_path.open("a", encoding="utf-8") as out, ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(one, c) for c in todo]
        for count, future in enumerate(as_completed(futures), 1):
            row = future.result()
            with lock:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")
                out.flush()
                done[row["id"]] = row
            if count % 10 == 0:
                print(f"  {count}/{len(todo)}  {summarize(list(done.values()))}", flush=True)

    rows = [done[c["id"]] for c in cases if c["id"] in done]
    summary = summarize(rows)
    errors = sum(1 for r in rows if r.get("error"))
    print(json.dumps({"system": args.system, "split": args.split, "errors": errors, **summary}, indent=1))


if __name__ == "__main__":
    main()
