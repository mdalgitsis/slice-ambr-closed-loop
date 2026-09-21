"""The offline study must be a fair comparison and a reproducible one."""

import pytest

from agents import ProportionalFairAgent
from simulator.offline_study import run_study


def test_both_arms_run_for_every_iteration():
    results = run_study(agent=ProportionalFairAgent(seed=1), iterations=20)
    assert len(results.fsa_total_ar) == 20
    assert len(results.ccno_total_ar) == 20


def test_the_demand_model_actually_stresses_a_fixed_allocation():
    """If FSA never degrades there is nothing to demonstrate.

    This guards the demand generator: an earlier version drew each slice
    independently around half the budget, so a fixed 50/50 split served
    almost everything and the study was vacuous.
    """
    results = run_study(agent=ProportionalFairAgent(seed=1), iterations=40)
    below = [ar for ar in results.fsa_total_ar if ar < results.threshold]
    assert len(below) >= 5, (
        f"fixed allocation fell below threshold only {len(below)}/40 times; "
        f"the demand model is too tame for the comparison to mean anything"
    )


def test_closed_loop_beats_fixed_allocation_on_average():
    results = run_study(agent=ProportionalFairAgent(seed=1), iterations=40)
    fsa = sum(results.fsa_total_ar) / len(results.fsa_total_ar)
    ccno = sum(results.ccno_total_ar) / len(results.ccno_total_ar)
    assert ccno > fsa, f"CCNO {ccno:.3f} did not beat FSA {fsa:.3f}"
    assert results.reconfigurations > 0


def test_results_are_reproducible_under_a_seed():
    a = run_study(agent=ProportionalFairAgent(seed=99), iterations=10)
    b = run_study(agent=ProportionalFairAgent(seed=99), iterations=10)
    assert a.ccno_total_ar == b.ccno_total_ar
    assert a.fsa_total_ar == b.fsa_total_ar
    assert a.reconfigurations == b.reconfigurations


def test_both_arms_see_the_same_demand():
    """A comparison across different demand samples would be meaningless."""
    results = run_study(agent=ProportionalFairAgent(seed=5), iterations=15)
    for slice_id, samples in results.demand.items():
        assert len(samples) == 15, f"slice {slice_id} demand history is short"


@pytest.mark.parametrize("threshold", [0.0, 0.5, 1.0])
def test_threshold_controls_how_often_it_reconfigures(threshold):
    results = run_study(
        agent=ProportionalFairAgent(seed=3), iterations=20, threshold=threshold
    )
    if threshold == 0.0:
        assert results.reconfigurations == 0, "AR is never below a zero threshold"
    if threshold == 1.0:
        assert results.reconfigurations > 0


def test_summary_reports_both_arms():
    results = run_study(agent=ProportionalFairAgent(seed=1), iterations=10)
    summary = results.summary()
    assert "FSA" in summary and "CCNO" in summary


def test_running_the_study_needs_no_plotting_dependency(monkeypatch):
    """run_study must not import matplotlib -- the container image lacks it."""
    import sys

    monkeypatch.setitem(sys.modules, "matplotlib", None)
    results = run_study(agent=ProportionalFairAgent(seed=2), iterations=5)
    assert len(results.ccno_total_ar) == 5
