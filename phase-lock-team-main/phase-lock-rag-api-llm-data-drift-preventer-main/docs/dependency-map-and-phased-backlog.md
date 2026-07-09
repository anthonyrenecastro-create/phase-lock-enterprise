# Step 3: Dependency Map and Phased Backlog

## Dependency map

### Runtime dependencies

- FastAPI service runtime
- Rust stabilization engine extension
- Redis for shared state (preferred)
- Identity provider (OIDC endpoints/JWKS)
- Optional OPA policy endpoint

### Platform dependencies

- Kubernetes API and scheduler
- Helm chart and values configuration
- Operator controller and webhook server

### Release dependencies

- Air-gap bundle tooling
- SBOM/signature/provenance verification path
- Governance checks and report generation

## Dependency criticality

- Tier 0 (critical): gateway, auth path, policy fallback, state backend continuity
- Tier 1 (high): operator reconcile path, webhook availability, telemetry
- Tier 2 (supporting): offline bundle generation, governance report archival

## Failure impact and fallback summary

- Redis unavailable: degrade to memory continuity mode and surface degraded health
- OPA unavailable: deny-by-default fallback decision path
- IdP unavailable: no new session issuance; existing valid sessions continue until expiry
- Webhook unavailable: rollout blocked by control-plane policy until recovered

## Phased backlog (post-implementation operationalization)

### Phase A: Operational readiness (immediate)

- Finalize runbooks and pager ownership
- Execute game day for Redis and IdP outage scenarios
- Validate change approval and sign-off workflow in staging

### Phase B: Production launch controls

- Enforce mandatory sign-off artifact per release window
- Store governance reports in immutable artifact location
- Add alert thresholds tied to SLO and degraded backend states

### Phase C: Continuous assurance

- Quarterly trust-boundary review and threat model refresh
- Semiannual disaster recovery drill and RTO/RPO verification
- Annual compliance evidence review for auth/policy/audit controls

## Ownership model

- Platform team: operator, deployment, and HA controls
- Security team: auth, policy, and trust boundary controls
- SRE team: on-call runbooks, incident response, and postmortems
- Product engineering: feature-level reliability and policy behavior

## Step 3 acceptance criteria

- Dependencies and fallback behavior are explicitly documented
- Backlog phases are sequenced with ownership
- Operationalization tasks are linked to governance artifacts
