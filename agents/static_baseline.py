"""A closed-form baseline policy, so the loop runs out of the box.

This is *not* the policy behind the published results -- it is a deliberately
simple proportional-fair heuristic that implements
:class:`agents.base.SliceAllocationAgent` so that the control loop, the
exporter, the dashboards and the charts can be run, reviewed and tested
end to end without a learned policy.

It also doubles as the honest comparison point: the loop exports the metrics of
a *static* allocation alongside the reconfigured one, and a reviewer can see
what reconfiguration is worth before any RL is involved.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

SliceVector = dict[int, list[float]]


class ProportionalFairAgent:
    """Allocate the shared budget in proportion to demand, floored per slice.

    Priorities bias the split when demand exceeds the budget: a slice with
    weight 0.9 is served before one with weight 0.1.  There is no learning --
    the allocation is a direct function of the current demand sample.
    """

    def __init__(
        self,
        num_slices: int = 2,
        max_total_resource: float = 100.0,
        min_demand: float = 5.0,
        alloc_step: float = 10.0,
        priorities: list[float] | None = None,
        seed: int | None = None,
    ) -> None:
        self.num_slices = num_slices
        self.max_total_resource = max_total_resource
        self.min_demand = min_demand
        self.alloc_step = alloc_step
        self.priorities = priorities or self._default_priorities(num_slices)
        if len(self.priorities) != num_slices:
            raise ValueError("priorities must have one entry per slice")

        self._rng = random.Random(seed)
        self._ar_history: dict[int, list[float]] = defaultdict(list)
        self.action_space = self._build_action_space()

    @staticmethod
    def _default_priorities(num_slices: int) -> list[float]:
        # Front-loaded weights: the first slice is the premium one.
        if num_slices == 2:
            return [0.9, 0.1]
        return [1.0 / num_slices] * num_slices

    def _build_action_space(self) -> list[tuple[float, ...]]:
        """Every discrete split of the budget across slices, in alloc_step units."""
        steps = int(self.max_total_resource / self.alloc_step)

        def splits(remaining: int, slices_left: int) -> list[list[int]]:
            if slices_left == 1:
                return [[remaining]]
            out = []
            for take in range(remaining + 1):
                for rest in splits(remaining - take, slices_left - 1):
                    out.append([take] + rest)
            return out

        return [
            tuple(v * self.alloc_step for v in combo)
            for combo in splits(steps, self.num_slices)
        ]

    # ---- SliceAllocationAgent -------------------------------------------

    def train_agent(self, consider_fairness: bool = False) -> tuple[Any, Any]:
        """No-op: the policy is closed-form. Returns (None, diagnostics)."""
        return None, {"policy": "proportional-fair", "fairness": consider_fairness}

    def calculate_new_rand_demand(self) -> SliceVector:
        """Draw offered demand: a total load, then an uneven split.

        Drawing each slice independently around half the budget produces a
        demand mix that a fixed 50/50 allocation already serves, which makes
        the whole system look pointless. Real traffic is not like that -- the
        load moves *between* slices, and the total oversubscribes at peaks.

        So: draw a total between 50% and 140% of the budget, then split it with
        a random skew. That produces the two situations reconfiguration exists
        for -- one slice starved while the other sits on unused headroom, and
        genuine oversubscription where priority has to decide.
        """
        total = self._rng.uniform(
            0.5 * self.max_total_resource, 1.4 * self.max_total_resource
        )
        weights = [self._rng.uniform(0.05, 0.95) for _ in range(self.num_slices)]
        weight_sum = sum(weights) or 1.0

        demand: SliceVector = defaultdict(list)
        for slice_id in range(self.num_slices):
            share = total * weights[slice_id] / weight_sum
            demand[slice_id] = [max(self.min_demand, share)]
        return demand

    def map_allocation_2_action(self, ambr_dict: SliceVector) -> int:
        """Nearest action index to the allocation currently in the core."""
        current = [self._scalar(ambr_dict[i]) for i in range(self.num_slices)]
        best, best_dist = 0, float("inf")
        for idx, candidate in enumerate(self.action_space):
            dist = sum((a - b) ** 2 for a, b in zip(candidate, current, strict=True))
            if dist < best_dist:
                best, best_dist = idx, dist
        return best

    def calculate_performance_metrics(
        self, action: int, demand_dict: SliceVector
    ) -> tuple[float, ...]:
        """Per-slice and total acceptance ratio for an allocation.

        Returns ``(ar_0, ar_avg_0, ar_1, ar_avg_1, ..., total_ar)`` -- the
        per-slice pairs in order, then the demand-weighted total.  For the
        two-slice default this is the five-element vector the loop unpacks.
        """
        allocation = self.action_space[action]
        metrics: list[float] = []
        served_total = 0.0
        demand_total = 0.0

        for slice_id in range(self.num_slices):
            demand = self._scalar(demand_dict[slice_id])
            alloc = allocation[slice_id]
            served = min(demand, alloc)
            ar = 1.0 if demand <= 0 else served / demand

            self._ar_history[slice_id].append(ar)
            history = self._ar_history[slice_id]
            metrics.extend([ar, sum(history) / len(history)])

            served_total += served
            demand_total += demand

        total_ar = 1.0 if demand_total <= 0 else served_total / demand_total
        metrics.append(total_ar)
        return tuple(metrics)

    def calculate_new_slice_AMBR_values(
        self, policy_state: Any, demand_dict: SliceVector, ambr_dict: SliceVector
    ) -> tuple[int, SliceVector]:
        """Split the budget across slices, snapped to the action grid.

        Progressive fill: no slice is given more than it can use, and whatever
        that frees is redistributed to the slices still short.  Priority
        weights decide the split only among slices that are *all* still
        unsatisfied -- which is the only point at which the question "who gives
        way?" actually arises.

        Handing a premium slice more than its demand because its weight is high
        is the obvious trap here, and it costs total acceptance ratio directly.
        """
        demands = [self._scalar(demand_dict[i]) for i in range(self.num_slices)]
        share = self._progressive_fill(demands)

        # Snapping to the action grid keeps the baseline and any learned policy
        # in the same allocation space, so their metrics are comparable.
        action = self.map_allocation_2_action(
            {i: [share[i]] for i in range(self.num_slices)}
        )
        allocation = self.action_space[action]

        new_ambr: SliceVector = defaultdict(list)
        for slice_id in range(self.num_slices):
            new_ambr[slice_id] = [allocation[slice_id]]
        return action, new_ambr

    def _progressive_fill(self, demands: list[float]) -> list[float]:
        """Priority-weighted water-filling, capped at each slice's demand."""
        share = [0.0] * self.num_slices
        remaining = self.max_total_resource
        pending = [i for i in range(self.num_slices) if demands[i] > 0]

        if not pending:
            return [self.max_total_resource / self.num_slices] * self.num_slices

        while pending and remaining > 1e-9:
            weights = [self.priorities[i] for i in pending]
            total_weight = sum(weights)
            if total_weight <= 0:
                weights = [1.0] * len(pending)
                total_weight = float(len(pending))

            # Slices whose weighted share would exceed their demand are capped
            # and settled now; the rest split what is left on the next pass.
            capped = []
            for idx, slice_id in enumerate(pending):
                tentative = remaining * weights[idx] / total_weight
                if tentative >= demands[slice_id] - share[slice_id]:
                    capped.append(slice_id)

            if not capped:
                for idx, slice_id in enumerate(pending):
                    share[slice_id] += remaining * weights[idx] / total_weight
                remaining = 0.0
                break

            for slice_id in capped:
                take = demands[slice_id] - share[slice_id]
                share[slice_id] += take
                remaining -= take
                pending.remove(slice_id)

        # Nothing left to serve but budget to spare: park it on the highest
        # priority slice rather than leave the ceiling artificially low.
        if remaining > 1e-9:
            top = max(range(self.num_slices), key=lambda i: self.priorities[i])
            share[top] += remaining

        return share

    # ---- helpers ---------------------------------------------------------

    @staticmethod
    def _scalar(value: Any) -> float:
        """Accept either ``[x]`` or ``x`` -- the loop carries both shapes."""
        if isinstance(value, (list, tuple)):
            return float(value[0]) if value else 0.0
        return float(value)
