"""Charts for the README and article, drawn from the recorded result files (no AWS calls).

    python eval/charts.py          # writes docs/images/{accuracy-vs-cost,review-tiers,ablation}.png

Cost is list price in us-east-1 from the AWS Price List API (checked 2026-10-19): Amazon Nova Pro
$0.0008 / 1K input and $0.0032 / 1K output tokens; g6.xlarge (NVIDIA L4) $0.8048 per hour, billed
for the measured per-product time of the GPU replication run, one product at a time (no batching).
Titan embedding calls cost under $0.02 per 1,000 products and are left out.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "eval" / "results"
OUT = ROOT / "docs" / "images"

NOVA_PRO_IN, NOVA_PRO_OUT = 0.0008 / 1000, 0.0032 / 1000
G6_XLARGE_HOUR = 0.8048

ENAMEL, SIGNAL, NOPE, INK, MUTED, GRID = "#102f86", "#ffd21a", "#e5533a", "#14182b", "#8a93ab", "#e6e9f2"

plt.rcParams.update({
    "font.family": ["Segoe UI", "DejaVu Sans"],
    "font.size": 12,
    "axes.edgecolor": MUTED,
    "axes.labelcolor": INK,
    "axes.titleweight": "bold",
    "axes.titlesize": 15,
    "axes.titlelocation": "left",
    "xtick.color": INK,
    "ytick.color": INK,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.dpi": 200,
    "savefig.bbox": "tight",
    "savefig.facecolor": "white",
})


def read(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()] if path.exists() else []


def right10(code: str | None, gold: str) -> bool:
    """Same rule as eval/report.py: the first 10 digits match the ruling's code."""
    return len(code or "") >= 10 and (code or "")[:10] == gold[:10]


def acc10(rows: list[dict], key=lambda r: r.get("code")) -> float:
    return sum(right10(key(r), r["gold"]) for r in rows) / len(rows)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    p = k / n
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)
    return centre - half, centre + half


def bedrock_per_1k(rows: list[dict]) -> float:
    n = len(rows)
    return 1000 * sum(r.get("llm_in", 0) * NOVA_PRO_IN + r.get("llm_out", 0) * NOVA_PRO_OUT for r in rows) / n


def accuracy_vs_cost() -> None:
    test = {s: read(RESULTS / "test" / f"{s}.jsonl") for s in ("llm_direct", "llm_agent", "knn", "tariff_trail")}
    gpu = read(RESULTS / "latency" / "gpu_l4" / "tariff_trail.jsonl")
    gpu_wall = 1000 * G6_XLARGE_HOUR * sum(r["wall_ms"] for r in gpu) / len(gpu) / 3_600_000
    gpu_decider = 1000 * G6_XLARGE_HOUR * sum(r["decider_ms"] for r in gpu) / len(gpu) / 3_600_000
    trail = test["tariff_trail"]
    # (label, cost, rows, code of a row, colour, label offset in data units, alignment)
    points = [
        ("LLM, direct answer", bedrock_per_1k(test["llm_direct"]), test["llm_direct"], lambda r: r.get("code"), MUTED, (0.3, 1.0), "left"),
        ("LLM agent + HTS search tools", bedrock_per_1k(test["llm_agent"]), test["llm_agent"], lambda r: r.get("code"), MUTED, (-0.3, 0.6), "right"),
        ("Nearest past rulings", 0.0, test["knn"], lambda r: r.get("code"), MUTED, (0.1, -6.4), "left"),
        ("Strands Decider only", gpu_decider, trail, lambda r: r.get("decider_code"), ENAMEL, (0.3, 3.2), "left"),
        ("TariffTrail", bedrock_per_1k(trail) + gpu_wall, trail, lambda r: r.get("code") or r.get("decider_code"), ENAMEL, (0.3, 2.2), "left"),
    ]
    invented = {"LLM, direct answer": 1 - sum(r.get("valid", False) for r in test["llm_direct"]) / len(test["llm_direct"]),
                "LLM agent + HTS search tools": 1 - sum(r.get("valid", False) for r in test["llm_agent"]) / len(test["llm_agent"])}
    fig, ax = plt.subplots(figsize=(10, 5.6))
    for label, cost, rows, key, colour, (dx, dy), ha in points:
        k = sum(right10(key(r), r["gold"]) for r in rows)
        lo, hi = wilson(k, len(rows))
        y = 100 * k / len(rows)
        is_ours = label == "TariffTrail"
        ax.errorbar(cost, y, yerr=[[y - 100 * lo], [100 * hi - y]], fmt="none", ecolor=colour, elinewidth=1.4, capsize=4, alpha=0.7)
        ax.scatter(cost, y, s=260 if is_ours else 110, color=SIGNAL if is_ours else colour, edgecolor=ENAMEL if is_ours else "white",
                   linewidth=2.2 if is_ours else 1.2, zorder=3)
        text = f"{label}\n{y:.1f}% · ${cost:.2f}"
        if label in invented:
            text += f"\n{100 * invented[label]:.1f}% invented codes"
        ax.annotate(text, (cost, y), xytext=(cost + dx, y + dy), ha=ha, va="center",
                    fontsize=12 if is_ours else 10.5, fontweight="bold" if is_ours else "normal",
                    color=NOPE if label == "LLM, direct answer" else INK)
    ax.set_xlim(-0.6, 10.4)
    ax.set_ylim(-2, 48)
    ax.set_xlabel("Cost per 1,000 products, US$ (Bedrock tokens + GPU time at list price)")
    ax.set_ylabel("Correct 10-digit code (%)")
    ax.grid(color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_title("More right answers for a fifth of the agent's cost", pad=14)
    fig.text(0.0, -0.04, "332 held-out 2026 CBP rulings. Bars: 95% Wilson intervals. Same Bedrock model (Amazon Nova Pro) for every LLM step. "
             "GPU: g6.xlarge on-demand, one product at a time.\nTitan embedding calls (under $0.02 per 1,000 products) are not shown.",
             fontsize=9, color=MUTED, va="top")
    fig.savefig(OUT / "accuracy-vs-cost.png")
    plt.close(fig)


def review_tiers() -> None:
    trail = read(RESULTS / "test" / "tariff_trail.jsonl")
    final = lambda r: r.get("code") or r.get("decider_code")  # noqa: E731

    def agree(r: dict) -> int:
        f = final(r)
        return (f == r.get("decider_code")) + (f == r.get("precedent_code"))

    ranked = sorted(trail, key=lambda r: (agree(r), r.get("p_best", 0.0)), reverse=True)
    xs, ys, right = [], [], 0
    for i, r in enumerate(ranked, 1):
        right += right10(final(r), r["gold"])
        if i >= 10:  # skip the first few points, where one product swings the share by 10+ points
            xs.append(100 * i / len(ranked))
            ys.append(100 * right / i)
    fast = [r for r in trail if agree(r) == 2]
    fast_x = 100 * len(fast) / len(trail)
    fast_y = 100 * sum(right10(final(r), r["gold"]) for r in fast) / len(fast)
    overall = 100 * sum(right10(final(r), r["gold"]) for r in trail) / len(trail)

    fig, ax = plt.subplots(figsize=(10, 5.2))
    ax.axvspan(0, fast_x, color=SIGNAL, alpha=0.28, lw=0)
    ax.plot(xs, ys, color=ENAMEL, linewidth=2.6)
    ax.axhline(overall, color=MUTED, linestyle="--", linewidth=1.2)
    ax.text(99, overall - 4.5, f"all products: {overall:.1f}%", ha="right", color=MUTED, fontsize=10.5)
    ax.scatter([fast_x], [fast_y], s=120, color=SIGNAL, edgecolor=ENAMEL, linewidth=2, zorder=3)
    ax.annotate(f"Fast-track review: {fast_x:.0f}% of products,\n{fast_y:.0f}% right (Decider, Bedrock and\npast rulings all name the same code)",
                (fast_x, fast_y), xytext=(fast_x + 5, fast_y + 4), fontsize=11, color=INK,
                arrowprops={"arrowstyle": "-", "color": ENAMEL, "lw": 1.2})
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_xlabel("Products reviewed, most-agreed first (%)")
    ax.set_ylabel("Of those, correct at 10 digits (%)")
    ax.grid(color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_title("Agreement says which answers to trust, so a broker can clear those first", pad=14)
    fig.text(0.0, -0.04, "Order: how many of the three sources agree with the final code, then Decider's path probability; curve starts "
             "at 10 products. No code is filed without a broker.", fontsize=9, color=MUTED)
    fig.savefig(OUT / "review-tiers.png")
    plt.close(fig)


def ablation() -> None:
    trail = read(RESULTS / "test" / "tariff_trail.jsonl")
    retrieved = {r["id"]: [c for c, _ in r["codes"]] for r in read(RESULTS / "test" / "retrieval.jsonl")}
    arms = {arm: read(RESULTS / "test" / f"ablation_{arm}.jsonl") for arm in ("retrieval4", "decider3", "decider3_retrieval4")}
    if any(len(rows) < len(trail) for rows in arms.values()):
        print("ablation arms incomplete; skipping ablation chart")
        return
    n = len(trail)
    final = lambda r: r.get("code") or r.get("decider_code")  # noqa: E731
    recall = lambda arm: sum(r["gold"] in r["shortlist"] for r in arms[arm]) / n  # noqa: E731
    rows = [
        ("Nearest past rulings (vote)", acc10(trail, lambda r: (retrieved.get(r["id"]) or [""])[0]), None, MUTED),
        ("Strands Decider only (best path)", acc10(trail, lambda r: r.get("decider_code")), None, MUTED),
        ("Decider top 3  →  Bedrock picks", acc10(arms["decider3"]), recall("decider3"), MUTED),
        ("Retrieval top 4  →  Bedrock picks", acc10(arms["retrieval4"]), recall("retrieval4"), MUTED),
        ("TariffTrail: Decider top 3 + ruling vote  →  Bedrock", acc10(trail, final),  # recorded test run
         sum(r["gold"] in [c["code"] for c in r.get("candidates", [])[:3]] + [r.get("precedent_code")] for r in trail) / n, ENAMEL),
        ("Exploratory: Decider top 3 + retrieval top 4  →  Bedrock", acc10(arms["decider3_retrieval4"]), recall("decider3_retrieval4"), MUTED),
    ]
    fig, ax = plt.subplots(figsize=(10, 5.4))
    for i, (label, acc, share, colour) in enumerate(rows):
        y = len(rows) - 1 - i
        is_ours = label.startswith("TariffTrail")
        if share is not None:
            ax.barh(y, 100 * share, color=GRID, height=0.62)
            ax.text(100 * share + 0.6, y + 0.18, f"answer on shortlist {100 * share:.0f}%", va="center", fontsize=9.5, color=MUTED)
        ax.barh(y, 100 * acc, color=SIGNAL if is_ours else colour, edgecolor=ENAMEL if is_ours else "none", linewidth=1.6, height=0.42,
                hatch="//" if label.startswith("Exploratory") else None)
        ax.text(100 * acc + 0.6, y - 0.12, f"{100 * acc:.1f}%", va="center", fontsize=11.5, fontweight="bold", color=INK)
    ax.set_yticks(range(len(rows)), [r[0] for r in reversed(rows)])
    ax.set_xlim(0, 70)
    ax.set_xlabel("Correct 10-digit code (%)")
    ax.grid(axis="x", color=GRID, linewidth=1)
    ax.set_axisbelow(True)
    ax.set_title("Decider and retrieval find different right answers; Bedrock needs both", pad=14)
    fig.text(0.0, -0.05, "Post-hoc ablation on the 332 test products: same Bedrock prompt and model (temperature 0); only the shortlist changes.\n"
             "Grey bar: share of products whose answer was on the shortlist. Hatched: exploratory arm chosen after seeing the test results.",
             fontsize=9, color=MUTED, va="top")
    fig.savefig(OUT / "ablation.png")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    accuracy_vs_cost()
    review_tiers()
    ablation()
    print(f"charts written to {OUT}")


if __name__ == "__main__":
    main()
