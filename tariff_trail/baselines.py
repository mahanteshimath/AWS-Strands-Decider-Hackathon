"""LLM baselines for the evaluation, on the same Bedrock reasoner model TariffTrail escalates to.

  llm_direct  one Converse call: "give the 10-digit HTSUS code"
  llm_agent   a Strands agent with two tools over the same HTS data (keyword search, list the lines
              under a code), the way most teams would build a classification agent today
"""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any

from . import bedrock
from .hts.tree import HTSTree, digits, load

DIRECT_PROMPT = """Classify this product under the Harmonized Tariff Schedule of the United States (HTSUS).

Product facts:
{facts}

Reply with JSON only: {{"code": "<10-digit HTSUS statistical number, digits only>", "reason": "<one sentence>"}}"""

AGENT_SYSTEM = (
    "You are a licensed US customs broker. Classify the product under the Harmonized Tariff Schedule of "
    "the United States (HTSUS) to the full 10-digit statistical number. Use the tools to find candidate "
    "headings and to read the lines under a heading or subheading before you decide; do not guess codes "
    "you have not seen in a tool result. Finish with JSON only: "
    '{"code": "<10 digits>", "reason": "<one sentence>"}'
)


@dataclass
class BaselineAnswer:
    code: str
    reason: str
    valid: bool
    llm_calls: int
    llm_input_tokens: int
    llm_output_tokens: int
    wall_ms: float
    tool_calls: int = 0
    raw: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _parse_code(text: str) -> tuple[str, str]:
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group(0))
            return digits(str(data.get("code", ""))), str(data.get("reason", ""))
        except json.JSONDecodeError:
            pass
    codes = re.findall(r"\b\d{4}\.\d{2}\.\d{2}\.?\d{0,2}\b|\b\d{10}\b", text)
    return (digits(codes[-1]) if codes else ""), ""


def llm_direct(facts: str, tree: HTSTree | None = None) -> BaselineAnswer:
    tree = tree or load()
    usage = bedrock.Usage()
    started = time.perf_counter()
    reply = bedrock.converse(DIRECT_PROMPT.format(facts=facts), role="reasoner", max_tokens=300, usage=usage)
    code, reason = _parse_code(reply.text)
    return BaselineAnswer(code, reason, tree.exists(code), usage.calls, usage.input_tokens, usage.output_tokens,
                          (time.perf_counter() - started) * 1000, raw=reply.text[:500])


def _search(tree: HTSTree, query: str, limit: int = 15) -> list[dict]:
    words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 2]
    if not words:
        return []
    scored = []
    for node in tree.nodes.values():
        if node.kind not in ("heading", "line") or not node.code:
            continue
        text = node.text.lower()
        hits = sum(1 for w in words if w in text)
        if hits:
            scored.append((hits, -len(node.code), node))
    scored.sort(key=lambda t: (t[0], t[1]), reverse=True)
    return [{"code": n.htsno, "description": tree.path_text(n.id).splitlines()[-1]} for _, _, n in scored[:limit]]


def _children(tree: HTSTree, code: str) -> list[dict]:
    node_id = tree.by_code.get(digits(code))
    if not node_id:
        return [{"error": f"no HTS line {code}"}]
    out = []

    def walk(nid: str, depth: int) -> None:
        for child in tree.children(nid):
            out.append({"code": child.htsno or "(group)", "indent": depth, "description": child.text})
            if not child.code or len(out) < 40:
                if child.children and depth < 3:
                    walk(child.id, depth + 1)

    walk(node_id, 0)
    return out[:60]


def llm_agent(facts: str, tree: HTSTree | None = None, max_tool_calls: int = 8, max_model_calls: int = 12) -> BaselineAnswer:
    """A Strands agent with HTS search tools. Hard-capped: an uncapped run once looped 201 tool calls."""
    from strands import Agent, tool
    from strands.interventions import Deny, InterventionHandler, Proceed
    from strands.models import BedrockModel

    tree = tree or load()
    calls = {"n": 0, "model": 0}
    exhausted = json.dumps({"error": "tool budget exhausted; reply now with your best final JSON answer"})

    class Budget(InterventionHandler):
        name = "baseline-budget"

        def before_model_call(self, event, **kwargs):
            calls["model"] += 1
            if calls["model"] > max_model_calls:
                return Deny(reason="model-call budget exhausted")
            return Proceed()

    @tool
    def search_hts(query: str) -> str:
        """Keyword search over HTSUS lines. Returns up to 15 matching codes with their official wording.

        Args:
            query: words describing the product, e.g. "knitted sweater wool women"
        """
        calls["n"] += 1
        if calls["n"] > max_tool_calls:
            return exhausted
        return json.dumps(_search(tree, query))

    @tool
    def list_lines(code: str) -> str:
        """List the official lines under an HTSUS heading or subheading (4, 6 or 8 digits), indented.

        Args:
            code: an HTSUS heading or subheading, e.g. "6110" or "6110.90"
        """
        calls["n"] += 1
        if calls["n"] > max_tool_calls:
            return exhausted
        return json.dumps(_children(tree, code))

    model = BedrockModel(model_id=bedrock.model_for("reasoner"), boto_session=bedrock.session(), temperature=0.0)
    agent = Agent(model=model, tools=[search_hts, list_lines], system_prompt=AGENT_SYSTEM, callback_handler=None,
                  interventions=[Budget()])
    started = time.perf_counter()
    try:
        result = agent(f"Product facts:\n{facts}")
        text = str(result)
    except Exception as exc:  # a failed run counts as no answer
        text = f"error: {exc}"
    wall = (time.perf_counter() - started) * 1000
    metrics = getattr(agent, "event_loop_metrics", None)
    usage = getattr(metrics, "accumulated_usage", {}) or {}
    cycles = getattr(metrics, "cycle_count", 0) or 0
    code, reason = _parse_code(text)
    return BaselineAnswer(
        code, reason, tree.exists(code), int(cycles), int(usage.get("inputTokens", 0)), int(usage.get("outputTokens", 0)),
        wall, tool_calls=calls["n"], raw=text[:500],
    )
