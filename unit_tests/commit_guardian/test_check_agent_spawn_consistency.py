"""
MODULE: test_check_agent_spawn_consistency
GOAL: Unit tests for scripts/commit_guardian/hooks/check_agent_spawn_consistency.py.
BUSINESS CONTEXT: Verifies the bidirectional spawn consistency hook correctly
    detects mismatches in agent_registry.json at commit time, so engineers
    receive immediate named-pair error messages before bad registry state
    reaches main.
ARCHITECTURE: Tests invoke the hook's main() function directly by importing it,
    with mocked staged-file list and in-memory registry JSON.  The hook script
    does not exist yet — these tests are intentionally RED (TDD red-baseline phase).

These tests cover the 8 Acceptance Criteria from
TICKET-20260604-AgentRegistrySpawnValidationHook.
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = REPO_ROOT / "scripts" / "commit_guardian" / "hooks" / "check_agent_spawn_consistency.py"
REGISTRY_PATH_IN_REPO = "config/agent_registry.json"


def _load_hook_module() -> types.ModuleType:
    """Dynamically load the hook module from its script path.

    Raises ImportError if the file does not exist yet (expected during
    the red-baseline phase).
    """
    if not HOOK_PATH.exists():
        _msg = f"Hook script not found at {HOOK_PATH}. Implement it (python-coder phase)."
        raise ImportError(_msg)
    spec = importlib.util.spec_from_file_location(
        "check_agent_spawn_consistency", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Registry builders
# ---------------------------------------------------------------------------

def _build_registry(agents: list[dict]) -> dict:
    """Wrap a list of agent dicts in the top-level registry structure."""
    return {"agents": agents}


def _make_agent(
    agent_id: str,
    spawn_allowlist: list[str] | None = None,
    spawned_by: list[str] | None = None,
) -> dict:
    """Build a minimal agent entry for testing."""
    entry: dict = {"id": agent_id}
    if spawn_allowlist is not None:
        entry["spawn_allowlist"] = spawn_allowlist
    if spawned_by is not None:
        entry["spawned_by"] = spawned_by
    return entry


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestCheckAgentSpawnConsistency(unittest.TestCase):
    """Tests for the check_agent_spawn_consistency pre-commit hook.

    All tests import main() from the hook module and exercise it via
    patched _get_staged_files() and in-memory registry JSON.
    """

    def setUp(self) -> None:
        """Import the hook module, expecting ImportError until implemented."""
        self.module = _load_hook_module()

    # -- AC-1 ----------------------------------------------------------------

    def test_exits_0_when_registry_not_staged(self) -> None:
        """AC-1: hook exits 0 immediately when config/agent_registry.json is not staged.

        When the registry is not in the staged file list, the hook must return
        0 without loading or parsing the registry.
        """
        staged = ["some_other_file.py", "docs/README.md"]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            result = self.module.main()
        self.assertEqual(
            result, 0,
            "Expected exit 0 when registry is not staged",
        )

    # -- AC-2 ----------------------------------------------------------------

    def test_exits_0_when_registry_consistent(self) -> None:
        """AC-2: hook exits 0 when all spawn relationships are bidirectionally consistent."""
        registry = _build_registry([
            _make_agent("agent-a", spawn_allowlist=["agent-b"], spawned_by=[]),
            _make_agent("agent-b", spawn_allowlist=[], spawned_by=["agent-a"]),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                result = self.module.main()

        self.assertEqual(result, 0, "Expected exit 0 when spawn relationships are consistent")

    # -- AC-3 ----------------------------------------------------------------

    def test_exits_1_on_allowlist_mismatch(self) -> None:
        """AC-3: hook exits 1 and prints named-pair error when A lists B in spawn_allowlist
        but B does not list A in spawned_by.
        """
        registry = _build_registry([
            _make_agent("create-ticket", spawn_allowlist=["brainstorm-lead"], spawned_by=[]),
            _make_agent("brainstorm-lead", spawn_allowlist=[], spawned_by=[]),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                import io
                err_buf = io.StringIO()
                with patch("sys.stderr", err_buf):
                    result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 on allowlist mismatch")
        err_output = err_buf.getvalue()
        self.assertIn("create-ticket", err_output)
        self.assertIn("brainstorm-lead", err_output)

    def test_exits_1_on_spawned_by_mismatch(self) -> None:
        """AC-3 (spawned_by direction): hook exits 1 when B lists A in spawned_by
        but A does not list B in its spawn_allowlist.
        """
        registry = _build_registry([
            _make_agent("create-ticket-v2", spawn_allowlist=[], spawned_by=[]),
            _make_agent("it-po", spawn_allowlist=[], spawned_by=["create-ticket-v2"]),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                import io
                err_buf = io.StringIO()
                with patch("sys.stderr", err_buf):
                    result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 on spawned_by mismatch")
        err_output = err_buf.getvalue()
        self.assertIn("it-po", err_output)
        self.assertIn("create-ticket-v2", err_output)

    def test_error_message_format(self) -> None:
        """AC-3: The error message must contain the header and fix guidance line."""
        registry = _build_registry([
            _make_agent("agent-a", spawn_allowlist=["agent-b"], spawned_by=[]),
            _make_agent("agent-b", spawn_allowlist=[], spawned_by=[]),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                import io
                err_buf = io.StringIO()
                with patch("sys.stderr", err_buf):
                    self.module.main()

        err_output = err_buf.getvalue()
        self.assertIn("[check-agent-spawn-consistency]", err_output)
        self.assertIn("config/agent_registry.json", err_output)

    # -- AC-4 ----------------------------------------------------------------

    def test_skips_special_token(self) -> None:
        """AC-4: __ticket_phase_agents__ in spawn_allowlist is silently skipped."""
        registry = _build_registry([
            _make_agent(
                "ticket-supervisor",
                spawn_allowlist=["__ticket_phase_agents__"],
                spawned_by=[],
            ),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                result = self.module.main()

        self.assertEqual(
            result, 0,
            "__ticket_phase_agents__ token must be silently skipped — should not trigger an error",
        )

    # -- AC-5 ----------------------------------------------------------------

    def test_skips_user_in_spawned_by(self) -> None:
        """AC-5: 'user' in spawned_by is silently skipped."""
        registry = _build_registry([
            _make_agent("some-agent", spawn_allowlist=[], spawned_by=["user"]),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                result = self.module.main()

        self.assertEqual(
            result, 0,
            "'user' in spawned_by must be silently skipped — should not trigger an error",
        )

    # -- AC-6 ----------------------------------------------------------------

    def test_exits_1_on_invalid_json(self) -> None:
        """AC-6: hook exits 1 with a clear error when the registry is not valid JSON."""
        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(self.module, "_read_registry_json", return_value="{invalid"):
                import io
                err_buf = io.StringIO()
                with patch("sys.stderr", err_buf):
                    result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 on invalid JSON")
        err_output = err_buf.getvalue()
        # Must print a clear error, not just a traceback
        self.assertGreater(
            len(err_output), 0,
            "Expected a non-empty error message to stderr on invalid JSON",
        )

    def test_exits_1_on_os_error(self) -> None:
        """AC-6: hook exits 1 with a clear error when the registry file cannot be read."""
        staged = [REGISTRY_PATH_IN_REPO]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            with patch.object(
                self.module,
                "_read_registry_json",
                side_effect=OSError("Permission denied"),
            ):
                import io
                err_buf = io.StringIO()
                with patch("sys.stderr", err_buf):
                    result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 on OSError")
        err_output = err_buf.getvalue()
        self.assertGreater(len(err_output), 0, "Expected a non-empty error message to stderr")

    # -- AC-7: tested via integration (commit_guardian.json content) ----------

    def test_hook_registered_in_commit_guardian_json(self) -> None:
        """AC-7: hook is registered in commit_guardian.json with correct fields."""
        cg_path = REPO_ROOT / "scripts" / "commit_guardian" / "commit_guardian.json"
        self.assertTrue(cg_path.exists(), f"commit_guardian.json not found at {cg_path}")

        with cg_path.open() as fh:
            cg_data = json.load(fh)

        hooks = cg_data.get("hooks_manifest", {}).get("hooks", [])
        hook_ids = [h.get("id") for h in hooks]
        self.assertIn(
            "check-agent-spawn-consistency",
            hook_ids,
            "check-agent-spawn-consistency not found in commit_guardian.json hooks",
        )

        hook = next(h for h in hooks if h.get("id") == "check-agent-spawn-consistency")
        self.assertEqual(
            hook.get("files"),
            r"^config/agent_registry\.json$",
            "files pattern must be '^config/agent_registry\\.json$'",
        )
        self.assertFalse(
            hook.get("pass_filenames", True),
            "pass_filenames must be false",
        )

    # -- AC-8: tested via module introspection --------------------------------

    def test_hook_has_module_docstring(self) -> None:
        """AC-8: hook script has a module-level docstring with required sections."""
        docstring = self.module.__doc__
        self.assertIsNotNone(docstring, "Hook module must have a docstring")
        assert docstring is not None
        for required_field in ("MODULE", "GOAL", "BUSINESS CONTEXT", "ARCHITECTURE"):
            self.assertIn(
                required_field,
                docstring,
                f"Module docstring missing required field: {required_field}",
            )

    def test_hook_has_decision_history_block(self) -> None:
        """AC-8: hook script has a DECISION HISTORY block at the bottom."""
        source_code = HOOK_PATH.read_text()
        self.assertIn(
            "DECISION HISTORY",
            source_code,
            "Hook script must contain a '# DECISION HISTORY' block",
        )


if __name__ == "__main__":
    unittest.main()
