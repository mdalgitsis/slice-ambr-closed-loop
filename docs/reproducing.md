# The paper, and what you can reproduce here

## Related publication

This system is one of the use cases in:

> M. Dalgitsis, E. Datsika, C. Santana Casillas and A. Antonopoulos,
> "**6G-Core-in-the-Loop: Enabling Service and Network Orchestration in a
> Cloud-Native Ecosystem**," *IEEE Communications Standards Magazine*,
> vol. 10, no. 2, pp. 72–79, June 2026.
> doi: [10.1109/MCOMSTD.2026.3657234](https://doi.org/10.1109/MCOMSTD.2026.3657234)
> · [IEEE Xplore](https://ieeexplore.ieee.org/document/11373561)

The paper covers service and network orchestration in a cloud-native 6G core.
The slice-reconfiguration loop in this repository is the concrete mechanism
behind one of its use cases: closing a control loop around per-slice AMBR so
that admission keeps up with traffic that moves between slices.

Two names in the paper carry over into the code and are worth decoding:

| Paper | Here |
| --- | --- |
| **FSA** — Fixed Slice Allocation | The static baseline arm. The budget is split once and never moves. |
| **CCNO** — the proposed cloud-native orchestration approach | The closed-loop arm, reconfiguring when acceptance ratio degrades. |

That is also why an FSA arm exists in the code at all: it is the paper's
comparison point, not an implementation detail.

## Running the study

```bash
pip install -r requirements-plot.txt
python -m simulator.offline_study --iterations 20
```

This runs both arms over one shared demand sequence and writes
`fsa_vs_ccno_acceptance_ratio.pdf`:

```
FSA  mean acceptance ratio: 81.4%
CCNO mean acceptance ratio: 90.0%
Delta: +8.6 percentage points over 20 iterations, 12 reconfiguration(s)
```

Both arms see the **same** demand samples — comparing across different draws
would say nothing — and the run is seeded, so a given seed gives a given
figure.

## What this does and does not reproduce

**It reproduces the shape of the comparison**: FSA degrading as load moves
between slices while the closed loop recovers, against a fixed acceptance
threshold.

**It does not reproduce the paper's numbers.** The policy behind the published
results is a tabular Q-learning agent implemented by a colleague; it is theirs
to publish and is not in this repository (see
[`agents/README.md`](../agents/README.md)). What ships is a closed-form
proportional-fair baseline. The loop, the trigger, the metrics and the study
harness are the same; the decision function is not.

To reproduce the published figures, implement `SliceAllocationAgent` with the
learned policy and set `SLICE_AGENT` — nothing else changes.

## Reading the figure honestly

Two things are visible in the output that are easy to gloss over:

- **The closed loop still dips below the threshold.** It reacts *after*
  acceptance ratio has already fallen — it does not predict. A production
  deployment would want either forecasting or a margin above the threshold.
- **Some reconfigurations recover nothing.** Under genuine oversubscription —
  total demand well past the budget — no split of that budget serves everyone,
  and the loop pays a reconfiguration for no gain. A dwell time or a minimum
  expected-improvement gate would suppress those.

Both are properties of the mechanism rather than artefacts of the baseline
policy, so they carry over to a learned one.
