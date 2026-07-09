from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from secrets import token_urlsafe
from threading import Lock, RLock
from typing import Protocol
from uuid import uuid4

try:
    import psycopg
except ImportError:  # pragma: no cover - exercised when dependency is missing
    psycopg = None


Role = str
ROLE_RANK: dict[Role, int] = {
    "viewer": 10,
    "analyst": 20,
    "admin": 30,
    "owner": 40,
}


DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/phaselock"


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_now_iso() -> str:
    return utc_now().isoformat()


def _dt_to_iso(value: datetime | str) -> str:
    if isinstance(value, datetime):
        return value.astimezone(UTC).isoformat()
    return value


@dataclass(frozen=True)
class Organization:
    org_id: str
    name: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class Workspace:
    workspace_id: str
    org_id: str
    name: str
    created_by: str
    created_at: str


@dataclass(frozen=True)
class Membership:
    org_id: str
    user_id: str
    role: Role
    created_at: str


@dataclass(frozen=True)
class ApiKeyRecord:
    key_id: str
    workspace_id: str
    name: str
    key_prefix: str
    key_hash: str
    created_by: str
    created_at: str
    revoked: bool
    use_count: int = 0
    last_used_at: str | None = None


@dataclass(frozen=True)
class AuditEvent:
    event_id: str
    org_id: str
    workspace_id: str | None
    actor_user_id: str
    action: str
    resource_type: str
    resource_id: str
    at: str
    request_id: str | None = None
    drift_score: float | None = None
    prevented_incident: bool | None = None
    api_key_id: str | None = None
    corrected: bool | None = None
    risk_level: str | None = None


@dataclass(frozen=True)
class DriftTrendPoint:
    bucket: str
    avg_drift_score: float
    request_count: int


@dataclass(frozen=True)
class ApiKeyUsage:
    key_id: str
    name: str
    revoked: bool
    use_count: int
    last_used_at: str | None


@dataclass(frozen=True)
class TeamActivity:
    actor_user_id: str
    action: str
    resource_type: str
    resource_id: str
    at: str


class TeamStoreProtocol(Protocol):
    def reset(self) -> None: ...

    def create_org(self, name: str, created_by: str) -> Organization: ...

    def get_org(self, org_id: str) -> Organization | None: ...

    def role_for(self, org_id: str, user_id: str) -> Role | None: ...

    def has_role_at_least(self, org_id: str, user_id: str, minimum_role: Role) -> bool: ...

    def add_member(self, org_id: str, actor_user_id: str, user_id: str, role: Role) -> Membership: ...

    def list_members(self, org_id: str) -> list[Membership]: ...

    def create_workspace(self, org_id: str, actor_user_id: str, name: str) -> Workspace: ...

    def get_workspace(self, workspace_id: str) -> Workspace | None: ...

    def create_api_key(self, workspace_id: str, actor_user_id: str, name: str) -> tuple[ApiKeyRecord, str]: ...

    def list_api_keys(self, workspace_id: str) -> list[ApiKeyRecord]: ...

    def get_api_key(self, key_id: str) -> ApiKeyRecord | None: ...

    def revoke_api_key(self, workspace_id: str, key_id: str, actor_user_id: str) -> ApiKeyRecord: ...

    def list_audit_events(self, org_id: str, workspace_id: str | None = None) -> list[AuditEvent]: ...

    def record_runtime_event(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: str,
        request_id: str,
        drift_score: float | None = None,
        prevented_incident: bool | None = None,
        api_key_id: str | None = None,
        corrected: bool | None = None,
        risk_level: str | None = None,
    ) -> AuditEvent: ...

    def workspace_analytics(self, workspace_id: str, window_hours: int = 24) -> dict[str, object]: ...

    def org_team_activity(self, org_id: str, window_hours: int = 24, limit: int = 100) -> list[TeamActivity]: ...


class InMemoryTeamStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._orgs: dict[str, Organization] = {}
        self._workspaces: dict[str, Workspace] = {}
        self._memberships: dict[tuple[str, str], Membership] = {}
        self._api_keys: dict[str, ApiKeyRecord] = {}
        self._audit_events: list[AuditEvent] = []

    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    def _record_audit(
        self,
        org_id: str,
        actor_user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        workspace_id: str | None = None,
        request_id: str | None = None,
        drift_score: float | None = None,
        prevented_incident: bool | None = None,
        api_key_id: str | None = None,
        corrected: bool | None = None,
        risk_level: str | None = None,
    ) -> AuditEvent:
        event = AuditEvent(
            event_id=self._id("evt"),
            org_id=org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            at=utc_now_iso(),
            request_id=request_id,
            drift_score=drift_score,
            prevented_incident=prevented_incident,
            api_key_id=api_key_id,
            corrected=corrected,
            risk_level=risk_level,
        )
        self._audit_events.append(event)
        return event

    def reset(self) -> None:
        with self._lock:
            self._orgs = {}
            self._workspaces = {}
            self._memberships = {}
            self._api_keys = {}
            self._audit_events = []

    def create_org(self, name: str, created_by: str) -> Organization:
        with self._lock:
            org = Organization(
                org_id=self._id("org"),
                name=name,
                created_by=created_by,
                created_at=utc_now_iso(),
            )
            self._orgs[org.org_id] = org
            self._memberships[(org.org_id, created_by)] = Membership(
                org_id=org.org_id,
                user_id=created_by,
                role="owner",
                created_at=utc_now_iso(),
            )
            self._record_audit(
                org_id=org.org_id,
                actor_user_id=created_by,
                action="org.created",
                resource_type="organization",
                resource_id=org.org_id,
            )
            return org

    def get_org(self, org_id: str) -> Organization | None:
        with self._lock:
            return self._orgs.get(org_id)

    def role_for(self, org_id: str, user_id: str) -> Role | None:
        with self._lock:
            member = self._memberships.get((org_id, user_id))
            return None if member is None else member.role

    def has_role_at_least(self, org_id: str, user_id: str, minimum_role: Role) -> bool:
        role = self.role_for(org_id, user_id)
        if role is None:
            return False
        return ROLE_RANK[role] >= ROLE_RANK[minimum_role]

    def add_member(self, org_id: str, actor_user_id: str, user_id: str, role: Role) -> Membership:
        if role not in ROLE_RANK:
            raise ValueError("Invalid role")
        with self._lock:
            if org_id not in self._orgs:
                raise KeyError("Organization not found")
            membership = Membership(org_id=org_id, user_id=user_id, role=role, created_at=utc_now_iso())
            self._memberships[(org_id, user_id)] = membership
            self._record_audit(
                org_id=org_id,
                actor_user_id=actor_user_id,
                action="member.upserted",
                resource_type="membership",
                resource_id=f"{org_id}:{user_id}",
            )
            return membership

    def list_members(self, org_id: str) -> list[Membership]:
        with self._lock:
            members = [m for m in self._memberships.values() if m.org_id == org_id]
            return sorted(members, key=lambda m: (m.role, m.user_id))

    def create_workspace(self, org_id: str, actor_user_id: str, name: str) -> Workspace:
        with self._lock:
            if org_id not in self._orgs:
                raise KeyError("Organization not found")
            workspace = Workspace(
                workspace_id=self._id("wsp"),
                org_id=org_id,
                name=name,
                created_by=actor_user_id,
                created_at=utc_now_iso(),
            )
            self._workspaces[workspace.workspace_id] = workspace
            self._record_audit(
                org_id=org_id,
                workspace_id=workspace.workspace_id,
                actor_user_id=actor_user_id,
                action="workspace.created",
                resource_type="workspace",
                resource_id=workspace.workspace_id,
            )
            return workspace

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self._lock:
            return self._workspaces.get(workspace_id)

    def create_api_key(self, workspace_id: str, actor_user_id: str, name: str) -> tuple[ApiKeyRecord, str]:
        with self._lock:
            workspace = self._workspaces.get(workspace_id)
            if workspace is None:
                raise KeyError("Workspace not found")

            raw_key = "plk_" + token_urlsafe(24)
            record = ApiKeyRecord(
                key_id=self._id("key"),
                workspace_id=workspace_id,
                name=name,
                key_prefix=raw_key[:10],
                key_hash=sha256(raw_key.encode("utf-8")).hexdigest(),
                created_by=actor_user_id,
                created_at=utc_now_iso(),
                revoked=False,
            )
            self._api_keys[record.key_id] = record
            self._record_audit(
                org_id=workspace.org_id,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action="api_key.created",
                resource_type="api_key",
                resource_id=record.key_id,
            )
            return record, raw_key

    def list_api_keys(self, workspace_id: str) -> list[ApiKeyRecord]:
        with self._lock:
            keys = [k for k in self._api_keys.values() if k.workspace_id == workspace_id]
            return sorted(keys, key=lambda k: k.created_at)

    def get_api_key(self, key_id: str) -> ApiKeyRecord | None:
        with self._lock:
            return self._api_keys.get(key_id)

    def revoke_api_key(self, workspace_id: str, key_id: str, actor_user_id: str) -> ApiKeyRecord:
        with self._lock:
            workspace = self._workspaces.get(workspace_id)
            if workspace is None:
                raise KeyError("Workspace not found")
            key = self._api_keys.get(key_id)
            if key is None or key.workspace_id != workspace_id:
                raise KeyError("API key not found")

            revoked = ApiKeyRecord(
                key_id=key.key_id,
                workspace_id=key.workspace_id,
                name=key.name,
                key_prefix=key.key_prefix,
                key_hash=key.key_hash,
                created_by=key.created_by,
                created_at=key.created_at,
                revoked=True,
                use_count=key.use_count,
                last_used_at=key.last_used_at,
            )
            self._api_keys[key_id] = revoked
            self._record_audit(
                org_id=workspace.org_id,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action="api_key.revoked",
                resource_type="api_key",
                resource_id=key_id,
            )
            return revoked

    def list_audit_events(self, org_id: str, workspace_id: str | None = None) -> list[AuditEvent]:
        with self._lock:
            events = [e for e in self._audit_events if e.org_id == org_id]
            if workspace_id is not None:
                events = [e for e in events if e.workspace_id == workspace_id]
            return sorted(events, key=lambda e: e.at, reverse=True)

    def record_runtime_event(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: str,
        request_id: str,
        drift_score: float | None = None,
        prevented_incident: bool | None = None,
        api_key_id: str | None = None,
        corrected: bool | None = None,
        risk_level: str | None = None,
    ) -> AuditEvent:
        with self._lock:
            workspace = self._workspaces.get(workspace_id)
            if workspace is None:
                raise KeyError("Workspace not found")
            if api_key_id is not None and api_key_id in self._api_keys:
                key = self._api_keys[api_key_id]
                self._api_keys[api_key_id] = ApiKeyRecord(
                    key_id=key.key_id,
                    workspace_id=key.workspace_id,
                    name=key.name,
                    key_prefix=key.key_prefix,
                    key_hash=key.key_hash,
                    created_by=key.created_by,
                    created_at=key.created_at,
                    revoked=key.revoked,
                    use_count=key.use_count + 1,
                    last_used_at=utc_now_iso(),
                )
            return self._record_audit(
                org_id=workspace.org_id,
                workspace_id=workspace_id,
                actor_user_id=actor_user_id,
                action=action,
                resource_type="runtime",
                resource_id=request_id,
                request_id=request_id,
                drift_score=drift_score,
                prevented_incident=prevented_incident,
                api_key_id=api_key_id,
                corrected=corrected,
                risk_level=risk_level,
            )

    def workspace_analytics(self, workspace_id: str, window_hours: int = 24) -> dict[str, object]:
        with self._lock:
            ws = self._workspaces.get(workspace_id)
            if ws is None:
                raise KeyError("Workspace not found")

            cutoff = utc_now().timestamp() - (window_hours * 3600)
            scoped = [
                e
                for e in self._audit_events
                if e.workspace_id == workspace_id and datetime.fromisoformat(e.at).timestamp() >= cutoff
            ]
            stabilize = [e for e in scoped if e.action == "stabilize.request" and e.drift_score is not None]
            prevented = [e for e in stabilize if e.prevented_incident]
            feedback = [e for e in scoped if e.action == "feedback.received"]

            by_hour: dict[str, list[float]] = {}
            for event in stabilize:
                bucket = event.at[:13] + ":00:00+00:00"
                by_hour.setdefault(bucket, []).append(float(event.drift_score or 0.0))

            trend = [
                DriftTrendPoint(
                    bucket=bucket,
                    avg_drift_score=(sum(scores) / len(scores)) if scores else 0.0,
                    request_count=len(scores),
                )
                for bucket, scores in sorted(by_hour.items())
            ]

            key_usage = [
                ApiKeyUsage(
                    key_id=k.key_id,
                    name=k.name,
                    revoked=k.revoked,
                    use_count=k.use_count,
                    last_used_at=k.last_used_at,
                )
                for k in self.list_api_keys(workspace_id)
            ]

            team_activity = [
                TeamActivity(
                    actor_user_id=e.actor_user_id,
                    action=e.action,
                    resource_type=e.resource_type,
                    resource_id=e.resource_id,
                    at=e.at,
                )
                for e in sorted(scoped, key=lambda x: x.at, reverse=True)[:50]
            ]

            return {
                "workspace_id": workspace_id,
                "org_id": ws.org_id,
                "window_hours": window_hours,
                "drift_trend": [t.__dict__ for t in trend],
                "incident_preventions": {
                    "total": len(prevented),
                    "rate": (len(prevented) / len(stabilize)) if stabilize else 0.0,
                },
                "key_usage": [k.__dict__ for k in key_usage],
                "team_activity": [a.__dict__ for a in team_activity],
                "feedback_total": len(feedback),
            }

    def org_team_activity(self, org_id: str, window_hours: int = 24, limit: int = 100) -> list[TeamActivity]:
        with self._lock:
            cutoff = utc_now().timestamp() - (window_hours * 3600)
            events = [
                e
                for e in self._audit_events
                if e.org_id == org_id and datetime.fromisoformat(e.at).timestamp() >= cutoff
            ]
            events = sorted(events, key=lambda x: x.at, reverse=True)[:limit]
            return [
                TeamActivity(
                    actor_user_id=e.actor_user_id,
                    action=e.action,
                    resource_type=e.resource_type,
                    resource_id=e.resource_id,
                    at=e.at,
                )
                for e in events
            ]


class PostgresTeamStore:
    def __init__(self, database_url: str) -> None:
        if psycopg is None:
            raise RuntimeError("psycopg is required for Postgres persistence")
        self.database_url = database_url
        self._ensure_schema()

    def _conn(self):
        return psycopg.connect(self.database_url)

    def _id(self, prefix: str) -> str:
        return f"{prefix}_{uuid4().hex[:12]}"

    def _ensure_schema(self) -> None:
        ddl = """
        CREATE TABLE IF NOT EXISTS organizations (
            org_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS workspaces (
            workspace_id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE TABLE IF NOT EXISTS memberships (
            org_id TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (org_id, user_id)
        );
        CREATE TABLE IF NOT EXISTS api_keys (
            key_id TEXT PRIMARY KEY,
            workspace_id TEXT NOT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            key_prefix TEXT NOT NULL,
            key_hash TEXT NOT NULL,
            created_by TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked BOOLEAN NOT NULL DEFAULT FALSE,
            use_count BIGINT NOT NULL DEFAULT 0,
            last_used_at TIMESTAMPTZ NULL
        );
        CREATE TABLE IF NOT EXISTS audit_events (
            event_id TEXT PRIMARY KEY,
            org_id TEXT NOT NULL REFERENCES organizations(org_id) ON DELETE CASCADE,
            workspace_id TEXT NULL REFERENCES workspaces(workspace_id) ON DELETE CASCADE,
            actor_user_id TEXT NOT NULL,
            action TEXT NOT NULL,
            resource_type TEXT NOT NULL,
            resource_id TEXT NOT NULL,
            request_id TEXT NULL,
            drift_score DOUBLE PRECISION NULL,
            prevented_incident BOOLEAN NULL,
            api_key_id TEXT NULL,
            corrected BOOLEAN NULL,
            risk_level TEXT NULL,
            at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        CREATE INDEX IF NOT EXISTS idx_audit_workspace_time ON audit_events(workspace_id, at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_org_time ON audit_events(org_id, at DESC);
        CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action);
        """
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()

    def reset(self) -> None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("TRUNCATE TABLE audit_events, api_keys, memberships, workspaces, organizations CASCADE")
            conn.commit()

    def _record_audit(
        self,
        *,
        org_id: str,
        actor_user_id: str,
        action: str,
        resource_type: str,
        resource_id: str,
        workspace_id: str | None = None,
        request_id: str | None = None,
        drift_score: float | None = None,
        prevented_incident: bool | None = None,
        api_key_id: str | None = None,
        corrected: bool | None = None,
        risk_level: str | None = None,
    ) -> AuditEvent:
        event_id = self._id("evt")
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO audit_events (
                        event_id, org_id, workspace_id, actor_user_id, action, resource_type, resource_id,
                        request_id, drift_score, prevented_incident, api_key_id, corrected, risk_level
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING at
                    """,
                    (
                        event_id,
                        org_id,
                        workspace_id,
                        actor_user_id,
                        action,
                        resource_type,
                        resource_id,
                        request_id,
                        drift_score,
                        prevented_incident,
                        api_key_id,
                        corrected,
                        risk_level,
                    ),
                )
                at = cur.fetchone()[0]
            conn.commit()
        return AuditEvent(
            event_id=event_id,
            org_id=org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            at=_dt_to_iso(at),
            request_id=request_id,
            drift_score=drift_score,
            prevented_incident=prevented_incident,
            api_key_id=api_key_id,
            corrected=corrected,
            risk_level=risk_level,
        )

    def create_org(self, name: str, created_by: str) -> Organization:
        org_id = self._id("org")
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO organizations (org_id, name, created_by) VALUES (%s, %s, %s) RETURNING created_at",
                    (org_id, name, created_by),
                )
                created_at = cur.fetchone()[0]
                cur.execute(
                    "INSERT INTO memberships (org_id, user_id, role) VALUES (%s, %s, %s)",
                    (org_id, created_by, "owner"),
                )
            conn.commit()
        self._record_audit(
            org_id=org_id,
            actor_user_id=created_by,
            action="org.created",
            resource_type="organization",
            resource_id=org_id,
        )
        return Organization(org_id=org_id, name=name, created_by=created_by, created_at=_dt_to_iso(created_at))

    def get_org(self, org_id: str) -> Organization | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT org_id, name, created_by, created_at FROM organizations WHERE org_id = %s",
                    (org_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return Organization(org_id=row[0], name=row[1], created_by=row[2], created_at=_dt_to_iso(row[3]))

    def role_for(self, org_id: str, user_id: str) -> Role | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT role FROM memberships WHERE org_id = %s AND user_id = %s",
                    (org_id, user_id),
                )
                row = cur.fetchone()
        return None if row is None else str(row[0])

    def has_role_at_least(self, org_id: str, user_id: str, minimum_role: Role) -> bool:
        role = self.role_for(org_id, user_id)
        if role is None:
            return False
        return ROLE_RANK[role] >= ROLE_RANK[minimum_role]

    def add_member(self, org_id: str, actor_user_id: str, user_id: str, role: Role) -> Membership:
        if role not in ROLE_RANK:
            raise ValueError("Invalid role")
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM organizations WHERE org_id = %s", (org_id,))
                if cur.fetchone() is None:
                    raise KeyError("Organization not found")
                cur.execute(
                    """
                    INSERT INTO memberships (org_id, user_id, role)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (org_id, user_id)
                    DO UPDATE SET role = EXCLUDED.role
                    RETURNING created_at
                    """,
                    (org_id, user_id, role),
                )
                created_at = cur.fetchone()[0]
            conn.commit()
        self._record_audit(
            org_id=org_id,
            actor_user_id=actor_user_id,
            action="member.upserted",
            resource_type="membership",
            resource_id=f"{org_id}:{user_id}",
        )
        return Membership(org_id=org_id, user_id=user_id, role=role, created_at=_dt_to_iso(created_at))

    def list_members(self, org_id: str) -> list[Membership]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT org_id, user_id, role, created_at FROM memberships WHERE org_id = %s ORDER BY role, user_id",
                    (org_id,),
                )
                rows = cur.fetchall()
        return [Membership(org_id=r[0], user_id=r[1], role=r[2], created_at=_dt_to_iso(r[3])) for r in rows]

    def create_workspace(self, org_id: str, actor_user_id: str, name: str) -> Workspace:
        workspace_id = self._id("wsp")
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT 1 FROM organizations WHERE org_id = %s", (org_id,))
                if cur.fetchone() is None:
                    raise KeyError("Organization not found")
                cur.execute(
                    """
                    INSERT INTO workspaces (workspace_id, org_id, name, created_by)
                    VALUES (%s, %s, %s, %s)
                    RETURNING created_at
                    """,
                    (workspace_id, org_id, name, actor_user_id),
                )
                created_at = cur.fetchone()[0]
            conn.commit()
        self._record_audit(
            org_id=org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action="workspace.created",
            resource_type="workspace",
            resource_id=workspace_id,
        )
        return Workspace(
            workspace_id=workspace_id,
            org_id=org_id,
            name=name,
            created_by=actor_user_id,
            created_at=_dt_to_iso(created_at),
        )

    def get_workspace(self, workspace_id: str) -> Workspace | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT workspace_id, org_id, name, created_by, created_at FROM workspaces WHERE workspace_id = %s",
                    (workspace_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return Workspace(
            workspace_id=row[0],
            org_id=row[1],
            name=row[2],
            created_by=row[3],
            created_at=_dt_to_iso(row[4]),
        )

    def create_api_key(self, workspace_id: str, actor_user_id: str, name: str) -> tuple[ApiKeyRecord, str]:
        raw_key = "plk_" + token_urlsafe(24)
        key_id = self._id("key")
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT org_id FROM workspaces WHERE workspace_id = %s", (workspace_id,))
                row = cur.fetchone()
                if row is None:
                    raise KeyError("Workspace not found")
                org_id = row[0]
                cur.execute(
                    """
                    INSERT INTO api_keys (key_id, workspace_id, name, key_prefix, key_hash, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING created_at, revoked, use_count, last_used_at
                    """,
                    (key_id, workspace_id, name, raw_key[:10], sha256(raw_key.encode("utf-8")).hexdigest(), actor_user_id),
                )
                created_at, revoked, use_count, last_used_at = cur.fetchone()
            conn.commit()
        self._record_audit(
            org_id=org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action="api_key.created",
            resource_type="api_key",
            resource_id=key_id,
        )
        return (
            ApiKeyRecord(
                key_id=key_id,
                workspace_id=workspace_id,
                name=name,
                key_prefix=raw_key[:10],
                key_hash=sha256(raw_key.encode("utf-8")).hexdigest(),
                created_by=actor_user_id,
                created_at=_dt_to_iso(created_at),
                revoked=bool(revoked),
                use_count=int(use_count),
                last_used_at=None if last_used_at is None else _dt_to_iso(last_used_at),
            ),
            raw_key,
        )

    def list_api_keys(self, workspace_id: str) -> list[ApiKeyRecord]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key_id, workspace_id, name, key_prefix, key_hash, created_by, created_at, revoked, use_count, last_used_at
                    FROM api_keys
                    WHERE workspace_id = %s
                    ORDER BY created_at
                    """,
                    (workspace_id,),
                )
                rows = cur.fetchall()
        return [
            ApiKeyRecord(
                key_id=r[0],
                workspace_id=r[1],
                name=r[2],
                key_prefix=r[3],
                key_hash=r[4],
                created_by=r[5],
                created_at=_dt_to_iso(r[6]),
                revoked=bool(r[7]),
                use_count=int(r[8]),
                last_used_at=None if r[9] is None else _dt_to_iso(r[9]),
            )
            for r in rows
        ]

    def get_api_key(self, key_id: str) -> ApiKeyRecord | None:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT key_id, workspace_id, name, key_prefix, key_hash, created_by, created_at, revoked, use_count, last_used_at
                    FROM api_keys
                    WHERE key_id = %s
                    """,
                    (key_id,),
                )
                r = cur.fetchone()
        if r is None:
            return None
        return ApiKeyRecord(
            key_id=r[0],
            workspace_id=r[1],
            name=r[2],
            key_prefix=r[3],
            key_hash=r[4],
            created_by=r[5],
            created_at=_dt_to_iso(r[6]),
            revoked=bool(r[7]),
            use_count=int(r[8]),
            last_used_at=None if r[9] is None else _dt_to_iso(r[9]),
        )

    def revoke_api_key(self, workspace_id: str, key_id: str, actor_user_id: str) -> ApiKeyRecord:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT org_id FROM workspaces WHERE workspace_id = %s", (workspace_id,))
                ws_row = cur.fetchone()
                if ws_row is None:
                    raise KeyError("Workspace not found")
                org_id = ws_row[0]
                cur.execute(
                    """
                    UPDATE api_keys
                    SET revoked = TRUE
                    WHERE key_id = %s AND workspace_id = %s
                    RETURNING key_id, workspace_id, name, key_prefix, key_hash, created_by, created_at, revoked, use_count, last_used_at
                    """,
                    (key_id, workspace_id),
                )
                row = cur.fetchone()
                if row is None:
                    raise KeyError("API key not found")
            conn.commit()
        self._record_audit(
            org_id=org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action="api_key.revoked",
            resource_type="api_key",
            resource_id=key_id,
        )
        return ApiKeyRecord(
            key_id=row[0],
            workspace_id=row[1],
            name=row[2],
            key_prefix=row[3],
            key_hash=row[4],
            created_by=row[5],
            created_at=_dt_to_iso(row[6]),
            revoked=bool(row[7]),
            use_count=int(row[8]),
            last_used_at=None if row[9] is None else _dt_to_iso(row[9]),
        )

    def list_audit_events(self, org_id: str, workspace_id: str | None = None) -> list[AuditEvent]:
        query = (
            "SELECT event_id, org_id, workspace_id, actor_user_id, action, resource_type, resource_id, "
            "request_id, drift_score, prevented_incident, api_key_id, corrected, risk_level, at "
            "FROM audit_events WHERE org_id = %s"
        )
        params: list[object] = [org_id]
        if workspace_id is not None:
            query += " AND workspace_id = %s"
            params.append(workspace_id)
        query += " ORDER BY at DESC"

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, tuple(params))
                rows = cur.fetchall()
        return [
            AuditEvent(
                event_id=r[0],
                org_id=r[1],
                workspace_id=r[2],
                actor_user_id=r[3],
                action=r[4],
                resource_type=r[5],
                resource_id=r[6],
                request_id=r[7],
                drift_score=r[8],
                prevented_incident=r[9],
                api_key_id=r[10],
                corrected=r[11],
                risk_level=r[12],
                at=_dt_to_iso(r[13]),
            )
            for r in rows
        ]

    def record_runtime_event(
        self,
        *,
        workspace_id: str,
        actor_user_id: str,
        action: str,
        request_id: str,
        drift_score: float | None = None,
        prevented_incident: bool | None = None,
        api_key_id: str | None = None,
        corrected: bool | None = None,
        risk_level: str | None = None,
    ) -> AuditEvent:
        workspace = self.get_workspace(workspace_id)
        if workspace is None:
            raise KeyError("Workspace not found")

        if api_key_id is not None:
            with self._conn() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE api_keys
                        SET use_count = use_count + 1, last_used_at = NOW()
                        WHERE key_id = %s AND workspace_id = %s
                        """,
                        (api_key_id, workspace_id),
                    )
                conn.commit()

        return self._record_audit(
            org_id=workspace.org_id,
            workspace_id=workspace_id,
            actor_user_id=actor_user_id,
            action=action,
            resource_type="runtime",
            resource_id=request_id,
            request_id=request_id,
            drift_score=drift_score,
            prevented_incident=prevented_incident,
            api_key_id=api_key_id,
            corrected=corrected,
            risk_level=risk_level,
        )

    def workspace_analytics(self, workspace_id: str, window_hours: int = 24) -> dict[str, object]:
        workspace = self.get_workspace(workspace_id)
        if workspace is None:
            raise KeyError("Workspace not found")

        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT date_trunc('hour', at) AS bucket,
                           AVG(drift_score) AS avg_drift_score,
                           COUNT(*) AS request_count
                    FROM audit_events
                    WHERE workspace_id = %s
                      AND action = 'stabilize.request'
                      AND drift_score IS NOT NULL
                      AND at >= NOW() - (%s || ' hours')::interval
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    (workspace_id, window_hours),
                )
                trend_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT
                        COUNT(*) FILTER (WHERE action = 'stabilize.request' AND prevented_incident = TRUE) AS prevented_total,
                        COUNT(*) FILTER (WHERE action = 'stabilize.request') AS stabilize_total,
                        COUNT(*) FILTER (WHERE action = 'feedback.received') AS feedback_total
                    FROM audit_events
                    WHERE workspace_id = %s
                      AND at >= NOW() - (%s || ' hours')::interval
                    """,
                    (workspace_id, window_hours),
                )
                prevented_total, stabilize_total, feedback_total = cur.fetchone()

                cur.execute(
                    """
                    SELECT key_id, name, revoked, use_count, last_used_at
                    FROM api_keys
                    WHERE workspace_id = %s
                    ORDER BY created_at
                    """,
                    (workspace_id,),
                )
                key_rows = cur.fetchall()

                cur.execute(
                    """
                    SELECT actor_user_id, action, resource_type, resource_id, at
                    FROM audit_events
                    WHERE workspace_id = %s
                      AND at >= NOW() - (%s || ' hours')::interval
                    ORDER BY at DESC
                    LIMIT 100
                    """,
                    (workspace_id, window_hours),
                )
                activity_rows = cur.fetchall()

        trend = [
            DriftTrendPoint(bucket=_dt_to_iso(r[0]), avg_drift_score=float(r[1] or 0.0), request_count=int(r[2]))
            for r in trend_rows
        ]
        key_usage = [
            ApiKeyUsage(
                key_id=r[0],
                name=r[1],
                revoked=bool(r[2]),
                use_count=int(r[3]),
                last_used_at=None if r[4] is None else _dt_to_iso(r[4]),
            )
            for r in key_rows
        ]
        team_activity = [
            TeamActivity(
                actor_user_id=r[0],
                action=r[1],
                resource_type=r[2],
                resource_id=r[3],
                at=_dt_to_iso(r[4]),
            )
            for r in activity_rows
        ]

        stabilize_total = int(stabilize_total or 0)
        prevented_total = int(prevented_total or 0)

        return {
            "workspace_id": workspace_id,
            "org_id": workspace.org_id,
            "window_hours": window_hours,
            "drift_trend": [t.__dict__ for t in trend],
            "incident_preventions": {
                "total": prevented_total,
                "rate": (prevented_total / stabilize_total) if stabilize_total else 0.0,
            },
            "key_usage": [k.__dict__ for k in key_usage],
            "team_activity": [a.__dict__ for a in team_activity],
            "feedback_total": int(feedback_total or 0),
        }

    def org_team_activity(self, org_id: str, window_hours: int = 24, limit: int = 100) -> list[TeamActivity]:
        with self._conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT actor_user_id, action, resource_type, resource_id, at
                    FROM audit_events
                    WHERE org_id = %s
                      AND at >= NOW() - (%s || ' hours')::interval
                    ORDER BY at DESC
                    LIMIT %s
                    """,
                    (org_id, window_hours, limit),
                )
                rows = cur.fetchall()
        return [
            TeamActivity(
                actor_user_id=r[0],
                action=r[1],
                resource_type=r[2],
                resource_id=r[3],
                at=_dt_to_iso(r[4]),
            )
            for r in rows
        ]


def load_team_store() -> TeamStoreProtocol:
    backend = os.getenv("TEAM_STORE_BACKEND", "postgres").lower()
    if backend == "memory":
        return InMemoryTeamStore()

    database_url = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)
    return PostgresTeamStore(database_url=database_url)


team_store: TeamStoreProtocol = load_team_store()
