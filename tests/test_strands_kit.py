"""Offline tests for the Strands wiring of Calibrated Tree Descent (no Decider server, no Bedrock)."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

pytest.importorskip("strands.interventions")

from strands.interventions import Confirm, Deny, Guide, Proceed  # noqa: E402

from tariff_trail.strands_kit import DecisionGate, DecisionLedger, decision_tool  # noqa: E402
from tariff_trail.tree_descent import NONE_KEY, CalibratedTreeDescent, DictTree, Policy  # noqa: E402

CATALOG = {"name": "tools", "children": [
    {"name": "slack", "description": "team chat", "children": [
        {"name": "send_channel", "description": "post to a channel"},
        {"name": "send_user", "description": "direct message a person"}]},
    {"name": "github", "description": "code hosting", "children": [
        {"name": "create_pull_request", "description": "open a PR"},
        {"name": "list_issues", "description": "list issues"}]},
]}


class FixedDecider:
    """Puts `weight` on the option whose name is in `wanted` at every fork, the rest spread evenly."""

    def __init__(self, wanted: set[str], weight: float) -> None:
        self.wanted, self.weight = wanted, weight

    def ask(self, state, questions):
        criteria = questions["child"]["criteria"]
        hits = [k for k, text in criteria.items() if k != NONE_KEY and text.split(":", 1)[0] in self.wanted]
        rest = [k for k in criteria if k not in hits]
        if hits:
            probs = {k: self.weight / len(hits) for k in hits}
            probs.update({k: (1 - self.weight) / len(rest) for k in rest})
        else:
            probs = {k: 1 / len(rest) for k in rest}
        top = max(probs, key=probs.get)
        return {"child": {"choice": top, "probabilities": probs, "confidence": probs[top]}}


def _setup(weight: float):
    descent = CalibratedTreeDescent(DictTree(CATALOG), FixedDecider({"slack", "send_user"}, weight), policy=Policy(auto=0.6))
    ledger = DecisionLedger()
    gate = DecisionGate(descent, ledger, guarded={"run_tool": "tool_id"}, decide_tool="choose_tool")
    return descent, ledger, gate, decision_tool(descent, ledger, name="choose_tool")


def _call(tool_id: str, name: str = "run_tool") -> SimpleNamespace:
    return SimpleNamespace(tool_use={"name": name, "toolUseId": "t1", "input": {"tool_id": tool_id}})


def test_tool_decides_and_records():
    _, ledger, _, choose = _setup(0.95)
    reply = json.loads(choose(request="DM Priya the release notes"))
    assert reply["item"] == "slack/send_user" and "safe_to_act" not in reply  # the gate enforces the bar, not the LLM
    assert ledger.by_leaf["slack/send_user"].auto


def test_gate_verdicts():
    _, ledger, gate, choose = _setup(0.95)
    assert isinstance(gate.before_tool_call(_call("slack/send_user", name="other_tool")), Proceed)
    assert isinstance(gate.before_tool_call(_call("slack/delete_workspace")), Deny)
    assert isinstance(gate.before_tool_call(_call("slack")), Deny)  # a service, not a tool
    assert isinstance(gate.before_tool_call(_call("slack/send_user")), Guide)  # not decided yet
    choose(request="DM Priya the release notes")
    assert isinstance(gate.before_tool_call(_call("slack/send_user")), Proceed)
    assert isinstance(gate.before_tool_call(_call("slack/send_channel")), Guide)  # not what was decided


def test_low_confidence_needs_a_person():
    _, ledger, gate, choose = _setup(0.7)  # p(path) = 0.7 x 0.7 < 0.6
    reply = json.loads(choose(request="tell Priya"))
    assert reply["item"] == "slack/send_user" and not ledger.by_leaf["slack/send_user"].auto
    assert isinstance(gate.before_tool_call(_call("slack/send_user")), Confirm)
