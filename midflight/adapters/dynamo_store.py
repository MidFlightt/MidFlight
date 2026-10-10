"""The Store on DynamoDB, for AWS (task H-5). Behaves exactly like MemoryStore; the same
tests run against both (tests/unit/test_store.py).

One table, keys `PK` and `SK`. Every entity is saved as JSON in a `data` attribute.

Item keys (PK, then SK):

- Project: `PROJECT#<project id>`, `META`, with a `coord_rev` number.
- Things inside a project: `PROJECT#<project id>`, then `PARTICIPANT#<id>`,
  `PLAN#<version>`, `CLAIM#<id>#<revision>`, `DIRECTIVE#<id>`, `ESCALATION#<id>`,
  `VERIFICATION#<id>`, `JOB#<id>`, or `AUDIT#<time>#<id>`.
- Where an id lives, for lookups by id alone: `ID#<id>`, `ID`.
- Lookups: `JOIN#<code>`, `REPO#<owner/name>`, `TOKEN#<hash>`, `GITHUB#<id>`, `LOOKUP`.
- Users and their memberships: `USER#<user id>`, `META` or `MEMBER#<participant id>`.
- Sign-in records: `AUTH#<kind>#<key>`, `AUTH`, with a `ttl` so DynamoDB deletes them.
- Id counters and applied commits: `COUNTER#<prefix>` and `COMMIT#<idempotency key>`.

A commit is one DynamoDB transaction. The project item's update carries the
`coord_rev` condition (INV-02), and a `COMMIT#` item that must not exist yet makes
retries safe (INV-13). The worker Lambda reads new job items from the table's stream.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterable
from typing import Any

import boto3
from botocore.exceptions import ClientError

from midflight.domain.models import (
    AuditEvent,
    Claim,
    Directive,
    Entity,
    Escalation,
    Job,
    Participant,
    Plan,
    PlanStatus,
    Project,
    User,
    Verification,
)
from midflight.ports import Commit, CommitResult, RevisionConflict

# The parts of a saved claim revision that may still change: its verdict.
_CLAIM_VERDICT_FIELDS = {"state", "findings"}

_SK_PREFIX: dict[type, str] = {
    Participant: "PARTICIPANT#",
    Directive: "DIRECTIVE#",
    Escalation: "ESCALATION#",
    Verification: "VERIFICATION#",
    Job: "JOB#",
}


class DynamoStore:
    def __init__(self, table_name: str, client: Any | None = None) -> None:
        self._table = table_name
        self._db = client or boto3.client("dynamodb")

    @staticmethod
    def create_table(client: Any, table_name: str) -> None:
        """Create the table (tests and local experiments; on AWS the SAM template does)."""
        client.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "PK", "KeyType": "HASH"},
                {"AttributeName": "SK", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "PK", "AttributeType": "S"},
                {"AttributeName": "SK", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            StreamSpecification={"StreamEnabled": True, "StreamViewType": "NEW_IMAGE"},
        )

    # Writes ----------------------------------------------------------------------------

    def commit(self, commit: Commit) -> CommitResult:
        applied = self._get("COMMIT#" + commit.idempotency_key, "COMMIT")
        if applied is not None:
            return CommitResult(applied=False, duplicate=True, coord_rev=int(applied["rev"]["N"]))

        stored = self.get_project(commit.project_id)
        if commit.expected_coord_rev is not None:
            actual = stored.coord_rev if stored else 0
            if actual != commit.expected_coord_rev:
                raise RevisionConflict(commit.expected_coord_rev, actual)
        new_project = next((e for e in commit.puts if isinstance(e, Project)), None)
        if stored is None and new_project is None:
            raise LookupError(f"unknown project {commit.project_id}")
        for entity in commit.puts:
            self._check(commit.project_id, entity)

        ops: list[dict[str, Any]] = []
        project_index = None
        if (
            new_project is not None
            or commit.bump_coord_rev
            or commit.expected_coord_rev is not None
        ):
            project_index = len(ops)
            ops.append(self._project_update(commit, stored, new_project))
            if new_project is not None:
                ops += self._project_lookups(stored, new_project)
        for entity in commit.puts:
            if not isinstance(entity, Project):
                ops += self._entity_puts(entity)
        for event in commit.audit:
            ops.append(self._put(_pk(event.project_id), _audit_sk(event), event))
        base_rev = stored.coord_rev if stored else 0
        new_rev = base_rev + (1 if commit.bump_coord_rev else 0)
        commit_index = len(ops)
        ops.append(
            {
                "Put": {
                    "TableName": self._table,
                    "Item": {
                        "PK": {"S": "COMMIT#" + commit.idempotency_key},
                        "SK": {"S": "COMMIT"},
                        "rev": {"N": str(new_rev)},
                    },
                    "ConditionExpression": "attribute_not_exists(PK)",
                }
            }
        )

        try:
            self._db.transact_write_items(TransactItems=ops)
        except ClientError as error:
            if error.response["Error"]["Code"] != "TransactionCanceledException":
                raise
            reasons = error.response.get("CancellationReasons", [])
            failed = {i for i, r in enumerate(reasons) if r.get("Code") == "ConditionalCheckFailed"}
            if commit_index in failed:
                current = self.get_project(commit.project_id)
                return CommitResult(False, True, current.coord_rev if current else 0)
            if project_index in failed:
                current = self.get_project(commit.project_id)
                raise RevisionConflict(
                    commit.expected_coord_rev or 0, current.coord_rev if current else 0
                ) from error
            raise
        return CommitResult(applied=True, duplicate=False, coord_rev=new_rev)

    def next_id(self, project_id: str, prefix: str) -> str:
        # Numbered across all projects, so ids never collide between teams.
        response = self._db.update_item(
            TableName=self._table,
            Key={"PK": {"S": f"COUNTER#{prefix}"}, "SK": {"S": "COUNTER"}},
            UpdateExpression="ADD n :one",
            ExpressionAttributeValues={":one": {"N": "1"}},
            ReturnValues="UPDATED_NEW",
        )
        return f"{prefix}-{response['Attributes']['n']['N']}"

    def _check(self, project_id: str, entity: Entity) -> None:
        """Refuse invalid data and writes that would rewrite history, before saving anything."""
        type(entity).model_validate(entity.model_dump())
        owner = entity.id if isinstance(entity, Project) else entity.project_id
        if owner != project_id:
            raise ValueError(f"{type(entity).__name__} belongs to {owner}, not {project_id}")
        if isinstance(entity, Plan):
            saved = self.get_plan(entity.project_id, entity.version)
            if saved is not None and saved.status is PlanStatus.APPROVED and saved != entity:
                raise ValueError(f"plan v{entity.version} is approved and can't change")
        if isinstance(entity, Claim):
            saved_claim = self.get_claim(entity.id, entity.revision)
            if saved_claim is not None:
                before = saved_claim.model_dump(exclude=_CLAIM_VERDICT_FIELDS)
                if before != entity.model_dump(exclude=_CLAIM_VERDICT_FIELDS):
                    raise ValueError(
                        f"claim {entity.id} rev {entity.revision} is saved; submit a new "
                        "revision instead of editing it"
                    )

    def _project_update(
        self, commit: Commit, stored: Project | None, new_project: Project | None
    ) -> dict[str, Any]:
        sets = ["coord_rev = if_not_exists(coord_rev, :zero) + :bump"]
        values: dict[str, Any] = {
            ":zero": {"N": "0"},
            ":bump": {"N": "1" if commit.bump_coord_rev else "0"},
        }
        if new_project is not None:
            sets += ["#data = :data", "#type = :type"]
            values[":data"] = {"S": new_project.model_dump_json()}
            values[":type"] = {"S": "project"}
        update: dict[str, Any] = {
            "TableName": self._table,
            "Key": {"PK": {"S": _pk(commit.project_id)}, "SK": {"S": "META"}},
            "UpdateExpression": "SET " + ", ".join(sets),
            "ExpressionAttributeValues": values,
        }
        if new_project is not None:
            update["ExpressionAttributeNames"] = {"#data": "data", "#type": "type"}
        if commit.expected_coord_rev is not None:
            update["ConditionExpression"] = "coord_rev = :expected"
            values[":expected"] = {"N": str(commit.expected_coord_rev)}
        elif stored is None:
            update["ConditionExpression"] = "attribute_not_exists(PK)"
        return {"Update": update}

    def _project_lookups(self, stored: Project | None, project: Project) -> list[dict[str, Any]]:
        ops = [self._lookup(f"REPO#{project.repository.lower()}", {"project_id": project.id})]
        if stored is not None and stored.join_code and stored.join_code != project.join_code:
            ops.append(self._delete(f"JOIN#{stored.join_code}", "LOOKUP"))
        if project.join_code:
            ops.append(self._lookup(f"JOIN#{project.join_code}", {"project_id": project.id}))
        return ops

    def _entity_puts(self, entity: Entity) -> list[dict[str, Any]]:
        pk = _pk(entity.project_id)  # type: ignore[union-attr]
        if isinstance(entity, Plan):
            return [self._put(pk, f"PLAN#{entity.version:06d}", entity)]
        if isinstance(entity, Claim):
            return [
                self._put(pk, f"CLAIM#{entity.id}#{entity.revision:06d}", entity),
                self._lookup(f"ID#{entity.id}", {"project_id": entity.project_id}, sk="ID"),
            ]
        ops = [
            self._put(pk, _SK_PREFIX[type(entity)] + entity.id, entity),
            self._lookup(f"ID#{entity.id}", {"project_id": entity.project_id}, sk="ID"),
        ]
        if isinstance(entity, Job):
            # The stream filter in infra/template.yaml picks job items by this attribute.
            ops[0]["Put"]["Item"]["job_state"] = {"S": entity.state.value}
        if isinstance(entity, Participant):
            if entity.user_id:
                ops.append(
                    self._lookup(
                        f"USER#{entity.user_id}",
                        {"participant_id": entity.id, "project_id": entity.project_id},
                        sk=f"MEMBER#{entity.id}",
                    )
                )
            if entity.token_hash:
                ops.append(
                    self._lookup(
                        f"TOKEN#{entity.token_hash}",
                        {"participant_id": entity.id, "project_id": entity.project_id},
                    )
                )
        return ops

    def _put(self, pk: str, sk: str, entity: Entity | AuditEvent) -> dict[str, Any]:
        return {
            "Put": {
                "TableName": self._table,
                "Item": {
                    "PK": {"S": pk},
                    "SK": {"S": sk},
                    "type": {"S": type(entity).__name__.lower()},
                    "data": {"S": entity.model_dump_json()},
                },
            }
        }

    def _lookup(self, pk: str, values: dict[str, str], sk: str = "LOOKUP") -> dict[str, Any]:
        item = {"PK": {"S": pk}, "SK": {"S": sk}} | {k: {"S": v} for k, v in values.items()}
        return {"Put": {"TableName": self._table, "Item": item}}

    def _delete(self, pk: str, sk: str) -> dict[str, Any]:
        return {"Delete": {"TableName": self._table, "Key": {"PK": {"S": pk}, "SK": {"S": sk}}}}

    # Reads -----------------------------------------------------------------------------

    def get_project(self, project_id: str) -> Project | None:
        item = self._get(_pk(project_id), "META")
        if item is None or "data" not in item:
            return None
        project = Project.model_validate_json(item["data"]["S"])
        return project.model_copy(update={"coord_rev": int(item.get("coord_rev", {"N": "0"})["N"])})

    def get_participant(self, participant_id: str) -> Participant | None:
        return self._by_id(Participant, participant_id)

    def find_participant_by_token_hash(self, token_hash: str) -> Participant | None:
        found = self._get(f"TOKEN#{token_hash}", "LOOKUP")
        return self.get_participant(found["participant_id"]["S"]) if found else None

    def list_participants(self, project_id: str) -> list[Participant]:
        return [Participant.model_validate_json(d) for d in self._query(project_id, "PARTICIPANT#")]

    def get_plan(self, project_id: str, version: int) -> Plan | None:
        item = self._get(_pk(project_id), f"PLAN#{version:06d}")
        return Plan.model_validate_json(item["data"]["S"]) if item else None

    def list_plans(self, project_id: str) -> list[Plan]:
        return [Plan.model_validate_json(d) for d in self._query(project_id, "PLAN#")]

    def get_claim(self, claim_id: str, revision: int | None = None) -> Claim | None:
        project_id = self._project_of(claim_id)
        if project_id is None:
            return None
        if revision is not None:
            item = self._get(_pk(project_id), f"CLAIM#{claim_id}#{revision:06d}")
            return Claim.model_validate_json(item["data"]["S"]) if item else None
        history = self.claim_history(claim_id)
        return history[-1] if history else None

    def claim_history(self, claim_id: str) -> list[Claim]:
        project_id = self._project_of(claim_id)
        if project_id is None:
            return []
        return [Claim.model_validate_json(d) for d in self._query(project_id, f"CLAIM#{claim_id}#")]

    def list_claims(self, project_id: str) -> list[Claim]:
        latest: dict[str, Claim] = {}
        for data in self._query(project_id, "CLAIM#"):
            claim = Claim.model_validate_json(data)
            latest[claim.id] = claim  # revisions come in order, so the last one wins
        return sorted(latest.values(), key=lambda c: _number(c.id))

    def get_directive(self, directive_id: str) -> Directive | None:
        return self._by_id(Directive, directive_id)

    def list_directives(self, project_id: str, task_id: str | None = None) -> list[Directive]:
        found = [Directive.model_validate_json(d) for d in self._query(project_id, "DIRECTIVE#")]
        return sorted(
            (d for d in found if task_id is None or d.task_id == task_id),
            key=lambda d: (d.created_at, _number(d.id)),
        )

    def get_escalation(self, escalation_id: str) -> Escalation | None:
        return self._by_id(Escalation, escalation_id)

    def list_escalations(self, project_id: str) -> list[Escalation]:
        found = [Escalation.model_validate_json(d) for d in self._query(project_id, "ESCALATION#")]
        return sorted(found, key=lambda e: (e.created_at, _number(e.id)))

    def get_verification(self, verification_id: str) -> Verification | None:
        return self._by_id(Verification, verification_id)

    def list_verifications(self, project_id: str) -> list[Verification]:
        found = [
            Verification.model_validate_json(d) for d in self._query(project_id, "VERIFICATION#")
        ]
        return sorted(found, key=lambda v: (v.created_at, _number(v.id)))

    def get_job(self, job_id: str) -> Job | None:
        return self._by_id(Job, job_id)

    def list_jobs(self, project_id: str) -> list[Job]:
        found = [Job.model_validate_json(d) for d in self._query(project_id, "JOB#")]
        return sorted(found, key=lambda j: _number(j.id))

    def list_audit(self, project_id: str, entity_id: str | None = None) -> list[AuditEvent]:
        events = [AuditEvent.model_validate_json(d) for d in self._query(project_id, "AUDIT#")]
        return [e for e in events if entity_id is None or entity_id in e.entity_ids]

    # People and projects ---------------------------------------------------------------

    def save_user(self, user: User) -> None:
        user = User.model_validate(user.model_dump())
        self._db.transact_write_items(
            TransactItems=[
                self._put(f"USER#{user.id}", "META", user),  # type: ignore[arg-type]
                self._lookup(f"GITHUB#{user.github_id}", {"user_id": user.id}),
            ]
        )

    def get_user(self, user_id: str) -> User | None:
        item = self._get(f"USER#{user_id}", "META")
        return User.model_validate_json(item["data"]["S"]) if item else None

    def find_user_by_github_id(self, github_id: int) -> User | None:
        found = self._get(f"GITHUB#{github_id}", "LOOKUP")
        return self.get_user(found["user_id"]["S"]) if found else None

    def find_project_by_join_code(self, join_code: str) -> Project | None:
        found = self._get(f"JOIN#{join_code}", "LOOKUP")
        return self.get_project(found["project_id"]["S"]) if found else None

    def find_project_by_repository(self, repository: str) -> Project | None:
        found = self._get(f"REPO#{repository.lower()}", "LOOKUP")
        return self.get_project(found["project_id"]["S"]) if found else None

    def list_memberships(self, user_id: str) -> list[Participant]:
        members = []
        for item in self._query_items(f"USER#{user_id}", "MEMBER#"):
            member = self.get_participant(item["participant_id"]["S"])
            if member is not None:
                members.append(member)
        return members

    # Sign-in records -------------------------------------------------------------------

    def put_auth(
        self, kind: str, key: str, value: dict[str, Any], expires_at: float | None = None
    ) -> None:
        item: dict[str, Any] = {
            "PK": {"S": f"AUTH#{kind}#{key}"},
            "SK": {"S": "AUTH"},
            "data": {"S": json.dumps(value)},
        }
        if expires_at is not None:
            item["ttl"] = {"N": str(int(expires_at))}  # DynamoDB deletes it eventually
            item["expires_at"] = {"N": repr(float(expires_at))}
        self._db.put_item(TableName=self._table, Item=item)

    def get_auth(self, kind: str, key: str) -> dict[str, Any] | None:
        item = self._get(f"AUTH#{kind}#{key}", "AUTH")
        if item is None:
            return None
        if "expires_at" in item and float(item["expires_at"]["N"]) < time.time():
            return None  # TTL deletion can lag, so check expiry ourselves
        return json.loads(item["data"]["S"])

    def delete_auth(self, kind: str, key: str) -> None:
        self._db.delete_item(
            TableName=self._table, Key={"PK": {"S": f"AUTH#{kind}#{key}"}, "SK": {"S": "AUTH"}}
        )

    # Helpers ---------------------------------------------------------------------------

    def _get(self, pk: str, sk: str) -> dict[str, Any] | None:
        response = self._db.get_item(
            TableName=self._table, Key={"PK": {"S": pk}, "SK": {"S": sk}}, ConsistentRead=True
        )
        return response.get("Item")

    def _project_of(self, entity_id: str) -> str | None:
        found = self._get(f"ID#{entity_id}", "ID")
        return found["project_id"]["S"] if found else None

    def _by_id(self, model: Any, entity_id: str) -> Any:
        project_id = self._project_of(entity_id)
        if project_id is None:
            return None
        item = self._get(_pk(project_id), _SK_PREFIX[model] + entity_id)
        return model.model_validate_json(item["data"]["S"]) if item else None

    def _query(self, project_id: str, sk_prefix: str) -> Iterable[str]:
        return (item["data"]["S"] for item in self._query_items(_pk(project_id), sk_prefix))

    def _query_items(self, pk: str, sk_prefix: str) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        kwargs: dict[str, Any] = {
            "TableName": self._table,
            "KeyConditionExpression": "PK = :pk AND begins_with(SK, :prefix)",
            "ExpressionAttributeValues": {":pk": {"S": pk}, ":prefix": {"S": sk_prefix}},
            "ConsistentRead": True,
        }
        while True:
            response = self._db.query(**kwargs)
            items += response.get("Items", [])
            if "LastEvaluatedKey" not in response:
                return items
            kwargs["ExclusiveStartKey"] = response["LastEvaluatedKey"]


def _pk(project_id: str) -> str:
    return f"PROJECT#{project_id}"


def _audit_sk(event: AuditEvent) -> str:
    return f"AUDIT#{event.timestamp.isoformat()}#{_number(event.id):012d}"


def _number(entity_id: str) -> int:
    """The counter in an id like `C-12`, for sorting in creation order."""
    tail = entity_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else 0
