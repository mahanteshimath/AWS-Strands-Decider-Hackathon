"""Probe the simulated stand-in on labelled cases: how far it gets and how much it searches.

    python scripts/sim_probe.py [dev|test] [limit]
"""

import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tariff_trail.hts.tree import load  # noqa: E402
from tariff_trail.simulate import Simulator  # noqa: E402

split = sys.argv[1] if len(sys.argv) > 1 else "dev"
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 60
t0 = time.perf_counter()
tree = load()
sim = Simulator(tree)
print(f"load+index {time.perf_counter() - t0:.1f}s", flush=True)
cases = [json.loads(line) for line in open(f"data/eval/{split}.jsonl", encoding="utf-8")][:limit]
hits = {2: 0, 4: 0, 6: 0, 10: 0}
forks, off, ms = [], [], []
for case in cases:
    r = sim.run(case["facts"])
    for k in hits:
        hits[k] += r.code[:k] == case["gold"][:k]
    forks.append(r.forks)
    off.append(r.result.off_path)
    ms.append(r.wall_ms)
n = len(cases)
print(" ".join(f"acc{k} {100 * v / n:.1f}%" for k, v in hits.items()))
print(f"forks mean {statistics.mean(forks):.1f} max {max(forks)}; off-path mean {statistics.mean(off):.1f}; "
      f"budget-hit {sum(f >= 24 for f in forks)}; ms p50 {statistics.median(ms):.0f}")
