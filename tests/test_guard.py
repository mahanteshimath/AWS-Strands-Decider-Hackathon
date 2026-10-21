"""The public-deployment run guard: per-visitor hourly budget and a concurrency cap."""

from __future__ import annotations

from tariff_trail.web.guard import RunGuard


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_allows_up_to_the_hourly_budget_then_says_when_to_come_back():
    clock = Clock()
    guard = RunGuard(per_hour=2, concurrent=5, clock=clock)
    assert guard.acquire("a") is None
    guard.release()
    assert guard.acquire("a") is None
    guard.release()
    refusal = guard.acquire("a")
    assert refusal and "2 an hour" in refusal and "Simulate" in refusal
    assert guard.acquire("b") is None, "another visitor has their own budget"
    guard.release()
    clock.now += 3601
    assert guard.acquire("a") is None, "the hour rolls over"


def test_caps_concurrent_runs_and_frees_a_slot_on_release():
    guard = RunGuard(per_hour=10, concurrent=1, clock=Clock())
    assert guard.acquire("a") is None
    busy = guard.acquire("b")
    assert busy and "busy" in busy
    guard.release()
    assert guard.acquire("b") is None


def test_a_refused_run_does_not_use_budget():
    guard = RunGuard(per_hour=1, concurrent=1, clock=Clock())
    assert guard.acquire("a") is None
    assert guard.acquire("b") is not None  # refused: busy
    guard.release()
    assert guard.acquire("b") is None  # b still has its one run
