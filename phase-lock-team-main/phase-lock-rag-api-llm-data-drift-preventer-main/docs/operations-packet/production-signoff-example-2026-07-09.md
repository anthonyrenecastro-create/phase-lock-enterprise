# Release Sign-off (Filled Example, Production)

## Release metadata

- Release ID: rel-prd-2026-07-09-01
- Date/time window: 2026-07-09 18:00-23:30 UTC
- Environment: production
- Operator on call: platform-oncall-2
- Incident commander: sre-ic-1

## Preconditions

- Governance checks: pass
- Rollout plan validation: pass
- Air-gap bundle verification (if applicable): pass
- Rollback strategy reviewed: yes

## Stricter production promotion criteria

- Canary error-rate threshold: 0.0070
- Canary p95 latency threshold: 320 ms
- Regional error-rate threshold: 0.0060
- Regional p95 latency threshold: 290 ms
- Global error-rate threshold: 0.0040
- Global p95 latency threshold: 260 ms

## Evidence links

- Governance summary: dist/release-governance/20260709-202130/summary.json
- Rollout validator output: [rollout-waves] validated 3 waves from docs/release-rollout-waves.json
- Change approval ticket: CHG-PRD-2026-0709-22
- Security review record: SEC-REV-2026-0709-09

## Wave sign-off

### Wave 1 (canary)

- Start time: 2026-07-09 18:10 UTC
- End time: 2026-07-09 18:55 UTC
- Error-rate threshold met: yes (observed 0.0027 <= 0.0070)
- Latency threshold met: yes (p95 241ms <= 320ms)
- Approval to promote: approved
- Approver: release-manager-1

### Wave 2 (regional)

- Start time: 2026-07-09 19:00 UTC
- End time: 2026-07-09 20:25 UTC
- Error-rate threshold met: yes (observed 0.0038 <= 0.0060)
- Latency threshold met: yes (p95 258ms <= 290ms)
- Approval to promote: approved
- Approver: sre-lead-1

### Wave 3 (global)

- Start time: 2026-07-09 20:30 UTC
- End time: 2026-07-09 22:55 UTC
- Error-rate threshold met: yes (observed 0.0031 <= 0.0040)
- Latency threshold met: yes (p95 246ms <= 260ms)
- Final production sign-off: approved
- Approver: vp-engineering-1

## Risk and exceptions

- Known risk accepted: brief metric-cardinality spike expected during regional wave expansion
- Mitigation owner: observability-lead-1
- Follow-up due date: 2026-07-14

## Final approval block (expanded production approver set)

- Release manager: release-manager-1 (approved)
- Platform approver: platform-lead-1 (approved)
- Security approver: security-lead-1 (approved)
- SRE approver: sre-lead-1 (approved)
- Product owner approver: product-director-1 (approved)
- Executive approver: vp-engineering-1 (approved)

## Post-release closure

- Packet archive path: dist/release-governance/20260709-202130/
- Post-release review scheduled: 2026-07-11 17:00 UTC
- Action items created: 3
