"""Offline tests for ClassificationGate (no Decider server, no Bedrock)."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(not Path("data/raw/hts_full.json").exists(), reason="run data/fetch_hts.py first")


def _event(code: str, description: str = "women's knitted pullover") -> SimpleNamespace:
    return SimpleNamespace(tool_use={"name": "file_entry", "toolUseId": "t1",
                                     "input": {"hts_code": code, "description": description, "value_usd": 10, "country_of_origin": "CN"}})


def _classification(code: str, auto: bool):
    from tariff_trail.classify import Classification

    route = "decider" if auto else "uncertain"
    return Classification(
        facts="women's knitted pullover", code=code, status="done", route="auto" if auto else "adjudicated", auto=auto,
        p=0.8 if auto else 0.3, min_confidence=0.95 if auto else 0.6, routes={route: 1},
        steps=[{"node_label": "6110.90.90", "route": route, "p": 0.95 if auto else 0.6, "confidence": 0.9}],
        candidates=[], path_text="", duty="6%", question=None,
    )


@pytest.fixture(scope="module")
def tree():
    from tariff_trail.hts.tree import load

    return load()


def test_unknown_code_is_denied(tree):
    from strands.interventions import Deny

    from tariff_trail.gate import ClassificationGate, Ledger

    gate = ClassificationGate(tree, Ledger())
    assert isinstance(gate.before_tool_call(_event("6110.99.9999")), Deny)


def test_code_not_from_classifier_is_guided(tree):
    from strands.interventions import Guide

    from tariff_trail.gate import ClassificationGate, Ledger

    gate = ClassificationGate(tree, Ledger())
    assert isinstance(gate.before_tool_call(_event("6110.90.9028")), Guide)


def test_auto_cleared_proceeds_and_uncertain_needs_broker(tree):
    from strands.interventions import Confirm, Proceed

    from tariff_trail.gate import ClassificationGate, Ledger

    ledger = Ledger()
    ledger.record(_classification("6110909028", auto=True))
    gate = ClassificationGate(tree, ledger)
    assert isinstance(gate.before_tool_call(_event("6110.90.9028")), Proceed)

    ledger.record(_classification("6110909028", auto=False))
    assert isinstance(gate.before_tool_call(_event("6110.90.9028")), Confirm)


def test_other_tools_pass_through(tree):
    from strands.interventions import Proceed

    from tariff_trail.gate import ClassificationGate, Ledger

    gate = ClassificationGate(tree, Ledger())
    event = SimpleNamespace(tool_use={"name": "lookup_duty", "toolUseId": "t2", "input": {"hts_code": "6110"}})
    assert isinstance(gate.before_tool_call(event), Proceed)
