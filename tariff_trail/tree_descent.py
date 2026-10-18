"""Calibrated Tree Descent: a reusable Strands Decider 2B decision pattern.

**The decision.** An agent must pick one item out of thousands (a tariff code, a medical code, a
product category, one tool out of hundreds). Showing an LLM all of them at once fails: it
invents items that do not exist and cannot say how sure it is. Walk the hierarchy instead, and
let Strands Decider answer one typed question per fork:

    child   choice   Which of these options describes the item?    (+ "none of these", below the top)

Decider returns a calibrated distribution over the options. Multiplying the probabilities along
a path gives the probability of that whole path, so every partial path in the tree can be
compared with every other. The descent is a best-first search on that number:

    pop the most probable partial path; if it ends in a leaf, that leaf is the best answer found;
    otherwise ask Decider about its children and push each child with  p(path) x p(child).

A wrong turn shows up by itself: Decider puts its mass on "none of these", the children of the
wrong node all become improbable, and the search resumes from the best alternative anywhere in
the tree, not just the last fork. Plain code then routes on the calibrated path probability:

    p(best path) >= auto            act without review                         ("auto")
    otherwise, with on_shortlist    an LLM picks among the top complete paths  ("adjudicated")
    otherwise                       return the best path flagged for review    ("review")

and, when a person or tool can answer (on_missing), the fork where the top candidates split is
asked two more questions (enough: noul, missing: choice) to request exactly the missing fact.

The model can only choose among the options it is shown, so every answer is a real leaf of the
tree. Thresholds are a policy you own: measure them on your own labelled cases.

**Using it.** Implement the four-method `Tree` protocol (or build a `DictTree`), create a
`Decider`, and call `CalibratedTreeDescent(tree, decider).descend(facts)`.
"""

from __future__ import annotations

import heapq
import itertools
import string
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol

from .decider import Decider, choice, noul

NONE_KEY = "none_of_these"


class Tree(Protocol):
    root_id: str

    def child_ids(self, node_id: str) -> list[str]: ...

    def option_text(self, node_id: str) -> str: ...

    def path_text(self, node_id: str) -> str: ...

    def is_terminal(self, node_id: str) -> bool: ...


@dataclass
class Policy:
    auto: float = 0.5  # act without review when the best path's probability is at least this
    act: float = 0.9  # a single fork counts as confident at or above this choice confidence
    budget: int = 24  # most Decider calls per descent
    shortlist: int = 3  # complete candidates handed to the LLM when the best path is not auto
    max_questions: int = 2  # missing-fact questions per descent (interactive use)
    offer_none: bool = True  # add "none of these" below the top level, to detect a wrong turn
    max_option_chars: int = 420
    max_prompt_chars: int = 9000  # all options of one fork together (Decider's window is 4,096 tokens)
    seed_weight: float = 1.0  # share of the root's probability given to the seeded shortcut (rest: full walk)


@dataclass
class Wording:
    """The words of the typed questions. Domain packages override these."""

    child: str = "Which option describes the item?"
    none_text: str = "None of these options describes the item; an earlier choice was wrong"
    enough: str = "Do the facts state everything needed to choose between these options?"
    enough_true: str = "the facts are enough to tell these options apart"
    enough_false: str = "a fact needed to tell these options apart is missing or unclear"
    missing: str = "Which single missing fact would best settle the choice between these options?"
    missing_facts: Mapping[str, str] = field(default_factory=dict)  # name -> description


@dataclass
class Step:
    node: str
    options: dict[str, float]  # child id (or NONE_KEY) -> Decider's probability
    chosen: str
    p: float  # probability of the chosen child at this fork
    confidence: float  # Decider's normalised confidence for this fork's answer
    route: str  # decider (confident) | uncertain | forced (single child)
    latency_ms: float = 0.0


@dataclass
class Candidate:
    leaf: str
    p: float  # path probability
    steps: list[Step]


@dataclass
class Result:
    leaf: str | None
    status: str  # done | needs_info | failed
    route: str = "review"  # auto | adjudicated | review
    p: float = 0.0  # path probability of the returned leaf
    steps: list[Step] = field(default_factory=list)  # the returned leaf's path
    candidates: list[tuple[str, float]] = field(default_factory=list)  # complete leaves found, best first
    expansions: int = 0  # Decider calls
    off_path: int = 0  # expansions that were not on the returned path (wrong turns explored)
    question: dict[str, Any] | None = None  # set when status == needs_info
    facts: str = ""
    note: str = ""

    @property
    def auto(self) -> bool:
        return self.status == "done" and self.route == "auto"

    @property
    def path(self) -> list[str]:
        return [s.chosen for s in self.steps]

    @property
    def min_confidence(self) -> float:
        real = [s.confidence for s in self.steps if s.route != "forced"]
        return min(real) if real else 1.0

    def counts(self) -> dict[str, int]:
        out: dict[str, int] = {}
        for step in self.steps:
            out[step.route] = out.get(step.route, 0) + 1
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaf": self.leaf, "status": self.status, "route": self.route, "auto": self.auto, "p": self.p,
            "candidates": self.candidates, "expansions": self.expansions, "off_path": self.off_path,
            "question": self.question, "note": self.note, "steps": [asdict(s) for s in self.steps],
        }


# on_shortlist(tree, [(leaf id, path probability)], facts) -> chosen leaf id, or None to keep the best
OnShortlist = Callable[[Tree, list[tuple[str, float]], str], str | None]
# on_missing(tree, node_id, fact_name, fact_description, facts) -> extra facts text, or None if unknown
OnMissing = Callable[[Tree, str, str, str, str], str | None]
# seed(tree, facts) -> a few likely mid-level node ids (e.g. from retrieval), best first; [] to skip
Seed = Callable[[Tree, str], list[str]]
SEED_KEY = "seeded"


def option_keys(n: int) -> list[str]:
    """Neutral option names: A..Z, AA..AZ, BA.. (the server allows up to 255 options)."""
    letters = string.ascii_uppercase
    keys = list(letters)
    for first in letters:
        if len(keys) >= n:
            break
        keys.extend(first + second for second in letters)
    return keys[:n]


class CalibratedTreeDescent:
    def __init__(
        self,
        tree: Tree,
        decider: Decider,
        *,
        policy: Policy | None = None,
        wording: Wording | None = None,
        render_state: Callable[[str, str], str] | None = None,
        on_shortlist: OnShortlist | None = None,
        on_missing: OnMissing | None = None,
        seed: Seed | None = None,
        observe: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.tree = tree
        self.decider = decider
        self.policy = policy or Policy()
        self.wording = wording or Wording()
        self.render_state = render_state or default_state
        self.on_shortlist = on_shortlist
        self.on_missing = on_missing
        self.seed = seed
        self.observe = observe  # called after every Decider fork, e.g. to stream the search to a UI

    # ---- one fork ----------------------------------------------------------

    def _option(self, node_id: str, siblings: int) -> str:
        text = self.tree.option_text(node_id)
        limit = max(60, min(self.policy.max_option_chars, self.policy.max_prompt_chars // max(1, siblings)))
        return text if len(text) <= limit else text[: limit - 3].rsplit(" ", 1)[0] + "..."

    def _state(self, node_id: str, facts: str) -> str:
        return self.render_state(facts, self.tree.path_text(node_id) if node_id != self.tree.root_id else "")

    def fork(self, node_id: str, facts: str, *, diagnose: bool = False) -> tuple[dict[str, float], float, dict[str, Any], float]:
        """Ask Decider about one fork: (probability by child id, confidence, extra answers, latency ms)."""
        children = self.tree.child_ids(node_id)
        keys = option_keys(len(children))
        key_to_child = dict(zip(keys, children))
        criteria: dict[str, str] = {k: self._option(c, len(children)) for k, c in key_to_child.items()}
        if self.policy.offer_none and node_id != self.tree.root_id:
            criteria[NONE_KEY] = self.wording.none_text
        questions: dict[str, Any] = {"child": choice(self.wording.child, criteria)}
        if diagnose:
            questions["enough"] = noul(self.wording.enough, {"true": self.wording.enough_true, "false": self.wording.enough_false})
            if self.wording.missing_facts:
                questions["missing"] = choice(self.wording.missing, dict(self.wording.missing_facts))
        started = time.perf_counter()
        answers = self.decider.ask(self._state(node_id, facts), questions)
        latency = (time.perf_counter() - started) * 1000
        child = answers["child"]
        probs = {key_to_child.get(k, k): float(p) for k, p in child["probabilities"].items()}
        return probs, float(child["confidence"]), answers, latency

    # ---- the search ----------------------------------------------------------

    def search(self, facts: str, *, want: int = 1) -> tuple[list[Candidate], int, set[str]]:
        """Best-first search on path probability. Returns up to `want` complete candidates, best first.

        With a `seed`, the first fork is a shortcut: Decider chooses among the seeded nodes (plus
        "none of these"), and each pick enters the frontier with that probability. "None of these"
        sends its probability mass to the full walk from the root, so a bad seed costs one call.
        """
        tie = itertools.count()
        frontier: list[tuple[float, int, str, list[Step]]] = []
        found: list[Candidate] = []
        expanded: set[str] = set()
        calls = 0

        seeds = [s for s in (self.seed(self.tree, facts) if self.seed else []) if s != self.tree.root_id]
        if len(seeds) >= 1:
            probs, confidence, latency = self._seed_fork(seeds, facts)
            calls += 1
            expanded.add(SEED_KEY)
            self._emit(SEED_KEY, 1.0, probs, confidence, latency)
            weight = self.policy.seed_weight
            top = max(probs, key=probs.get)
            for node, q in probs.items():
                if node == NONE_KEY:
                    continue
                route = "decider" if node == top and confidence >= self.policy.act else "uncertain"
                step = Step(SEED_KEY, probs, node, q, confidence if node == top else 0.0, route, latency)
                heapq.heappush(frontier, (-(weight * q), next(tie), node, [step]))
            root_mass = (1 - weight) + weight * probs.get(NONE_KEY, 0.0)
            if root_mass > 0:
                heapq.heappush(frontier, (-root_mass, next(tie), self.tree.root_id, []))
        else:
            frontier.append((-1.0, next(tie), self.tree.root_id, []))

        while frontier and len(found) < want:
            negp, _, node, steps = heapq.heappop(frontier)
            p = -negp
            if self.tree.is_terminal(node):
                found.append(Candidate(node, p, steps))
                continue
            children = self.tree.child_ids(node)
            if not children:
                continue  # a dead end that is not an answer
            if len(children) == 1:
                step = Step(node, {children[0]: 1.0}, children[0], 1.0, 1.0, "forced")
                heapq.heappush(frontier, (-p, next(tie), children[0], steps + [step]))
                continue
            if calls >= self.policy.budget:
                if not found:  # out of budget with no answer: finish this path greedily
                    found.append(self._greedy(node, p, steps, facts))
                break
            probs, confidence, _, latency = self.fork(node, facts)
            calls += 1
            expanded.add(node)
            self._emit(node, p, probs, confidence, latency)
            ranked = sorted(((c, q) for c, q in probs.items() if c != NONE_KEY), key=lambda kv: kv[1], reverse=True)
            top = ranked[0][0]
            for child, q in ranked:
                route = "decider" if child == top and confidence >= self.policy.act else "uncertain"
                step = Step(node, probs, child, q, confidence if child == top else 0.0, route, latency)
                heapq.heappush(frontier, (-(p * q), next(tie), child, steps + [step]))
        return found, calls, expanded

    def _emit(self, node: str, p: float, probs: dict[str, float], confidence: float, latency: float) -> None:
        if self.observe is not None:
            self.observe({"event": "fork", "node": node, "p_path": p, "probs": probs,
                          "confidence": confidence, "latency_ms": latency})

    def _seed_fork(self, seeds: list[str], facts: str) -> tuple[dict[str, float], float, float]:
        """One Decider call choosing among seeded nodes, each described by its full path."""
        keys = option_keys(len(seeds))
        key_to_node = dict(zip(keys, seeds))
        limit = max(80, min(2 * self.policy.max_option_chars, self.policy.max_prompt_chars // max(1, len(seeds))))
        criteria: dict[str, str] = {}
        for key, node in key_to_node.items():
            text = " > ".join(line.split(": ", 1)[-1] for line in self.tree.path_text(node).splitlines())
            criteria[key] = text if len(text) <= limit else "..." + text[-(limit - 3):]
        criteria[NONE_KEY] = self.wording.none_text
        started = time.perf_counter()
        answers = self.decider.ask(self.render_state(facts, ""), {"child": choice(self.wording.child, criteria)})
        latency = (time.perf_counter() - started) * 1000
        child = answers["child"]
        probs = {key_to_node.get(k, k): float(p) for k, p in child["probabilities"].items()}
        return probs, float(child["confidence"]), latency

    def _greedy(self, node: str, p: float, steps: list[Step], facts: str) -> Candidate:
        while not self.tree.is_terminal(node):
            children = self.tree.child_ids(node)
            if not children:
                break
            if len(children) == 1:
                steps = steps + [Step(node, {children[0]: 1.0}, children[0], 1.0, 1.0, "forced")]
                node = children[0]
                continue
            probs, confidence, _, latency = self.fork(node, facts)
            child, q = max(((c, v) for c, v in probs.items() if c != NONE_KEY), key=lambda kv: kv[1])
            route = "decider" if confidence >= self.policy.act else "uncertain"
            steps = steps + [Step(node, probs, child, q, confidence, route, latency)]
            p, node = p * q, child
        return Candidate(node, p, steps)

    def descend(self, facts: str) -> Result:
        questions_asked = 0
        while True:
            want = self.policy.shortlist if (self.on_shortlist or self.on_missing) else 1
            found, calls, expanded = self.search(facts, want=want)
            if not found:
                return Result(None, "failed", facts=facts, expansions=calls, note="no complete path found")
            best = found[0]
            result = Result(
                leaf=best.leaf, status="done", p=best.p, steps=best.steps, expansions=calls, facts=facts,
                candidates=[(c.leaf, c.p) for c in found],
                off_path=len(expanded - {s.node for s in best.steps}),
            )
            if best.p >= self.policy.auto:
                result.route = "auto"
                return result

            # Not sure. Ask for the fact that splits the top candidates, if someone can answer.
            if self.on_missing and len(found) > 1 and questions_asked < self.policy.max_questions:
                split = _divergence(best, found[1])
                if split is not None:
                    _, _, answers, _ = self.fork(split, facts, diagnose=True)
                    result.expansions += 1
                    enough = answers.get("enough", {}).get("noul", 1.0)
                    missing = answers.get("missing", {}).get("choice")
                    if enough < 0.5 and missing and missing != "nothing":
                        description = self.wording.missing_facts.get(missing, missing)
                        extra = self.on_missing(self.tree, split, missing, description, facts)
                        if extra:
                            questions_asked += 1
                            facts = f"{facts}\n{extra}".strip()
                            continue  # search again with the new fact
                        if self.on_shortlist is None:
                            result.status = "needs_info"
                            result.question = {"node": split, "fact": missing, "description": description,
                                               "candidates": result.candidates}
                            return result

            if self.on_shortlist and found:
                picked = self.on_shortlist(self.tree, [(c.leaf, c.p) for c in found], facts)
                chosen = next((c for c in found if c.leaf == picked), None)
                if chosen is not None:
                    result.leaf, result.p, result.steps = chosen.leaf, chosen.p, chosen.steps
                elif picked is not None:  # the hook may add candidates of its own (e.g. from retrieval)
                    result.leaf, result.p = picked, 0.0
                result.route = "adjudicated"
            return result


def _divergence(a: Candidate, b: Candidate) -> str | None:
    """The tree fork where two candidate paths part ways (the seeded shortcut is not a tree node)."""
    for sa, sb in zip(a.steps, b.steps):
        if sa.node == sb.node and sa.chosen != sb.chosen:
            return None if sa.node == SEED_KEY else sa.node
    return None


def default_state(facts: str, path: str) -> str:
    if not path:
        return f"ITEM FACTS:\n{facts}"
    return f"ITEM FACTS:\n{facts}\n\nCHOSEN SO FAR:\n{path}"


class DictTree:
    """A `Tree` over nested dicts, for small hierarchies (tool catalogs, taxonomies).

    {"name": "root", "children": [{"name": "github", "description": "...", "children": [...]}, ...]}
    Node ids are slash-joined names: "github/create_pull_request".
    """

    root_id = ""

    def __init__(self, spec: Mapping[str, Any]) -> None:
        self._nodes: dict[str, Mapping[str, Any]] = {}
        self._children: dict[str, list[str]] = {}

        def walk(node: Mapping[str, Any], node_id: str) -> None:
            self._nodes[node_id] = node
            kids = []
            for child in node.get("children", []):
                child_id = f"{node_id}/{child['name']}" if node_id else child["name"]
                kids.append(child_id)
                walk(child, child_id)
            self._children[node_id] = kids

        walk(spec, "")

    def child_ids(self, node_id: str) -> list[str]:
        return self._children[node_id]

    def option_text(self, node_id: str) -> str:
        node = self._nodes[node_id]
        return f"{node['name']}: {node.get('description', '')}".strip(": ")

    def path_text(self, node_id: str) -> str:
        parts = node_id.split("/") if node_id else []
        return "\n".join(self.option_text("/".join(parts[: i + 1])) for i in range(len(parts)))

    def is_terminal(self, node_id: str) -> bool:
        return not self._children[node_id]


__all__ = [
    "NONE_KEY", "SEED_KEY", "Tree", "Policy", "Wording", "Step", "Candidate", "Result", "CalibratedTreeDescent",
    "DictTree", "option_keys", "OnShortlist", "OnMissing", "Seed", "Sequence",
]
