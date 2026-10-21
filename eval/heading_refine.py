"""Post-hoc probe of the final pick: does reading the whole heading fix "right heading, wrong 10 digits"?

Run after the preregistered test evaluation (research/PREREGISTRATION.md); it changes no headline
number and nothing in the app. Every arm re-uses the recorded Decider search for each product, so
only the Bedrock step after the search changes.

  pick_frozen:<model>   the frozen shortlist (Decider top 3 + nearest-ruling vote), adjudicator.py's prompt
  pick_wide:<model>     Decider top 3 + retrieval top 4 + nearest-ruling vote
  refine:<src>:<model>  take arm <src>'s final code ("frozen" = TariffTrail's recorded answer), show the
                        complete official outline of its 4-digit heading (+ up to 4 past rulings under that
                        heading) and re-pick the 10-digit line inside it: one extra Bedrock call. A reply
                        that is not a line of that heading keeps the original code.

The dev arms were compared first; the test arms were declared before they ran (HEADING_REFINE.md).

    python eval/heading_refine.py --split dev --arms refine:frozen:moonshotai.kimi-k2.5   # Bedrock calls
    python eval/heading_refine.py --stats                                                 # test tables, no AWS
"""

from __future__ import annotations

import argparse
import json
import os
import re
import string
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

RESULTS = ROOT / "eval" / "results"
OUT = RESULTS / "heading_refine"
TEST_ARMS = ("refine:frozen:moonshotai.kimi-k2.5", "refine:frozen:us.amazon.nova-pro-v1:0")

_tree = None


def tree():
    global _tree
    if _tree is None:
        from tariff_trail.hts.tree import load
        _tree = load()
    return _tree


def jl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.open(encoding="utf-8") if line.strip()] if path.exists() else []


def arm_path(split: str, arm: str) -> Path:
    return OUT / f"{split}__{arm.replace(':', '~').replace('/', '_')}.jsonl"


def norm(code: str) -> str:
    code = re.sub(r"\D", "", code or "")
    return code + "00" if len(code) == 8 else code


def depth(a: str, b: str) -> int:
    k = 0
    for x, y in zip(a or "", b or ""):
        if x != y:
            break
        k += 1
    return k


def call(prompt: str, model: str, system: str, max_tokens: int) -> tuple[dict, int, int]:
    from tariff_trail import bedrock

    os.environ["TT_REASONER_MODEL"] = model
    bedrock.model_for.cache_clear()
    for attempt in range(6):
        try:
            reply = bedrock.converse(prompt, role="reasoner", system=system, max_tokens=max_tokens)
            m = re.search(r"\{[^{}]*\}", reply.text, re.DOTALL)
            return (json.loads(m.group(0)) if m else {}), reply.input_tokens, reply.output_tokens
        except Exception as exc:  # throttling / transient
            if "Throttl" in type(exc).__name__ or "Throttl" in str(exc) or "timed out" in str(exc).lower():
                time.sleep(4 * (attempt + 1))
                continue
            return {"error": str(exc)[:200]}, 0, 0
    return {"error": "throttled"}, 0, 0


# ---------------------------------------------------------------- data
def load_split(split: str) -> dict[str, dict]:
    from tariff_trail import precedents

    facts = {c["id"]: c["facts"] for c in jl(ROOT / "data" / "eval" / f"{split}.jsonl")}
    rows = {r["id"]: r for r in jl(RESULTS / split / "tariff_trail.jsonl") if r["id"] in facts}
    cases = {}
    if split == "dev":  # the frozen config on dev was measured by readjudicate (knn added after the dev run)
        for r in jl(RESULTS / "dev" / "readjudicate_top3_plus_knn.jsonl"):
            row = rows[r["id"]]
            cases[r["id"]] = dict(gold=r["gold"], facts=facts[r["id"]], d3=[c["code"] for c in row.get("candidates", [])[:3]],
                                  p3=[c["p"] for c in row.get("candidates", [])[:3]], knn=r.get("knn_code") or "",
                                  frozen=r["code"])
    else:
        for i, row in rows.items():
            cases[i] = dict(gold=row["gold"], facts=facts[i], d3=[c["code"] for c in row.get("candidates", [])[:3]],
                            p3=[c["p"] for c in row.get("candidates", [])[:3]], knn=row.get("precedent_code") or "",
                            frozen=row.get("code") or row.get("decider_code") or "")
    cache = OUT / f"{split}__retrieval.jsonl"  # retrieval top codes (Titan only), cached
    have = {r["id"]: r["codes"] for r in jl(cache)}
    if split == "test" and not have:
        have = {r["id"]: [c for c, _ in r["codes"]] for r in jl(RESULTS / "test" / "retrieval.jsonl")}
    todo = [i for i in cases if i not in have]

    def one(i):
        votes: dict[str, float] = {}
        for p in precedents.search(cases[i]["facts"], k=20):
            for code in p.codes:
                if code[:2] not in ("98", "99") and len(code) == 10 and tree().exists(code):
                    votes[code] = votes.get(code, 0.0) + p.score
        return i, [c for c, _ in sorted(votes.items(), key=lambda kv: kv[1], reverse=True)[:10]]

    if todo:
        with ThreadPoolExecutor(4) as pool, cache.open("a", encoding="utf-8") as out:
            for i, codes in pool.map(one, todo):
                have[i] = codes
                out.write(json.dumps({"id": i, "codes": codes}) + "\n")
    for i in cases:
        cases[i]["retr"] = have.get(i, [])
    return cases


# ---------------------------------------------------------------- pick
def precedent_block(prefixes: list[str], facts: str, per: int = 2, top: int = 4) -> str:
    from tariff_trail import precedents
    from tariff_trail.adjudicator import _dotted

    seen = {}
    for pre in prefixes:
        for p in precedents.search(facts, k=per, prefix=pre):
            seen.setdefault(p.ruling, p)
    found = sorted(seen.values(), key=lambda p: p.score, reverse=True)[:top]
    if not found:
        return ""
    lines = ["", "Similar past CBP rulings (for reference; decide on the facts of this product):"]
    for p in found:
        lines.append(f"- {p.ruling} ({p.date}) -> {', '.join(_dotted(c) for c in p.codes[:3])}: {p.subject[:120]}. {p.summary[:300]}")
    return "\n".join(lines) + "\n"


def pick(case: dict, codes: list[str], probs: list[float], model: str) -> dict:
    from tariff_trail.adjudicator import PROMPT, SYSTEM, _indent

    t = tree()
    short = []
    for k, c in enumerate(codes):
        c = norm(c)
        if c and c in t.by_code and c not in [x for x, _ in short]:
            short.append((c, probs[k] if k < len(probs) else 0.0))
    if not short:
        return {"code": "", "shortlist": [], "tin": 0, "tout": 0}
    if len(short) == 1:
        return {"code": short[0][0], "shortlist": [short[0][0]], "tin": 0, "tout": 0}
    letters = string.ascii_uppercase[: len(short)]
    options = "\n\n".join(f"{L}. {t[t.by_code[c]].htsno} [{p:.2f}]\n{_indent(t.path_text(t.by_code[c]))}"
                          for L, (c, p) in zip(letters, short))
    block = precedent_block([c[:4] for c, _ in short], case["facts"])
    data, tin, tout = call(PROMPT.format(facts=case["facts"], options=options, precedents=block), model, SYSTEM,
                           300 if "nova" in model else 4000)
    letter = str(data.get("choice", "")).strip().upper()[:1]
    chosen = short[letters.index(letter)][0] if letter in letters else short[0][0]
    return {"code": chosen, "shortlist": [c for c, _ in short], "tin": tin, "tout": tout,
            "reason": str(data.get("reason", data.get("error", "")))[:300]}


# ---------------------------------------------------------------- refine
REFINE = """Product facts:
{facts}

This product has been placed in heading {heading}. Below is the complete official outline of that heading
(indentation shows the hierarchy; only lines marked "=>" are complete statistical reporting numbers that can be
filed). Apply GRI 6: compare only lines at the same level, choose the matching line at each level, then go one
level down; "Other" covers anything not described by its sibling lines.

{outline}
{precedents}
Which "=>" line is correct for this product? Reply with JSON only:
{{"code": "<number exactly as printed on the => line>", "reason": "<one sentence citing the deciding fact and wording>"}}"""


def outline(heading_id: str) -> tuple[str, set[str]]:
    t = tree()
    lines, leaves = [], set()
    for node in t.path(heading_id)[:-1]:
        label = {"section": "Section", "chapter": "Chapter"}.get(node.kind, "")
        if label:
            lines.append(f"{label} {node.id.split(':', 1)[1]}: {node.text}")

    def walk(nid: str, d: int) -> None:
        node = t[nid]
        term = t.is_terminal(nid)
        if term:
            leaves.add(norm(node.code))
        lines.append(f"{'  ' * d}{'=> ' if term else ''}{node.htsno or '(group)'} {node.text.rstrip(':')}")
        for c in node.children:
            walk(c, d + 1)

    walk(heading_id, 0)
    return "\n".join(lines), leaves


def refine(case: dict, code: str, model: str) -> dict:
    from tariff_trail.adjudicator import SYSTEM

    t = tree()
    code = norm(code)
    hid = t.by_code.get(code[:4])
    if not hid:
        return {"code": code, "changed": False, "tin": 0, "tout": 0}
    text, leaves = outline(hid)
    block = precedent_block([code[:4]], case["facts"], per=4)
    data, tin, tout = call(REFINE.format(facts=case["facts"], heading=t[hid].htsno, outline=text, precedents=block),
                           model, SYSTEM, 300 if "nova" in model else 4000)
    new = norm(str(data.get("code", "")))
    ok = new in leaves
    return {"code": new if ok else code, "changed": ok and new != code, "invalid_reply": not ok, "tin": tin, "tout": tout,
            "leaves": len(leaves), "reason": str(data.get("reason", data.get("error", "")))[:300]}


# ---------------------------------------------------------------- run
def run(split: str, arm: str, cases: dict[str, dict], workers: int) -> dict[str, dict]:
    path = arm_path(split, arm)
    done = {r["id"]: r for r in jl(path)}
    kind, rest = arm.split(":", 1)
    if kind == "refine":
        src, model = rest.split(":", 1)
        src = src.replace("~", ":")  # e.g. refine:pick_wide~deepseek.v3.2:deepseek.v3.2
        src_rows = {i: {"code": c["frozen"]} for i, c in cases.items()} if src == "frozen" else run(split, src, cases, workers)
    else:
        model = rest
    todo = [i for i in cases if i not in done]

    def one(i):
        c = cases[i]
        if kind == "pick_frozen":
            r = pick(c, c["d3"] + [c["knn"]], c["p3"], model)
        elif kind == "pick_wide":
            r = pick(c, c["d3"] + c["retr"][:4] + [c["knn"]], c["p3"], model)
        else:
            r = refine(c, src_rows[i]["code"], model)
        r["id"] = i
        r["gold"] = c["gold"]
        return r

    if todo:
        OUT.mkdir(parents=True, exist_ok=True)
        print(f"[{arm}] running {len(todo)}", flush=True)
        with ThreadPoolExecutor(workers) as pool, path.open("a", encoding="utf-8") as out:
            for r in pool.map(one, todo):
                done[r["id"]] = r
                out.write(json.dumps(r, ensure_ascii=False) + "\n")
                out.flush()
    return done


def summary(split: str, arm: str, res: dict[str, dict], cases: dict[str, dict]) -> str:
    n = len(cases)
    a10 = sum(norm(res[i]["code"]) == cases[i]["gold"] for i in cases)
    a4 = sum(depth(norm(res[i]["code"]), cases[i]["gold"]) >= 4 for i in cases)
    fz = sum(norm(cases[i]["frozen"]) == cases[i]["gold"] for i in cases)
    win = sum(norm(res[i]["code"]) == cases[i]["gold"] and norm(cases[i]["frozen"]) != cases[i]["gold"] for i in cases)
    loss = sum(norm(res[i]["code"]) != cases[i]["gold"] and norm(cases[i]["frozen"]) == cases[i]["gold"] for i in cases)
    tok = sum(res[i].get("tin", 0) + res[i].get("tout", 0) for i in cases) / n
    rec = ""
    if "shortlist" in next(iter(res.values())):
        rec = f" recall {sum(cases[i]['gold'] in res[i]['shortlist'] for i in cases) / n:.1%}"
    bad = sum(bool(res[i].get("invalid_reply")) for i in cases)
    return (f"{split:4s} {arm:70s} acc10 {a10 / n:6.1%} ({a10}/{n})  acc4 {a4 / n:6.1%}  vs frozen {fz}: +{win}/-{loss}"
            f"{rec}  tok {tok:,.0f}" + (f"  bad-replies {bad}" if bad else ""))


# ---------------------------------------------------------------- stats (no AWS)
def stats() -> None:
    """Exact accuracy, Wilson CI and paired McNemar test of the declared test arms against the recorded run."""
    from eval.report import mcnemar_p, wilson
    from tariff_trail.agreement import agreed_heading

    trail = {r["id"]: r for r in jl(RESULTS / "test" / "tariff_trail.jsonl")}
    n = len(trail)
    old = {i: (r.get("code") or r.get("decider_code")) == r["gold"] for i, r in trail.items()}
    print(f"recorded TariffTrail: {sum(old.values())}/{n} = {sum(old.values()) / n:.1%}")
    for arm in TEST_ARMS:
        res = {r["id"]: r for r in jl(arm_path("test", arm))}
        if len(res) < n:
            print(f"{arm}: {len(res)}/{n} rows recorded, run it first")
            continue
        new = {i: res[i]["code"] == trail[i]["gold"] for i in trail}
        b = sum(new[i] and not old[i] for i in trail)
        c = sum(old[i] and not new[i] for i in trail)
        k = sum(new.values())
        lo, hi = wilson(k, n)
        changed = sum(res[i]["code"] != (trail[i].get("code") or trail[i].get("decider_code")) for i in trail)
        print(f"{arm}\n  10-digit {k}/{n} = {k / n:.1%} (95% CI {lo:.1%}-{hi:.1%}); fixed {b}, broke {c}, "
              f"McNemar p = {mcnemar_p(b, c):.2g}; changed the code on {changed}/{n}")
        tiers: dict[str, list[str]] = {"fast-track": [], "heading-agreed": [], "review": []}
        for i, r in trail.items():
            code, d, p = res[i]["code"], r.get("decider_code") or "", r.get("precedent_code") or ""
            tier = "fast-track" if code and code == d == p else "heading-agreed" if agreed_heading(code, d, p) else "review"
            tiers[tier].append(i)
        for t, ids in tiers.items():
            ex = sum(new[i] for i in ids) / max(1, len(ids))
            print(f"  {t:15s} {len(ids):3d} ({len(ids) / n:5.1%})  exact {ex:.1%}")
        leaves = [res[i].get("leaves", 0) for i in trail]
        print(f"  heading outline shown: mean {sum(leaves) / n:.0f} filing lines, max {max(leaves)}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="dev")
    ap.add_argument("--arms", nargs="+")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--stats", action="store_true", help="print the declared test arms' statistics (no AWS calls)")
    a = ap.parse_args()
    if a.stats:
        stats()
        return
    if not a.arms:
        ap.error("--arms or --stats is required")
    os.environ.setdefault("AWS_PROFILE", "hackathon")
    cases = load_split(a.split)
    for arm in a.arms:
        print(summary(a.split, arm, run(a.split, arm, cases, a.workers), cases), flush=True)


if __name__ == "__main__":
    main()
