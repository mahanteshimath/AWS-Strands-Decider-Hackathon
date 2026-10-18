"""A small synchronous client for a Strands Decider server (`strands-decider serve`).

`urllib` on purpose, so the pattern files in this package need no HTTP library. One state,
many typed questions, one round trip: the server encodes the state once and shares it across
the questions, so ask everything a step needs in the same call.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

DEFAULT_URL = os.environ.get("STRANDS_DECIDER_URL", "http://127.0.0.1:8099")


class DeciderUnavailable(RuntimeError):
    """Nothing is answering at the configured URL."""


def noul(instructions: str, criteria: Mapping[str, str] | None = None) -> dict[str, Any]:
    """Yes/no question; the answer is P(true)."""
    question: dict[str, Any] = {"type": "noul", "instructions": instructions}
    if criteria:
        question["criteria"] = dict(criteria)
    return question


def choice(instructions: str, criteria: Mapping[str, str | None]) -> dict[str, Any]:
    """Pick one of N named options; `criteria` maps option name -> what it means."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    """Rate on an ordered rubric, lowest level first."""
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


@dataclass
class DeciderStats:
    calls: int = 0
    questions: int = 0
    input_tokens: int = 0
    server_ms: float = 0.0
    wall_ms: float = 0.0
    latencies_ms: list[float] = field(default_factory=list)


class Decider:
    def __init__(self, url: str = DEFAULT_URL, timeout: float = 120.0) -> None:
        self.url = url.rstrip("/")
        self.timeout = timeout
        self.stats = DeciderStats()

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        """Evaluate `state` against `questions`; answers come back under the same keys."""
        body = json.dumps({"state": state, "model": "strands-decider-latest", "questions": dict(questions)}).encode()
        request = urllib.request.Request(
            f"{self.url}/v1/systemone", data=body, headers={"content-type": "application/json"}
        )
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"decider rejected the request: {exc.code} {exc.read()[:300]!r}") from exc
        except urllib.error.URLError as exc:
            raise DeciderUnavailable(f"no decider at {self.url}: {exc}") from exc
        wall = (time.perf_counter() - started) * 1000
        self.stats.calls += 1
        self.stats.questions += len(questions)
        self.stats.input_tokens += payload.get("usage", {}).get("input_tokens", 0)
        self.stats.server_ms += payload.get("latency_ms") or 0.0
        self.stats.wall_ms += wall
        self.stats.latencies_ms.append(wall)
        return payload["answers"]

    def health(self) -> dict[str, Any]:
        try:
            with urllib.request.urlopen(f"{self.url}/health", timeout=10) as response:
                return json.loads(response.read())
        except urllib.error.URLError as exc:
            raise DeciderUnavailable(f"no decider at {self.url}: {exc}") from exc
