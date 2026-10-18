"""Summarise evaluation results: accuracy by depth, the auto-clear threshold sweep, calibration, cost.

    python eval/report.py --split dev                 # print tables
    python eval/report.py --split test --threshold 0.5 --markdown eval/RESULTS_test.md

TariffTrail rows record both Decider's best path (`decider_code`, `p_best`) and Bedrock's
shortlist pick (`llm_code`). At an auto-clear threshold t the deployed system returns Decider's
answer with no LLM call when p_best >= t, and Bedrock's pick otherwise; this script applies any t
offline. LLM cost is therefore counted only for the cases below t.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
THRESHOLDS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]


def match(a: str | None, b: str) -> int:
    n = 0
    for x, y in zip(a or "", b):
        if x != y:
            break
        n += 1
    return n


def load(split: str, system: str) -> list[dict]:
    path = RESULTS / split / f"{system}.jsonl"
    if not path.exists():
        return []
    rows = {}
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        rows[row["id"]] = row
    return list(rows.values())


def depth_accuracy(codes: list[tuple[str | None, str]]) -> dict[str, float]:
    n = len(codes) or 1
    return {f"acc{d}": sum(1 for got, gold in codes if match(got, gold) >= d) / n for d in (2, 4, 6, 8, 10)}


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    return values[min(len(values) - 1, int(q * len(values)))]


def baseline_summary(rows: list[dict]) -> dict:
    n = len(rows)
    out = {"n": n, **depth_accuracy([(r.get("code"), r["gold"]) for r in rows])}
    out["invalid"] = sum(1 for r in rows if not r.get("valid")) / n
    out["llm_calls"] = sum(r.get("llm_calls", 0) for r in rows) / n
    out["llm_tokens"] = sum(r.get("llm_in", 0) + r.get("llm_out", 0) for r in rows) / n
    out["p50_s"] = percentile([r["wall_ms"] for r in rows], 0.5) / 1000
    out["p95_s"] = percentile([r["wall_ms"] for r in rows], 0.95) / 1000
    return out


def final_summary(rows: list[dict]) -> dict:
    n = len(rows)
    out = {"n": n, **depth_accuracy([(r.get("code") or r.get("decider_code"), r["gold"]) for r in rows])}
    out["invalid"] = sum(1 for r in rows if not r.get("valid", True)) / n
    out["llm_calls"] = sum(r.get("llm_calls", 0) for r in rows) / n
    out["llm_tokens"] = sum(r.get("llm_in", 0) + r.get("llm_out", 0) for r in rows) / n
    return out


def trail_at(rows: list[dict], t: float) -> dict:
    n = len(rows)
    chosen, auto_rows, llm_tokens, llm_calls = [], [], 0, 0
    for r in rows:
        is_auto = r.get("p_best", 0.0) >= t
        code = r.get("decider_code") if is_auto else (r.get("llm_code") or r.get("decider_code"))
        chosen.append((code, r["gold"]))
        if is_auto:
            auto_rows.append(r)
        else:
            llm_calls += r.get("llm_calls", 0)
            llm_tokens += r.get("llm_in", 0) + r.get("llm_out", 0)
    out = {"t": t, "n": n, **depth_accuracy(chosen)}
    out["auto_share"] = len(auto_rows) / n
    out["auto_acc10"] = (sum(1 for r in auto_rows if match(r.get("decider_code"), r["gold"]) >= 10) / len(auto_rows)) if auto_rows else None
    out["llm_calls"] = llm_calls / n
    out["llm_tokens"] = llm_tokens / n
    out["invalid"] = 0.0
    return out


def decider_summary(rows: list[dict]) -> dict:
    n = len(rows)
    out = {"n": n, **depth_accuracy([(r.get("decider_code"), r["gold"]) for r in rows])}
    out["top3_acc10"] = sum(1 for r in rows if any(c["code"] == r["gold"] for c in r.get("candidates", [])[:3])) / n
    out["decider_calls"] = sum(r.get("decider_calls", 0) for r in rows) / n
    out["off_path"] = sum(r.get("off_path", 0) for r in rows) / n
    out["p50_s"] = percentile([r["wall_ms"] for r in rows], 0.5) / 1000
    out["p95_s"] = percentile([r["wall_ms"] for r in rows], 0.95) / 1000
    out["decider_ms_per_call"] = sum(r.get("decider_ms", 0) for r in rows) / max(1, sum(r.get("decider_calls", 0) for r in rows))
    return out


def calibration(rows: list[dict], bins: int = 5) -> list[dict]:
    out = []
    for i in range(bins):
        lo, hi = i / bins, (i + 1) / bins
        inside = [r for r in rows if lo <= r.get("p_best", 0.0) < hi or (i == bins - 1 and r.get("p_best", 0.0) == 1.0)]
        if inside:
            right = sum(1 for r in inside if match(r.get("decider_code"), r["gold"]) >= 10)
            out.append({"bin": f"{lo:.1f}-{hi:.1f}", "n": len(inside), "mean_p": sum(r["p_best"] for r in inside) / len(inside),
                        "acc10": right / len(inside)})
    return out


def pct(x) -> str:
    return "-" if x is None else f"{100 * x:.1f}%"


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """95% Wilson score interval for k successes out of n."""
    if n == 0:
        return 0.0, 0.0
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return centre - half, centre + half


def mcnemar_p(b: int, c: int) -> float:
    """Exact two-sided McNemar p-value: b = only A right, c = only B right."""
    from math import comb

    n = b + c
    if n == 0:
        return 1.0
    tail = sum(comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def significance(split: str, trail: list[dict]) -> list[str]:
    # Same correctness rule as the accuracy tables: the first 10 digits match the ruling's code.
    ours = {r["id"]: match(r.get("code") or r.get("decider_code"), r["gold"]) >= 10 for r in trail}
    k = sum(ours.values())
    lo, hi = wilson(k, len(ours))
    out = [f"\n### Uncertainty\n", f"TariffTrail 10-digit: {k}/{len(ours)} = {pct(k / len(ours))} (95% CI {pct(lo)}-{pct(hi)})\n",
           "| vs | their 10-digit (95% CI) | only TariffTrail right | only them right | exact McNemar p |", "|---|---|---|---|---|"]
    for system, label in (("knn", "Nearest past rulings"), ("llm_agent", "LLM agent + tools"), ("llm_direct", "LLM, direct")):
        rows = {r["id"]: match(r.get("code"), r["gold"]) >= 10 for r in load(split, system)}
        shared = [i for i in ours if i in rows]
        if not shared:
            continue
        theirs = sum(rows[i] for i in shared)
        a, b = wilson(theirs, len(shared))
        only_us = sum(1 for i in shared if ours[i] and not rows[i])
        only_them = sum(1 for i in shared if rows[i] and not ours[i])
        p = mcnemar_p(only_us, only_them)
        out.append(f"| {label} | {pct(theirs / len(shared))} ({pct(a)}-{pct(b)}) | {only_us} | {only_them} | {p:.2g} |")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--split", default="dev")
    parser.add_argument("--threshold", type=float, default=0.5, help="auto-clear threshold to headline")
    parser.add_argument("--markdown", help="also write the tables to this markdown file")
    args = parser.parse_args()

    lines: list[str] = []
    emit = lines.append
    emit(f"## Results on the {args.split} split\n")
    emit("| System | n | 2-digit | 4-digit | 6-digit | 8-digit | **10-digit** | invalid codes | LLM calls / product | LLM tokens / product | auto-cleared | auto-cleared correct |")
    emit("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for system, label in (("knn", "Nearest past rulings (retrieval only)"), ("llm_direct", "LLM, direct answer"),
                          ("llm_agent", "LLM agent + HTS search tools (Strands)")):
        rows = load(args.split, system)
        if rows:
            s = baseline_summary(rows)
            emit(f"| {label} | {s['n']} | {pct(s['acc2'])} | {pct(s['acc4'])} | {pct(s['acc6'])} | {pct(s['acc8'])} | **{pct(s['acc10'])}** | "
                 f"{pct(s['invalid'])} | {s['llm_calls']:.2f} | {s['llm_tokens']:,.0f} | - | - |")
    trail = load(args.split, "tariff_trail")
    if trail:
        d = decider_summary(trail)
        emit(f"| Strands Decider only (best path) | {d['n']} | {pct(d['acc2'])} | {pct(d['acc4'])} | {pct(d['acc6'])} | {pct(d['acc8'])} | "
             f"**{pct(d['acc10'])}** | 0.0% | 0 | 0 | - | - |")
        s = final_summary(trail)
        emit(f"| **TariffTrail** (Decider search + one Bedrock shortlist call) | {s['n']} | {pct(s['acc2'])} | {pct(s['acc4'])} | {pct(s['acc6'])} | "
             f"{pct(s['acc8'])} | **{pct(s['acc10'])}** | {pct(s['invalid'])} | {s['llm_calls']:.2f} | {s['llm_tokens']:,.0f} | 0% (by policy) | - |")

        emit("\n### Review tiers (TariffTrail never auto-files a tariff code)\n")
        emit("| tier | products | correct at 10 digits |")
        emit("|---|---|---|")
        fast = [r for r in trail if r.get("code") and r.get("code") == r.get("decider_code") == r.get("precedent_code")]
        rest = [r for r in trail if r not in fast]
        for name, rows in (("fast-track (Decider, Bedrock and past rulings agree)", fast), ("full review", rest)):
            right = sum(1 for r in rows if r.get("code") == r["gold"])
            emit(f"| {name} | {len(rows)} ({pct(len(rows) / len(trail))}) | {right} ({pct(right / len(rows)) if rows else '-'}) |")

        emit("\n### Why not auto-clear: Decider's path probability vs correctness\n")
        emit("| path probability | products | mean probability | actually correct (10-digit) |")
        emit("|---|---|---|---|")
        for b in calibration(trail):
            emit(f"| {b['bin']} | {b['n']} | {b['mean_p']:.2f} | {pct(b['acc10'])} |")

        emit("\n### Search cost (Strands Decider)\n")
        emit(f"- Decider calls per product: {d['decider_calls']:.1f} (wrong-turn forks explored and abandoned: {d['off_path']:.1f})")
        emit(f"- Decider latency per call: {d['decider_ms_per_call']:.0f} ms; per product p50 {d['p50_s']:.1f} s, p95 {d['p95_s']:.1f} s")
        emit(f"- Correct code among Decider's top 3 complete paths: {pct(d['top3_acc10'])}")
        for line in significance(args.split, trail):
            emit(line)

    text = "\n".join(lines)
    print(text)
    if args.markdown:
        Path(args.markdown).write_text(text + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
