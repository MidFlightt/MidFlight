"""Minimal persistence proof, deliberately NOT the application's Store adapter.

Each accepted operation is one conditional write query. No process lock, client-side
read/modify/write, MULTI/EXEC, or background synchronization supplies correctness.
The test harness opens independent clients against the same real graph.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from falkordb import FalkorDB
from redis.backoff import NoBackoff
from redis.retry import Retry


class RevisionConflict(Exception):
    pass


class IdempotencyConflict(Exception):
    pass


@dataclass(frozen=True)
class Result:
    revision: int
    duplicate: bool


# All mutations and the receipt live in the same write query. The optional receipt
# and revision predicates are evaluated by the database, not by a preceding read.
PREFIX = """
MATCH (p:Project {id: $project})
OPTIONAL MATCH (p)-[:RECORDED]->(receipt:Receipt {key: $key})
WITH p, receipt
WHERE receipt IS NULL AND p.coord_rev = $expected
"""
SUFFIX = """
CREATE (p)-[:RECORDED]->(:Receipt {
    key: $key, fingerprint: $fingerprint, revision: p.coord_rev
})
CREATE (p)-[:AUDITED]->(:Audit {key: $key, operation: $operation})
RETURN p.coord_rev
"""
SUBMIT = """
SET p.coord_rev = p.coord_rev + 1
CREATE (p)-[:HAS_CLAIM]->(c:Claim {
    id: $key, state: 'pending', payload: $payload
})
CREATE (p)-[:HAS_JOB]->(j:Job {id: $key, state: 'pending'})
CREATE (j)-[:REVIEWS]->(c)
"""
CHANGE_PLAN = """
SET p.coord_rev = p.coord_rev + 1, p.plan_version = p.plan_version + 1
"""
COMPLETE_REVIEW = """
MATCH (p)-[:HAS_JOB]->(j:Job {id: $job})-[:REVIEWS]->(c:Claim)
WHERE j.state = 'pending'
SET p.coord_rev = p.coord_rev + 1, j.state = 'succeeded', c.state = 'approved'
"""
# A single read query gives a consistent observation for atomic-visibility tests.
SNAPSHOT = """
MATCH (p:Project {id: $project})
OPTIONAL MATCH (p)-[:HAS_CLAIM]->(c:Claim)
WITH p, c ORDER BY c.id
WITH p, collect(CASE WHEN c IS NULL THEN null ELSE [c.id,c.state,c.payload] END) AS claims
OPTIONAL MATCH (p)-[:HAS_JOB]->(j:Job)-[:REVIEWS]->(target:Claim)
WITH p, claims, j, target ORDER BY j.id
WITH p, claims, collect(CASE WHEN j IS NULL THEN null ELSE [j.id,j.state,target.id] END) AS jobs
OPTIONAL MATCH (p)-[:RECORDED]->(r:Receipt)
WITH p, claims, jobs, r ORDER BY r.key
WITH p, claims, jobs,
    collect(CASE WHEN r IS NULL THEN null ELSE [r.key,r.revision] END) AS receipts
OPTIONAL MATCH (p)-[:AUDITED]->(a:Audit)
WITH p, claims, jobs, receipts, a ORDER BY a.key
RETURN p.coord_rev, p.plan_version, claims, jobs, receipts,
    collect(CASE WHEN a IS NULL THEN null ELSE [a.key,a.operation] END)
"""


class ProofStore:
    def __init__(self, port: int, graph_name: str):
        self.graph_name = graph_name
        self.db = FalkorDB(
            host="127.0.0.1",
            port=port,
            socket_timeout=15,
            socket_connect_timeout=2,
            retry=Retry(NoBackoff(), 0),
        )
        self.graph = self.db.select_graph(graph_name)
        self.project = "synthetic-project"

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.connection.close()

    def initialize(self):
        self.graph.query(
            "MERGE (p:Project {id: $project}) "
            "ON CREATE SET p.coord_rev=0, p.plan_version=1 RETURN p.coord_rev",
            {"project": self.project},
        )

    def revision(self) -> int:
        return self.graph.ro_query(
            "MATCH (p:Project {id: $project}) RETURN p.coord_rev",
            {"project": self.project},
        ).result_set[0][0]

    def submit(self, key: str, expected: int, payload: str = "work") -> Result:
        return self._commit(key, expected, "submit", SUBMIT, {"payload": payload})

    def change_plan(self, key: str, expected: int) -> Result:
        return self._commit(key, expected, "change_plan", CHANGE_PLAN, {})

    def complete_review(self, key: str, job: str, expected: int) -> Result:
        return self._commit(key, expected, "complete_review", COMPLETE_REVIEW, {"job": job})

    def _commit(self, key, expected, operation, body, values) -> Result:
        # Include expected revision: a changed request must use a new key. A failed
        # CAS reserves no key; callers can retry it after reading the new revision.
        fingerprint = hashlib.sha256(
            json.dumps(
                [self.project, operation, expected, values],
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        params = {
            "project": self.project,
            "key": key,
            "expected": expected,
            "fingerprint": fingerprint,
            "operation": operation,
            **values,
        }
        rows = self.graph.query(PREFIX + body + SUFFIX, params).result_set
        if rows:
            return Result(revision=rows[0][0], duplicate=False)
        # No writes happened. A concurrent winner may have recorded this exact
        # request, or the revision/precondition was stale. Resolve via durable receipt.
        receipts = self.graph.ro_query(
            "MATCH (:Project {id:$project})-[:RECORDED]->(r:Receipt {key:$key}) "
            "RETURN r.fingerprint, r.revision",
            {"project": self.project, "key": key},
        ).result_set
        if receipts:
            saved_fingerprint, revision = receipts[0]
            if saved_fingerprint != fingerprint:
                raise IdempotencyConflict("request key reused with different input")
            return Result(revision=revision, duplicate=True)
        raise RevisionConflict("revision changed or operation precondition no longer holds")

    def pending_jobs(self) -> list[str]:
        return [
            row[0]
            for row in self.graph.ro_query(
                "MATCH (:Project {id:$project})-[:HAS_JOB]->(j:Job) "
                "WHERE j.state='pending' RETURN j.id ORDER BY j.id",
                {"project": self.project},
            ).result_set
        ]

    def snapshot(self) -> dict:
        row = self.graph.ro_query(SNAPSHOT, {"project": self.project}).result_set[0]
        return dict(
            zip(
                ("revision", "plan_version", "claims", "jobs", "receipts", "audits"),
                row,
                strict=True,
            )
        )
