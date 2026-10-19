"""Agreement between the three sources that name a code: Decider, Bedrock and the nearest past rulings.

Fast-track (all three name the same full code) is the frozen tier. Heading-agreed (all three name the
same 4-digit heading) was added after the test run, from eval/report.py: 34% of test products, 76% of
them right at the heading (82% on dev, which did not shape the rule). Exploratory, not preregistered.
"""

from __future__ import annotations


def agreed_heading(code: str | None, decider_code: str | None, precedent_code: str | None) -> str:
    """The 4-digit heading all three sources name, or "" when any is missing or they split."""
    codes = (code, decider_code, precedent_code)
    if not all(c and len(c) >= 4 for c in codes):
        return ""
    heads = {c[:4] for c in codes}
    return heads.pop() if len(heads) == 1 else ""
