"""Offline batch study: fixed slice allocation vs. closed-loop reconfiguration.

This is the evaluation that sits behind the paper (see docs/reproducing.md).
It runs the same decision logic as the live loop, but against a batch of demand
samples with no 5G core in the path, and plots total acceptance ratio for two
arms:

* **FSA** -- Fixed Slice Allocation. The budget is split once and never moves.
* **CCNO** -- the closed-loop arm, which reconfigures whenever acceptance ratio
  falls below the trigger threshold.

Both arms see the *same* demand sequence, which is the only way the comparison
means anything. The run is seeded, so a given seed reproduces a given figure.

The policy behind CCNO is whatever `SLICE_AGENT` resolves to. With the bundled
baseline this reproduces the *shape* of the published comparison, not its
numbers -- the learned policy used for the paper is not in this repository.
"""

from __future__ import annotations

import argparse
import copy
import logging
from collections import defaultdict
from dataclasses import dataclass, field

from simulator.agent_factory import load_agent

log = logging.getLogger(__name__)

DEFAULT_ITERATIONS = 20
DEFAULT_INITIAL_AMBR = 50.0
DEFAULT_THRESHOLD = 0.8


@dataclass
class StudyResults:
    """Per-iteration history for both arms."""

    iterations: int
    threshold: float
    fsa_total_ar: list = field(default_factory=list)
    ccno_total_ar: list = field(default_factory=list)
    fsa_slice_ar: dict = field(default_factory=lambda: defaultdict(list))
    ccno_slice_ar: dict = field(default_factory=lambda: defaultdict(list))
    ccno_allocation: dict = field(default_factory=lambda: defaultdict(list))
    demand: dict = field(default_factory=lambda: defaultdict(list))
    reconfigurations: int = 0

    def summary(self) -> str:
        def mean(values):
            return sum(values) / len(values) if values else 0.0

        fsa, ccno = mean(self.fsa_total_ar), mean(self.ccno_total_ar)
        delta = (ccno - fsa) * 100
        return (
            f"FSA  mean acceptance ratio: {fsa * 100:.1f}%\n"
            f"CCNO mean acceptance ratio: {ccno * 100:.1f}%\n"
            f"Delta: {delta:+.1f} percentage points over {self.iterations} "
            f"iterations, {self.reconfigurations} reconfiguration(s)"
        )


def run_study(
    agent=None,
    iterations: int = DEFAULT_ITERATIONS,
    initial_ambr: float = DEFAULT_INITIAL_AMBR,
    threshold: float = DEFAULT_THRESHOLD,
) -> StudyResults:
    """Run both arms over one shared demand sequence."""
    agent = agent or load_agent()
    results = StudyResults(iterations=iterations, threshold=threshold)

    fsa_ambr = defaultdict(list)
    ccno_ambr = defaultdict(list)
    for slice_id in range(agent.num_slices):
        fsa_ambr[slice_id] = [initial_ambr]
        ccno_ambr[slice_id] = [initial_ambr]

    log.info("Preparing allocation policy...")
    policy_state, _diagnostics = agent.train_agent(consider_fairness=True)

    for index in range(iterations):
        # One demand sample, shown to both arms.
        demand = agent.calculate_new_rand_demand()
        for slice_id in range(agent.num_slices):
            results.demand[slice_id].append(_scalar(demand[slice_id]))

        # --- FSA: never moves -------------------------------------------
        fsa_action = agent.map_allocation_2_action(fsa_ambr)
        fsa_metrics = agent.calculate_performance_metrics(fsa_action, demand)
        results.fsa_total_ar.append(fsa_metrics[-1])
        for slice_id in range(agent.num_slices):
            results.fsa_slice_ar[slice_id].append(fsa_metrics[slice_id * 2])

        # --- CCNO: reconfigures when acceptance ratio degrades -----------
        ccno_action = agent.map_allocation_2_action(ccno_ambr)
        ccno_metrics = agent.calculate_performance_metrics(ccno_action, demand)
        total_ar = ccno_metrics[-1]

        if total_ar < threshold:
            ccno_action, new_ambr = agent.calculate_new_slice_AMBR_values(
                policy_state, demand, ccno_ambr
            )
            ccno_metrics = agent.calculate_performance_metrics(ccno_action, demand)
            results.reconfigurations += 1
            log.info(
                "Iteration %s: AR %.1f%% below %.0f%% -- reconfigured to %.1f%%",
                index + 1,
                total_ar * 100,
                threshold * 100,
                ccno_metrics[-1] * 100,
            )
            ccno_ambr = copy.deepcopy(new_ambr)

        results.ccno_total_ar.append(ccno_metrics[-1])
        for slice_id in range(agent.num_slices):
            results.ccno_slice_ar[slice_id].append(ccno_metrics[slice_id * 2])
            results.ccno_allocation[slice_id].append(_scalar(ccno_ambr[slice_id]))

    return results


def plot_study(results: StudyResults, output: str | None = None, show: bool = False):
    """Render the FSA vs CCNO acceptance-ratio comparison."""
    import matplotlib.colors as mcolors
    import matplotlib.pyplot as plt

    tableau = list(mcolors.TABLEAU_COLORS.values())
    x = list(range(results.iterations))

    plt.figure(figsize=(10, 6))
    plt.plot(
        x,
        [100 * y for y in results.fsa_total_ar],
        marker="x",
        linestyle="-",
        color=tableau[0],
        label="FSA",
    )
    plt.plot(
        x,
        [100 * y for y in results.ccno_total_ar],
        marker="^",
        linestyle="-",
        color=tableau[3],
        label="CCNO",
    )
    plt.axhline(
        y=results.threshold * 100,
        color="gray",
        linestyle="--",
        linewidth=2,
        label=f"Acceptance Threshold ({results.threshold * 100:.0f}%)",
    )

    plt.xlabel("Iterations", fontsize=20)
    plt.ylabel("Acceptance Ratio (%)", fontsize=20)
    plt.xticks(fontsize=18)
    plt.yticks(fontsize=18)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend(loc="lower right", fontsize=14)
    plt.tight_layout()

    if output:
        plt.savefig(output)
        log.info("Wrote %s", output)
    if show:
        plt.show()
    return plt


def _scalar(value):
    if isinstance(value, (list, tuple)):
        return float(value[0]) if value else 0.0
    return float(value)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Offline FSA vs CCNO acceptance-ratio study."
    )
    parser.add_argument("--iterations", type=int, default=DEFAULT_ITERATIONS)
    parser.add_argument("--initial-ambr", type=float, default=DEFAULT_INITIAL_AMBR)
    parser.add_argument("--threshold", type=float, default=DEFAULT_THRESHOLD)
    parser.add_argument(
        "--output",
        default="fsa_vs_ccno_acceptance_ratio.pdf",
        help="Figure path; pass an empty string to skip plotting.",
    )
    parser.add_argument("--show", action="store_true", help="Display the figure.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    results = run_study(
        iterations=args.iterations,
        initial_ambr=args.initial_ambr,
        threshold=args.threshold,
    )
    print(results.summary())

    if args.output or args.show:
        plot_study(results, output=args.output or None, show=args.show)


if __name__ == "__main__":
    main()
