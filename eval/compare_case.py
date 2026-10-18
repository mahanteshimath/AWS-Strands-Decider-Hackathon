"""Show every system's answer for a few rulings, plus TariffTrail's trace (for the article and video).

    python eval/compare_case.py N357194 N357985
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results" / "test"


def row(system: str, case_id: str) -> dict:
    for line in (RESULTS / f"{system}.jsonl").open(encoding="utf-8"):
        r = json.loads(line)
        if r["id"] == case_id:
            return r
    return {}


def main() -> None:
    cases = {json.loads(l)["id"]: json.loads(l) for l in (ROOT / "data" / "eval" / "test.jsonl").open(encoding="utf-8")}
    for case_id in sys.argv[1:]:
        case = cases[case_id]
        print(f"\n== {case_id} gold {case['gold']} | {case['title']}\n{case['facts']}\n")
        for system in ("llm_direct", "llm_agent", "knn", "tariff_trail"):
            r = row(system, case_id)
            tokens = r.get("llm_in", 0) + r.get("llm_out", 0)
            mark = "OK " if r.get("code") == case["gold"] else "-- "
            print(f"  {mark}{system:12} {r.get('code') or '(none)':12} valid={r.get('valid')} tokens={tokens}")
        r = row("tariff_trail", case_id)
        for step in r.get("steps", []):
            tops = ", ".join(f"{t['label'][:34]}={t['p']:.2f}" for t in step["top"][:4])
            print(f"    {step['route']:9} {str(step['node_label'])[:26]:26} -> {str(step['chosen_label'])[:26]:26} | {tops}")
        print("    candidates:", [(c["htsno"], c["p"]) for c in r.get("candidates", [])])
        print("    bedrock:", [a.get("reason") for a in r.get("adjudications", [])])


if __name__ == "__main__":
    main()
