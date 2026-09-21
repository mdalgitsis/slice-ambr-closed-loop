"""Resolve the allocation policy named in the environment.

Keeping this in one place is what makes the policy swappable without touching
the control loop: point ``SLICE_AGENT`` at any class implementing
:class:`agents.base.SliceAllocationAgent` and the loop picks it up.
"""

from __future__ import annotations

import importlib
import logging
import os
from typing import Any

DEFAULT_AGENT = "agents.static_baseline:ProportionalFairAgent"


def load_agent(spec: str | None = None) -> Any:
    """Instantiate the configured agent.

    ``spec`` is ``module.path:ClassName``.  Falls back to the bundled
    proportional-fair baseline, which is what ships in this repository -- see
    ``agents/README.md`` for the learned policy that is not included.
    """
    spec = spec or os.getenv("SLICE_AGENT", DEFAULT_AGENT)
    try:
        module_name, _, class_name = spec.partition(":")
        if not class_name:
            raise ValueError(f"expected 'module:ClassName', got {spec!r}")
        module = importlib.import_module(module_name)
        agent_cls = getattr(module, class_name)
    except (ImportError, AttributeError, ValueError) as exc:
        raise RuntimeError(
            f"Could not load allocation agent {spec!r}: {exc}. "
            f"Set SLICE_AGENT to 'module.path:ClassName' or unset it to use "
            f"the bundled baseline ({DEFAULT_AGENT})."
        ) from exc

    logging.info("Allocation policy: %s", spec)
    return agent_cls()
