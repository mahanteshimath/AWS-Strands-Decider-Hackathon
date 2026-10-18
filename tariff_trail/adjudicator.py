"""Shortlist adjudication on Amazon Bedrock: the `on_shortlist` hook for Calibrated Tree Descent.

Called at most once per product, and only when Strands Decider's best path is not probable
enough to act on. The LLM sees the product facts, the top complete tariff codes the search
found (each with its full path of official wording and Decider's path probability), and the
most similar past CBP rulings under those codes, and picks one by letter. It cannot leave the
shortlist, so it cannot invent a code.
"""

from __future__ import annotations

import string
from dataclasses import dataclass, field

from . import bedrock, precedents
from .hts.tree import HTSTree

SYSTEM = (
    "You are a licensed US customs broker. You classify goods under the Harmonized Tariff Schedule "
    "of the United States by applying the General Rules of Interpretation in order: the terms of "
    "the headings and the section and chapter notes first, then the other rules. Be precise and brief."
)

PROMPT = """Product facts:
{facts}

Candidate classifications (full official wording, most specific line last; the decision model's
probability for the whole path in brackets, 0.00 for a candidate taken from similar past rulings):
{options}
{precedents}
Which candidate is correct for this product? Reply with JSON only:
{{"choice": "<letter>", "reason": "<one sentence citing the deciding fact and wording>"}}"""


@dataclass
class Adjudication:
    candidates: list[str]
    chosen: str | None
    reason: str = ""
    precedents: list[str] = field(default_factory=list)
    model: str = ""


class ShortlistAdjudicator:
    """Callable `on_shortlist(tree, [(leaf id, p)], facts) -> leaf id`; keeps a log of every call.

    `extra()` may return one more candidate code from outside the search, e.g. the nearest past
    ruling's code; it is added to the shortlist when it is not already on it.
    """

    def __init__(self, tree: HTSTree, *, use_precedents: bool = True, usage: bedrock.Usage | None = None,
                 extra=None) -> None:
        self.tree = tree
        self.use_precedents = use_precedents and precedents.available()
        self.usage = usage
        self.extra = extra
        self.log: list[Adjudication] = []

    def _precedent_block(self, leaves: list[str], facts: str) -> tuple[str, list[str]]:
        if not self.use_precedents:
            return "", []
        seen: dict[str, precedents.Precedent] = {}
        for leaf in leaves:
            for p in precedents.search(facts, k=2, prefix=self.tree.code_of(leaf)[:4]):
                seen.setdefault(p.ruling, p)
        found = sorted(seen.values(), key=lambda p: p.score, reverse=True)[:4]
        if not found:
            return "", []
        lines = ["", "Similar past CBP rulings (for reference; decide on the facts of this product):"]
        for p in found:
            codes = ", ".join(_dotted(c) for c in p.codes[:3])
            lines.append(f"- {p.ruling} ({p.date}) -> {codes}: {p.subject[:120]}. {p.summary[:300]}")
        return "\n".join(lines) + "\n", [p.ruling for p in found]

    def __call__(self, tree: HTSTree, shortlist: list[tuple[str, float]], facts: str) -> str | None:
        shortlist = list(shortlist)
        extra = self.extra() if self.extra else ""
        if extra and extra in tree.by_code and tree.by_code[extra] not in [leaf for leaf, _ in shortlist]:
            shortlist.append((tree.by_code[extra], 0.0))
        if len(shortlist) < 2:
            return None
        letters = string.ascii_uppercase[: len(shortlist)]
        options = "\n\n".join(
            f"{letter}. {tree[leaf].htsno} [{p:.2f}]\n{_indent(tree.path_text(leaf))}"
            for letter, (leaf, p) in zip(letters, shortlist)
        )
        block, used = self._precedent_block([leaf for leaf, _ in shortlist], facts)
        record = Adjudication(candidates=[tree[leaf].htsno for leaf, _ in shortlist], chosen=None, precedents=used)
        try:
            data, reply = bedrock.converse_json(
                PROMPT.format(facts=facts, options=options, precedents=block),
                role="reasoner", system=SYSTEM, max_tokens=300, usage=self.usage,
            )
            record.model = reply.model
            letter = str(data.get("choice", "")).strip().upper()[:1]
            if letter in letters:
                record.chosen = shortlist[letters.index(letter)][0]
            record.reason = str(data.get("reason", ""))
        except Exception as exc:  # keep Decider's best path if the LLM call fails
            record.reason = f"adjudication failed: {exc}"
        self.log.append(record)
        return record.chosen


def _indent(text: str) -> str:
    return "\n".join("   " + line for line in text.splitlines())


def _dotted(code: str) -> str:
    if len(code) <= 4:
        return code
    parts = [code[:4], code[4:6], code[6:8], code[8:10]]
    return ".".join(p for p in parts if p)
