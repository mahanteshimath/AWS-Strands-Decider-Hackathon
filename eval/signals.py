"""Which signal tells a correct TariffTrail answer from a wrong one? (offline, from recorded rows)

    python eval/signals.py --split dev

For each candidate signal, prints AUROC against 10-digit correctness, and precision/coverage when
auto-clearing on it. Signals use only data already in the result rows (no new model calls),
except the nearest-ruling code, which is recomputed with one Titan embedding per case.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "eval" / "results"


def load(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    return {json.loads(l)["id"]: json.loads(l) for l in path.open(encoding="utf-8")}


def auroc(scores: list[float], labels: list[bool]) -> float | None:
    pos = [s for s, y in zip(scores, labels) if y]
    neg = [s for s, y in zip(scores, labels) if not y]
    if not pos or not neg:
        return None
    wins = sum((p > n) + 0.5 * (p == n) for p in pos for n in neg)
    return wins / (len(pos) * len(neg))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", default="dev")
    args = parser.parse_args()
    trail = load(RESULTS / args.split / "tariff_trail.jsonl")
    knn = load(RESULTS / args.split / "knn.jsonl")
    rows = [r for r in trail.values() if r.get("candidates")]
    print(f"{len(rows)} TariffTrail rows; nearest-ruling rows: {len(knn)}")

    def first_fork(r: dict) -> float:
        step = next((s for s in r["steps"] if s["route"] != "forced"), None)
        return step["p"] if step else 0.0

    def min_fork(r: dict) -> float:
        ps = [s["p"] for s in r["steps"] if s["route"] != "forced"]
        return min(ps) if ps else 1.0

    def share(r: dict) -> float:
        total = sum(c["p"] for c in r["candidates"][:3]) or 1.0
        return r["candidates"][0]["p"] / total

    final = {r["id"]: (r.get("llm_code") or r["decider_code"]) for r in rows}
    signals = {
        "path probability": lambda r: r.get("p_best", 0.0),
        "share of best among top 3": share,
        "min fork probability": min_fork,
        "heading (first fork) probability": first_fork,
        "Decider == Bedrock pick": lambda r: float(r["decider_code"] == r.get("llm_code")),
        "Decider == nearest ruling": lambda r: float(r["decider_code"] == knn.get(r["id"], {}).get("code")),
        "Decider == Bedrock == nearest": lambda r: float(r["decider_code"] == r.get("llm_code") == knn.get(r["id"], {}).get("code")),
    }
    for target, pick in (("Decider's best", lambda r: r["decider_code"]), ("final (Bedrock pick)", lambda r: final[r["id"]])):
        labels = [pick(r) == r["gold"] for r in rows]
        print(f"\n== correctness of {target}: {sum(labels)}/{len(rows)} correct")
        print(f"{'signal':36} AUROC   precision@top25%  precision@top50%")
        for name, fn in signals.items():
            scores = [fn(r) for r in rows]
            order = sorted(range(len(rows)), key=lambda i: scores[i], reverse=True)
            out = []
            for frac in (0.25, 0.5):
                top = order[: max(1, int(frac * len(rows)))]
                out.append(sum(labels[i] for i in top) / len(top))
            a = auroc(scores, labels)
            print(f"{name:36} {('-' if a is None else f'{a:.2f}'):6}  {out[0]:.0%}              {out[1]:.0%}")
        for name in ("Decider == Bedrock pick", "Decider == nearest ruling", "Decider == Bedrock == nearest"):
            agree = [i for i, r in enumerate(rows) if signals[name](r) == 1.0]
            if agree:
                print(f"  when {name}: {len(agree)}/{len(rows)} cases, {sum(labels[i] for i in agree)} correct "
                      f"({sum(labels[i] for i in agree) / len(agree):.0%})")


if __name__ == "__main__":
    main()
