"""Runtime configuration, all environment-driven.

Nothing here carries a real address or credential: the defaults are RFC 5737
documentation addresses and empty secrets, so a misconfigured deployment fails
loudly instead of quietly talking to whatever happens to be at a baked-in IP.
"""

from __future__ import annotations

import os

# --- 5G core (Aggregate Maximum Bit Rate actuator) -----------------------
# RFC 5737 TEST-NET-1: replace with your own core's address.
RAEMIS_API_URL = os.getenv(
    "RAEMIS_API_URL", "https://192.0.2.10:30443/api/subscription_profile"
)
RAEMIS_USERNAME = os.getenv("RAEMIS_USERNAME", "")
RAEMIS_PASSWORD = os.getenv("RAEMIS_PASSWORD", "")
RAEMIS_VERIFY_TLS = os.getenv("RAEMIS_VERIFY_TLS", "true").lower() not in (
    "false",
    "0",
    "no",
)

# --- control loop --------------------------------------------------------
INITIAL_AMBR = float(os.getenv("INITIAL_AMBR", "50"))
RECONFIG_TRIGGER_THRESHOLD = float(os.getenv("RECONFIG_TRIGGER_THRESHOLD", "0.8"))
SIMULATION_INTERVAL = int(os.getenv("SIMULATION_INTERVAL", "25"))
PROMETHEUS_PORT = int(os.getenv("PROMETHEUS_PORT", "8999"))
# 0 = run forever. A positive value stops after N iterations, which is what
# the CI smoke test uses to exercise the loop without a timeout.
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "0"))

# Maps this simulation's slice index -> the subscription profile id in the core.
# Format: "0=6,1=7"
_DEFAULT_SLICE_MAP = "0=1,1=2"


def slice_profile_map() -> dict:
    """Parse SLICE_PROFILE_MAP into {slice_index: core_profile_id}."""
    raw = os.getenv("SLICE_PROFILE_MAP", _DEFAULT_SLICE_MAP)
    mapping = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        key, _, value = pair.partition("=")
        try:
            mapping[int(key)] = int(value)
        except ValueError as exc:
            raise ValueError(
                f"SLICE_PROFILE_MAP entry {pair!r} is not 'index=profile_id'"
            ) from exc
    if not mapping:
        raise ValueError("SLICE_PROFILE_MAP resolved to no slices")
    return mapping


def raemis_auth():
    """Basic-auth tuple, or None when no credentials are configured."""
    if RAEMIS_USERNAME or RAEMIS_PASSWORD:
        return (RAEMIS_USERNAME, RAEMIS_PASSWORD)
    return None
