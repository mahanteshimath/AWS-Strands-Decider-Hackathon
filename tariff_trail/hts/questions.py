"""Tariff-specific wording for the Calibrated Tree Descent questions."""

from __future__ import annotations

from ..tree_descent import Wording

# The facts customs classification most often turns on. The decision model picks the one that
# would settle the current fork; the agent then asks the importer for exactly that fact.
MISSING_FACTS = {
    "material": "what it is made of, with percentages by weight of each material or fiber",
    "construction": "how it is made: knitted or crocheted versus woven, cast, forged, molded, assembled",
    "user": "who it is for: men, women, boys, girls, infants, unisex",
    "function": "its principal function or use, and how it works",
    "form": "its form or state: raw, processed, prepared, frozen, dried, in bulk or retail packing",
    "dimensions": "size, weight, thickness, width, length or capacity",
    "power": "how it is powered: electric, battery, motor rating, voltage",
    "composition": "chemical composition or ingredients and their proportions",
    "value": "unit value or price per item, per kilogram or per dozen",
    "set_or_part": "whether it is a complete article, a part, an accessory, or a set of items",
    "nothing": "nothing is missing; the facts already settle the choice",
}

HTS_WORDING = Wording(
    child=(
        "Which tariff line in the list describes the product? Choose by the product's facts and the "
        "official wording of each line, at this level of the US Harmonized Tariff Schedule."
    ),
    none_text="None of these lines can describe the product; an earlier level was chosen wrongly",
    enough="Do the product facts state everything needed to choose between these tariff lines?",
    enough_true="the facts are enough to tell these tariff lines apart",
    enough_false="a fact needed to tell these tariff lines apart is missing or unclear",
    missing="Which single missing product fact would best settle the choice between these tariff lines?",
    missing_facts=MISSING_FACTS,
)


def hts_state(facts: str, path: str) -> str:
    if not path:
        return f"PRODUCT FACTS:\n{facts}"
    return f"PRODUCT FACTS:\n{facts}\n\nCLASSIFIED SO FAR (official tariff wording):\n{path}"
