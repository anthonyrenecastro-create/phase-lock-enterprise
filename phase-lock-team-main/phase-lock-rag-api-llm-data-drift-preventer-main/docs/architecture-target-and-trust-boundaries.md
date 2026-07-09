# Step 1: Target Architecture and Trust Boundaries

## Scope

This document defines the production target architecture, security domains, and trust boundaries for enterprise deployment of Phase-Lock Gateway.

## Target architecture

### Core components

- Edge ingress/API gateway
- Phase-Lock FastAPI service
- OIDC identity provider integration
- Policy engine (builtin or OPA)
- Shared state backend (Redis primary, in-process continuity fallback)
- Telemetry and log sinks
- Kubernetes operator/controller and webhook server

### Deployment topology

- Multi-replica gateway pods across zones
- PodDisruptionBudget and anti-affinity enabled
- Operator-managed deployment and service lifecycle
- Air-gapped mode with explicit egress allowlist controls

## Security domains

- Domain A: Public ingress and API clients
- Domain B: Cluster internal service mesh/network
- Domain C: Control plane and operator webhooks
- Domain D: Identity provider and policy dependencies
- Domain E: Artifact supply chain and governance reports

## Trust boundaries

### Boundary 1: Client to gateway

- Enforce API key or OIDC auth mode
- Validate payload schema and rate/cost controls
- Record auth and runtime audit events

### Boundary 2: Gateway to identity provider

- OIDC token verification and bounded session lifecycle
- One-time state token usage on callback
- Restrict outbound egress in air-gapped mode

### Boundary 3: Gateway to policy backend

- Deny-by-default fallback when OPA unavailable or blocked
- Decision logging with retention controls
- Optional local bundle path for offline policy mode

### Boundary 4: Gateway to shared state backend

- Atomic streak updates and revocation checks
- Redis failover and degraded continuity mode to memory
- Health exposed in service health endpoint

### Boundary 5: Operator/webhook to cluster API

- Finalizers for lifecycle safety
- Rollback to last-known-good reconcile state
- Conversion and validation webhook controls

## Data classification and handling

- Auth/session tokens: sensitive; never logged raw
- Decision logs: operational sensitive; retained with rotation
- Governance reports: controlled operational artifact
- Metrics and telemetry: low-to-medium sensitivity, tenant scoped

## Primary failure domains

- Identity provider outage
- Policy backend outage
- Redis dependency outage
- Node disruption / zone failure
- Admission webhook unavailability

## Required controls by domain

- Authentication: OIDC + API key controls
- Authorization: role/group mapping, least privilege
- Availability: multi-replica, disruption automation, dependency failover
- Integrity: signed air-gap artifacts and verification
- Auditability: auth/policy/governance report outputs

## Acceptance criteria for Step 1

- Architecture components and data flows are documented
- Trust boundaries and controls are explicit
- Failure domains and protections are identified
