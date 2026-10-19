"""Calibrated Tree Descent in any Strands agent: one tool that decides, one gate that guards.

The domain-free version of TariffTrail's wiring (`classify_product` + `ClassificationGate`):

    from strands import Agent
    from tariff_trail.decider import Decider
    from tariff_trail.strands_kit import DecisionGate, DecisionLedger, decision_tool
    from tariff_trail.tree_descent import CalibratedTreeDescent, DictTree, Policy

    descent = CalibratedTreeDescent(DictTree(catalog), Decider(), policy=Policy(auto=0.6))
    ledger = DecisionLedger()
    agent = Agent(
        tools=[decision_tool(descent, ledger, name="choose_tool"), run_tool],
        interventions=[DecisionGate(descent, ledger, guarded={"run_tool": "tool_id"}, decide_tool="choose_tool")],
    )

`decision_tool` lets the agent ask for a decision; it records every result in the ledger. Before
each guarded tool call, the gate reads the argument that names the item and decides in plain code:

    the item is not a leaf of the tree                    Deny
    the descent did not choose it in this session         Guide  ("decide with <tool> first")
    its path probability is below the policy's auto bar   Confirm (a person approves)
    otherwise                                             Proceed

So the LLM can never act on an item it made up or on a low-confidence choice without a person
saying yes, and the threshold that makes that call is the one you measured (see PATTERN.md).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from strands import tool
from strands.interventions import Confirm, Deny, Guide, InterventionHandler, Proceed

from .tree_descent import CalibratedTreeDescent, Result


@dataclass
class DecisionLedger:
    """Every decision the descent made in this session, by chosen leaf."""

    by_leaf: dict[str, Result] = field(default_factory=dict)

    def record(self, result: Result) -> None:
        if result.leaf:
            self.by_leaf[result.leaf] = result


def decision_tool(descent: CalibratedTreeDescent, ledger: DecisionLedger, *, name: str = "decide",
                  description: str = "Choose the one item of the catalog that fits the request. Returns the item, "
                                     "its probability and the alternatives considered."):
    """A Strands tool that runs the descent on a request and records the result in `ledger`.

    The reply does not tell the LLM whether the item is safe to act on: `DecisionGate` enforces that
    in code, so the policy holds even when the model would have gone ahead (or asks first) on its own.
    """

    def decide(request: str) -> str:
        """Run Calibrated Tree Descent on the request.

        Args:
            request: the user's request or the item's facts, in plain words
        """
        result = descent.descend(request)
        ledger.record(result)
        return json.dumps({
            "item": result.leaf, "probability": round(result.p, 3), "status": result.status,
            "alternatives": [leaf for leaf, _ in result.candidates[1:4]],
        })

    return tool(decide, name=name, description=description)


class DecisionGate(InterventionHandler):
    """Guards tools whose argument names an item of the tree (`guarded`: tool name -> argument)."""

    name = "calibrated-tree-descent-gate"

    def __init__(self, descent: CalibratedTreeDescent, ledger: DecisionLedger, *, guarded: dict[str, str],
                 decide_tool: str = "decide") -> None:
        self.descent = descent
        self.ledger = ledger
        self.guarded = guarded
        self.decide_tool = decide_tool
        self.log: list[dict[str, Any]] = []

    def _is_leaf(self, item: str) -> bool:
        try:
            return bool(item) and self.descent.tree.is_terminal(item)
        except (KeyError, IndexError):
            return False

    def before_tool_call(self, event, **kwargs):
        tool_use = event.tool_use
        arg = self.guarded.get(tool_use.get("name"))
        if arg is None:
            return Proceed()
        item = str((tool_use.get("input") or {}).get(arg, ""))
        entry = {"tool": tool_use.get("name"), "item": item, "verdict": None}
        # Strands runs this hook again when a paused (Confirm) call resumes: log each tool call once.
        if self.log and tool_use.get("toolUseId") and self.log[-1].get("id") == tool_use.get("toolUseId"):
            entry = self.log[-1]
        else:
            entry["id"] = tool_use.get("toolUseId")
            self.log.append(entry)

        if not self._is_leaf(item):
            entry["verdict"] = "deny: not an item of the tree"
            return Deny(reason=f"{item!r} is not an item this agent can act on. Use {self.decide_tool} to choose one.")
        result = self.ledger.by_leaf.get(item)
        if result is None:
            entry["verdict"] = "guide: not decided"
            return Guide(feedback=f"Only act on items chosen by {self.decide_tool} in this session. Call {self.decide_tool} first.")
        if not result.auto:
            entry["verdict"] = f"confirm: p={result.p:.2f}"
            others = ", ".join(leaf for leaf, _ in result.candidates if leaf != item)[:120] or "none"
            return Confirm(prompt=f"Not sure enough to act on {item} (probability {result.p:.2f}, "
                                  f"bar {self.descent.policy.auto:.2f}; alternatives: {others}). Go ahead? (yes/no)")
        entry["verdict"] = "proceed"
        return Proceed(reason=f"path probability {result.p:.2f} >= {self.descent.policy.auto:.2f}")


__all__ = ["DecisionLedger", "DecisionGate", "decision_tool"]
