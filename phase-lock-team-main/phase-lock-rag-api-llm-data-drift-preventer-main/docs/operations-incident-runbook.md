# Operations Runbook: Incident Response

## Purpose

Operational procedures for production incidents involving auth, policy, state backend, and rollout failures.

## Severity model

- Sev 1: customer-wide outage or security-impacting fault
- Sev 2: partial outage or sustained degradation
- Sev 3: non-critical degradation with workaround

## First 15 minutes checklist

- Declare incident commander
- Open incident channel and timeline
- Identify impacted services/endpoints
- Capture current health and governance status artifacts
- Assign comms owner and remediation owner

## Triage playbooks

### Auth/OIDC failure

- Confirm IdP availability and JWKS reachability
- Validate callback/session endpoints behavior
- Confirm session max lifetime and revocation behavior
- Check auth audit log continuity

### State backend degradation

- Check health endpoint state_backend metadata
- Confirm Redis failover/degraded memory continuity mode
- Validate spike streak and session revocation behavior

### Policy engine degradation

- Verify OPA endpoint or bundle availability
- Confirm deny-by-default fallback behavior
- Confirm decision log write and rotation state

### Rollout failure

- Pause wave promotion
- Confirm operator status and webhook health
- Verify rollback path and last-known-good state
- Re-run governance checks and rollout wave validator

## Communication expectations

- Sev 1 updates every 15 minutes
- Sev 2 updates every 30 minutes
- External status updates approved by incident commander

## Exit criteria

- Service restored to SLO thresholds
- Mitigation validated and monitored for one full soak window
- Root cause and follow-up actions recorded

## Post-incident actions

- Publish postmortem within 2 business days
- Add preventive action items to backlog with owners
- Update runbook if detection/remediation gaps found
