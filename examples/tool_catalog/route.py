"""Calibrated Tree Descent, reused: route a request to one tool out of a 48-tool catalog.

The same pattern that walks the tariff schedule walks a tool catalog (service -> tool), so an
agent never sees all 48 tool schemas at once. Decider makes the calibrated choice at each level,
"none of these" catches a wrong service, and the path probability says whether to call the tool
directly or ask the user first.

    python examples/tool_catalog/route.py                      # all labelled cases
    python examples/tool_catalog/route.py "ping Priya privately"
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from tariff_trail.decider import Decider  # noqa: E402
from tariff_trail.tree_descent import CalibratedTreeDescent, DictTree, Policy, Wording  # noqa: E402

WORDING = Wording(
    child="Which option is the right one to handle the user's request?",
    none_text="None of these can handle the request; an earlier choice was wrong",
)


def state(facts: str, path: str) -> str:
    return f"USER REQUEST:\n{facts}" + (f"\n\nCHOSEN SO FAR:\n{path}" if path else "")


def main() -> None:
    tree = DictTree(json.loads((HERE / "catalog.json").read_text(encoding="utf-8")))
    router = CalibratedTreeDescent(tree, Decider(), policy=Policy(auto=0.6), wording=WORDING, render_state=state)

    if len(sys.argv) > 1:
        result = router.descend(" ".join(sys.argv[1:]))
        print(f"{result.leaf}  p={result.p:.2f}  {'call it' if result.auto else 'confirm with the user first'}")
        return

    cases = [json.loads(line) for line in (HERE / "cases.jsonl").open(encoding="utf-8")]
    right = auto = auto_right = 0
    started = time.perf_counter()
    for case in cases:
        result = router.descend(case["request"])
        ok = result.leaf == case["gold"]
        right += ok
        auto += result.auto
        auto_right += result.auto and ok
        print(f"{'ok ' if ok else 'XX '} p={result.p:.2f} {'auto ' if result.auto else 'ask  '} {result.leaf:32} <- {case['request']}")
    n = len(cases)
    seconds = time.perf_counter() - started
    print(f"\naccuracy {right}/{n} = {100 * right / n:.0f}%; auto (p >= 0.6) {auto}/{n}, of which correct {auto_right}/{auto or 1}; "
          f"{seconds / n:.1f} s per request on this host")


if __name__ == "__main__":
    main()
