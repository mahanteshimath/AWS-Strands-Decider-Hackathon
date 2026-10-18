"""Report which Bedrock text models this account can actually invoke (one 5-token call each).

    AWS_PROFILE=hackathon python scripts/probe_models.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tariff_trail import bedrock  # noqa: E402


def main() -> None:
    seen = set()
    for role in ("reasoner", "fast"):
        for model_id in bedrock.candidates_for(role):
            if model_id in seen or not model_id.startswith(("us.", "global.", "anthropic.", "amazon.")):
                continue
            seen.add(model_id)
            status = "OK  " if bedrock._callable(model_id) else "deny"
            print(f"{status} {role:8} {model_id}", flush=True)


if __name__ == "__main__":
    main()
