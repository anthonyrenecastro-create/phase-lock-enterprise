# Step 2: Non-Functional Requirements and Governance Baseline

## Objectives

- Define SLO, RTO/RPO, scale, and compliance targets
- Define release and operational governance requirements
- Establish measurable gates for production readiness

## Service-level objectives

- API availability target: 99.9% monthly
- Stabilize endpoint p95 latency target: under 300 ms under nominal load
- Auth/session endpoint p95 latency target: under 200 ms under nominal load
- Error budget policy: 0.1% monthly unavailability

## Recovery objectives

- RTO target: 30 minutes for regional service disruption
- RPO target: 5 minutes for shared-state and audit pipeline continuity
- Critical auth/path fallback: continue in degraded mode when Redis unavailable

## Scale assumptions

- Baseline sustained traffic: 100 requests/second per region
- Burst target: 300 requests/second per region for 15 minutes
- Horizontal scaling: stateless-by-default runtime with opt-in cache control

## Security and compliance controls

- OIDC session max lifetime enforced
- Login callback replay prevention enabled
- Auth and policy decision logs rotated and retained by policy
- Air-gap egress restrictions and allowlist controls
- Signed artifact provenance verification in release governance

## Governance gates

- Automated test suite pass
- Helm render pass
- Air-gap bundle build and verification pass
- Rollout waves schema validation pass
- Plan guard and release summary generation pass

## Operational governance requirements

- Incident runbook exists and is version controlled
- Change approval matrix is documented
- Release sign-off template completed before production wave promotion
- Post-release review recorded for each rollout window

## Step 2 acceptance criteria

- NFR targets are documented and testable
- Governance checks are mapped to commands/artifacts
- Operational ownership and sign-off requirements are defined
