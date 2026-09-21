"""Offline figures for a simulation run: static allocation vs. the loop.

Every panel is the same comparison at a different granularity -- total, then
per slice -- so the five near-identical blocks this started as are expressed
once, driven by a table.
"""

import matplotlib.pyplot as plt

STATIC_STYLE = {"color": "teal", "marker": "^", "linestyle": ":", "label": "Static"}
DYNAMIC_STYLE = {"color": "b", "marker": "o", "linestyle": "-", "label": "Dynamic"}


def _panel(x, static, dynamic, title, ylabel):
    plt.figure(figsize=(10, 6))
    plt.plot(x, [100 * y for y in static], **STATIC_STYLE)
    plt.plot(x, [100 * y for y in dynamic], **DYNAMIC_STYLE)
    plt.title(title, fontsize=16)
    plt.xlabel("Iterations", fontsize=14)
    plt.ylabel(ylabel, fontsize=14)
    plt.grid(True, linestyle="--", alpha=0.6)
    plt.legend()
    plt.tight_layout()


def plot_results(
    iterations,
    total_ar_hist_static,
    total_ar_hist_dynamic,
    slice_1_ar_hist_dynamic,
    slice_1_ar_hist_static,
    slice_2_ar_hist_dynamic,
    slice_2_ar_hist_static,
    slice_1_tot_ar_hist_dynamic,
    slice_1_tot_ar_hist_static,
    slice_2_tot_ar_hist_dynamic,
    slice_2_tot_ar_hist_static,
    show=True,
):
    """Render the acceptance-ratio comparison panels for a completed run."""
    x = list(range(iterations))

    panels = [
        (
            total_ar_hist_static,
            total_ar_hist_dynamic,
            "Total acceptance ratio",
            "Acceptance ratio in %",
        ),
        (
            slice_1_ar_hist_static,
            slice_1_ar_hist_dynamic,
            "Slice 1 acceptance ratio",
            "Slice 1 acceptance ratio in %",
        ),
        (
            slice_2_ar_hist_static,
            slice_2_ar_hist_dynamic,
            "Slice 2 acceptance ratio",
            "Slice 2 acceptance ratio in %",
        ),
        (
            slice_1_tot_ar_hist_static,
            slice_1_tot_ar_hist_dynamic,
            "Slice 1 total acceptance ratio",
            "Slice 1 total acceptance ratio in %",
        ),
        (
            slice_2_tot_ar_hist_static,
            slice_2_tot_ar_hist_dynamic,
            "Slice 2 total acceptance ratio",
            "Slice 2 total acceptance ratio in %",
        ),
    ]

    for static, dynamic, title, ylabel in panels:
        _panel(x, static, dynamic, title, ylabel)

    if show:
        plt.show()
