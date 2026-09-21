"""Prometheus gauges exported by the control loop.

The static/dynamic pairing is the point: every reconfiguration decision is
published alongside what a fixed allocation would have achieved on the same
demand sample, so the dashboard shows the delta the loop is responsible for
rather than just an absolute number.
"""

from prometheus_client import Gauge

PREFIX = "slice_ambr"

ambr_static = Gauge(
    f"{PREFIX}_static_bitrate",
    "AMBR a fixed allocation would hold for this slice",
    ["slice_id"],
)
ambr_dynamic = Gauge(
    f"{PREFIX}_dynamic_bitrate",
    "AMBR chosen by the allocation policy for this slice",
    ["slice_id"],
)
demand = Gauge(
    f"{PREFIX}_demand",
    "Offered demand for this slice",
    ["slice_id"],
)
acceptance_ratio_static = Gauge(
    f"{PREFIX}_acceptance_ratio_static",
    "Total acceptance ratio under a fixed allocation",
)
acceptance_ratio_dynamic = Gauge(
    f"{PREFIX}_acceptance_ratio_dynamic",
    "Total acceptance ratio under the allocation policy",
)
iteration = Gauge(
    f"{PREFIX}_iteration",
    "Control loop iteration counter",
)
core_ambr = Gauge(
    f"{PREFIX}_core_reported_bitrate",
    "Downlink APN AMBR as currently reported by the 5G core",
    ["profile_id"],
)
reconfigurations = Gauge(
    f"{PREFIX}_reconfigurations_total",
    "Number of reconfigurations triggered since start",
)
