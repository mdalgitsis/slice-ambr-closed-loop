# Deployment

## Prerequisites

- A Kubernetes cluster
- Prometheus, with the Prometheus Operator if you want the `ServiceMonitor`
- Grafana, if you want the dashboard installed automatically
- Network reachability from the cluster to the 5G core's management API

## Credentials

Neither chart accepts a credential through `values.yaml`. Both read from
Secrets you create, so nothing sensitive ends up in a values file, a git
history, or a `helm get values` output.

```bash
kubectl create secret generic raemis-creds \
  --from-literal=username=<user> \
  --from-literal=password=<pass>

kubectl create secret generic grafana-token \
  --from-literal=token=<grafana service account token>
```

The Grafana chart **fails to render** without `grafana.existingSecret`. That is
intentional — a dashboard installer that silently falls back to an unauthenticated
request just produces a confusing 401 later.

## The simulator

```bash
helm install slice-sim charts/slice-simulator \
  --set core.apiUrl=https://<core-host>:30443/api/subscription_profile \
  --set core.sliceProfileMap="0=6,1=7" \
  --set core.existingSecret=raemis-creds
```

`sliceProfileMap` maps this system's zero-based slice index to the subscription
profile id in your core. Get it wrong and the loop refuses to start rather than
driving the wrong profile:

```
ValueError: SLICE_PROFILE_MAP has no core profile for slice index(es) [1];
the agent allocates across 2 slices
```

### TLS

Lab cores commonly carry a self-signed certificate. `core.verifyTls=false`
turns verification off and the process logs a warning every start. Do not carry
that setting beyond a lab.

### Prometheus

`serviceMonitor.labels.release` must match whatever your Prometheus selects on.
If metrics do not appear, that label is the first thing to check — the
`ServiceMonitor` will exist and simply be ignored.

```bash
kubectl get servicemonitor -l app.kubernetes.io/name=slice-simulator
kubectl port-forward svc/slice-sim-slice-simulator 8999:8999
curl -s localhost:8999/metrics | grep slice_ambr
```

## The dashboard

```bash
helm install slice-dash charts/grafana-dashboard-manager \
  --set grafana.url=http://grafana.monitoring.svc.cluster.local:3000 \
  --set grafana.existingSecret=grafana-token
```

Installed as a `post-install`/`post-upgrade` hook and removed on `pre-delete`,
so the dashboard's lifecycle follows the release rather than drifting from it.
The panels reference a `DS_PROMETHEUS` datasource variable, so the same JSON
works on any Grafana instead of carrying one instance's datasource UID.

## Actuation

This deployment decides and publishes; it does not write to the core. To close
the loop in the network you need a patch controller consuming
`slice_ambr_dynamic_bitrate` and issuing the profile update. That component is
not part of this repository — see
[architecture](architecture.md#why-decision-and-actuation-are-separate) for
why it is kept separate.

Until one is wired up, the system runs as a live advisor: every decision is
visible on the dashboard next to the fixed-allocation counterfactual, and
nothing is written.

## Troubleshooting

| Symptom | Cause |
| --- | --- |
| `Error fetching AMBR for profile N` every iteration | Core unreachable or credentials wrong. The loop continues by design; check `RAEMIS_API_URL` and the Secret. |
| Loop starts, no metrics in Prometheus | `serviceMonitor.labels.release` does not match your Prometheus selector. |
| Reconfigures on every single iteration | The policy is returning allocations off the grid that `map_allocation_2_action` resolves against, so the read-back never round-trips. |
| `grafana.existingSecret is required` at install | Intended. Create the Secret. |
| Dashboard panels empty | Datasource variable unset on the dashboard, or the exporter is not being scraped. |
