"""The hosted Strands Decider client: wire format, pacing, retries, errors and safe .env reading."""

from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tariff_trail import hosted
from tariff_trail.decider import DeciderUnavailable
from tariff_trail.env import env_value
from tariff_trail.hosted import HostedDecider, RateLimiter, with_confidence

CHOICE = {"child": {"type": "choice", "instructions": "pick", "criteria": {"A": "one", "B": "two", "C": "three"}}}


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


class Stub(BaseHTTPRequestHandler):
    seen: list[tuple[str, dict, dict]] = []
    script: list[tuple[int, dict, dict]] = []  # (status, body, extra headers), consumed per request

    def log_message(self, *args):  # silence
        pass

    def _reply(self, status: int, body: dict, headers: dict | None = None) -> None:
        data = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("content-type", "application/json")
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.send_header("content-length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        length = int(self.headers.get("content-length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        Stub.seen.append((self.path, {k.lower(): v for k, v in self.headers.items()}, body))
        status, payload, headers = Stub.script.pop(0) if Stub.script else (200, ANSWER, {})
        self._reply(status, payload, headers)

    def do_GET(self):
        Stub.seen.append((self.path, dict(self.headers), {}))
        self._reply(200, {"data": [{"id": "strands-decider-2b-hobson-v19", "ready": True}]})


ANSWER = {"answers": {"child": {"type": "choice", "choice": "B", "probabilities": {"A": 0.1, "B": 0.7, "C": 0.2}}},
          "usage": {"input_tokens": 12}, "latency_ms": 5}


@pytest.fixture()
def server():
    Stub.seen, Stub.script = [], []
    hosted._QUOTA["out_at"] = 0.0
    httpd = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}"
    httpd.shutdown()
    hosted._QUOTA["out_at"] = 0.0


def make(url: str, **kw) -> HostedDecider:
    clock = FakeClock()
    return HostedDecider(url, "dcd_test_key", limiter=RateLimiter(clock=clock, sleep=clock.sleep), sleep=lambda s: None, **kw)


def test_posts_to_v1_decide_with_bearer_key_and_no_model_field(server):
    answers = make(server).ask("state text", CHOICE)
    path, headers, body = Stub.seen[-1]
    assert path == "/v1/decide"
    assert headers["authorization"] == "Bearer dcd_test_key"
    assert set(body) == {"state", "questions"}
    assert answers["child"]["choice"] == "B"


def test_confidence_is_derived_when_the_host_omits_it(server):
    answers = make(server).ask("s", CHOICE)
    # (N * pmax - 1) / (N - 1) with N=3, pmax=0.7 -> 0.55, the formula the local server uses
    assert answers["child"]["confidence"] == pytest.approx(0.55)
    kept = with_confidence({"x": {"type": "choice", "probabilities": {"a": 0.5, "b": 0.5}, "confidence": 0.9}})
    assert kept["x"]["confidence"] == 0.9
    assert with_confidence({"n": {"type": "noul", "noul": 0.8}})["n"].get("confidence") is None


def test_stats_and_usage_are_counted(server):
    before = hosted.usage()
    d = make(server)
    d.ask("s", CHOICE)
    assert d.stats.calls == 1 and d.stats.questions == 1 and d.stats.input_tokens == 12
    assert hosted.usage()["decisions"] == before["decisions"] + 1


def test_retries_a_rate_limit_then_succeeds(server):
    Stub.script = [(429, {"error": "slow down"}, {"Retry-After": "2"})]
    waits: list[float] = []
    d = make(server, on_wait=waits.append)
    assert d.ask("s", CHOICE)["child"]["choice"] == "B"
    assert len(Stub.seen) == 2
    assert waits, "the UI is told it is waiting"


def test_quota_and_bad_key_errors_are_plain_and_never_echo_the_key(server):
    Stub.script = [(402, {"error": "quota"}, {})]
    with pytest.raises(RuntimeError) as quota:
        make(server).ask("s", CHOICE)
    assert "monthly" in str(quota.value) and "402" in str(quota.value)
    Stub.script = [(401, {"error": "nope"}, {})]
    with pytest.raises(RuntimeError) as bad:
        make(server).ask("s", CHOICE)
    assert "key" in str(bad.value)
    assert "dcd_test_key" not in str(quota.value) + str(bad.value)


def test_a_used_up_quota_turns_the_hosted_button_off_with_a_plain_reason(server, monkeypatch):
    hosted._HEALTH.update(at=0.0, value=None, error=None)
    Stub.script = [(402, {"error": "quota"}, {})]
    with pytest.raises(RuntimeError) as quota:
        make(server).ask("s", CHOICE)
    assert "recorded runs" in str(quota.value) and "402" in str(quota.value)
    assert hosted.quota_out()
    with pytest.raises(DeciderUnavailable, match="used up"):
        make(server).health()
    monkeypatch.setattr(hosted, "hosted_key", lambda: "dcd_test_key")
    s = hosted.status()
    assert s["ready"] is False and "Simulate" in s["error"]
    assert hosted.quota_out(clock=lambda: hosted._QUOTA["out_at"] + hosted.QUOTA_RECHECK_S + 1) is False


def test_missing_key_and_unreachable_host_raise_decider_unavailable():
    with pytest.raises(DeciderUnavailable):
        HostedDecider("http://127.0.0.1:9", "").ask("s", CHOICE)
    with pytest.raises(DeciderUnavailable):
        make("http://127.0.0.1:9").ask("s", CHOICE)


def test_limiter_spaces_the_call_after_the_window_is_full():
    clock = FakeClock()
    limiter = RateLimiter(calls=3, window=60.0, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        limiter.acquire()
    assert clock.now == 0.0
    waits: list[float] = []
    limiter.acquire(waits.append)
    assert clock.now >= 60.0 and waits and waits[0] == pytest.approx(60.0)


def test_health_reads_the_model_list_and_status_needs_a_key(server, monkeypatch):
    hosted._HEALTH.update(at=0.0, value=None, error=None)
    h = make(server).health()
    assert h == {"ready": True, "model": "strands-decider-2b-hobson-v19"}
    monkeypatch.setattr(hosted, "hosted_key", lambda: "")
    assert hosted.status() is None


def test_env_value_reads_only_the_names_asked_for(tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("[hackathon]\naws_access_key_id = AKIAEXAMPLE\naws_strands_decider_key = dcd_abc  # note\n", encoding="utf-8")
    monkeypatch.delenv("aws_strands_decider_key", raising=False)
    monkeypatch.delenv("AWS_STRANDS_DECIDER_KEY", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    assert env_value("aws_strands_decider_key", path=env) == "dcd_abc"
    assert env_value("DECIDER_API_KEY", path=env, default="none") == "none"
    import os
    assert "AWS_ACCESS_KEY_ID" not in os.environ, "reading .env must not export AWS credentials"
    monkeypatch.setenv("AWS_STRANDS_DECIDER_KEY", "from_env")
    assert env_value("aws_strands_decider_key", path=env) == "from_env"
