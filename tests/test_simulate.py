"""The demo's simulated mode: the real search over the real HTS tree, with a keyword stand-in for Decider."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(not Path("data/raw/hts_full.json").exists(), reason="run data/fetch_hts.py first")


@pytest.fixture(scope="module")
def sim():
    from tariff_trail.hts.tree import load
    from tariff_trail.simulate import Simulator

    return Simulator(load())


def test_simulated_run_reaches_a_real_code_and_streams_forks(sim):
    events = []
    run = sim.run("Plush stuffed toy shaped like a dinosaur, polyester shell and stuffing, for children",
                  observe=events.append, seed=1)
    assert run.result.status == "done"
    assert sim.tree.is_terminal(run.result.leaf) and sim.tree.exists(run.code)
    assert run.forks == len(events) >= 2
    for event in events:
        assert abs(sum(event["probs"].values()) - 1) < 1e-6


def test_same_seed_same_route(sim):
    facts = "Polished granite slabs, cut and polished on one face, for kitchen countertops"
    a, b = sim.run(facts, seed=42), sim.run(facts, seed=42)
    assert a.code == b.code and a.result.path == b.result.path
