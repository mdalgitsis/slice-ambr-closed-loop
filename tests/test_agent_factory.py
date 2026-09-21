import pytest

from agents import ProportionalFairAgent
from simulator.agent_factory import load_agent


def test_loads_the_bundled_baseline_by_default(monkeypatch):
    monkeypatch.delenv("SLICE_AGENT", raising=False)
    assert isinstance(load_agent(), ProportionalFairAgent)


def test_explicit_spec_is_honoured():
    agent = load_agent("agents.static_baseline:ProportionalFairAgent")
    assert isinstance(agent, ProportionalFairAgent)


@pytest.mark.parametrize(
    "spec", ["nope.module:Missing", "agents.static_baseline:NotAClass", "garbage"]
)
def test_a_bad_spec_names_the_fix(spec):
    with pytest.raises(RuntimeError, match="SLICE_AGENT"):
        load_agent(spec)
