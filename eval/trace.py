"""Print the step-by-step trace of TariffTrail eval results, to see where walks go wrong.

    python eval/trace.py eval/results/dev/decider_only.jsonl [CASE_ID ...]
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tariff_trail.hts.tree import load  # noqa: E402


def main() -> None:
    path = Path(sys.argv[1])
    wanted = set(sys.argv[2:])
    tree = load()
    cases = {json.loads(l)["id"]: json.loads(l) for name in ("dev", "test")
             for l in (ROOT / "data" / "eval" / f"{name}.jsonl").open(encoding="utf-8")}
    for line in path.open(encoding="utf-8"):
        row = json.loads(line)
        if wanted and row["id"] not in wanted:
            continue
        case = cases.get(row["id"], {})
        gold_path = [n.id for n in tree.path(tree.by_code[row["gold"]])] if row["gold"] in tree.by_code else []
        print(f"\n=== {row['id']} gold {row['gold']} got {row.get('code')} (match {row['match']}) | {case.get('title', '')}")
        print(f"    {case.get('facts', '')[:300]}")
        print("    gold path: " + " > ".join(tree[n].htsno or tree[n].id for n in gold_path))
        for step in row.get("steps", []):
            on_gold = "ok " if step["chosen"] in gold_path else ("-- " if step["route"] != "backtrack" else "<< ")
            gold_child = next((g for g in gold_path if tree[g].parent == step["node"]), None)
            gold_p = next((t["p"] for t in step["top"] if t["id"] == gold_child), None)
            tops = ", ".join(f"{t['label'][:28]}={t['p']:.2f}" for t in step["top"][:3])
            print(f"  {on_gold}{step['route']:11} at {str(step['node_label'])[:24]:24} conf {step['confidence']:.2f} "
                  f"-> {str(step['chosen_label'])[:30]:30} | gold opt p={gold_p} | top: {tops}")


if __name__ == "__main__":
    main()
