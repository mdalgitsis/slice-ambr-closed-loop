"""The property that matters: reconfiguring must never make things worse.

A policy that lowers total acceptance ratio is worse than no policy at all,
because the loop pays a reconfiguration for it. These tests pin that down.
"""

import pytest

from agents import ProportionalFairAgent, SliceAllocationAgent


@pytest.fixture
def agent():
    return ProportionalFairAgent(seed=7)


def test_satisfies_the_loop_interface(agent):
    assert isinstance(agent, SliceAllocationAgent)


def test_action_space_covers_the_whole_budget(agent):
    for allocation in agent.action_space:
        assert sum(allocation) == pytest.approx(agent.max_total_resource)


@pytest.mark.parametrize(
    "demand",
    [
        (11.7, 47.4),   # both fit
        (80.0, 40.0),   # contention
        (90.0, 5.0),    # premium slice dominant
        (20.0, 95.0),   # low-priority slice dominant -- the starvation trap
        (5.0, 5.0),     # far under budget
        (55.0, 55.0),   # just over budget
        (0.0, 100.0),   # one slice idle
        (100.0, 100.0), # saturated
    ],
)
def test_reconfiguration_never_reduces_acceptance_ratio(demand):
    agent = ProportionalFairAgent(seed=7)
    demand_dict = {i: [d] for i, d in enumerate(demand)}
    current = {0: [50.0], 1: [50.0]}

    static_ar = agent.calculate_performance_metrics(
        agent.map_allocation_2_action(current), demand_dict
    )[-1]
    action, _new = agent.calculate_new_slice_AMBR_values(None, demand_dict, current)
    dynamic_ar = agent.calculate_performance_metrics(action, demand_dict)[-1]

    assert dynamic_ar >= static_ar - 1e-9, (
        f"reconfiguration degraded AR for demand {demand}: "
        f"{static_ar:.3f} -> {dynamic_ar:.3f}"
    )


def test_no_slice_is_given_more_than_it_can_use_while_another_starves():
    """The bug this heuristic exists to avoid."""
    agent = ProportionalFairAgent(seed=7)
    # Slice 0 is the premium slice but wants very little; slice 1 wants a lot.
    demand_dict = {0: [10.0], 1: [90.0]}
    current = {0: [50.0], 1: [50.0]}
    _action, new = agent.calculate_new_slice_AMBR_values(
        None, demand_dict, current
    )
    assert new[1][0] > new[0][0], (
        "priority weighting starved the high-demand slice: " f"{dict(new)}"
    )


def test_acceptance_ratio_is_bounded(agent):
    demand_dict = agent.calculate_new_rand_demand()
    for action in range(len(agent.action_space)):
        metrics = agent.calculate_performance_metrics(action, demand_dict)
        assert all(0.0 <= m <= 1.0 for m in metrics)


def test_demand_is_reproducible_under_a_seed():
    a = ProportionalFairAgent(seed=42).calculate_new_rand_demand()
    b = ProportionalFairAgent(seed=42).calculate_new_rand_demand()
    assert {k: v[0] for k, v in a.items()} == {k: v[0] for k, v in b.items()}


def test_mapping_an_allocation_back_to_an_action_is_stable(agent):
    for index, allocation in enumerate(agent.action_space):
        ambr = {i: [allocation[i]] for i in range(agent.num_slices)}
        assert agent.map_allocation_2_action(ambr) == index


def test_rejects_mismatched_priorities():
    with pytest.raises(ValueError):
        ProportionalFairAgent(num_slices=2, priorities=[1.0])
