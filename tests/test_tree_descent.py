"""Offline tests for Calibrated Tree Descent, with a scripted stand-in for the Decider server."""

from __future__ import annotations

from pathlib import Path

import pytest

from tariff_trail.tree_descent import NONE_KEY, CalibratedTreeDescent, DictTree, Policy, Wording, option_keys

CATALOG = {
    "name": "tools",
    "children": [
        {"name": "github", "description": "code hosting", "children": [
            {"name": "create_pull_request", "description": "open a PR"},
            {"name": "list_issues", "description": "list issues"},
        ]},
        {"name": "slack", "description": "team chat", "children": [
            {"name": "send_channel", "description": "post to a channel"},
            {"name": "send_user", "description": "direct message a person"},
        ]},
    ],
}


class ScriptedDecider:
    """Answers each fork with `script(node_id, state) -> {option name or NONE_KEY: weight}`."""

    def __init__(self, tree: DictTree, script, enough: float = 0.9, missing: str = "user"):
        self.tree, self.script, self.enough, self.missing, self.calls = tree, script, enough, missing, 0

    def ask(self, state, questions):
        self.calls += 1
        criteria = questions["child"]["criteria"]
        node = self._node(criteria)
        wanted = self.script(node, state)
        probs = {}
        for key, text in criteria.items():
            name = NONE_KEY if key == NONE_KEY else text.split(":", 1)[0]
            probs[key] = wanted.get(name, 0.001)
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}
        top = max(probs, key=probs.get)
        n = len(probs)
        answers = {"child": {"choice": top, "probabilities": probs, "confidence": (n * probs[top] - 1) / (n - 1)}}
        if "enough" in questions:
            answers["enough"] = {"noul": self.enough}
        if "missing" in questions:
            answers["missing"] = {"choice": self.missing, "probabilities": {self.missing: 1.0}, "confidence": 1.0}
        return answers

    def _node(self, criteria):
        names = {t.split(":", 1)[0] for k, t in criteria.items() if k != NONE_KEY}
        for node in ["", "github", "slack"]:
            if names == {c.rsplit("/", 1)[-1] for c in self.tree.child_ids(node)}:
                return node
        raise AssertionError(names)


def fixed(table):
    """Scripted forks answer from `table`; unscripted forks answer evenly."""
    return lambda node, state: table.get(node, {})


def test_option_keys_are_unique_past_26():
    keys = option_keys(80)
    assert len(keys) == len(set(keys)) == 80
    assert keys[:3] == ["A", "B", "C"] and keys[26] == "AA"


def test_confident_walk_is_automatic():
    tree = DictTree(CATALOG)
    decider = ScriptedDecider(tree, fixed({"": {"slack": 0.97}, "slack": {"send_user": 0.96}}))
    result = CalibratedTreeDescent(tree, decider).descend("DM Priya the release notes")
    assert result.leaf == "slack/send_user"
    assert result.auto and result.status == "done"
    assert result.p > 0.9
    assert decider.calls == 2


def test_wrong_turn_recovers_through_path_probability():
    tree = DictTree(CATALOG)
    decider = ScriptedDecider(tree, fixed({
        "": {"github": 0.6, "slack": 0.4},
        "github": {NONE_KEY: 0.9, "list_issues": 0.05, "create_pull_request": 0.05},
        "slack": {"send_channel": 0.95, "send_user": 0.05},
    }))
    result = CalibratedTreeDescent(tree, decider, policy=Policy(auto=0.3)).descend("announce in #general")
    assert result.leaf == "slack/send_channel"
    assert result.off_path == 1  # explored github, then left it
    assert result.auto


def test_uncertain_product_goes_to_shortlist_adjudicator():
    tree = DictTree(CATALOG)
    decider = ScriptedDecider(tree, fixed({"": {"slack": 0.95}, "slack": {"send_channel": 0.55, "send_user": 0.45}}))
    seen = []

    def on_shortlist(tree_, shortlist, facts):
        seen.append([leaf for leaf, _ in shortlist])
        return "slack/send_user"

    result = CalibratedTreeDescent(tree, decider, policy=Policy(auto=0.9), on_shortlist=on_shortlist).descend("tell Priya")
    assert result.leaf == "slack/send_user"
    assert result.route == "adjudicated" and not result.auto
    assert seen and seen[0][:2] == ["slack/send_channel", "slack/send_user"]


def test_missing_fact_without_answer_returns_question():
    tree = DictTree(CATALOG)
    decider = ScriptedDecider(tree, fixed({"": {"slack": 0.95}, "slack": {"send_channel": 0.5, "send_user": 0.5}}), enough=0.2)
    wording = Wording(missing_facts={"user": "who it is for", "nothing": "nothing is missing"})
    result = CalibratedTreeDescent(tree, decider, policy=Policy(auto=0.9), wording=wording,
                                   on_missing=lambda *a: None).descend("send it")
    assert result.status == "needs_info"
    assert result.question["fact"] == "user" and result.question["node"] == "slack"


def test_missing_fact_answer_searches_again():
    tree = DictTree(CATALOG)

    def script(node, state):
        if node == "slack":
            return {"send_user": 0.97} if "Priya" in state else {"send_channel": 0.5, "send_user": 0.5}
        return {"slack": 0.97}

    decider = ScriptedDecider(tree, script, enough=0.2)
    wording = Wording(missing_facts={"user": "who it is for"})
    result = CalibratedTreeDescent(tree, decider, policy=Policy(auto=0.9), wording=wording,
                                   on_missing=lambda *a: "Recipient: one person, Priya").descend("send it")
    assert result.leaf == "slack/send_user" and result.auto
    assert "Priya" in result.facts


class TwoStage(ScriptedDecider):
    """The seeded fork shows full paths rather than child names, so it is answered by option key."""

    def __init__(self, tree, script, seed_probs):
        super().__init__(tree, script)
        self.seed_probs = seed_probs

    def ask(self, state, questions):
        criteria = questions["child"]["criteria"]
        names = {t.split(":", 1)[0] for k, t in criteria.items() if k != NONE_KEY}
        if any(names == {c.rsplit("/", 1)[-1] for c in self.tree.child_ids(n)} for n in ["", "github", "slack"]):
            return super().ask(state, questions)
        self.calls += 1
        probs = {k: self.seed_probs.get(k, 0.001) for k in criteria}
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}
        top = max(probs, key=probs.get)
        n = len(probs)
        return {"child": {"choice": top, "probabilities": probs, "confidence": (n * probs[top] - 1) / (n - 1)}}


def test_seeded_shortcut_and_its_fallback():
    from tariff_trail.tree_descent import SEED_KEY

    tree = DictTree(CATALOG)
    script = fixed({"": {"github": 0.97}, "github": {"create_pull_request": 0.96}, "slack": {"send_user": 0.96}})

    # A good seed: one call picks the seeded node, the walk continues below it.
    decider = TwoStage(tree, script, {"A": 0.95, NONE_KEY: 0.05})
    result = CalibratedTreeDescent(tree, decider, seed=lambda t, f: ["slack"]).descend("DM Priya")
    assert result.leaf == "slack/send_user" and result.auto
    assert result.steps[0].node == SEED_KEY
    assert decider.calls == 2

    # A wrong seed: Decider says "none of these" and that mass goes to the full walk from the root.
    decider = TwoStage(tree, script, {"A": 0.05, NONE_KEY: 0.95})
    result = CalibratedTreeDescent(tree, decider, seed=lambda t, f: ["slack"]).descend("open a PR")
    assert result.leaf == "github/create_pull_request"
    assert result.steps[0].node == ""


@pytest.mark.skipif(not Path("data/raw/hts_full.json").exists(), reason="run data/fetch_hts.py first")
def test_hts_tree_matches_protocol_and_known_path():
    from tariff_trail.hts.tree import load

    tree = load()
    leaf = tree.by_code["6110909028"]
    assert tree.is_terminal(leaf)
    codes = [n.code for n in tree.path(leaf) if n.code]
    assert codes[:4] == ["61", "6110", "611090", "61109090"]
    assert all(tree.child_ids(n.id) for n in tree.path(leaf)[:-1])
    section = tree.path(leaf)[0]
    assert "chapters:" in tree.option_text(section.id)
