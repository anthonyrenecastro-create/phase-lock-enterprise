# Release Sign-off (Filled Example)

## Release metadata

- Release ID: rel-stg-2026-07-09-01
- Date/time window: 2026-07-09 14:00-17:30 UTC
- Environment: staging
- Operator on call: platform-oncall-1
- Incident commander: sre-ic-1

## Preconditions

- Governance checks: pass
- Rollout plan validation: pass
- Air-gap bundle verification (if applicable): pass
- Rollback strategy reviewed: yes

## Evidence links

- Governance summary: dist/release-governance/20260709-202130/summary.json
- Rollout validator output: [rollout-waves] validated 3 waves from docs/release-rollout-waves.json
- Change approval ticket: CHG-STG-2026-0709-14

## Wave sign-off

### Wave 1 (canary)

- Start time: 2026-07-09 14:10 UTC
- End time: 2026-07-09 14:45 UTC
- Error-rate threshold met: yes (observed 0.0032 <= 0.0100)
- Latency threshold met: yes (p95 286ms <= 400ms)
- Approval to promote: approved
- Approver: release-manager-1

### Wave 2 (regional)

- Start time: 2026-07-09 14:50 UTC
- End time: 2026-07-09 16:00 UTC
- Error-rate threshold met: yes (observed 0.0045 <= 0.0080)
- Latency threshold met: yes (p95 301ms <= 350ms)
- Approval to promote: approved
- Approver: sre-lead-1

### Wave 3 (global)

- Start time: 2026-07-09 16:05 UTC
- End time: 2026-07-09 17:20 UTC
- Error-rate threshold met: yes (observed 0.0039 <= 0.0050)
- Latency threshold met: yes (p95 274ms <= 300ms)
- Final production sign-off: approved for production readiness criteria
- Approver: platform-lead-1

## Risk and exceptions

- Known risk accepted: temporary elevated auth-audit volume due to onboarding load test
- Mitigation owner: security-ops-1
- Follow-up due date: 2026-07-12

## Final approval block

- Release manager: release-manager-1 (approved)
- Platform approver: platform-lead-1 (approved)
- Security approver (if required): security-lead-1 (approved)
- SRE approver: sre-lead-1 (approved)

## Post-release closure

- Packet archive path: dist/release-governance/20260709-202130/
- Post-release review scheduled: 2026-07-11 15:00 UTC
- Action items created: 2
