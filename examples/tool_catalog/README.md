# Example: the same pattern routing 1 of 48 tools

The decision pattern from [`PATTERN.md`](../../PATTERN.md), pointed at a different tree: a catalog of
48 tools across 8 services (`catalog.json`: GitHub, Slack, Jira, Calendar, Gmail, S3, Salesforce,
PagerDuty). Same `CalibratedTreeDescent` class as TariffTrail; only the tree and the question
wording change. The agent never sees 48 tool schemas: Decider walks service, then tool.

| File | What it shows |
|---|---|
| [`route.py`](route.py) | The descent on its own, no LLM: 24 labelled requests, accuracy, and which calls cleared the bar |
| [`agent.py`](agent.py) | The full wiring in a Strands agent: `decision_tool` + `DecisionGate` from [`tariff_trail/strands_kit.py`](../../tariff_trail/strands_kit.py) |
| [`RESULTS.md`](RESULTS.md) | The recorded `route.py` run: 23 of 24 correct, all 17 calls above the bar right |

## Run it

Both need a Decider server on `127.0.0.1:8099` (see the main README, "Classify live"); `agent.py`
also needs Amazon Bedrock access.

```bash
python examples/tool_catalog/route.py                         # all 24 labelled requests
python examples/tool_catalog/route.py "ping Priya privately"
python examples/tool_catalog/agent.py "Move PAY-311 to Done"
python examples/tool_catalog/agent.py --yes "Push tomorrow's design review to Friday 3pm"
```

## The wiring

```python
descent = CalibratedTreeDescent(DictTree(catalog), Decider(), policy=Policy(auto=0.6))
ledger = DecisionLedger()
agent = Agent(
    model=BedrockModel(...),
    tools=[decision_tool(descent, ledger, name="choose_tool"), run_tool],
    interventions=[DecisionGate(descent, ledger, guarded={"run_tool": "tool_id"}, decide_tool="choose_tool")],
)
```

Before every `run_tool` call, `DecisionGate` (a Strands `InterventionHandler`) checks the `tool_id`
argument in plain code: not a tool in the catalog → **Deny**; not chosen by `choose_tool` in this
session → **Guide**; path probability below 0.6 → **Confirm** (Strands pauses the agent and a
person answers); otherwise **Proceed**. The tool's reply does not tell the LLM whether the call is
safe, so the policy holds whatever the model decides to do.

## Recorded agent runs

Laptop CPU Decider, Amazon Nova Pro, 2026-10-19.

Above the bar, the call goes straight through:

```
$ python examples/tool_catalog/agent.py "Move PAY-311 to Done"
Ticket PAY-311 has been successfully moved to the 'Done' status.

decision: jira/transition_ticket  p=0.72  safe to act  <- 'Move PAY-311 to Done'
gate log: [{"tool": "run_tool", "item": "jira/transition_ticket", "verdict": "proceed"}]
```

Below the bar, Strands pauses the agent until a person says yes (`--yes` answers for you):

```
$ python examples/tool_catalog/agent.py --yes "Push tomorrow's design review to Friday 3pm"
[confirm] Not sure enough to act on calendar/reschedule_event (probability 0.38, bar 0.60; alternatives: none). Go ahead? (yes/no)
The design review has been rescheduled to Friday at 3pm.

decision: calendar/reschedule_event  p=0.38  needs a person  <- "Push tomorrow's design review to Friday 3pm"
gate log: [{"tool": "run_tool", "item": "calendar/reschedule_event", "verdict": "confirm: p=0.38"}]
```

An earlier version of the tool told the model `safe_to_act: false`. Nova Pro then asked the user on
its own and never called `run_tool`, which looks safe but leaves the policy to the model. The tool
now reports only the choice, and the gate enforces the bar.
