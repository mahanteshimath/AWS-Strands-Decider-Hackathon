"""Limits for a public deployment of the demo API (TT_PUBLIC=1).

A hosted run spends the shared hosted-Decider quota (10 requests a minute, 2,000 decisions a month)
and a Bedrock call, so a stranger should not be able to burn it all. State is in memory, so on a
serverless host the limits apply per warm instance; the platform's reserved concurrency is the
global ceiling.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from collections.abc import Callable


class RunGuard:
    def __init__(self, per_hour: int = 6, concurrent: int = 2, clock: Callable[[], float] = time.time) -> None:
        self.per_hour, self.concurrent, self._clock = per_hour, concurrent, clock
        self._seen: dict[str, deque[float]] = defaultdict(deque)
        self._running = 0
        self._lock = threading.Lock()

    def acquire(self, who: str) -> str | None:
        """None when the run may start (call release() afterwards), else the reason it may not."""
        with self._lock:
            now = self._clock()
            stamps = self._seen[who]
            while stamps and now - stamps[0] >= 3600:
                stamps.popleft()
            if self._running >= self.concurrent:
                return "The hosted Decider is busy with other visitors' runs. Try again in a minute, or press Simulate."
            if len(stamps) >= self.per_hour:
                wait = int((3600 - (now - stamps[0])) // 60) + 1
                return (f"Hosted runs are limited to {self.per_hour} an hour per visitor to protect the free-tier quota. "
                        f"Try again in about {wait} min, press Simulate, or replay a recorded run.")
            stamps.append(now)
            self._running += 1
            return None

    def release(self) -> None:
        with self._lock:
            self._running = max(0, self._running - 1)
