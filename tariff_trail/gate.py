"""ClassificationGate: a Strands InterventionHandler that guards the filing tool.

The agent may only file a customs entry with a tariff code that TariffTrail produced in this
session. Before `file_entry` runs, the gate checks, in order:

  1. the code exists in the current HTS                          else Deny
  2. the code came from `classify_product` in this session       else Guide ("classify it first")
  3. Strands Decider: is the entry's goods description grounded
     in the product that was classified? (one noul question)     else Guide ("describe the same goods")
  4. the path probability cleared the auto-clear bar             else Confirm (a broker approves)
  5. otherwise                                                   Proceed

Checks 1-2 are plain code, 3 is a second Decider decision in the agent's path, and 4 turns the
classifier's calibrated confidence into the human-in-the-loop rule.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

from .classify import Classification
from .decider import Decider, DeciderUnavailable, noul
from .hts.tree import HTSTree, digits

GROUNDED = noul(
    "Does the goods description on the customs entry describe the same product that was classified?",
    {
        "true": "the entry describes the same goods: same kind of article, material and use",
        "false": "the entry describes different goods, or adds or changes facts that matter for classification",
    },
)


@dataclass
class Ledger:
    """What `classify_product` decided in this session, keyed by tariff code."""

    by_code: dict[str, Classification] = field(default_factory=dict)
    filed: list[dict[str, Any]] = field(default_factory=list)

    def record(self, result: Classification) -> None:
        if result.code:
            self.by_code[result.code] = result


class ClassificationGate(InterventionHandler):
    name = "tariff-trail-classification-gate"

    def __init__(self, tree: HTSTree, ledger: Ledger, decider: Decider | None = None, grounded_bar: float = 0.5) -> None:
        self.tree = tree
        self.ledger = ledger
        self.decider = decider
        self.grounded_bar = grounded_bar
        self.log: list[dict[str, Any]] = []

    def before_tool_call(self, event, **kwargs):
        tool_use = event.tool_use
        if tool_use.get("name") != "file_entry":
            return Proceed()
        args = tool_use.get("input") or {}
        code = digits(str(args.get("hts_code", "")))
        entry = {"code": code, "verdict": None}
        self.log.append(entry)

        if not self.tree.exists(code):
            entry["verdict"] = "deny: not an HTS code"
            return Deny(reason=f"{args.get('hts_code')!r} is not a line in the current HTS. Classify the product with classify_product.")

        result = self.ledger.by_code.get(code)
        if result is None:
            entry["verdict"] = "guide: not from classifier"
            return Guide(feedback="Only file codes produced by classify_product in this session. Classify the product first.")

        if self.decider is not None:
            state = json.dumps({"classified_product": result.facts, "entry_goods_description": args.get("description", "")})
            try:
                p = self.decider.ask(state, {"grounded": GROUNDED})["grounded"]["noul"]
            except DeciderUnavailable:
                p = None
            entry["grounded"] = p
            if p is not None and p < self.grounded_bar:
                entry["verdict"] = "guide: description not grounded"
                return Guide(feedback=(
                    "The entry's goods description does not match the product that was classified. "
                    "Use the classified product's description, or classify the new description first."
                ))

        if not result.auto:
            entry["verdict"] = "confirm: broker review" + (" (fast-track)" if result.fast_track else "")
            if result.fast_track:
                why = "Decider, Bedrock and the nearest past CBP rulings all agree (fast-track review)"
            else:
                alternatives = ", ".join(c["htsno"] for c in result.candidates if c["code"] != result.code)[:80]
                why = f"the sources disagree; alternatives considered: {alternatives or 'none'}"
            return Confirm(prompt=f"Broker review needed before filing {result.htsno}: {why}. Approve filing? (yes/no)")

        entry["verdict"] = "proceed"
        return Proceed(reason=f"auto-cleared: path probability {result.p:.2f}")
