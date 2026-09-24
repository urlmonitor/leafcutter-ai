"""Repository-local SQLite state, atomic claims, capacity and bounded attempts.

Transactions serialize admission across processes. Expiry is diagnostic only:
only a proven completion or explicit recovery releases a live capacity lease.
"""

from __future__ import annotations

import json
import logging
import math
import sqlite3
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from pathlib import Path

from .store_schema import DEFAULT_SETTINGS, SCHEMA as _SCHEMA, StoreError, initialize_metadata  # noqa: F401

logger = logging.getLogger(__name__)


class Store:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.connection = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA busy_timeout=30000")
            self.connection.execute("PRAGMA foreign_keys=ON")
            self.connection.execute("PRAGMA journal_mode=WAL")
            self.connection.executescript(_SCHEMA)
            with self._transaction():
                initialize_metadata(self.connection)
        except (sqlite3.Error, OSError) as error:
            logger.exception("Cannot initialize worker state at %s", self.path)
            raise StoreError(f"Cannot initialize worker state: {self.path}") from error

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def close(self):
        try:
            self.connection.close()
        except sqlite3.Error as error:
            logger.exception("Cannot close worker state")
            raise StoreError("Cannot close worker state") from error

    @contextmanager
    def _transaction(self):
        try:
            self.connection.execute("BEGIN IMMEDIATE")
            yield
            self.connection.commit()
        except sqlite3.Error as error:
            logger.exception("Worker state transaction failed")
            raise StoreError("Worker state transaction failed") from error
        finally:
            if self.connection.in_transaction:
                self.connection.rollback()

    def _read(self, sql, parameters=()):
        try:
            return self.connection.execute(sql, parameters).fetchall()
        except sqlite3.Error as error:
            logger.exception("Cannot read worker state")
            raise StoreError("Cannot read worker state") from error

    @staticmethod
    def _json(raw):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as error:
            logger.exception("Corrupt JSON in worker state")
            raise StoreError(
                "Corrupt persisted worker state; explicit recovery required"
            ) from error

    def get_settings(self) -> dict:
        return self._json(self._read("SELECT body FROM settings WHERE id=1")[0][0])

    def update_settings(self, **fields) -> dict:
        if "max_agent_calls" in fields and (
            type(fields["max_agent_calls"]) is not int or fields["max_agent_calls"] < 1
        ):
            raise ValueError("max_agent_calls must be a positive integer")
        if "enabled" in fields and type(fields["enabled"]) is not bool:
            raise ValueError("enabled must be boolean")
        with self._transaction():
            settings = self.get_settings()
            settings.update(fields)
            settings["settings_revision"] = uuid.uuid4().hex
            self.connection.execute(
                "UPDATE settings SET body=? WHERE id=1", (json.dumps(settings),)
            )
        return settings

    def claim_feature(self, plan) -> dict | None:
        plan = asdict(plan) if is_dataclass(plan) else dict(plan)
        feature = plan["feature_id"]
        with self._transaction():
            if not self.get_settings()["enabled"]:
                return None
            if self.connection.execute(
                "SELECT id FROM runs WHERE feature_id=?", (feature,)
            ).fetchone():
                return None
            run_id, now = uuid.uuid4().hex, time.time()
            self.connection.execute(
                "INSERT INTO runs(id,feature_id,state,plan,payload,scope_digest,created_at,updated_at) VALUES(?,?,'claimed',?,'{}',?,?,?)",
                (run_id, feature, json.dumps(plan), plan.get("scope_digest", ""), now, now),
            )
            for ac_id in plan.get("ac_ids", []):
                self.connection.execute(
                    "INSERT INTO budgets(run_id,ac_id) VALUES(?,?)", (run_id, ac_id)
                )
        return self.get_run(run_id)

    def get_run(self, run_id: str) -> dict:
        rows = self._read("SELECT * FROM runs WHERE id=?", (run_id,))
        if not rows:
            raise KeyError(f"Unknown run {run_id}")
        run = dict(rows[0])
        run["run_id"] = run["id"]
        run["plan"], run["payload"] = self._json(run["plan"]), self._json(run["payload"])
        run["workspace"] = run["payload"].get("workspace")
        run["budgets"] = {
            row["ac_id"]: self._budget(row)
            for row in self._read("SELECT * FROM budgets WHERE run_id=?", (run_id,))
        }
        return run

    def list_runs(self) -> list[dict]:
        return [
            self.get_run(row[0]) for row in self._read("SELECT id FROM runs ORDER BY created_at,id")
        ]

    def reserved_features(self) -> set[str]:
        # Delivered and blocked runs remain reservations until explicit lifecycle reconciliation.
        return {row[0] for row in self._read("SELECT feature_id FROM runs")}

    def checkpoint(self, run_id: str, state: str, payload: dict | None = None) -> dict:
        with self._transaction():
            run = self.get_run(run_id)
            merged = {**run["payload"], **(payload or {})}
            self.connection.execute(
                "UPDATE runs SET state=?,payload=?,updated_at=? WHERE id=?",
                (state, json.dumps(merged), time.time(), run_id),
            )
        return self.get_run(run_id)

    def acquire_lease(
        self, run_id: str, role: str, owner: str, ttl_seconds: float = 300
    ) -> dict | None:
        if not owner or not role or ttl_seconds <= 0:
            raise ValueError("Lease owner, role and positive TTL are required")
        with self._transaction():
            settings = self.get_settings()
            run = self.get_run(run_id)
            if not settings["enabled"] or run["state"] in {"blocked", "delivered", "completed"}:
                return None
            # Expired leases still count. Their subprocess may be alive or its effects uncertain.
            count = self.connection.execute(
                "SELECT COUNT(*) FROM leases WHERE released_at IS NULL"
            ).fetchone()[0]
            if count >= settings["max_agent_calls"]:
                return None
            lease_id, now = uuid.uuid4().hex, time.time()
            self.connection.execute(
                "INSERT INTO leases VALUES(?,?,?,?,?,?,NULL)",
                (lease_id, run_id, role, owner, now, now + ttl_seconds),
            )
        return {
            "lease_id": lease_id,
            "run_id": run_id,
            "role": role,
            "owner": owner,
            "acquired_at": now,
            "expires_at": now + ttl_seconds,
            "settings_revision": settings["settings_revision"],
        }

    def renew_lease(self, lease_id: str, owner: str, ttl_seconds: float = 300) -> bool:
        if ttl_seconds <= 0:
            raise ValueError("TTL must be positive")
        with self._transaction():
            cursor = self.connection.execute(
                "UPDATE leases SET expires_at=? WHERE lease_id=? AND owner=? AND released_at IS NULL",
                (time.time() + ttl_seconds, lease_id, owner),
            )
        return cursor.rowcount == 1

    def release_lease(self, lease_id: str, owner: str) -> bool:
        """Caller must prove termination/completion, not merely a timed-out wait."""
        with self._transaction():
            cursor = self.connection.execute(
                "UPDATE leases SET released_at=? WHERE lease_id=? AND owner=? AND released_at IS NULL",
                (time.time(), lease_id, owner),
            )
        return cursor.rowcount == 1

    def list_leases(self, run_id: str | None = None) -> list[dict]:
        sql = "SELECT * FROM leases WHERE released_at IS NULL"
        return [
            dict(row)
            for row in self._read(
                sql + (" AND run_id=?" if run_id else ""), (run_id,) if run_id else ()
            )
        ]

    @staticmethod
    def _budget(row) -> dict:
        result = dict(row)
        result["in_progress"] = bool(result["in_progress"])
        result["remaining_seconds"] = max(0, 3600 - result["elapsed_seconds"])
        return result

    def begin_attempt(self, run_id: str, ac_id: str) -> dict | None:
        with self._transaction():
            run = self.get_run(run_id)
            if not self.get_settings()["enabled"] or run["state"] in {
                "blocked",
                "delivered",
                "completed",
            }:
                return None
            if ac_id not in run["plan"].get("ac_ids", []):
                raise ValueError(f"AC {ac_id} is outside the claimed plan")
            budget = run["budgets"][ac_id]
            if (
                budget["in_progress"]
                or budget["attempts"] >= 3
                or budget["elapsed_seconds"] >= 3600
            ):
                return None
            self.connection.execute(
                "UPDATE budgets SET attempts=attempts+1,in_progress=1 WHERE run_id=? AND ac_id=?",
                (run_id, ac_id),
            )
        return self.get_run(run_id)["budgets"][ac_id]

    def finish_attempt(
        self, run_id: str, ac_id: str, elapsed_seconds: float, success: bool = False
    ) -> dict:
        if (
            not isinstance(elapsed_seconds, (int, float))
            or not math.isfinite(elapsed_seconds)
            or elapsed_seconds < 0
        ):
            raise ValueError("Elapsed implementation time must be finite and nonnegative")
        with self._transaction():
            cursor = self.connection.execute(
                "UPDATE budgets SET elapsed_seconds=elapsed_seconds+?,in_progress=0,last_success=? WHERE run_id=? AND ac_id=? AND in_progress=1",
                (elapsed_seconds, int(success), run_id, ac_id),
            )
            if cursor.rowcount != 1:
                raise ValueError(
                    "No in-progress attempt to finish; duplicate results cannot reset accounting"
                )
        return self.get_run(run_id)["budgets"][ac_id]

    def record_attempt(
        self, run_id: str, ac_id: str, elapsed_seconds: float, success: bool = False
    ) -> dict:
        """Compatibility completion alias; callers must reserve with begin_attempt first."""
        return self.finish_attempt(run_id, ac_id, elapsed_seconds, success)

    def begin_review(self, run_id: str) -> int | None:
        with self._transaction():
            run = self.get_run(run_id)
            if (
                not self.get_settings()["enabled"]
                or run["state"] in {"blocked", "delivered", "completed"}
                or run["review_count"] >= 2
            ):
                return None
            count = run["review_count"] + 1
            self.connection.execute(
                "UPDATE runs SET review_count=?,updated_at=? WHERE id=?",
                (count, time.time(), run_id),
            )
        return count

    def record_review(self, run_id: str) -> int | None:
        return self.begin_review(run_id)

    def block_run(self, run_id: str, reason: str, details: dict | None = None) -> dict:
        details = details or {}
        fingerprint = json.dumps([reason, details], sort_keys=True)
        with self._transaction():
            self.get_run(run_id)
            self.connection.execute(
                "UPDATE runs SET state='blocked',updated_at=? WHERE id=?", (time.time(), run_id)
            )
            existing = self.connection.execute(
                "SELECT id FROM inbox WHERE run_id=? AND fingerprint=? AND status='pending'",
                (run_id, fingerprint),
            ).fetchone()
            item_id = existing[0] if existing else uuid.uuid4().hex
            if not existing:
                self.connection.execute(
                    "INSERT INTO inbox(id,run_id,reason,details,fingerprint,created_at) VALUES(?,?,?,?,?,?)",
                    (item_id, run_id, reason, json.dumps(details), fingerprint, time.time()),
                )
        return self.get_inbox(item_id)

    def get_inbox(self, item_id: str) -> dict:
        rows = self._read("SELECT * FROM inbox WHERE id=?", (item_id,))
        if not rows:
            raise KeyError(f"Unknown attention item {item_id}")
        item = dict(rows[0])
        item["details"] = self._json(item["details"])
        return item

    def list_inbox(self, *, pending_only: bool = False) -> list[dict]:
        where = " WHERE status='pending'" if pending_only else ""
        return [
            self.get_inbox(row[0])
            for row in self._read("SELECT id FROM inbox" + where + " ORDER BY created_at,id")
        ]

    def resolve_inbox(self, item_id: str, answer: str) -> bool:
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("An explicit non-empty answer is required")
        with self._transaction():
            cursor = self.connection.execute(
                "UPDATE inbox SET status='resolved',answer=?,resolved_at=? WHERE id=? AND status='pending'",
                (answer, time.time(), item_id),
            )
        return cursor.rowcount == 1

    def answer_request(self, run_id: str, item_id: str, answer: str) -> dict | None:
        """Atomically bind an answer and the resumable checkpoint to its own run.

        A crash cannot leave an answered request blocking a run forever, and
        simultaneous answers cannot overwrite another request's saved context.
        """
        if not isinstance(answer, str) or not answer.strip():
            raise ValueError("An explicit non-empty answer is required")
        with self._transaction():
            row = self.connection.execute(
                "SELECT * FROM inbox WHERE id=? AND run_id=? AND status='pending'",
                (item_id, run_id),
            ).fetchone()
            if not row:
                return None
            run = self.get_run(run_id)
            if run["state"] in {"delivered", "completed"}:
                return None
            self.connection.execute(
                "UPDATE inbox SET status='resolved',answer=?,resolved_at=? WHERE id=?",
                (answer, time.time(), item_id),
            )
            answers = {
                item["id"]: item["answer"]
                for item in self.connection.execute(
                    "SELECT id,answer FROM inbox WHERE run_id=? AND status='resolved'", (run_id,)
                )
            }
            pending = self.connection.execute(
                "SELECT COUNT(*) FROM inbox WHERE run_id=? AND status='pending'", (run_id,)
            ).fetchone()[0]
            state = "blocked" if pending else "paused"
            answered_requests = {
                item["id"]: {
                    "question": item["reason"],
                    "details": self._json(item["details"]),
                    "answer": item["answer"],
                }
                for item in self.connection.execute(
                    "SELECT id,reason,details,answer FROM inbox WHERE run_id=? AND status='resolved'",
                    (run_id,),
                )
            }
            payload = {
                **run["payload"],
                "request_answers": answers,
                "answered_requests": answered_requests,
            }
            self.connection.execute(
                "UPDATE runs SET state=?,payload=?,updated_at=? WHERE id=?",
                (state, json.dumps(payload), time.time(), run_id),
            )
        return {"run_id": run_id, "request_id": item_id, "state": state}

    def get_queue_status(self) -> dict:
        rows = self._read("SELECT value FROM metadata WHERE key='queue_status'")
        return self._json(rows[0][0]) if rows else {}

    def set_queue_status(self, payload: dict) -> dict:
        snapshot = {**payload, "updated_at": time.time()}
        with self._transaction():
            self.connection.execute(
                "INSERT INTO metadata(key,value) VALUES('queue_status',?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (json.dumps(snapshot),),
            )
        return snapshot
