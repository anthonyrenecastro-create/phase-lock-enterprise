# Enterprise Feature Plan and Execution

This plan tracks delivery of:

- SSO
- HA deployment
- Kubernetes operator
- Air-gapped mode
- Policy engine

## 20-step implementation plan

1. Define target architecture and trust boundaries.
2. Lock non-functional requirements (SLO, RTO/RPO, scale, compliance).
3. Build dependency map and phased backlog.
4. Standardize runtime config and secret references.
5. Externalize state required for HA behavior.
6. Add provider-agnostic auth abstraction for API key and SSO modes.
7. Implement OIDC flow and token verification.
8. Add enterprise role/group mapping and least-privilege defaults.
9. Add SSO hardening controls (rotation, expiry, audit).
10. Remove sticky in-memory runtime assumptions.
11. Upgrade Kubernetes manifests for HA topology and graceful disruption.
12. Add HA for data dependencies.
13. Run resilience and failover test suite.
14. Define Kubernetes Operator CRDs and versioning strategy.
15. Implement operator reconcile loops and status conditions.
16. Add operator lifecycle safety (finalizers/rollback/webhooks).
17. Build air-gapped artifact supply chain with signing/SBOM.
18. Implement runtime air-gapped controls and offline operations.
19. Integrate policy engine with deny-by-default decisions.
20. Validate, package, and release through staged rollout waves.

## Execution status

- [x] Step 1 complete: target architecture and trust boundaries are documented.
- [x] Step 2 complete: non-functional requirements and governance gates are documented.
- [x] Step 3 complete: dependency map and phased backlog with ownership are documented.
- [x] Step 4 started: unified config model now includes auth, HA, air-gap, and policy modes.
- [x] Step 6 started: auth abstraction now supports api_key and oidc runtime modes.
- [x] Step 7 started: OIDC bearer tokens can now be validated against JWKS.
- [x] Step 7 advanced: full OIDC login + callback + session cookie flow is implemented.
- [x] Step 8 started: IdP group mapping to platform roles is now supported.
- [x] Step 13 started: HA disruption suite automation added for node drain, pod eviction, and dependency outage.
- [x] Step 11 started: Helm chart now includes HA topology settings and PodDisruptionBudget support.
- [x] Step 14 started: Kubernetes Operator CRD scaffold and sample custom resource are defined.
- [x] Step 15 started: operator reconcile loop now manages deployment/service desired state and status conditions.
- [x] Step 16 complete: operator lifecycle safety now includes finalizers, rollback to last-known-good, and webhook scaffold manifests.
- [x] Step 16 advanced: validating + conversion webhook server and rollout health gates are implemented.
- [x] Step 19 started: policy decision flow now routes through a backend-selectable decision function.
- [x] Step 19 advanced: OPA mode can now load local policy bundles for air-gapped use.
- [x] Step 5 complete: HA-required breaker/runtime state now uses atomic shared backend operations with health visibility.
- [x] Step 9 complete: OIDC session hardening now includes one-time state usage, bounded lifetime, rotation, and auth audit logging.
- [x] Step 10 complete: sticky tenant runtime assumptions are disabled by default with explicit cache opt-in control.
- [x] Step 12 complete: dependency HA now includes resilient Redis failover with in-memory continuity fallback mode.
- [x] Step 17 complete: signed bundle provenance pipeline now includes metadata, checksums, signature hooks, and verification script.
- [x] Step 18 complete: runtime air-gap controls now cover centralized egress allowlist policy and offline operator/runtime wiring.
- [x] Step 19 complete: policy engine now enforces deny-by-default fallback with audit logging and size-based retention rotation.
- [x] Steps 5, 9-10, 12 completion hardening finished.
- [x] Step 20 groundwork started: release-governance baseline gate script added for tests, helm render, and air-gap bundle generation.
- [x] Step 20 increment: CI-ready governance runner now writes timestamped report artifacts and machine-readable summary.
- [x] Step 20 increment: governance runner now verifies offline bundle provenance artifacts.
- [x] Step 20 complete: staged rollout-wave validation is now enforced as a release-governance gate.
- [x] External operations tranche started: incident response runbook, change approval matrix, and release sign-off workflow templates are defined.
- [x] External operations packet complete: release-ready packet and filled staging sign-off example are now in-repo.

### Step 5-20 status snapshot

- Step 17: complete (offline bundle, SBOM/checksum/signing hooks, and verification pipeline).
- Step 18: complete (runtime egress restrictions, allowlist controls, and offline operator wiring).
- Step 19: complete (policy mode routing, deny-by-default fallback, decision logs, and retention rotation).
- Step 20: complete for governance baseline (tests/template/airgap provenance + staged rollout-wave checks).
- Step 5: complete (shared backend state with atomic increments and health telemetry).
- Step 9: complete (session replay protection, bounded session lifetime, and auth audit logging).
- Step 10: complete (non-sticky runtime by default, optional cache toggle).
- Step 12: complete (Redis dependency failover with memory fallback continuity mode).

### Step 1-3 governance artifact references

- Step 1: docs/architecture-target-and-trust-boundaries.md
- Step 2: docs/non-functional-requirements-and-governance.md
- Step 3: docs/dependency-map-and-phased-backlog.md

### External operations artifact references

- Incident runbook: docs/operations-incident-runbook.md
- Approval matrix: docs/operations-change-approval-matrix.md
- Sign-off template: docs/operations-release-signoff-template.md
- Sign-off workflow: docs/operations-signoff-workflow.md
- Operations packet index: docs/operations-packet/README.md
- Staging sign-off example: docs/operations-packet/staging-signoff-example-2026-07-09.md
- Production sign-off example: docs/operations-packet/production-signoff-example-2026-07-09.md

## Immediate next execution tranche

- Execute first live tabletop using operations runbook and capture follow-up actions.
- Pilot approval/sign-off workflow in staging release window.
- Define report archival destination and retention enforcement automation.
