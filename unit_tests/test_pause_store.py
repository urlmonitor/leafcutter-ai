"""
MODULE: test_pause_store
GOAL: Verify the correctness of scripts/pause_store.py — the durable persistence
    helper for the BO-2300 pause/resume mechanism — using real filesystem I/O
    in pytest's tmp_path fixture. No mocks.
BUSINESS CONTEXT: pause_store.py is invoked by agents dispatched from the JS
    workflow engine (which has no filesystem access). All assertions here
    exercise the actual on-disk behavior: files must appear, JSON must be
    parseable, idempotency must hold, and staleness detection must fire on
    both TTL expiry and an explicit stale flag.
ARCHITECTURE: Imports write_record, read_record, and _is_stale directly from
    scripts/pause_store.py via sys.path insertion (the established project test
    pattern). One test exercises the write subcommand through a real subprocess
    invocation to verify that the CLI layer creates an actual file at the
    expected path. All other tests use the core functions directly with
    tmp_path-backed store directories.

====================================================================
DECISION HISTORY
====================================================================
- 2026-07-21 [python-coder/BO-2300-pause-resume]: Initial test suite.
  Covers: round-trip write+read, absent run_id, TTL staleness, explicit
  stale flag, idempotent write (same gate_id / different gate_id), and
  CLI subprocess proof that a real file appears on disk.
====================================================================
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Import core functions via sys.path insertion (project convention).
# parents: [unit_tests/, worktree-root]
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parents[1]
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_SCRIPT_PATH = _SCRIPTS_DIR / "pause_store.py"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from pause_store import _is_stale, read_record, write_record  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_record(run_id: str = "run-1", gate_id: str = "gate-1") -> dict:
    """Return a minimal valid pending-question record dict.

    Args:
        run_id: Run identifier to embed in the record body.
        gate_id: Gate identifier; controls idempotency behaviour.

    Returns:
        Dict with all required pending-question fields except created_at.
    """
    return {
        "run_id": run_id,
        "gate_id": gate_id,
        "question": "Continue with deployment?",
        "context": {"branch": "main"},
        "status": "pending",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestWriteThenRead:
    """write_record then read_record — basic round-trip."""

    def test_write_adds_created_at_and_round_trips(self, tmp_path: Path) -> None:
        """Writing a record without created_at stamps it; read returns it intact."""
        store = tmp_path / "store"
        record = _base_record()
        assert "created_at" not in record

        write_result = write_record(store, "run-1", record)

        assert write_result["ok"] is True
        assert write_result["idempotent"] is False
        assert write_result["path"].endswith("run-1.json")

        # File must actually exist on disk
        assert (store / "run-1.json").exists()

        read_result = read_record(store, "run-1")

        assert read_result["exists"] is True
        assert read_result["stale"] is False
        persisted = read_result["record"]
        assert persisted is not None
        assert persisted["gate_id"] == "gate-1"
        assert persisted["question"] == "Continue with deployment?"
        assert "created_at" in persisted
        assert isinstance(persisted["created_at"], int)

    def test_write_preserves_explicit_created_at(self, tmp_path: Path) -> None:
        """When the caller provides created_at, write_record must not replace it."""
        store = tmp_path / "store"
        record = {**_base_record(), "created_at": 123456789}

        write_record(store, "run-ts", record)
        read_result = read_record(store, "run-ts")

        assert read_result["record"]["created_at"] == 123456789


class TestAbsentRunId:
    """read_record on a run_id that has never been written."""

    def test_absent_run_returns_not_exists(self, tmp_path: Path) -> None:
        """Reading a non-existent run_id returns exists=False, stale=False, record=None."""
        store = tmp_path / "store"
        result = read_record(store, "never-written")

        assert result["exists"] is False
        assert result["stale"] is False
        assert result["record"] is None


class TestStalenessByTTL:
    """Staleness detection via TTL expiry."""

    def test_stale_when_age_exceeds_ttl(self, tmp_path: Path) -> None:
        """A record whose age exceeds ttl_seconds is reported as stale."""
        store = tmp_path / "store"
        record = {**_base_record("run-old"), "created_at": 1000}

        write_record(store, "run-old", record)

        # now=5000, ttl=100 → age=4000 > 100 → stale
        result = read_record(store, "run-old", ttl_seconds=100, now=5000)

        assert result["exists"] is True
        assert result["stale"] is True

    def test_not_stale_when_age_within_ttl(self, tmp_path: Path) -> None:
        """A record whose age is within ttl_seconds is not stale."""
        store = tmp_path / "store"
        record = {**_base_record("run-fresh"), "created_at": 1000}

        write_record(store, "run-fresh", record)

        # now=1050, ttl=100 → age=50 ≤ 100 → not stale
        result = read_record(store, "run-fresh", ttl_seconds=100, now=1050)

        assert result["exists"] is True
        assert result["stale"] is False


class TestExplicitStaleFlag:
    """Staleness detection via the explicit 'stale' key in the record."""

    def test_stale_flag_true_overrides_ttl(self, tmp_path: Path) -> None:
        """A record with 'stale': True is stale regardless of TTL."""
        store = tmp_path / "store"
        record = {**_base_record("run-flagged"), "created_at": int(1e9), "stale": True}

        write_record(store, "run-flagged", record)

        # Use a very large TTL so TTL alone would not trigger staleness
        result = read_record(store, "run-flagged", ttl_seconds=10_000_000, now=int(1e9) + 1)

        assert result["exists"] is True
        assert result["stale"] is True

    def test_stale_flag_false_leaves_ttl_in_control(self, tmp_path: Path) -> None:
        """A record with 'stale': False is fresh when within TTL."""
        store = tmp_path / "store"
        record = {**_base_record("run-ok"), "created_at": 1000, "stale": False}

        write_record(store, "run-ok", record)

        result = read_record(store, "run-ok", ttl_seconds=100, now=1050)

        assert result["stale"] is False


class TestIdempotency:
    """Idempotent write behaviour."""

    def test_same_gate_id_does_not_overwrite(self, tmp_path: Path) -> None:
        """Writing the same run_id+gate_id twice is a no-op; created_at is preserved."""
        store = tmp_path / "store"
        record = {**_base_record(), "created_at": 1111}

        r1 = write_record(store, "run-idem", record)
        assert r1["idempotent"] is False

        r2 = write_record(store, "run-idem", {**record, "created_at": 9999})
        assert r2["idempotent"] is True

        # The first created_at must survive
        read_result = read_record(store, "run-idem")
        assert read_result["record"]["created_at"] == 1111

    def test_different_gate_id_overwrites(self, tmp_path: Path) -> None:
        """Writing the same run_id with a different gate_id replaces the record."""
        store = tmp_path / "store"
        r1 = write_record(store, "run-gated", {**_base_record(gate_id="gate-A"), "created_at": 111})
        assert r1["idempotent"] is False

        r2 = write_record(store, "run-gated", {**_base_record(gate_id="gate-B"), "created_at": 222})
        assert r2["idempotent"] is False

        read_result = read_record(store, "run-gated")
        assert read_result["record"]["gate_id"] == "gate-B"


class TestIsStale:
    """Unit tests for the pure _is_stale helper."""

    def test_explicit_stale_true(self) -> None:
        assert _is_stale({"stale": True, "created_at": 0}, ttl_seconds=9999, now=1) is True

    def test_explicit_stale_false_with_age_within_ttl(self) -> None:
        assert _is_stale({"stale": False, "created_at": 1000}, ttl_seconds=100, now=1050) is False

    def test_ttl_exceeded(self) -> None:
        assert _is_stale({"created_at": 0}, ttl_seconds=10, now=100) is True

    def test_ttl_not_exceeded(self) -> None:
        assert _is_stale({"created_at": 1000}, ttl_seconds=100, now=1050) is False

    def test_zero_ttl_disables_staleness(self) -> None:
        assert _is_stale({"created_at": 0}, ttl_seconds=0, now=999999) is False


class TestCLISubprocess:
    """Exercise the CLI subcommands through a real subprocess invocation."""

    def test_cli_write_creates_file_on_disk(self, tmp_path: Path) -> None:
        """The write subcommand must create the JSON file at the expected path."""
        store_dir = tmp_path / ".leafcutter" / "paused_runs"
        payload = json.dumps(
            {
                "run_id": "cli-1",
                "gate_id": "g-cli",
                "question": "Deploy?",
                "context": {},
                "status": "pending",
            }
        )

        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_PATH),
                "--store-dir", str(store_dir),
                "write",
                "--run-id", "cli-1",
                "--record", payload,
            ],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0, f"CLI write exited {proc.returncode}: {proc.stderr}"
        out = json.loads(proc.stdout)
        assert out["ok"] is True
        assert out["idempotent"] is False

        # Real file must exist on disk at the expected path
        expected_file = store_dir / "cli-1.json"
        assert expected_file.exists(), f"Expected file not found: {expected_file}"

        # File must be valid JSON with created_at stamped
        on_disk = json.loads(expected_file.read_text(encoding="utf-8"))
        assert on_disk["gate_id"] == "g-cli"
        assert "created_at" in on_disk

    def test_cli_read_absent_run_id(self, tmp_path: Path) -> None:
        """The read subcommand reports exists=false for an absent run_id (exit 0)."""
        store_dir = tmp_path / "empty_store"

        proc = subprocess.run(
            [
                sys.executable,
                str(_SCRIPT_PATH),
                "--store-dir", str(store_dir),
                "read",
                "--run-id", "no-such-run",
            ],
            capture_output=True,
            text=True,
        )

        assert proc.returncode == 0
        out = json.loads(proc.stdout)
        assert out["exists"] is False
        assert out["stale"] is False
        assert out["record"] is None

    def test_cli_write_idempotent_replay(self, tmp_path: Path) -> None:
        """The CLI write subcommand reports idempotent=true on a gate_id replay."""
        store_dir = tmp_path / "store"
        payload = json.dumps(
            {
                "run_id": "cli-idem",
                "gate_id": "g-idem",
                "question": "Q?",
                "context": {},
                "status": "pending",
                "created_at": 5555,
            }
        )
        base_args = [
            sys.executable,
            str(_SCRIPT_PATH),
            "--store-dir", str(store_dir),
            "write",
            "--run-id", "cli-idem",
            "--record", payload,
        ]

        r1 = subprocess.run(base_args, capture_output=True, text=True)
        assert json.loads(r1.stdout)["idempotent"] is False

        r2 = subprocess.run(base_args, capture_output=True, text=True)
        assert json.loads(r2.stdout)["idempotent"] is True
