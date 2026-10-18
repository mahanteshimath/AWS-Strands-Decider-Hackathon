"""Smoke-test the AWS side: Bedrock model resolution, one Converse call per role, one embedding,
and (if a tunnel is open) the Decider server on STRANDS_DECIDER_URL.

    AWS_PROFILE=hackathon python scripts/smoke.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tariff_trail import bedrock  # noqa: E402
from tariff_trail.decider import Decider, DeciderUnavailable, choice, noul  # noqa: E402


def main() -> int:
    ok = True
    for role in ("fast", "reasoner"):
        try:
            model = bedrock.model_for(role)
            reply = bedrock.converse("Reply with exactly: OK", role=role, max_tokens=16)
            print(f"bedrock {role:8} {model}: {reply.text.strip()!r} ({reply.input_tokens} in / {reply.output_tokens} out, {reply.latency_ms:.0f} ms)")
        except Exception as exc:  # report and keep checking the rest
            ok = False
            print(f"bedrock {role:8} FAILED: {exc}")
    try:
        vector = bedrock.embed("women's knitted sweater, 44% polyamide, 21% alpaca")
        print(f"embed    {bedrock.EMBED_MODEL}: {len(vector)} dims")
    except Exception as exc:
        ok = False
        print(f"embed FAILED: {exc}")

    decider = Decider()
    try:
        health = decider.health()
        answers = decider.ask(
            "A women's pullover, knitted, 44% polyamide, 21% alpaca, 21% wool, 14% metallic yarn.",
            {
                "kind": choice("Which kind of article is this?", {"A": "Knitted or crocheted apparel", "B": "Woven apparel", "C": "Footwear"}),
                "for_women": noul("Is the article for women or girls?"),
            },
        )
        print(f"decider  {health.get('checkpoint')} on {health.get('device')}: {answers}")
        print(f"decider  latency {decider.stats.latencies_ms[-1]:.0f} ms (wall, incl. tunnel)")
    except DeciderUnavailable as exc:
        print(f"decider  not reachable ({exc}); start infra/tunnel.ps1 once the GPU host is up")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
