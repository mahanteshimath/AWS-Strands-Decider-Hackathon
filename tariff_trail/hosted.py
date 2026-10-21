"""A Strands Decider hosted by the AWS User Group Madurai, behind the same `.ask()` as the local client.

    from tariff_trail.hosted import HostedDecider
    TariffTrail(decider=HostedDecider())      # key from `aws_strands_decider_key` / DECIDER_API_KEY in .env

The wire format differs from a local `strands-decider serve`: `POST /v1/decide` with
`Authorization: Bearer <key>`. The free tier allows 10 requests a minute, 4 questions per request
and 2,000 decisions a month, so calls are paced by a limiter shared across every request in the
process, and the model is a hosted build of strands-decider-2B, not the local `v1-2610` the evaluation was run on.
"""

from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from collections import deque
from collections.abc import Callable, Mapping
from typing import Any

from .decider import Decider, DeciderUnavailable
from .env import env_value

HOSTED_URL = "https://da25tnxy06gjk.cloudfront.net"
HOSTED_MODEL = "strands-decider-2b-hobson-v19"
CALLS_PER_WINDOW = 9  # the free tier says 10 a minute; keep one call of headroom
WINDOW_S = 60.0
MONTHLY_FREE_DECISIONS = 2000
MAX_RETRIES = 3
HEALTH_TTL_S = 60.0
QUOTA_RECHECK_S = 3600.0  # after a 402, report the hosted button as unavailable for an hour
QUOTA_MESSAGE = ("The hosted Decider's free monthly quota (2,000 decisions, shared by every visitor) is used up (402). "
                 "The 392 recorded runs and Simulate still work.")

_HINTS = {
    401: "check the hosted Decider key (aws_strands_decider_key / DECIDER_API_KEY in .env)",
    402: "the monthly free quota is used up",
    429: "rate limited",
    503: "server busy",
}


def hosted_key() -> str:
    return env_value("aws_strands_decider_key", "DECIDER_API_KEY", "HOSTED_DECIDER_KEY")


def hosted_url() -> str:
    return env_value("HOSTED_DECIDER_URL", default=HOSTED_URL).rstrip("/")


class RateLimiter:
    """At most `calls` per sliding `window` seconds, shared by every thread that holds this object."""

    def __init__(self, calls: int = CALLS_PER_WINDOW, window: float = WINDOW_S,
                 clock: Callable[[], float] = time.monotonic, sleep: Callable[[float], None] = time.sleep) -> None:
        self.calls, self.window, self._clock, self._sleep = calls, window, clock, sleep
        self._stamps: deque[float] = deque()
        self._lock = threading.Lock()

    def acquire(self, on_wait: Callable[[float], None] | None = None) -> None:
        while True:
            with self._lock:
                now = self._clock()
                while self._stamps and now - self._stamps[0] >= self.window:
                    self._stamps.popleft()
                if len(self._stamps) < self.calls:
                    self._stamps.append(now)
                    return
                wait = self.window - (now - self._stamps[0])
            if on_wait:
                on_wait(wait)
            self._sleep(min(max(wait, 0.05), 1.0))


_LIMITER = RateLimiter()
_USAGE_LOCK = threading.Lock()
_USED = {"decisions": 0, "calls": 0}
_HEALTH: dict[str, Any] = {"at": 0.0, "value": None, "error": None}
_QUOTA: dict[str, float] = {"out_at": 0.0}


def quota_out(clock: Callable[[], float] = time.monotonic) -> bool:
    """True if the host answered 402 (monthly quota used up) within the last QUOTA_RECHECK_S."""
    return bool(_QUOTA["out_at"]) and clock() - _QUOTA["out_at"] < QUOTA_RECHECK_S


def usage() -> dict[str, int]:
    """Hosted decisions sent by this process so far (a question is a decision)."""
    with _USAGE_LOCK:
        return dict(_USED)


def with_confidence(answers: dict[str, Any]) -> dict[str, Any]:
    """The tree search reads `confidence`; fill it in from the probabilities if the host did not."""
    for ans in answers.values():
        probs = ans.get("probabilities") if isinstance(ans, dict) else None
        if probs and ans.get("type") in ("choice", "score") and "confidence" not in ans:
            n, top = len(probs), max(float(v) for v in probs.values())
            ans["confidence"] = (n * top - 1) / (n - 1) if n > 1 else 1.0
    return answers


class HostedDecider(Decider):
    def __init__(self, url: str | None = None, api_key: str | None = None, timeout: float = 120.0, *,
                 on_wait: Callable[[float], None] | None = None, limiter: RateLimiter | None = None,
                 sleep: Callable[[float], None] = time.sleep) -> None:
        super().__init__(url or hosted_url(), timeout)
        self.api_key = api_key if api_key is not None else hosted_key()
        self.on_wait = on_wait
        self.limiter = limiter or _LIMITER
        self._sleep = sleep

    def _headers(self) -> dict[str, str]:
        return {"content-type": "application/json", "authorization": f"Bearer {self.api_key}",
                "user-agent": "TariffTrail/1.0"}

    def _pause(self, seconds: float) -> None:
        left = seconds
        while left > 0:
            if self.on_wait:
                self.on_wait(left)
            step = min(left, 1.0)
            self._sleep(step)
            left -= step

    def ask(self, state: Any, questions: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
        if not self.api_key:
            raise DeciderUnavailable("no hosted Decider key: set aws_strands_decider_key (or DECIDER_API_KEY) in .env")
        body = json.dumps({"state": state, "questions": dict(questions)}).encode()
        attempt = 0
        while True:
            self.limiter.acquire(self.on_wait)
            request = urllib.request.Request(f"{self.url}/v1/decide", data=body, headers=self._headers(), method="POST")
            started = time.perf_counter()
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    payload = json.loads(response.read())
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read()[:300].decode(errors="replace")
                if exc.code in (429, 503) and attempt < MAX_RETRIES:
                    attempt += 1
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    self._pause(float(retry_after) if retry_after and retry_after.replace(".", "", 1).isdigit() else 10.0 * attempt)
                    continue
                if exc.code == 402:
                    _QUOTA["out_at"] = time.monotonic()
                    raise RuntimeError(QUOTA_MESSAGE) from None
                hint = _HINTS.get(exc.code, "")
                raise RuntimeError(f"hosted decider rejected the request: {exc.code} {hint} {detail}".strip()) from None
            except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
                raise DeciderUnavailable(f"no hosted decider at {self.url}: {exc}") from None
        wall = (time.perf_counter() - started) * 1000
        self.stats.calls += 1
        self.stats.questions += len(questions)
        self.stats.input_tokens += payload.get("usage", {}).get("input_tokens", 0)
        self.stats.server_ms += payload.get("latency_ms") or 0.0
        self.stats.wall_ms += wall
        self.stats.latencies_ms.append(wall)
        with _USAGE_LOCK:
            _USED["calls"] += 1
            _USED["decisions"] += len(questions)
        return with_confidence(payload["answers"])

    def health(self) -> dict[str, Any]:
        """`{ready, model}` from GET /v1/models, cached so a polling page does not spend requests."""
        if quota_out():
            raise DeciderUnavailable(QUOTA_MESSAGE)
        now = time.monotonic()
        if _HEALTH["at"] and now - _HEALTH["at"] < (HEALTH_TTL_S if _HEALTH["value"] else 10.0):
            if _HEALTH["value"]:
                return dict(_HEALTH["value"])
            raise DeciderUnavailable(_HEALTH["error"])
        request = urllib.request.Request(f"{self.url}/v1/models", headers=self._headers())
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                models = json.loads(response.read()).get("data") or []
        except urllib.error.HTTPError as exc:
            error = f"hosted decider answered {exc.code} {_HINTS.get(exc.code, '')}".strip()
        except (urllib.error.URLError, TimeoutError, ConnectionError, ValueError) as exc:
            error = f"no hosted decider at {self.url}: {exc}"
        else:
            first = models[0] if models else {}
            value = {"ready": bool(first.get("ready", True)), "model": first.get("id", HOSTED_MODEL)}
            _HEALTH.update(at=now, value=value, error=None)
            return dict(value)
        _HEALTH.update(at=now, value=None, error=error)
        raise DeciderUnavailable(error)


def status() -> dict[str, Any] | None:
    """What /api/health reports: None when no key is configured, otherwise readiness and usage."""
    if not hosted_key():
        return None
    used = usage()
    base = {"configured": True, "model": HOSTED_MODEL, "used_this_session": used["decisions"],
            "monthly_free": MONTHLY_FREE_DECISIONS, "per_minute": CALLS_PER_WINDOW + 1}
    try:
        return {**base, **HostedDecider().health()}
    except DeciderUnavailable as exc:
        return {**base, "ready": False, "error": str(exc)}
