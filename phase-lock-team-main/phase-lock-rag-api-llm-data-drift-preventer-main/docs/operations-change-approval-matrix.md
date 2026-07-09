# Operations Governance: Change Approval Matrix

## Purpose

Defines required approvers and evidence for infrastructure, security, and release changes.

## Approval matrix

| Change type | Example | Required approvers | Required evidence |
| --- | --- | --- | --- |
| Runtime config low risk | Non-security env tuning | Engineering lead | Test pass, rollback plan |
| Runtime config high risk | Auth/session/policy settings | Engineering lead, Security lead | Test pass, threat impact review, rollback plan |
| Dependency topology | Redis/IdP/OPA endpoint change | Engineering lead, SRE lead | HA test output, failover verification |
| Operator/CRD change | Reconcile/webhook/schema changes | Platform lead, SRE lead | Staging rollout results, rollback validation |
| Release wave promotion | Canary to regional/global | Incident commander on duty, Release manager | Governance report, rollout validation, sign-off record |
| Emergency change | Sev 1 mitigation | Incident commander, one secondary approver | Incident timeline, post-change verification |

## Separation of duties

- Code author cannot be sole production approver
- Security-impacting changes require security approver
- Emergency changes require retrospective approval within 24 hours

## Evidence retention

- Store sign-off and governance summary with release artifacts
- Retain approval records for minimum 12 months
