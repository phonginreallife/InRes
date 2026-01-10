# InRes Helm Chart

## Quick Start

1. Copy the example config and customize:
```bash
cp cfg.ex.yaml config.yaml
# Edit config.yaml with your actual values
```

2. Create the Kubernetes secret:
```bash
kubectl create secret generic inres-secrets --from-file=config.yaml
```

3. Install the chart:
```bash
helm install inres . -f values.yaml
```

## Configuration

See `values.yaml` for all configurable options.

## Secrets

The chart expects a secret named `inres-secrets` containing:
- `config.yaml` - Main configuration file

For production, use proper secret management (e.g., Sealed Secrets, External Secrets).