"""Durable worker database schema and initial operator settings."""

import json

DEFAULT_SETTINGS = {
    "enabled": False,
    "max_agent_calls": 1,
    "target_ref": "origin/main",
    "poll_seconds": 15,
    "implementation": {
        "executor": "codex-cli",
        "provider": "ollama",
        "model": "qwen3.5:9b-q4_K_M",
        "endpoint": "http://127.0.0.1:11434",
    },
    "reviewer": None,
    "checks": [],
    "settings_revision": "initial",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY CHECK(id=1), body TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
 id TEXT PRIMARY KEY, feature_id TEXT NOT NULL UNIQUE, state TEXT NOT NULL,
 plan TEXT NOT NULL, payload TEXT NOT NULL, scope_digest TEXT NOT NULL,
 review_count INTEGER NOT NULL DEFAULT 0, generation INTEGER NOT NULL DEFAULT 1,
 created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS budgets (
 run_id TEXT NOT NULL REFERENCES runs(id), ac_id TEXT NOT NULL,
 attempts INTEGER NOT NULL DEFAULT 0, elapsed_seconds REAL NOT NULL DEFAULT 0,
 in_progress INTEGER NOT NULL DEFAULT 0, last_success INTEGER NOT NULL DEFAULT 0,
 PRIMARY KEY(run_id,ac_id));
CREATE TABLE IF NOT EXISTS leases (
 lease_id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), role TEXT NOT NULL,
 owner TEXT NOT NULL, acquired_at REAL NOT NULL, expires_at REAL NOT NULL, released_at REAL);
CREATE TABLE IF NOT EXISTS inbox (
 id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id), reason TEXT NOT NULL,
 details TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 answer TEXT, created_at REAL NOT NULL, resolved_at REAL);
CREATE UNIQUE INDEX IF NOT EXISTS pending_inbox ON inbox(run_id,fingerprint) WHERE status='pending';
"""


class StoreError(RuntimeError):
    """Durable state could not be read or committed; never treat this as empty state."""


def initialize_metadata(connection):
    """Validate schema version and seed defaults inside the caller transaction."""
    version = connection.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
    if version and version[0] != "1":
        raise StoreError(f"Unsupported background-worker state version {version[0]}")
    connection.execute("INSERT OR IGNORE INTO metadata VALUES ('schema_version','1')")
    connection.execute(
        "INSERT OR IGNORE INTO settings VALUES (1,?)", (json.dumps(DEFAULT_SETTINGS),)
    )
