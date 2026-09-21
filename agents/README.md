# Allocation policies

The control loop does not care how an allocation is chosen. It needs seven
things from a policy — one attribute and six methods — and that is the whole
contract. It is written down in [`base.py`](base.py) and enforced by the tests.

## What ships here

`ProportionalFairAgent` in [`static_baseline.py`](static_baseline.py) is a
closed-form policy: priority-weighted water-filling, capped at each slice's
demand, snapped to the same discrete allocation grid a learned policy would
use. It exists so the loop, the exporter, the dashboards and the charts can be
run and reviewed end to end without anything else in place.

It is a genuine baseline, not a stub — the test suite pins the property that
matters, which is that reconfiguring must never lower total acceptance ratio.
It is not, however, the policy behind the published results.

## What does not ship here

The results this system was built to produce came from a **tabular Q-learning
policy** with a priority-weighted, fairness-aware reward over a discretised
demand/allocation state space.

That implementation was written by a colleague at Nearby Computing as part of
the same FREE6G work (see [`docs/reproducing.md`](../docs/reproducing.md) for
the paper it supports). The design — the state and action encoding, the reward
shaping, the reconfiguration trigger, and how the policy plugs into the loop —
was worked out jointly; the Q-learning module itself was theirs. It is their
code to publish, not mine, so it is not included here and this repository does
not reproduce the published figures.

If you want to run the learned policy, implement `SliceAllocationAgent` and
point the loop at it:

```bash
export SLICE_AGENT="my_package.my_module:MyQLearningAgent"
```

or set `agent:` in the Helm chart's values. Nothing else changes.

## The contract

| Member | Purpose |
| --- | --- |
| `num_slices` | How many slices the policy allocates across. |
| `train_agent(consider_fairness)` | Prepare the policy. Returns `(policy_state, diagnostics)`; `policy_state` is opaque to the loop and handed back on every decision. |
| `calculate_new_rand_demand()` | Draw the next demand sample. Replace with live counters against a real network. |
| `map_allocation_2_action(ambr_dict)` | Map an allocation the loop did not choose — e.g. one read back from the core — to an action index. |
| `calculate_performance_metrics(action, demand)` | Score an allocation. The loop reads the last element (total AR); the rest is exported. |
| `calculate_new_slice_AMBR_values(state, demand, ambr)` | Choose a new allocation. Called only once AR is below threshold. |

Two details are easy to get wrong:

- **`calculate_performance_metrics` returns the total acceptance ratio last.**
  The loop indexes `[-1]`. Per-slice values come before it, in slice order.
- **`calculate_new_slice_AMBR_values` must return allocations on the same grid
  that `map_allocation_2_action` resolves against.** Otherwise the loop's
  read-back of its own decision will not round-trip, and it will appear to
  reconfigure on every iteration.
