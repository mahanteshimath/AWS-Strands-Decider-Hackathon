"""The tool-catalog router as a Strands agent: Decider picks the tool, a gate guards the call.

    python examples/tool_catalog/agent.py "Move PAY-311 to Done"
    python examples/tool_catalog/agent.py --yes "Note that I spoke with Jordan at Globex"   # auto-approve prompts

Needs a running Decider server (README, "Run it live") and Amazon Bedrock access. The agent never
sees the 48 tool schemas. It calls `choose_tool`, which walks the catalog with Calibrated Tree
Descent, then `run_tool` with the chosen id. `DecisionGate` (a Strands InterventionHandler) lets
that call through only if the descent chose the tool in this session with path probability >= 0.6;
below the bar Strands pauses the agent and a person answers yes or no.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))

from strands import Agent, tool  # noqa: E402
from strands.models import BedrockModel  # noqa: E402

from tariff_trail import bedrock  # noqa: E402
from tariff_trail.decider import Decider  # noqa: E402
from tariff_trail.strands_kit import DecisionGate, DecisionLedger, decision_tool  # noqa: E402
from tariff_trail.tree_descent import CalibratedTreeDescent, DictTree, Policy  # noqa: E402

from route import WORDING, state  # noqa: E402

SYSTEM = """You are an operations assistant with access to 48 workplace tools.
To act, first call choose_tool with the user's request, word for word; it returns the one tool id that handles it.
Then call run_tool with that tool id and the arguments in plain text. Do not ask the user for confirmation
yourself: the system asks them before any uncertain call runs. Never invent a tool id.
If a call is cancelled, tell the user why in one sentence."""


@tool
def run_tool(tool_id: str, arguments: str) -> str:
    """Run one tool of the catalog (simulated: returns what would have been called).

    Args:
        tool_id: the id returned by choose_tool, for example "jira/transition_ticket"
        arguments: the tool's arguments, in plain text
    """
    return json.dumps({"ran": tool_id, "arguments": arguments})


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--yes"]
    auto_yes = "--yes" in sys.argv
    request = " ".join(args) or "Move PAY-311 to Done"

    descent = CalibratedTreeDescent(DictTree(json.loads((HERE / "catalog.json").read_text(encoding="utf-8"))), Decider(),
                                    policy=Policy(auto=0.6), wording=WORDING, render_state=state)
    ledger = DecisionLedger()
    gate = DecisionGate(descent, ledger, guarded={"run_tool": "tool_id"}, decide_tool="choose_tool")
    agent = Agent(
        model=BedrockModel(model_id=bedrock.model_for("reasoner"), boto_session=bedrock.session(), temperature=0.0),
        tools=[decision_tool(descent, ledger, name="choose_tool"), run_tool],
        system_prompt=SYSTEM,
        interventions=[gate],
        callback_handler=None,
    )

    result = agent(request)
    while result.stop_reason == "interrupt":  # the gate asked a person to confirm
        responses = []
        for interrupt in result.interrupts:
            print(f"\n[confirm] {interrupt.reason}")
            answer = "yes" if auto_yes else input("> ")
            responses.append({"interruptResponse": {"interruptId": interrupt.id, "response": answer}})
        result = agent(responses)

    print(f"\n{result}")
    for leaf, decision in ledger.by_leaf.items():
        print(f"decision: {leaf}  p={decision.p:.2f}  {'safe to act' if decision.auto else 'needs a person'}  <- {decision.facts!r}")
    print("gate log:", json.dumps(gate.log, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
