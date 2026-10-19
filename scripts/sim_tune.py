"""Grid over KeywordScorer settings on dev (scratch tuning for the demo stand-in)."""

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tariff_trail.hts.tree import load  # noqa: E402
from tariff_trail.simulate import Simulator  # noqa: E402

tree = load()
sim = Simulator(tree)
cases = [json.loads(line) for line in open("data/eval/dev.jsonl", encoding="utf-8")]
grid = {"saturate": [3, 6, 20], "size_penalty": [0.0, 0.3, 0.8], "temperature": [1.0, 1.6], "none_score": [1.4, 3.0]}
best = []
for values in itertools.product(*grid.values()):
    cfg = dict(zip(grid, values))
    for k, v in cfg.items():
        setattr(sim.scorer, k, v)
    a2 = a4 = forks = 0
    for case in cases:
        r = sim.run(case["facts"])
        a2 += r.code[:2] == case["gold"][:2]
        a4 += r.code[:4] == case["gold"][:4]
        forks += r.forks
    best.append((a2 + a4, a2, a4, forks / len(cases), cfg))
    print(a2, a4, round(forks / len(cases), 1), cfg, flush=True)
best.sort(key=lambda x: -x[0])
print("BEST", best[:5])
