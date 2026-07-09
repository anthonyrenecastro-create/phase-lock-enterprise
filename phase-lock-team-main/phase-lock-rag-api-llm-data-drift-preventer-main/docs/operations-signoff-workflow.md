# Operations Workflow: Approvals and Sign-off

## Workflow summary

1. Prepare release candidate and governance evidence.
2. Validate rollout plan and operational readiness.
3. Complete change approval according to matrix.
4. Execute staged rollout waves with sign-off at each promotion gate.
5. Close release with evidence archive and post-release review.

## Procedure

### Phase 1: Pre-approval package

- Run governance checks and retain summary output.
- Attach rollout plan validation output.
- Attach change scope and rollback plan.

### Phase 2: Approval

- Route change through approval matrix.
- Confirm required approvers signed before production execution.

### Phase 3: Wave execution

- Execute canary wave and soak.
- Record metrics and thresholds in sign-off template.
- Promote only after explicit approval for each wave.

### Phase 4: Post-release closure

- Archive sign-off template and governance artifacts.
- Open follow-up actions for any risk exceptions.
- Schedule post-release review within 2 business days.

## Required artifacts for closure

- Change approval record
- Completed release sign-off template
- Governance summary report
- Incident notes (if any)
