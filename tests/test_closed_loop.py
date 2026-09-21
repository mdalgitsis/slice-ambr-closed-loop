"""Loop behaviour, with the core stubbed out.

These cover the decisions the loop itself makes -- when to reconfigure, and
what it does when the core is unreachable -- independently of any policy.
"""

import pytest

from agents import ProportionalFairAgent
from simulator import closed_loop, core_client


@pytest.fixture(autouse=True)
def _no_core(monkeypatch):
    """The core is unreachable unless a test says otherwise."""
    monkeypatch.setattr(core_client, "fetch_all", lambda _map: {})


@pytest.fixture
def loop(monkeypatch):
    monkeypatch.setenv("SLICE_PROFILE_MAP", "0=6,1=7")
    import importlib

    from simulator import config

    importlib.reload(config)
    importlib.reload(closed_loop)
    return closed_loop


def make_loop(module, threshold):
    import importlib

    from simulator import config

    module.config = importlib.reload(config)
    instance = module.SliceReconfigurationLoop(ProportionalFairAgent(seed=3))
    instance.threshold = threshold
    return instance


def test_rejects_a_profile_map_missing_a_slice(loop, monkeypatch):
    monkeypatch.setenv("SLICE_PROFILE_MAP", "0=6")
    import importlib

    from simulator import config

    loop.config = importlib.reload(config)
    with pytest.raises(ValueError, match="no core profile"):
        loop.SliceReconfigurationLoop(ProportionalFairAgent())


def test_no_reconfiguration_above_threshold(loop):
    instance = make_loop(loop, threshold=0.0)
    demand = {0: [10.0], 1: [10.0]}
    current = {0: [50.0], 1: [50.0]}
    triggered, new, _action = instance.adjust_ambr(None, demand, current)
    assert triggered is False
    assert {k: v[0] for k, v in new.items()} == {0: 50.0, 1: 50.0}
    assert instance.reconfigurations == 0


def test_reconfiguration_below_threshold(loop):
    instance = make_loop(loop, threshold=1.01)
    demand = {0: [90.0], 1: [5.0]}
    current = {0: [50.0], 1: [50.0]}
    triggered, new, action = instance.adjust_ambr(None, demand, current)
    assert triggered is True
    assert instance.reconfigurations == 1
    improved = instance.agent.calculate_performance_metrics(action, demand)[-1]
    assert improved > 0.9


def test_loop_runs_bounded_and_survives_an_unreachable_core(loop):
    instance = make_loop(loop, threshold=0.8)
    instance.run(interval=0, max_iterations=5)
    from simulator import metrics

    assert metrics.iteration._value.get() == 5


def test_unreachable_core_does_not_stop_the_loop(loop, monkeypatch):
    calls = []

    def boom(_map):
        calls.append(1)
        return {}

    monkeypatch.setattr(core_client, "fetch_all", boom)
    instance = make_loop(loop, threshold=0.8)
    instance.run(interval=0, max_iterations=3)
    assert len(calls) == 3
