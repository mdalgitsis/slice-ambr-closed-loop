"""Read the live AMBR a 5G core is currently enforcing.

The core exposes subscription profiles over a REST API; each profile carries
the downlink APN AMBR that caps a slice.  Reading it back matters because the
loop should never assume its last decision was applied -- a profile can be
changed by an operator, another controller, or a failed write.
"""

from __future__ import annotations

import logging

import requests

from simulator import config

log = logging.getLogger(__name__)


def fetch_dl_apn_ambr(profile_id: int) -> float | None:
    """Return the downlink APN AMBR for one profile, or None if unavailable."""
    try:
        response = requests.get(
            config.RAEMIS_API_URL,
            params={"id": profile_id},
            auth=config.raemis_auth(),
            verify=config.RAEMIS_VERIFY_TLS,
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as exc:
        log.error("Error fetching AMBR for profile %s: %s", profile_id, exc)
        return None
    except ValueError as exc:
        log.error("Non-JSON response for profile %s: %s", profile_id, exc)
        return None

    if isinstance(data, list) and data:
        value = data[0].get("dl_apn_ambr")
        if value is not None:
            return float(value)
        log.warning("dl_apn_ambr absent for profile %s", profile_id)
    else:
        log.warning("Empty or unexpected payload for profile %s", profile_id)
    return None


def fetch_all(profile_map: dict[int, int]) -> dict[int, float]:
    """Fetch AMBR for every mapped slice. Slices that fail are omitted."""
    values: dict[int, float] = {}
    for slice_id, profile_id in profile_map.items():
        value = fetch_dl_apn_ambr(profile_id)
        if value is not None:
            values[profile_id] = value
            log.info(
                "Slice %s (profile %s) AMBR reported as %s",
                slice_id,
                profile_id,
                value,
            )
    return values
