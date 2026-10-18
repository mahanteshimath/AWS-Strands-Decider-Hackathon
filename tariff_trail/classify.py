"""TariffTrail classifier: Calibrated Tree Descent over the HTS, with Bedrock on uncertain products.

    from tariff_trail.classify import TariffTrail
    trail = TariffTrail()                     # Decider at STRANDS_DECIDER_URL, Bedrock via AWS_PROFILE
    result = trail.classify("Women's knitted pullover, 44% polyamide, 21% alpaca, 21% wool, 14% metallic")
    result.code, result.auto, result.path_text
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from . import bedrock
from .adjudicator import ShortlistAdjudicator
from .decider import Decider
from .hts.questions import HTS_WORDING, hts_state
from .hts.tree import HTSTree, load
from .precedents import HeadingSeed
from .tree_descent import NONE_KEY, CalibratedTreeDescent, OnMissing, Policy, Result

# Frozen from the dev split (research/PREREGISTRATION.md, amendment 1): Decider's path probability
# did not predict correctness, so no tariff classification is filed without a broker (auto > 1).
TARIFF_POLICY = Policy(auto=1.01, budget=24, shortlist=3)


@dataclass
class Classification:
    facts: str
    code: str  # digits; "" when the search found nothing
    status: str  # done | needs_info | failed
    route: str  # auto | adjudicated | review
    auto: bool  # cleared the policy bar: safe to file without review (never, for tariffs; see TARIFF_POLICY)
    p: float  # path probability of the returned code
    min_confidence: float
    routes: dict[str, int]
    steps: list[dict[str, Any]]
    candidates: list[dict[str, Any]]
    path_text: str
    duty: str
    question: dict[str, Any] | None
    adjudications: list[dict[str, Any]] = field(default_factory=list)
    decider_code: str = ""  # Decider's own best path
    precedent_code: str = ""  # the nearest past rulings' vote
    fast_track: bool = False  # Decider, Bedrock and past rulings agree: review first, still reviewed
    off_path: int = 0
    decider_calls: int = 0
    decider_ms: float = 0.0
    llm_calls: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    wall_ms: float = 0.0

    @property
    def htsno(self) -> str:
        c = self.code
        return ".".join(p for p in (c[:4], c[4:6], c[6:8], c[8:10]) if p)


class TariffTrail:
    def __init__(
        self,
        *,
        tree: HTSTree | None = None,
        decider: Decider | None = None,
        policy: Policy | None = None,
        adjudicate: bool = True,
        use_precedents: bool = True,
        seed: bool = True,
    ) -> None:
        self.tree = tree or load()
        self.decider = decider or Decider()
        self.policy = policy or TARIFF_POLICY
        self.adjudicate = adjudicate
        self.use_precedents = use_precedents
        self.seed = seed

    def classify(self, facts: str, *, on_missing: OnMissing | None = None, observe=None) -> Classification:
        usage = bedrock.Usage()
        seed = HeadingSeed() if self.seed else None
        extra = (lambda: seed.vote(self.tree)) if seed else None
        adjudicator = (ShortlistAdjudicator(self.tree, use_precedents=self.use_precedents, usage=usage, extra=extra)
                       if self.adjudicate else None)
        walker = CalibratedTreeDescent(
            self.tree, self.decider, policy=self.policy, wording=HTS_WORDING, render_state=hts_state,
            on_shortlist=adjudicator, on_missing=on_missing, seed=seed, observe=observe,
        )
        calls_before, ms_before = self.decider.stats.calls, self.decider.stats.wall_ms
        started = time.perf_counter()
        result: Result = walker.descend(facts)
        wall = (time.perf_counter() - started) * 1000

        leaf = result.leaf
        code = self.tree.code_of(leaf) if leaf else ""
        decider_code = self.tree.code_of(result.candidates[0][0]) if result.candidates else code
        precedent_code = seed.vote(self.tree) if seed else ""
        return Classification(
            facts=result.facts,
            code=code,
            status=result.status,
            route=result.route,
            auto=result.auto,
            p=result.p,
            min_confidence=result.min_confidence,
            routes=result.counts(),
            steps=[_step_dict(self.tree, s) for s in result.steps],
            candidates=[{"code": self.tree.code_of(c), "htsno": self.tree[c].htsno, "p": round(p, 4)} for c, p in result.candidates],
            path_text=self.tree.path_text(leaf) if leaf else "",
            duty=_duty(self.tree, leaf) if leaf else "",
            question=result.question,
            adjudications=[vars(a) for a in (adjudicator.log if adjudicator else [])],
            decider_code=decider_code,
            precedent_code=precedent_code,
            fast_track=bool(code) and code == decider_code == precedent_code,
            off_path=result.off_path,
            decider_calls=self.decider.stats.calls - calls_before,
            decider_ms=self.decider.stats.wall_ms - ms_before,
            llm_calls=usage.calls,
            llm_input_tokens=usage.input_tokens,
            llm_output_tokens=usage.output_tokens,
            wall_ms=wall,
        )


def _duty(tree: HTSTree, node_id: str) -> str:
    """The general rate printed on the line or the nearest ancestor that carries one."""
    for node in reversed(tree.path(node_id)):
        if node.duty:
            return node.duty
    return ""


def _label(tree: HTSTree, node_id: str) -> str:
    if node_id == NONE_KEY:
        return "none of these"
    if node_id not in tree.nodes:
        return node_id
    node = tree[node_id]
    return node.htsno or tree.option_text(node_id)[:60]


def _step_dict(tree: HTSTree, step) -> dict[str, Any]:
    top = sorted(step.options.items(), key=lambda kv: kv[1], reverse=True)[:5]
    return {
        "node": step.node,
        "node_label": _label(tree, step.node) if step.node != tree.root_id else "HTS",
        "chosen": step.chosen,
        "chosen_label": _label(tree, step.chosen),
        "p": round(step.p, 4),
        "confidence": round(step.confidence, 4),
        "route": step.route,
        "latency_ms": round(step.latency_ms, 1),
        "top": [{"id": c, "label": _label(tree, c), "p": round(p, 4)} for c, p in top],
    }
