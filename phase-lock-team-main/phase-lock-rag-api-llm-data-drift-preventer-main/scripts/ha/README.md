# HA Disruption Suite

This suite automates resilience checks for Kubernetes HA deployment behavior.

## Covered scenarios

- Node drain for a node hosting a gateway pod
- Forced pod eviction and rollout recovery
- Optional dependency outage (scale dependency deployment to zero and recover)

## Usage

```bash
NAMESPACE=phaselock \
GATEWAY_LABEL=app=phase-lock-gateway \
GATEWAY_DEPLOYMENT=phase-lock-gateway \
DEPENDENCY_DEPLOYMENT=postgres \
DEPENDENCY_REPLICAS=1 \
bash scripts/ha/run_disruption_suite.sh
```

## Test integration

The integration test is skipped by default:

```bash
RUN_HA_TESTS=1 pytest -q tests/ha/test_disruption_suite.py
```
