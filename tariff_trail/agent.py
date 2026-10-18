"""The TariffTrail Strands agent: classify goods, look up duty, and file an entry behind a gate.

    python -m tariff_trail.agent "We import women's knitted pullovers, 44% polyamide, 21% alpaca ..."

The LLM (Amazon Bedrock) runs the conversation and writes the explanation. The tariff decisions
are made by Strands Decider walking the HTS tree (`classify_product`); the LLM only adjudicates
the forks Decider is unsure about. Filing goes through `ClassificationGate`.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from strands import Agent, tool
from strands.models import BedrockModel

from . import bedrock
from .baselines import _children
from .classify import TariffTrail
from .decider import Decider
from .gate import ClassificationGate, Ledger
from .hts.tree import digits, load

ENTRIES = Path(__file__).resolve().parents[1] / "data" / "entries.jsonl"

SYSTEM = """You are TariffTrail, a customs classification assistant for importers shipping into the United States.

Rules:
- Never state a tariff code yourself. Always call classify_product with the importer's description and use its result.
- If classify_product returns status "needs_info", ask the importer exactly that question, then call classify_product
  again with the original description plus the answer.
- Explain the result briefly: the code, the path of official wording that led to it, and whether it was auto-cleared
  (every decision confident) or needs broker review (and which decision was uncertain).
- Only call file_entry when the importer asks to file, using the code from classify_product.
This is decision support, not legal advice; a licensed customs broker is responsible for the final entry."""


def build_agent(*, decider: Decider | None = None, ledger: Ledger | None = None, callback_handler=None) -> tuple[Agent, Ledger, ClassificationGate]:
    tree = load()
    decider = decider or Decider()
    ledger = ledger or Ledger()
    trail = TariffTrail(tree=tree, decider=decider)

    @tool
    def classify_product(description: str) -> str:
        """Classify a product into its 10-digit US HTS code by walking the official tariff tree.

        Args:
            description: the importer's product description: what it is, materials with percentages,
                how it is made, who it is for, its function, and anything else known.
        """
        result = trail.classify(description)
        ledger.record(result)
        return json.dumps({
            "status": result.status,
            "hts_code": result.htsno,
            "auto_cleared": result.auto,
            "decided_by": result.route,
            "path_probability": round(result.p, 3),
            "path": result.path_text,
            "general_duty": result.duty,
            "alternatives": [c["htsno"] for c in result.candidates if c["code"] != result.code][:2],
            "uncertain_decisions": [
                {"at": s["node_label"], "options": [t["label"] for t in s["top"][:3]], "p_chosen": s["p"]}
                for s in result.steps if s["route"] == "uncertain"
            ],
            "adjudicator_reasons": [a["reason"] for a in result.adjudications],
            "question_for_importer": result.question and result.question["description"],
        })

    @tool
    def lookup_duty(hts_code: str) -> str:
        """Return the official wording and general (column 1) duty rate for an HTS code.

        Args:
            hts_code: a 4- to 10-digit HTS code
        """
        node_id = tree.by_code.get(digits(hts_code))
        if not node_id:
            return json.dumps({"error": f"{hts_code} is not in the current HTS"})
        duty = next((n.duty for n in reversed(tree.path(node_id)) if n.duty), "")
        return json.dumps({"hts_code": tree[node_id].htsno, "path": tree.path_text(node_id), "general_duty": duty,
                           "hts_release": tree.release.get("name")})

    @tool
    def list_lines(hts_code: str) -> str:
        """List the official lines under an HTS heading or subheading, to show the importer the alternatives.

        Args:
            hts_code: a 4-, 6- or 8-digit HTS code
        """
        return json.dumps(_children(tree, hts_code))

    @tool
    def file_entry(hts_code: str, description: str, value_usd: float, country_of_origin: str) -> str:
        """File the customs entry line for this product (simulated: appends to data/entries.jsonl).

        Args:
            hts_code: the 10-digit HTS code returned by classify_product
            description: plain goods description for the entry
            value_usd: declared customs value in US dollars
            country_of_origin: country of origin
        """
        record = {"hts_code": hts_code, "description": description, "value_usd": value_usd, "origin": country_of_origin}
        ENTRIES.parent.mkdir(parents=True, exist_ok=True)
        with ENTRIES.open("a", encoding="utf-8") as out:
            out.write(json.dumps(record) + "\n")
        ledger.filed.append(record)
        return json.dumps({"filed": True, **record})

    gate = ClassificationGate(tree, ledger, decider)
    model = BedrockModel(model_id=bedrock.model_for("reasoner"), boto_session=bedrock.session(), temperature=0.0)
    agent = Agent(
        model=model,
        tools=[classify_product, lookup_duty, list_lines, file_entry],
        system_prompt=SYSTEM,
        interventions=[gate],
        callback_handler=callback_handler,
    )
    return agent, ledger, gate


def main() -> int:
    prompt = " ".join(sys.argv[1:]) or (
        "Please classify and file: women's knitted V-neck pullover, 44% polyamide, 21% alpaca, 21% wool, "
        "14% metallic yarn, raglan sleeves, value $18.50, made in China."
    )
    agent, ledger, gate = build_agent()
    print(agent(prompt))
    print("\ngate log:", json.dumps(gate.log, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
