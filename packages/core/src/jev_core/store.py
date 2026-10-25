"""Durable single-node state. All writes use short SQLite transactions.

Model/network I/O must never occur while a transaction is held.
"""

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from .models import Approval, DomainError, Principal, RunRequest, canonical, digest


class Store:
    def __init__(self, path: str):
        self.path = path
        if path == ":memory:":
            raise ValueError("Use a file: each operation uses an independent connection")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript("""
            CREATE TABLE IF NOT EXISTS schema_version(version INTEGER PRIMARY KEY);
            INSERT OR IGNORE INTO schema_version VALUES(1);
            CREATE TABLE IF NOT EXISTS runs(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, owner TEXT NOT NULL,
              idem TEXT NOT NULL, request_hash TEXT NOT NULL, state TEXT NOT NULL,
              lease TEXT, lease_until REAL NOT NULL DEFAULT 0,
              UNIQUE(tenant, owner, idem));
            CREATE TABLE IF NOT EXISTS events(
              seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
              tenant TEXT NOT NULL, name TEXT NOT NULL, ts REAL NOT NULL, data TEXT NOT NULL);
            CREATE INDEX IF NOT EXISTS events_run ON events(tenant, run_id, seq);
            CREATE TABLE IF NOT EXISTS documents(
              tenant TEXT NOT NULL, id TEXT NOT NULL, source TEXT NOT NULL,
              content TEXT NOT NULL, PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS memory(
              tenant TEXT NOT NULL, subject TEXT NOT NULL, session TEXT NOT NULL,
              kind TEXT NOT NULL, content TEXT NOT NULL, expires REAL NOT NULL,
              PRIMARY KEY(tenant,subject,session,kind));
            CREATE TABLE IF NOT EXISTS effects(
              tenant TEXT NOT NULL, run_id TEXT NOT NULL, step INTEGER NOT NULL,
              fingerprint TEXT NOT NULL, result TEXT NOT NULL, PRIMARY KEY(tenant,run_id,step));
            CREATE TABLE IF NOT EXISTS tickets(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, title TEXT NOT NULL, severity TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS invoices(
              tenant TEXT NOT NULL, id TEXT NOT NULL, paid_cents INTEGER NOT NULL,
              PRIMARY KEY(tenant,id));
            CREATE TABLE IF NOT EXISTS refunds(
              id TEXT PRIMARY KEY, tenant TEXT NOT NULL, invoice TEXT NOT NULL,
              amount_cents INTEGER NOT NULL, UNIQUE(tenant,invoice));
            CREATE TABLE IF NOT EXISTS rate_limits(
              tenant TEXT NOT NULL, subject TEXT NOT NULL, window INTEGER NOT NULL,
              count INTEGER NOT NULL, PRIMARY KEY(tenant,subject,window));
            """)
            if c.execute("SELECT max(version) FROM schema_version").fetchone()[0] != 1:
                raise RuntimeError("Unsupported schema version")

    @contextmanager
    def connection(self):
        c = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        c.execute("PRAGMA synchronous=FULL")
        try:
            yield c
        finally:
            c.close()

    @contextmanager
    def transaction(self):
        with self.connection() as c:
            c.execute("BEGIN IMMEDIATE")
            try:
                yield c
                c.commit()
            except BaseException:
                c.rollback()
                raise

    def _row(self, c, tenant, run_id):
        row = c.execute("SELECT * FROM runs WHERE tenant=? AND id=?", (tenant, run_id)).fetchone()
        if row is None:
            raise DomainError("run_not_found", 404)
        return row

    def _event(self, c, tenant, run_id, name, data=None):
        c.execute(
            "INSERT INTO events(run_id,tenant,name,ts,data) VALUES(?,?,?,?,?)",
            (run_id, tenant, name, time.time(), canonical(data or {})),
        )

    def create(self, p: Principal, request: RunRequest, idem: str) -> dict:
        if p.role != "operator":
            raise DomainError("operator_required", 403)
        request_hash = digest(request.model_dump())
        with self.transaction() as c:
            row = c.execute(
                "SELECT * FROM runs WHERE tenant=? AND owner=? AND idem=?",
                (p.tenant, p.subject, idem),
            ).fetchone()
            if row:
                if row["request_hash"] != request_hash:
                    raise DomainError("idempotency_conflict")
                return json.loads(row["state"])
            run_id = uuid.uuid4().hex
            state = {
                "id": run_id,
                "tenant": p.tenant,
                "owner": p.subject,
                "request": request.model_dump(),
                "status": "ready",
                "steps": 0,
                "observations": [],
                "pending": None,
                "answer": None,
                "citations": [],
                "error": None,
                "created": time.time(),
            }
            c.execute(
                "INSERT INTO runs(id,tenant,owner,idem,request_hash,state) VALUES(?,?,?,?,?,?)",
                (run_id, p.tenant, p.subject, idem, request_hash, canonical(state)),
            )
            self._event(c, p.tenant, run_id, "run.created", {"scenario": request.scenario})
            return state

    def get(self, tenant, run_id):
        with self.connection() as c:
            return json.loads(self._row(c, tenant, run_id)["state"])

    def claim(self, tenant, run_id, lease_seconds=45):
        with self.transaction() as c:
            row = self._row(c, tenant, run_id)
            state = json.loads(row["state"])
            if state["status"] not in {"ready", "running"}:
                return None
            if row["lease_until"] > time.time():
                raise DomainError("run_busy")
            lease = uuid.uuid4().hex
            state["status"] = "running"
            c.execute(
                "UPDATE runs SET state=?,lease=?,lease_until=? WHERE id=?",
                (canonical(state), lease, time.time() + lease_seconds, run_id),
            )
            self._event(c, tenant, run_id, "run.claimed")
            return state, lease

    def checkpoint(self, tenant, state, lease, event, data=None, release=False):
        with self.transaction() as c:
            row = self._row(c, tenant, state["id"])
            if row["lease"] != lease or row["lease_until"] < time.time():
                raise DomainError("lease_lost")
            c.execute(
                "UPDATE runs SET state=?,lease=?,lease_until=? WHERE id=?",
                (
                    canonical(state),
                    None if release else lease,
                    0 if release else row["lease_until"],
                    state["id"],
                ),
            )
            self._event(c, tenant, state["id"], event, data)

    def events(self, tenant, run_id):
        with self.connection() as c:
            self._row(c, tenant, run_id)
            return [
                {**dict(r), "data": json.loads(r["data"])}
                for r in c.execute(
                    "SELECT * FROM events WHERE tenant=? AND run_id=? ORDER BY seq",
                    (tenant, run_id),
                )
            ]

    def approve(self, p: Principal, run_id: str, approval: Approval):
        """Review, local effect, ledger, and checkpoint commit together or all roll back.

        This atomicity DOES NOT extend to a future remote Jira/payment API.
        """
        if p.role != "reviewer":
            raise DomainError("reviewer_required", 403)
        with self.transaction() as c:
            row = self._row(c, p.tenant, run_id)
            state = json.loads(row["state"])
            if row["owner"] == p.subject:
                raise DomainError("self_approval_forbidden", 403)
            pending = state["pending"]
            if state["status"] != "waiting" or not pending:
                raise DomainError("not_awaiting_review")
            if pending["expires"] < time.time():
                raise DomainError("approval_expired")
            if pending["fingerprint"] != approval.fingerprint:
                raise DomainError("approval_payload_mismatch")
            if not approval.approve:
                state.update(status="rejected", pending=None)
                self._event(c, p.tenant, run_id, "approval.rejected", {"reviewer": p.subject})
            else:
                # Recompute binding from persisted action; never accept action args from reviewer.
                binding = {
                    "run": run_id,
                    "step": state["steps"],
                    "tenant": p.tenant,
                    "tool": pending["tool"],
                    "arguments": pending["arguments"],
                }
                if digest(binding) != pending["fingerprint"]:
                    raise DomainError("approval_integrity_error")
                result = self._local_effect(c, p.tenant, pending["tool"], pending["arguments"])
                c.execute(
                    "INSERT INTO effects VALUES(?,?,?,?,?)",
                    (p.tenant, run_id, state["steps"], approval.fingerprint, canonical(result)),
                )
                state["observations"].append({"tool": pending["tool"], "result": result})
                state.update(status="ready", pending=None)
                self._event(
                    c,
                    p.tenant,
                    run_id,
                    "approval.applied",
                    {
                        "reviewer": p.subject,
                        "tool": pending["tool"],
                        "fingerprint": approval.fingerprint,
                    },
                )
            c.execute("UPDATE runs SET state=? WHERE id=?", (canonical(state), run_id))
            return state

    def _local_effect(self, c, tenant, tool, args):
        effect_id = uuid.uuid4().hex
        if tool == "create_ticket":
            c.execute(
                "INSERT INTO tickets VALUES(?,?,?,?)",
                (effect_id, tenant, args["title"], args["severity"]),
            )
            return {"ticket_id": effect_id, "system": "local_reference_store"}
        if tool == "issue_refund":
            invoice = c.execute(
                "SELECT paid_cents FROM invoices WHERE tenant=? AND id=?", (tenant, args["invoice"])
            ).fetchone()
            if invoice is None or not 0 < args["amount_cents"] <= min(invoice[0], 5000):
                raise DomainError("refund_not_eligible", 422)
            if c.execute(
                "SELECT 1 FROM refunds WHERE tenant=? AND invoice=?", (tenant, args["invoice"])
            ).fetchone():
                raise DomainError("invoice_already_refunded")
            c.execute(
                "INSERT INTO refunds VALUES(?,?,?,?)",
                (effect_id, tenant, args["invoice"], args["amount_cents"]),
            )
            return {
                "refund_id": effect_id,
                "amount_cents": args["amount_cents"],
                "system": "local_reference_store",
            }
        raise DomainError("unknown_write_tool", 403)

    def docs(self, tenant):
        with self.connection() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT id,source,content FROM documents WHERE tenant=? ORDER BY id LIMIT 100",
                    (tenant,),
                )
            ]

    def memory_get(self, p, session):
        with self.connection() as c:
            return [
                dict(r)
                for r in c.execute(
                    "SELECT kind,content FROM memory WHERE tenant=? AND subject=? "
                    "AND session IN (?, '*') AND expires>? ORDER BY kind",
                    (p.tenant, p.subject, session, time.time()),
                )
            ]

    def memory_put(self, p, session, kind, content, ttl=86400):
        if kind not in {"session", "long_term"} or not 0 < ttl <= 30 * 86400:
            raise ValueError("Invalid memory policy")
        with self.transaction() as c:
            c.execute(
                "INSERT OR REPLACE INTO memory VALUES(?,?,?,?,?,?)",
                (p.tenant, p.subject, session, kind, content[:2000], time.time() + ttl),
            )

    def memory_delete(self, p):
        with self.transaction() as c:
            c.execute("DELETE FROM memory WHERE tenant=? AND subject=?", (p.tenant, p.subject))

    def purge_expired(self):
        with self.transaction() as c:
            c.execute("DELETE FROM memory WHERE expires<=?", (time.time(),))
            c.execute("DELETE FROM rate_limits WHERE window<?", (int(time.time() // 60) - 1,))

    def rate_limit(self, p, limit=60):
        window = int(time.time() // 60)
        with self.transaction() as c:
            c.execute(
                "INSERT INTO rate_limits VALUES(?,?,?,1) ON CONFLICT(tenant,subject,window) "
                "DO UPDATE SET count=count+1",
                (p.tenant, p.subject, window),
            )
            count = c.execute(
                "SELECT count FROM rate_limits WHERE tenant=? AND subject=? AND window=?",
                (p.tenant, p.subject, window),
            ).fetchone()[0]
        if count > limit:
            raise DomainError("rate_limited", 429)
