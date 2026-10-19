# Decision pattern: Calibrated Tree Descent

**Reusable code:** [`tariff_trail/tree_descent.py`](tariff_trail/tree_descent.py) (one file; it needs only
the `urllib` Decider client in [`tariff_trail/decider.py`](tariff_trail/decider.py), so both files use the
standard library alone and can be copied into any project).
**Strands wiring for any domain:** [`tariff_trail/strands_kit.py`](tariff_trail/strands_kit.py): a tool that
decides and an `InterventionHandler` that guards the action ([below](#wiring-it-into-any-strands-agent)).
**Used here for:** US tariff classification (11,516 decisions, 18,946 final codes).
**Reused for:** routing a request to one of 48 tools, with and without a Strands agent
([`examples/tool_catalog`](examples/tool_catalog)).

## The problem it solves

An agent has to pick **one item out of thousands**: a tariff code, a diagnosis code, a product
category, a policy clause, one tool out of hundreds. Put every option in the prompt and an LLM:

- **invents items that do not exist.** On our tuning set, 93% of Nova Pro's direct answers were not real HTS codes.
- **cannot say how sure it is.** It sounds equally confident whether it is right or wrong.
- **wanders when it is given search tools.** One tuning case looped through 201 tool calls and 19.6 million tokens.

## The decision

Do not choose among thousands. Choose among a handful, many times, down a hierarchy. Let a
small calibrated model, Strands Decider, make each choice, and use its probabilities to decide
what happens next.

```
             retrieval proposes ──► SEED   "Which of these 8 headings fits?" (+ none of these)
                                     │                 │ none of these
                                     ▼                 ▼
 Decider decides ──────────────►  FORK  ◄────────  ROOT  (full walk: section ▸ chapter ▸ heading)
   "Which of these options          │
    describes the item?"            ▼   p(path) = product of Decider's probabilities
   (+ none of these)              ...   best-first: always expand the most probable partial path
                                     │
                                     ▼
                                   LEAF ──► route on p(path)
```

### Typed questions (one Decider call per fork)

| Name | Type | When | Question |
|---|---|---|---|
| `child` | `choice` (2 to 255 options, plus `none_of_these` below the top) | every fork | Which option describes the item? |
| `enough` | `noul` | interactive use, at the fork where the top two candidates split | Do the facts state everything needed to choose here? |
| `missing` | `choice` over named facts (material, user, function...) | same | Which single missing fact would settle it? |

Options are neutral letters (`A`, `B`, ... `AA`), described with the tree's own wording, so the
model chooses on meaning, never on a code it might have memorised.

### Routing table (plain code, no LLM)

| Signal | Action |
|---|---|
| `p(best path) >= auto` | Act on Decider's answer: no LLM call, no human review. **Only once you have measured that this bar is safe for your domain.** It was for tool routing (17/17); it was not for tariff codes, where TariffTrail sets `auto` above 1. |
| shortlist hook is set | One LLM call chooses among the top *complete* paths (plus any extra candidate the hook adds, e.g. from retrieval), so it cannot invent an item. |
| `enough < 0.5` and someone can answer | Ask for exactly the `missing` fact, then search again. |
| A fork puts its mass on `none_of_these` | Its subtree becomes improbable, so the search resumes at the best alternative anywhere in the tree. |
| Seeded shortcut answered `none_of_these` | Its mass goes to the full walk from the root. |
| Out of budget | Return the best path found, flagged for review. |

## Why path probability

Every fork's distribution sums to one, so multiplying along a path gives a probability that can
be **compared across the whole tree**. This gives two things a step-by-step walk does not:

1. **Backtracking for free.** A wrong turn shows up as "none of these" at the next fork. The
   search then picks up the best remaining option, even three levels up, without a hand-written
   backtracking rule. (Our first version backtracked to the most recent fork only and sent a
   cable through *Toys* and then *Furniture*.)
2. **One number to test as "safe to act".** Path probability is the candidate signal, and the
   threshold sweep in [`eval/report.py`](eval/report.py) shows what each bar would buy. Measure it
   before trusting it: over a short tool catalog (2 levels, 24 test requests) every request above the
   bar was right;
   over the 8-level tariff tree it was only modestly predictive (AUROC 0.63 on 332 test rulings),
   so TariffTrail uses agreement between independent sources to order a human review queue instead.

## How to tune it

1. Label 50+ cases from your domain.
2. Run once with the auto bar above 1, so every case records both Decider's best path and the LLM's
   shortlist pick: `eval/run_eval.py --system tariff_trail`.
3. Read the threshold sweep and the signal report (`eval/signals.py`), and choose the lowest bar whose
   auto-cleared cases meet your error tolerance. If nothing does, auto-clear nothing. That was
   TariffTrail's pre-registered rule and its outcome on tariffs.
4. Freeze it, then measure once on held-out cases.

## How to reuse it

```python
from tariff_trail.decider import Decider
from tariff_trail.tree_descent import CalibratedTreeDescent, DictTree, Policy

tree = DictTree({"name": "tools", "children": [
    {"name": "slack", "description": "team chat", "children": [
        {"name": "post_channel_message", "description": "post to a channel"},
        {"name": "send_direct_message", "description": "message one person privately"}]},
    {"name": "github", "description": "code hosting", "children": [...]},
]})
result = CalibratedTreeDescent(tree, Decider(), policy=Policy(auto=0.6)).descend("Ping Priya privately")
result.leaf, result.p, result.auto        # chosen tool, its path probability, and whether to call it unasked
```

For a large tree, implement the `Tree` protocol (`root_id` plus four methods: `child_ids`, `option_text`,
`path_text`, `is_terminal`) over your own data, as [`tariff_trail/hts/tree.py`](tariff_trail/hts/tree.py)
does for the HTS. Optional hooks:

- `seed(tree, facts) -> [node ids]` proposes a few likely mid-level nodes, for example from
  retrieval over past decisions.
- `on_shortlist(tree, [(leaf, p)], facts) -> leaf` lets an LLM choose among the top complete paths.
- `on_missing(tree, node, fact, description, facts) -> text | None` asks a person or a tool for a fact.

## Wiring it into any Strands agent

[`tariff_trail/strands_kit.py`](tariff_trail/strands_kit.py) packages the agent side for any tree:

```python
from strands import Agent
from tariff_trail.strands_kit import DecisionGate, DecisionLedger, decision_tool

descent = CalibratedTreeDescent(tree, Decider(), policy=Policy(auto=0.6))
ledger = DecisionLedger()
agent = Agent(
    tools=[decision_tool(descent, ledger, name="choose_tool"), run_tool],
    interventions=[DecisionGate(descent, ledger, guarded={"run_tool": "tool_id"}, decide_tool="choose_tool")],
)
```

| Before a guarded tool call | Strands action |
|---|---|
| The argument is not a leaf of the tree | `Deny` |
| The descent did not choose it in this session | `Guide` ("decide first") |
| Its path probability is below `Policy.auto` | `Confirm`: Strands pauses the agent until a person answers |
| Otherwise | `Proceed` |

The decision tool tells the LLM what was chosen but not whether it is safe to act on. That is
deliberate: when it did, Nova Pro sometimes asked the user itself and sometimes would not have, so
the policy depended on the model. With the gate, it is plain code and the threshold you measured.
Recorded runs of both paths: [`examples/tool_catalog/README.md`](examples/tool_catalog/README.md).

## Guarding the action: `ClassificationGate`

The decision is only half of the pattern. The other half is what the agent may *do* with it.
[`tariff_trail/gate.py`](tariff_trail/gate.py) is TariffTrail's domain version of `DecisionGate`, a Strands
`InterventionHandler` on the tool that has consequences (here `file_entry`):

| Check | Strands action |
|---|---|
| Code is not a real line | `Deny` |
| Code did not come from the classifier in this session | `Guide` ("classify it first") |
| Decider `noul`: the filing describes different goods from what was classified | `Guide` |
| Path probability below the auto bar (always, for tariffs) | `Confirm`: a licensed broker approves; fast-track wording when Decider, Bedrock and past rulings agree, heading-agreed wording when they share only the 4-digit heading |
| Otherwise | `Proceed` |
