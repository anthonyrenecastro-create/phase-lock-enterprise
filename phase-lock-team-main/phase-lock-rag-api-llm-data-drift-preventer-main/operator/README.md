# Phase-Lock Kubernetes Operator (Scaffold)

This directory provides an initial operator scaffold for managing enterprise deployments.

## Scope of this scaffold

- CRD shape for a `PhaseLockGateway` custom resource
- Sample manifest for cluster installation
- API fields for SSO, HA, air-gapped mode, and policy configuration
- Runtime wiring for air-gap allowlists and policy defaults/log paths
- Optional policy bundle ConfigMap mount for OPA bundle distribution
- Runtime toggle for sticky tenant cache behavior (`tenantRuntimeCacheEnabled`)
- OIDC session hardening env wiring (max lifetime + auth audit log retention)
- Reconcile rollback to last known good deployment/service state
- Admission webhook manifest scaffold for lifecycle safety
- Webhook server implementation for validation and version conversion
- Rollout health gate before controller reports resource as Ready

## Next implementation steps

1. Add operator e2e tests in a KinD or k3d cluster.
2. Add CRD version migration tests for conversion-webhook upgrade paths.
3. Add drift/policy chaos scenarios to the operator test suite.

## Controller runtime

Use either entrypoint to run the reconciler loop:

- `phase-lock-operator`
- `python operator/controller.py`

Run webhook server:

- `phase-lock-operator-webhook`
- `python operator/webhook_server.py`
