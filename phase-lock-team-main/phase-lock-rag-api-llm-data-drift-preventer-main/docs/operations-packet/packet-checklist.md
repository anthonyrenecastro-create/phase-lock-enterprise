# Packet Checklist

## Required before release window

- [ ] Governance report generated (`make governance` or `make governance-dry` for rehearsal)
- [ ] Rollout wave validation succeeded (`make rollout-plan-check`)
- [ ] Change approval obtained per approval matrix
- [ ] Incident commander and on-call roles assigned
- [ ] Rollback owner and rollback command path confirmed

## Required during release window

- [ ] Canary wave executed and soak complete
- [ ] Canary sign-off approved
- [ ] Regional wave executed and soak complete
- [ ] Regional sign-off approved
- [ ] Global wave executed and soak complete
- [ ] Final production sign-off approved

## Required after release window

- [ ] Final sign-off artifact archived
- [ ] Governance summary archived with sign-off
- [ ] Follow-up risks/action items logged
- [ ] Post-release review scheduled
