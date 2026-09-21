"""The policy seam of the closed loop.

The control loop in :mod:`simulator` is deliberately agnostic to *how* a new
AMBR allocation is chosen.  Everything it needs from a policy is the six
methods and one attribute below -- that is the entire surface.  Swap the
implementation and the loop, the exporter, the dashboards and the Helm charts
are unchanged.

Two implementations are discussed in the docs:

* :class:`agents.static_baseline.ProportionalFairAgent` -- ships here, and is
  what you get by default.
* A tabular Q-learning policy -- the one used for the published results.  It is
  not included; see ``agents/README.md`` for why and for what to implement.

Terminology
-----------
AMBR
    Aggregate Maximum Bit Rate: the per-slice rate ceiling enforced by the 5G
    core.  This is the actuator the loop drives.
Acceptance ratio (AR)
    Fraction of offered demand a slice can serve under its current AMBR.  This
    is the signal the loop closes on.
Action
    An index into a discrete allocation space -- one whole assignment of the
    shared resource budget across all slices.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

# demand/allocation dictionaries are keyed by zero-based slice index; the value
# is a single-element list so callers can carry history without changing shape.
SliceVector = dict[int, list[float]]

# (slice_1_ar, slice_1_ar_avg, slice_2_ar, slice_2_ar_avg, total_ar)
MetricVector = tuple[float, float, float, float, float]


@runtime_checkable
class SliceAllocationAgent(Protocol):
    """What the control loop requires of an allocation policy."""

    #: number of slices the policy allocates across
    num_slices: int

    def train_agent(self, consider_fairness: bool = False) -> tuple[Any, Any]:
        """Prepare the policy before the loop starts.

        Returns ``(policy_state, diagnostics)``.  ``policy_state`` is passed
        back verbatim to :meth:`calculate_new_slice_AMBR_values` and is opaque
        to the loop -- a Q-table for an RL policy, ``None`` for a closed-form
        one.  ``diagnostics`` is for plotting and is otherwise unused.

        Called once at startup, so it may be expensive.
        """
        ...

    def calculate_new_rand_demand(self) -> SliceVector:
        """Draw the next demand sample, one entry per slice.

        This is the synthetic traffic source.  Against a live network you would
        replace it with a reading from the core's counters.
        """
        ...

    def map_allocation_2_action(self, ambr_dict: SliceVector) -> Any:
        """Map a concrete AMBR allocation back to its action index.

        The loop needs this to score the allocation currently programmed into
        the core, which it did not necessarily choose itself.
        """
        ...

    def calculate_performance_metrics(
        self, action: Any, demand_dict: SliceVector
    ) -> MetricVector:
        """Score an allocation against a demand sample.

        The loop only reads the last element (total AR) to decide whether to
        reconfigure; the rest is exported for dashboards.
        """
        ...

    def calculate_new_slice_AMBR_values(
        self, policy_state: Any, demand_dict: SliceVector, ambr_dict: SliceVector
    ) -> tuple[Any, SliceVector]:
        """Choose a new allocation. Returns ``(action, new_ambr_dict)``.

        Called only when total AR has fallen below the reconfiguration
        threshold -- this is the decision the closed loop exists to make.
        """
        ...
