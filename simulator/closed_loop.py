"""Closed-loop slice AMBR reconfiguration.

Each iteration:

1. read back the AMBR the 5G core is actually enforcing,
2. sample the offered demand,
3. score the *current* allocation,
4. if total acceptance ratio has fallen below the threshold, ask the policy
   for a new allocation and score that too,
5. export both, plus the fixed-allocation counterfactual, to Prometheus.

The loop never assumes a decision took effect -- step 1 is what closes it.

Actuation note: this process decides and publishes; writing the new AMBR back
into the core is done by a separate patch controller (see docs/deployment.md).
Keeping the decision read-only means a bad policy cannot brick a live core,
which is why it was split that way.
"""

from __future__ import annotations

import copy
import logging
import signal
import sys
import time
from collections import defaultdict

from prometheus_client import REGISTRY, generate_latest, start_http_server

from simulator import config, core_client, metrics
from simulator.agent_factory import load_agent

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
log = logging.getLogger(__name__)


class SliceReconfigurationLoop:
    def __init__(self, agent):
        self.agent = agent
        self.threshold = config.RECONFIG_TRIGGER_THRESHOLD
        self.profile_map = config.slice_profile_map()
        self.reconfigurations = 0

        missing = [
            i for i in range(agent.num_slices) if i not in self.profile_map
        ]
        if missing:
            raise ValueError(
                f"SLICE_PROFILE_MAP has no core profile for slice index(es) "
                f"{missing}; the agent allocates across {agent.num_slices} slices"
            )

    def profile_for(self, slice_id: int) -> int:
        return self.profile_map[slice_id]

    def publish_core_state(self) -> None:
        """Export what the core says it is currently enforcing."""
        for profile_id, value in core_client.fetch_all(self.profile_map).items():
            metrics.core_ambr.labels(profile_id=str(profile_id)).set(value)

    def adjust_ambr(self, policy_state, demand_dict, current_ambr_dict):
        """Score the current allocation; reconfigure only if it has degraded."""
        previous_action = self.agent.map_allocation_2_action(current_ambr_dict)
        scores = self.agent.calculate_performance_metrics(
            previous_action, demand_dict
        )
        total_ar = scores[-1]

        if total_ar >= self.threshold:
            log.info(
                "Acceptance ratio %.1f%% at or above the %.0f%% threshold; "
                "no reconfiguration needed.",
                total_ar * 100,
                self.threshold * 100,
            )
            return False, copy.deepcopy(current_ambr_dict), previous_action

        new_action, new_ambr_dict = self.agent.calculate_new_slice_AMBR_values(
            policy_state, demand_dict, current_ambr_dict
        )
        log.info(
            "Reconfiguration triggered: acceptance ratio %.1f%% below the "
            "%.0f%% threshold.",
            total_ar * 100,
            self.threshold * 100,
        )

        for slice_id in range(self.agent.num_slices):
            profile_id = self.profile_for(slice_id)
            before = _scalar(current_ambr_dict[slice_id])
            after = _scalar(new_ambr_dict[slice_id])
            log.info(
                "Slice %s (profile %s): AMBR %s -> %s",
                slice_id,
                profile_id,
                before,
                after,
            )
            metrics.ambr_dynamic.labels(slice_id=str(profile_id)).set(after)

        improved = self.agent.calculate_performance_metrics(
            new_action, demand_dict
        )[-1]
        log.info(
            "Acceptance ratio %.1f%% -> %.1f%%.", total_ar * 100, improved * 100
        )

        self.reconfigurations += 1
        metrics.reconfigurations.set(self.reconfigurations)
        return True, new_ambr_dict, new_action

    def run(self, interval: int = None, max_iterations: int = None) -> None:
        # `or` would treat an explicit 0 as unset and silently fall back to
        # the configured interval, which makes a zero-delay test run take
        # minutes. Both of these are None-checked deliberately.
        if interval is None:
            interval = config.SIMULATION_INTERVAL
        if max_iterations is None:
            max_iterations = config.MAX_ITERATIONS

        static_ambr = defaultdict(list)
        dynamic_ambr = defaultdict(list)
        for slice_id in range(self.agent.num_slices):
            static_ambr[slice_id] = [config.INITIAL_AMBR]
            dynamic_ambr[slice_id] = [config.INITIAL_AMBR]

        started = time.process_time()
        log.info("Preparing allocation policy...")
        policy_state, _diagnostics = self.agent.train_agent(consider_fairness=True)
        log.info(
            "Policy ready in %.2fs.", round(time.process_time() - started, 2)
        )

        iteration = 0
        while True:
            iteration += 1
            log.info("--- iteration %s ---", iteration)

            self.publish_core_state()

            demand_dict = self.agent.calculate_new_rand_demand()
            for slice_id in range(self.agent.num_slices):
                profile_id = str(self.profile_for(slice_id))
                metrics.demand.labels(slice_id=profile_id).set(
                    _scalar(demand_dict[slice_id])
                )
                metrics.ambr_static.labels(slice_id=profile_id).set(
                    _scalar(static_ambr[slice_id])
                )

            # Counterfactual: the same demand under a never-changing allocation.
            static_action = self.agent.map_allocation_2_action(static_ambr)
            static_scores = self.agent.calculate_performance_metrics(
                static_action, demand_dict
            )
            metrics.acceptance_ratio_static.set(static_scores[-1])

            _triggered, new_ambr_dict, new_action = self.adjust_ambr(
                policy_state, demand_dict, dynamic_ambr
            )
            for slice_id in range(self.agent.num_slices):
                metrics.ambr_dynamic.labels(
                    slice_id=str(self.profile_for(slice_id))
                ).set(_scalar(new_ambr_dict[slice_id]))

            dynamic_scores = self.agent.calculate_performance_metrics(
                new_action, demand_dict
            )
            metrics.acceptance_ratio_dynamic.set(dynamic_scores[-1])
            metrics.iteration.set(iteration)

            log.debug(
                "Exported metrics:\n%s", generate_latest(REGISTRY).decode("utf-8")
            )
            dynamic_ambr = copy.deepcopy(new_ambr_dict)

            if max_iterations and iteration >= max_iterations:
                log.info("Reached MAX_ITERATIONS=%s; stopping.", max_iterations)
                return
            time.sleep(interval)


def _scalar(value):
    if isinstance(value, (list, tuple)):
        return float(value[0]) if value else 0.0
    return float(value)


def _shutdown(_sig, _frame):
    log.info("Shutting down.")
    sys.exit(0)


def main() -> None:
    if not config.RAEMIS_VERIFY_TLS:
        import urllib3

        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        log.warning(
            "TLS verification disabled for the core API (RAEMIS_VERIFY_TLS). "
            "Acceptable against a lab core with a self-signed certificate; "
            "do not run this way against anything else."
        )

    start_http_server(config.PROMETHEUS_PORT)
    log.info("Prometheus exporter listening on :%s", config.PROMETHEUS_PORT)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    SliceReconfigurationLoop(load_agent()).run()


if __name__ == "__main__":
    main()
