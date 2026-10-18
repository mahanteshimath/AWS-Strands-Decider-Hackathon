"""Small stdlib HTTP helpers shared by the data scripts (no third-party deps)."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request

USER_AGENT = "TariffTrail/0.1 (+https://github.com/mahanteshimath/AWS-Strands-Decider-Hackathon)"


def get(url: str, *, timeout: float = 60, retries: int = 4, backoff: float = 2.0) -> bytes:
    """GET a URL, retrying transient failures (network errors, 429, 5xx)."""
    last: Exception | None = None
    for attempt in range(retries):
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"})
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            if exc.code < 500 and exc.code != 429:
                raise
            last = exc
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last = exc
        time.sleep(backoff * (attempt + 1))
    raise RuntimeError(f"GET failed after {retries} tries: {url}: {last}")


def get_json(url: str, **kwargs):
    return json.loads(get(url, **kwargs))
