# Architecture

## The control problem

A 5G core enforces a per-slice AMBR: a ceiling on aggregate bit rate, held in a
subscription profile. The ceiling is normally provisioned once, at design time,
from an estimate of what each slice will need.

That estimate is wrong the moment traffic moves. Two slices sharing a fixed
budget will routinely sit in a state where one has headroom it is not using and
the other is turning demand away. The total acceptance ratio — demand served
over demand offered — is measurably below what the same budget could deliver if
the split were allowed to move.

This system closes that loop.

## Signal, actuator, decision

| | |
| --- | --- |
| **Signal** | Acceptance ratio per slice, derived from offered demand against the current ceiling. |
| **Actuator** | The per-slice AMBR in the core's subscription profile. |
| **Decision** | Which split of the shared budget to move to, and whether to move at all. |

The decision is gated: the loop reconfigures only when total acceptance ratio
falls below `RECONFIG_TRIGGER_THRESHOLD`. Reconfiguration is not free — it is a
write to a live core — so a loop that re-optimises every tick because it can is
generating risk for no gain.

## One iteration

1. **Read back.** Fetch the AMBR each mapped profile is *currently* enforcing
   and export it. This is what makes it a closed loop rather than an open one.
2. **Sample demand.** Draw the current offered demand per slice.
3. **Score what is in place.** Map the current allocation to an action, and
   compute acceptance ratios for it.
4. **Gate.** Above threshold, hold.
5. **Decide.** Below threshold, ask the policy for a new allocation and score
   that too.
6. **Export.** Publish the decision, the resulting ratios, and the
   fixed-allocation counterfactual.

Step 1 is the one most often skipped, and skipping it is how a controller ends
up confidently computing from a state the network left some time ago.

## Why decision and actuation are separate

This process never writes to the core. It publishes an intended allocation; a
separate patch controller performs the write.

The split costs an indirection and buys three things:

- A policy that misbehaves produces bad metrics, not a misconfigured core.
- The gap between *intended* and *enforced* becomes a visible quantity — two
  different series on the same dashboard — instead of an invisible assumption.
- The write path can carry its own rate limiting, approval, or rollback without
  any of that logic contaminating the policy.

## The policy seam

```
             ┌──────────────────────────────────────┐
             │  SliceReconfigurationLoop            │
             │   read back → score → gate → decide  │
             └───────────────┬──────────────────────┘
                             │ SliceAllocationAgent
                             │ (1 attribute, 6 methods)
             ┌───────────────┴──────────────────────┐
             │                                      │
   ProportionalFairAgent                  a learned policy
   (ships here)                           (not included)
```

The loop holds no reference to Q-learning, to a Q-table, or to any notion of
training beyond calling `train_agent()` once at startup and handing whatever it
returns back on each decision. That opacity is what makes the policy
swappable — see [`agents/README.md`](../agents/README.md) for the contract.

## Metrics

| Series | |
| --- | --- |
| `slice_ambr_core_reported_bitrate` | What the core says it is enforcing |
| `slice_ambr_dynamic_bitrate` | What the policy chose |
| `slice_ambr_static_bitrate` | The never-changing counterfactual |
| `slice_ambr_demand` | Offered demand |
| `slice_ambr_acceptance_ratio_dynamic` | AR under the policy |
| `slice_ambr_acceptance_ratio_static` | AR under a fixed allocation |
| `slice_ambr_reconfigurations_total` | Writes the loop has asked for |
| `slice_ambr_iteration` | Liveness |

The static/dynamic pairing is deliberate. An acceptance ratio of 92% means
nothing on its own; 92% against 75% for the same demand under a fixed
allocation is the claim the system is actually making.
