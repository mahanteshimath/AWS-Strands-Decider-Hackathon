"""Simulated runs for the demo: the real search over the real tariff tree, with a keyword stand-in for Decider.

    from tariff_trail.simulate import Simulator
    sim = Simulator()
    result = sim.run("Plush stuffed toy shaped like a dinosaur, polyester shell", observe=print)

Strands Decider needs its server. When none is reachable the demo can still show how Calibrated
Tree Descent moves on any product: each fork is answered by a transparent keyword scorer (IDF-weighted
overlap between the product facts and each option's wording plus everything beneath it), turned into a
probability distribution, with "none of these" below the top so wrong turns backtrack exactly as they do
live. The scorer is NOT Decider and NOT a classifier: every result it produces is labelled simulated.
"""

from __future__ import annotations

import math
import random
import re
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .hts.tree import HTSTree
from .tree_descent import NONE_KEY, CalibratedTreeDescent, Policy, Result

SIM_POLICY = Policy(auto=1.01, budget=24, shortlist=1)

_WORD = re.compile(r"[a-z]+")
_STOP = set(
    "a an and are as at be by for from has have in into is it its of on or other others than that the their "
    "this to used use using with without not nor which whether such any all each per one two three "
    "made make product products item items article articles parts part thereof type kind".split()
)


def stem(word: str) -> str:
    if len(word) > 4 and word.endswith("ies"):
        return word[:-3] + "y"
    if len(word) > 4 and word.endswith(("ches", "shes", "sses", "xes", "zes")):
        return word[:-2]
    if len(word) > 3 and word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def tokens(text: str) -> list[str]:
    return [stem(w) for w in _WORD.findall(text.lower()) if len(w) > 2 and w not in _STOP]


class KeywordScorer:
    """Scores tree nodes against product facts; built once per tree (about a second)."""

    # Defaults tuned on the 60 dev cases (scripts/sim_tune.py): right chapter 33%, right heading 17%,
    # about 8 forks per product. Plausible search behaviour, nowhere near a classifier.
    def __init__(self, tree: HTSTree, *, temperature: float = 1.6, other_bonus: float = 1.2, none_score: float = 3.0,
                 own_weight: float = 1.5, saturate: int = 20, size_penalty: float = 0.8) -> None:
        self.tree = tree
        self.temperature = temperature
        self.other_bonus = other_bonus
        self.none_score = none_score
        self.own_weight = own_weight
        self.saturate = saturate
        self.size_penalty = size_penalty
        self.own: dict[str, frozenset[str]] = {}
        self.sub: dict[str, Counter] = {}
        df: Counter = Counter()
        for node_id, node in tree.nodes.items():
            own = frozenset(tokens("" if node.is_other else node.text))
            self.own[node_id] = own
            df.update(own)
        n = len(tree.nodes)
        self.idf = {t: math.log(1 + n / c) for t, c in df.items()}
        self._fill(tree.root_id)

    def _fill(self, root: str) -> None:
        # Bottom-up term counts for every subtree, iteratively (the tree is ~12 levels deep but wide).
        order, stack = [], [root]
        while stack:
            node_id = stack.pop()
            order.append(node_id)
            stack.extend(self.tree.child_ids(node_id))
        for node_id in reversed(order):
            counts = Counter(self.own[node_id])
            for child in self.tree.child_ids(node_id):
                counts.update(self.sub[child])
            self.sub[node_id] = counts

    def score(self, node_id: str, facts: set[str]) -> float:
        own, sub = self.own[node_id], self.sub[node_id]
        total = 0.0
        for t in facts:
            w = self.idf.get(t)
            if w is None:
                continue
            if t in own:
                total += self.own_weight * w
            elif sub.get(t):
                total += w * min(1.0, math.log1p(sub[t]) / math.log1p(self.saturate))
        if self.size_penalty:
            total -= self.size_penalty * math.log1p(len(sub))
        if self.tree[node_id].is_other:
            total += self.other_bonus
        return total

    def distribution(self, children: list[str], facts: set[str], *, offer_none: bool, rng: random.Random | None) -> dict[str, float]:
        scores = {c: self.score(c, facts) for c in children}
        if offer_none:
            scores[NONE_KEY] = self.none_score
        if rng is not None:  # a little noise so repeated runs explore differently
            scores = {k: v + rng.gauss(0, 0.35) for k, v in scores.items()}
        top = max(scores.values())
        weights = {k: math.exp((v - top) / self.temperature) for k, v in scores.items()}
        total = sum(weights.values())
        return {k: w / total for k, w in weights.items()}


class SimulatedDescent(CalibratedTreeDescent):
    """The unchanged best-first search; only `fork` is answered locally instead of by Decider."""

    def __init__(self, tree: HTSTree, scorer: KeywordScorer, *, rng: random.Random | None, pace_s: float, **kwargs: Any) -> None:
        super().__init__(tree, decider=None, **kwargs)  # type: ignore[arg-type]
        self.scorer, self.rng, self.pace_s, self.calls = scorer, rng, pace_s, 0
        self._facts_key: str | None = None
        self._facts: set[str] = set()

    def fork(self, node_id: str, facts: str, *, diagnose: bool = False):
        if facts != self._facts_key:
            self._facts_key, self._facts = facts, set(tokens(facts))
        started = time.perf_counter()
        children = self.tree.child_ids(node_id)
        offer_none = self.policy.offer_none and node_id != self.tree.root_id
        probs = self.scorer.distribution(children, self._facts, offer_none=offer_none, rng=self.rng)
        n = len(probs)
        confidence = (n * max(probs.values()) - 1) / (n - 1) if n > 1 else 1.0
        self.calls += 1
        if self.pace_s:
            time.sleep(self.pace_s)  # paced so the map can be watched; not a latency measurement
        return probs, confidence, {}, (time.perf_counter() - started) * 1000


@dataclass
class SimResult:
    result: Result
    code: str
    forks: int
    wall_ms: float


class Simulator:
    def __init__(self, tree: HTSTree) -> None:
        self.tree = tree
        self.scorer = KeywordScorer(tree)

    def run(self, facts: str, *, observe: Callable[[dict[str, Any]], None] | None = None, seed: int | None = None,
            pace_s: float = 0.0, policy: Policy | None = None) -> SimResult:
        rng = random.Random(seed) if seed is not None else None
        walker = SimulatedDescent(self.tree, self.scorer, rng=rng, pace_s=pace_s, policy=policy or SIM_POLICY, observe=observe)
        started = time.perf_counter()
        result = walker.descend(facts)
        code = self.tree.code_of(result.leaf) if result.leaf else ""
        return SimResult(result, code, walker.calls, (time.perf_counter() - started) * 1000)
