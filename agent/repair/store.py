"""Persistence and idempotency. One msg_id is repaired once.

claim() inserts the msg_id as in_progress; a conflict means it is already handled and is skipped. A retry_later payment may be
claimed again until max_payment_tries; an in_progress claim older than the lease (a crashed worker) may be re-claimed.
finish() stores the result and the steps in one transaction; the worker treats a payment as done only after that commit.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field


@dataclass
class Row:
    msg_id: str
    status: str
    original_lines: list[str]
    repaired: dict | None = None
    route: str | None = None
    confidence: float | None = None
    attempts: int = 0
    cost_usd: float = 0.0
    api_failures: int = 0
    reasons: list[str] = field(default_factory=list)
    updated: float = 0.0


@dataclass
class Claim:
    claimed: bool
    api_failures: int = 0
    existing: Row | None = None


class InMemoryRepository:
    def __init__(self, max_payment_tries: int = 3, lease_s: float = 600, clock=time.time):
        self.rows: dict[str, Row] = {}
        self.steps: dict[str, list] = {}
        self.max_tries, self.lease, self.clock = max_payment_tries, lease_s, clock

    def claim(self, msg_id: str, lines: list[str]) -> Claim:
        row = self.rows.get(msg_id)
        now = self.clock()
        if row is None:
            self.rows[msg_id] = Row(msg_id, "in_progress", list(lines), updated=now)
            return Claim(True)
        if (row.status == "retry_later" and row.api_failures < self.max_tries) or (row.status == "in_progress" and now - row.updated > self.lease):
            row.status, row.updated = "in_progress", now
            return Claim(True, row.api_failures)
        return Claim(False, existing=row)

    def finish(self, msg_id: str, status: str, route: str | None, repaired: dict | None, confidence: float | None, attempts: int,
               cost_usd: float, reasons: list[str], api_failures: int, steps: list) -> None:
        row = self.rows[msg_id]
        row.status, row.route, row.repaired, row.confidence = status, route, repaired, confidence
        row.attempts += attempts
        row.cost_usd += cost_usd
        row.reasons, row.api_failures, row.updated = list(reasons), api_failures, self.clock()
        self.steps.setdefault(msg_id, []).extend(steps)

    def get(self, msg_id: str) -> Row | None:
        return self.rows.get(msg_id)

    def count(self) -> int:
        return len(self.rows)


class PostgresRepository:
    """The same contract on PostgreSQL (tables created by agent/db/schema.sql)."""

    def __init__(self, conn, max_payment_tries: int = 3, lease_s: float = 600):
        self.conn, self.max_tries, self.lease = conn, max_payment_tries, lease_s

    def claim(self, msg_id: str, lines: list[str]) -> Claim:
        cur = self.conn.execute(
            "INSERT INTO agent_repairs (msg_id, status, original_lines) VALUES (%s, 'in_progress', %s::jsonb) "
            "ON CONFLICT (msg_id) DO NOTHING RETURNING msg_id", (msg_id, json.dumps(lines)))
        if cur.fetchone():
            return Claim(True)
        cur = self.conn.execute(
            "UPDATE agent_repairs SET status = 'in_progress', updated_at = now() WHERE msg_id = %s AND "
            "((status = 'retry_later' AND api_failures < %s) OR (status = 'in_progress' AND updated_at < now() - make_interval(secs => %s))) "
            "RETURNING api_failures", (msg_id, self.max_tries, self.lease))
        got = cur.fetchone()
        if got:
            return Claim(True, int(got[0]))
        return Claim(False, existing=self.get(msg_id))

    def finish(self, msg_id, status, route, repaired, confidence, attempts, cost_usd, reasons, api_failures, steps) -> None:
        with self.conn.transaction():
            self.conn.execute(
                "UPDATE agent_repairs SET status=%s, route=%s, repaired=%s::jsonb, confidence=%s, attempts=attempts+%s, "
                "cost_usd=cost_usd+%s, reasons=%s::jsonb, api_failures=%s, updated_at=now() WHERE msg_id=%s",
                (status, route, json.dumps(repaired) if repaired is not None else None, confidence, attempts, cost_usd,
                 json.dumps(reasons), api_failures, msg_id))
            for s in steps:
                self.conn.execute(
                    "INSERT INTO agent_steps (msg_id, attempt, step, tool, input, output, tokens_in, tokens_out, latency_ms) "
                    "VALUES (%s,%s,%s,%s,%s::jsonb,%s::jsonb,%s,%s,%s)",
                    (msg_id, s.attempt, s.step, s.tool, json.dumps(s.input, default=str), json.dumps(s.output, default=str),
                     s.tokens_in, s.tokens_out, s.latency_ms))

    def get(self, msg_id: str) -> Row | None:
        r = self.conn.execute("SELECT msg_id,status,original_lines,repaired,route,confidence,attempts,cost_usd,api_failures,reasons "
                              "FROM agent_repairs WHERE msg_id=%s", (msg_id,)).fetchone()
        if not r:
            return None
        return Row(r[0], r[1], r[2], r[3], r[4], float(r[5]) if r[5] is not None else None, r[6], float(r[7]), r[8], r[9] or [])

    def count(self) -> int:
        return int(self.conn.execute("SELECT count(*) FROM agent_repairs").fetchone()[0])
