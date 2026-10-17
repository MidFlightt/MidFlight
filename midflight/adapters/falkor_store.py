"""GH-02: the Store protocol on FalkorDB, with one atomic query per commit.

Models round-trip as canonical JSON; typed nodes, ownership edges, lookup fields,
revision guards and immutable history are maintained in the same graph write.
No Python lock or pre-read decides whether a write may commit.
"""

from __future__ import annotations

import json
import time
from typing import Any

from midflight.domain.models import (
    AuditEvent,
    Claim,
    Directive,
    Entity,
    Escalation,
    Job,
    Model,
    Participant,
    Plan,
    Project,
    User,
    Verification,
)
from midflight.ports import Commit, CommitResult, RevisionConflict

_TYPES = (Project, Participant, Plan, Claim, Directive, Escalation, Verification, Job)


def _json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _key(entity: Model) -> str:
    if isinstance(entity, Plan):
        parts = ["Plan", entity.project_id, entity.version]
    elif isinstance(entity, Claim):
        parts = ["Claim", entity.id, entity.revision]
    else:
        parts = [type(entity).__name__, entity.id]
    return _json(parts)


def _properties(entity: Model) -> dict[str, Any]:
    data = entity.model_dump(mode="json")
    result = {k: v for k, v in data.items() if v is None or isinstance(v, (str, int, float, bool))}
    result.update(key=_key(entity), payload=_json(data))
    if isinstance(entity, Claim):
        result["declaration"] = _json(entity.model_dump(mode="json", exclude={"state", "findings"}))
    if isinstance(entity, Project):
        result.pop("coord_rev")
        result["repository_lower"] = entity.repository.lower()
    return result


class FalkorStore:
    """Use a dedicated graph for one deployment; projects share global ID counters.

    Pass a FalkorDB Graph for dependency injection, or use connect(). The caller
    owns an injected connection. connect() connections are closed by close().
    """

    def __init__(self, graph: Any) -> None:
        self.graph = graph
        self._client: Any = None
        # Establish labels/indexes before requests can compile queries against an
        # empty graph. On the pinned engine, racing first-project queries compiled
        # before MFProject exists can all observe an absent project (GH-02 CI).
        # Startup is synchronous; no requests may use this store until it returns.
        for model in (*_TYPES, User):
            self._ensure_index("MF" + model.__name__, "key")
            if model is not Plan:
                self._ensure_index("MF" + model.__name__, "id")
        for label, field in (
            ("MFReceipt", "key"),
            ("MFIdentity", "key"),
            ("MFCounter", "prefix"),
            ("MFAuth", "key"),
            ("MFAuditEvent", "project_id"),
        ):
            self._ensure_index(label, field)

    def _ensure_index(self, label: str, field: str) -> None:
        from redis.exceptions import ResponseError

        try:
            self._query(f"CREATE INDEX ON :{label}({field})")
        except ResponseError as exc:
            if str(exc) != f"Attribute '{field}' is already indexed":
                raise

    @classmethod
    def connect(cls, *, graph_name: str, **connection: Any) -> FalkorStore:
        from falkordb import FalkorDB
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        connection.setdefault("host", "127.0.0.1")
        connection.setdefault("socket_timeout", 15)
        connection.setdefault("socket_connect_timeout", 5)
        # An ambiguous transport failure must reach the caller. Only Commit's
        # durable receipt makes replay safe; counters must not auto-replay.
        connection["retry"] = Retry(NoBackoff(), 0)
        client = FalkorDB(**connection)
        try:
            store = cls(client.select_graph(graph_name))
        except Exception:
            client.connection.close()
            raise
        store._client = client
        return store

    def close(self) -> None:
        if self._client is not None:
            self._client.connection.close()

    def _query(self, query: str, params: dict[str, Any] | None = None) -> list:
        return self.graph.query(query, params or {}).result_set

    def commit(self, commit: Commit) -> CommitResult:
        params: dict[str, Any] = {
            "project": commit.project_id,
            "receipt": commit.idempotency_key,
            "expected": commit.expected_coord_rev,
            "bump": int(commit.bump_coord_rev),
            "initial": 0,
        }
        project_put = None
        entities: dict[str, Entity] = {}
        for entity in commit.puts:
            if type(entity) not in _TYPES:
                raise TypeError(f"can't store {type(entity).__name__}")
            type(entity).model_validate(entity.model_dump())
            owner = entity.id if isinstance(entity, Project) else entity.project_id
            if owner != commit.project_id:
                raise ValueError(
                    f"{type(entity).__name__} belongs to {owner}, not {commit.project_id}"
                )
            key = _key(entity)
            if key in entities and entities[key] != entity:
                raise ValueError("conflicting entities in one commit")
            entities[key] = entity
            if isinstance(entity, Project):
                project_put = entity
                params["initial"] = entity.coord_rev
        for event in commit.audit:
            AuditEvent.model_validate(event.model_dump())
            if event.project_id != commit.project_id:
                raise ValueError(f"audit belongs to {event.project_id}, not {commit.project_id}")

        query = [
            "OPTIONAL MATCH (p:MFProject {id:$project})",
            "OPTIONAL MATCH (r:MFReceipt {key:$receipt})",
        ]
        guards = []
        mutations = []
        variables = ["p", "r"]
        for i, entity in enumerate(entities.values()):
            if isinstance(entity, Project):
                continue
            label = "MF" + type(entity).__name__  # trusted allowlist above, never user input
            params[f"e{i}"] = _properties(entity)
            query.append(f"OPTIONAL MATCH (old{i}:{label} {{key:$e{i}.key}})")
            variables.append(f"old{i}")
            # Guard all revisions of a global entity ID against reassignment to
            # another project, including a previously unseen Claim revision.
            identity = _json([type(entity).__name__, getattr(entity, "id", _key(entity))])
            params[f"identity{i}"] = identity
            query.append(f"OPTIONAL MATCH (owner{i}:MFIdentity {{key:$identity{i}}})")
            variables.append(f"owner{i}")
            guards.append(
                f"WHEN owner{i} IS NOT NULL AND owner{i}.project <> $project THEN 'owner'"
            )
            if isinstance(entity, Plan):
                guards.append(
                    f"WHEN old{i}.status = 'approved' AND old{i}.payload <> $e{i}.payload "
                    "THEN 'plan'"
                )
            if isinstance(entity, Claim):
                guards.append(
                    f"WHEN old{i} IS NOT NULL AND old{i}.declaration <> $e{i}.declaration "
                    "THEN 'claim'"
                )
            mutations.extend(
                [
                    f"MERGE (n{i}:MFEntity:{label} {{key:$e{i}.key}})",
                    f"SET n{i} += $e{i}",
                    f"MERGE (target)-[:CONTAINS]->(n{i})",
                    f"MERGE (identity{i}:MFIdentity {{key:$identity{i}}})",
                    f"SET identity{i}.project = $project",
                ]
            )
        for i, event in enumerate(commit.audit):
            params[f"audit{i}"] = event.model_dump_json()
            mutations.extend(
                [
                    f"CREATE (a{i}:MFAuditEvent {{payload:$audit{i}, project_id:$project}})",
                    f"CREATE (target)-[:AUDITED]->(a{i})",
                ]
            )
        params["has_project"] = project_put is not None
        if project_put is not None:
            params["project_props"] = _properties(project_put)
        query.extend(
            [
                "WITH " + ", ".join(variables) + ", CASE "
                "WHEN r IS NOT NULL AND r.project <> $project THEN 'receipt_owner' "
                "WHEN r IS NOT NULL THEN 'duplicate' "
                "WHEN $expected IS NOT NULL AND coalesce(p.coord_rev,0) <> $expected "
                "THEN 'revision' "
                "WHEN p IS NULL AND NOT $has_project THEN 'missing' "
                + " ".join(guards)
                + " ELSE 'ok' END AS outcome",
                "WITH p, r, outcome, coalesce(p.coord_rev,$initial) + $bump AS revision",
                "FOREACH (_ IN CASE WHEN outcome = 'ok' THEN [1] ELSE [] END |",
                "MERGE (target:MFEntity:MFProject {id:$project})",
            ]
        )
        if project_put is not None:
            query.append("SET target += $project_props")
        query.extend(
            [
                "SET target.coord_rev = revision",
                *mutations,
                "CREATE (receipt:MFReceipt {key:$receipt, project:$project, coord_rev:revision})",
                "CREATE (target)-[:RECORDED]->(receipt)",
                ") RETURN outcome, coalesce(p.coord_rev,0), r.coord_rev, revision",
            ]
        )
        outcome, actual, previous, revision = self._query("\n".join(query), params)[0]
        if outcome == "duplicate":
            return CommitResult(False, True, previous)
        if outcome == "revision":
            raise RevisionConflict(commit.expected_coord_rev, actual)
        if outcome == "missing":
            raise LookupError(f"unknown project {commit.project_id}")
        if outcome == "plan":
            raise ValueError("plan is approved and can't change")
        if outcome == "claim":
            raise ValueError("claim is saved; submit a new revision instead of editing it")
        if outcome in {"owner", "receipt_owner"}:
            raise ValueError("stored entity or idempotency key belongs to another project")
        if outcome != "ok":
            raise RuntimeError(f"unexpected commit outcome: {outcome}")
        return CommitResult(True, False, revision)

    def next_id(self, project_id: str, prefix: str) -> str:
        rows = self._query(
            "MERGE (c:MFCounter {prefix:$prefix}) ON CREATE SET c.value=0 "
            "SET c.value=c.value+1 RETURN c.value",
            {"prefix": prefix},
        )
        return f"{prefix}-{rows[0][0]}"

    def _read[T: Model](self, model: type[T], where: str = "", **params: Any) -> list[T]:
        rows = self._query(
            f"MATCH (n:MF{model.__name__}) "
            + (f"WHERE {where} " if where else "")
            + "RETURN n.payload, n.coord_rev",
            params,
        )
        result = []
        for payload, revision in rows:
            data = json.loads(payload)
            if model is Project:
                data["coord_rev"] = revision
            result.append(model.model_validate(data))
        return result

    def _one[T: Model](self, model: type[T], where: str, **params: Any) -> T | None:
        return next(iter(self._read(model, where, **params)), None)

    def get_project(self, project_id: str) -> Project | None:
        return self._one(Project, "n.id=$id", id=project_id)

    def get_participant(self, participant_id: str) -> Participant | None:
        return self._one(Participant, "n.id=$id", id=participant_id)

    def find_participant_by_token_hash(self, token_hash: str) -> Participant | None:
        return self._one(Participant, "n.token_hash=$hash", hash=token_hash)

    def list_participants(self, project_id: str) -> list[Participant]:
        return self._read(Participant, "n.project_id=$id", id=project_id)

    def get_plan(self, project_id: str, version: int) -> Plan | None:
        return self._one(
            Plan, "n.project_id=$id AND n.version=$version", id=project_id, version=version
        )

    def list_plans(self, project_id: str) -> list[Plan]:
        return sorted(self._read(Plan, "n.project_id=$id", id=project_id), key=lambda p: p.version)

    def get_claim(self, claim_id: str, revision: int | None = None) -> Claim | None:
        if revision is not None:
            return self._one(
                Claim, "n.id=$id AND n.revision=$revision", id=claim_id, revision=revision
            )
        return next(iter(reversed(self.claim_history(claim_id))), None)

    def claim_history(self, claim_id: str) -> list[Claim]:
        return sorted(self._read(Claim, "n.id=$id", id=claim_id), key=lambda c: c.revision)

    def list_claims(self, project_id: str) -> list[Claim]:
        latest = {}
        for claim in sorted(
            self._read(Claim, "n.project_id=$id", id=project_id), key=lambda c: c.revision
        ):
            latest[claim.id] = claim
        return list(latest.values())

    def get_directive(self, directive_id: str) -> Directive | None:
        return self._one(Directive, "n.id=$id", id=directive_id)

    def list_directives(self, project_id: str, task_id: str | None = None) -> list[Directive]:
        return sorted(
            self._read(
                Directive,
                "n.project_id=$id AND ($task IS NULL OR n.task_id=$task)",
                id=project_id,
                task=task_id,
            ),
            key=lambda d: (d.created_at, d.id),
        )

    def get_escalation(self, escalation_id: str) -> Escalation | None:
        return self._one(Escalation, "n.id=$id", id=escalation_id)

    def list_escalations(self, project_id: str) -> list[Escalation]:
        return sorted(
            self._read(Escalation, "n.project_id=$id", id=project_id),
            key=lambda e: (e.created_at, e.id),
        )

    def get_verification(self, verification_id: str) -> Verification | None:
        return self._one(Verification, "n.id=$id", id=verification_id)

    def list_verifications(self, project_id: str) -> list[Verification]:
        return sorted(
            self._read(Verification, "n.project_id=$id", id=project_id),
            key=lambda v: (v.created_at, v.id),
        )

    def get_job(self, job_id: str) -> Job | None:
        return self._one(Job, "n.id=$id", id=job_id)

    def list_jobs(self, project_id: str) -> list[Job]:
        return self._read(Job, "n.project_id=$id", id=project_id)

    def list_audit(self, project_id: str, entity_id: str | None = None) -> list[AuditEvent]:
        events = self._read(AuditEvent, "n.project_id=$id", id=project_id)
        return sorted(
            (e for e in events if entity_id is None or entity_id in e.entity_ids),
            key=lambda e: (e.timestamp, e.id),
        )

    def save_user(self, user: User) -> None:
        User.model_validate(user.model_dump())
        self._query("MERGE (u:MFUser {id:$props.id}) SET u += $props", {"props": _properties(user)})

    def get_user(self, user_id: str) -> User | None:
        return self._one(User, "n.id=$id", id=user_id)

    def find_user_by_github_id(self, github_id: int) -> User | None:
        return self._one(User, "n.github_id=$id", id=github_id)

    def find_project_by_join_code(self, join_code: str) -> Project | None:
        return self._one(Project, "n.join_code=$code", code=join_code)

    def find_project_by_repository(self, repository: str) -> Project | None:
        return self._one(Project, "n.repository_lower=$repo", repo=repository.lower())

    def list_memberships(self, user_id: str) -> list[Participant]:
        return self._read(Participant, "n.user_id=$id", id=user_id)

    def put_auth(
        self, kind: str, key: str, value: dict[str, Any], expires_at: float | None = None
    ) -> None:
        self._query(
            "MERGE (a:MFAuth {key:$key}) SET a.payload=$payload, a.expires=$expires",
            {"key": _json([kind, key]), "payload": _json(value), "expires": expires_at},
        )

    def get_auth(self, kind: str, key: str) -> dict[str, Any] | None:
        rows = self._query(
            "MATCH (a:MFAuth {key:$key}) WHERE a.expires IS NULL OR a.expires >= $now "
            "RETURN a.payload",
            {"key": _json([kind, key]), "now": time.time()},
        )
        return json.loads(rows[0][0]) if rows else None

    def delete_auth(self, kind: str, key: str) -> None:
        self._query("MATCH (a:MFAuth {key:$key}) DELETE a", {"key": _json([kind, key])})
