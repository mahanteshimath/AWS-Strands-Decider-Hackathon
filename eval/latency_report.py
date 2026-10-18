"""Compare the CPU test run with the GPU replication: latency per Decider call and per product, accuracy, agreement.

    python eval/latency_report.py            # reads eval/results/test/tariff_trail.jsonl and eval/results/latency/gpu_l4/...
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

RESULTS = Path(__file__).resolve().parent / "results"


def load(path: Path) -> dict[str, dict]:
    return {r["id"]: r for r in map(json.loads, path.open(encoding="utf-8")) if not r.get("error")}


def pct(values: list[float], q: float) -> float:
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * q))]


def describe(name: str, rows: dict[str, dict]) -> dict:
    calls = [s["latency_ms"] for r in rows.values() for s in r.get("steps", []) if s.get("latency_ms")]
    wall = [r["wall_ms"] / 1000 for r in rows.values()]
    n = len(rows)
    return {
        "system": name, "n": n,
        "acc10": round(sum(r["match"] >= 10 for r in rows.values()) / n, 4),
        "acc4": round(sum(r["match"] >= 4 for r in rows.values()) / n, 4),
        "invalid": round(sum(not r.get("valid") for r in rows.values()) / n, 4),
        "decider_calls_per_product": round(statistics.mean(r.get("decider_calls", 0) for r in rows.values()), 1),
        "decider_call_p50_ms": round(statistics.median(calls)),
        "decider_call_p95_ms": round(pct(calls, 0.95)),
        "product_p50_s": round(statistics.median(wall), 1),
        "product_p95_s": round(pct(wall, 0.95), 1),
        "bedrock_tokens_per_product": round(statistics.mean(r.get("llm_in", 0) + r.get("llm_out", 0) for r in rows.values())),
    }


def main() -> None:
    cpu = load(RESULTS / "test" / "tariff_trail.jsonl")
    gpu = load(RESULTS / "latency" / "gpu_l4" / "tariff_trail.jsonl")
    common = sorted(set(cpu) & set(gpu))
    report = {
        "cpu_c7i.4xlarge": describe("cpu", cpu),
        "gpu_g6.xlarge_L4": describe("gpu", gpu),
        "same_final_code_on_shared_cases": f"{sum(cpu[i]['code'] == gpu[i]['code'] for i in common)}/{len(common)}",
        "same_decider_top_code_on_shared_cases": f"{sum(cpu[i]['decider_code'] == gpu[i]['decider_code'] for i in common)}/{len(common)}",
    }
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
