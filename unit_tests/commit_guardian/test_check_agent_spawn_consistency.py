"""
MODULE: test_check_agent_spawn_consistency
GOAL: Unit tests for scripts/commit_guardian/hooks/check_agent_spawn_consistency.py.
BUSINESS CONTEXT: Verifies the bidirectional spawn consistency hook correctly
    detects mismatches in agent_registry.json at commit time, so engineers
    receive immediate named-pair error messages before bad registry state
    reaches main.  Also verifies the card<->registry mirror check added in
    EPIC-RegistryCardMirror/01 (AC INF-600l-1): generated agent cards must
    agree with the registry's spawn relationships in both directions.
ARCHITECTURE: Tests invoke the hook's main() function directly by importing it,
    with mocked staged-file list and in-memory registry JSON.  New card-mirror
    tests call _parse_card_spawn_edges() and _check_card_registry_mirror()
    directly, using temporary directories with synthetic .card.md fixtures.

These tests cover the 8 Acceptance Criteria from
TICKET-20260604-AgentRegistrySpawnValidationHook, plus 3 new AC tests for
INF-600l-1 (card<->registry mirror mismatch detection).
"""

from __future__ import annotations

import importlib
import importlib.util
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch

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


# ---------------------------------------------------------------------------
# Helpers for card-mirror tests
# ---------------------------------------------------------------------------

def _make_card_text(
    agent_id: str,
    spawns: list[str] | None = None,
    dispatched_by: list[str] | None = None,
) -> str:
    """Build a minimal .card.md string with a mermaid Spawn and Dependency block.

    Args:
        agent_id: The agent identifier for this card (used as self_id).
        spawns: List of agent IDs this agent spawns (-->|spawns|).
        dispatched_by: List of agent IDs that dispatch this agent (-->|dispatches|).

    Returns:
        Minimal card text containing a mermaid block with the requested edges.
    """
    spawns = spawns or []
    dispatched_by = dispatched_by or []
    self_node = agent_id.replace("-", "_")

    lines = [
        "---",
        f"agent_id: {agent_id}",
        "type: card",
        "---",
        "",
        f"# {agent_id}",
        "",
        "## Spawn and Dependency",
        "",
        "```mermaid",
        "flowchart TD",
    ]

    # Parent nodes
    for parent in dispatched_by:
        parent_node = parent.replace("-", "_")
        lines.append(f'    {parent_node}["{parent}\\n(supervisor tier)"]:::supervisor')

    # Self node
    lines.append(f'    {self_node}["{agent_id}\\n(phase tier, priority 1)"]:::target')

    # Child nodes
    for child in spawns:
        child_node = child.replace("-", "_")
        lines.append(f'    {child_node}["{child}\\n(phase tier)"]:::phase')

    lines.append("")

    # Edges
    for parent in dispatched_by:
        parent_node = parent.replace("-", "_")
        lines.append(f"    {parent_node} -->|dispatches| {self_node}")
    for child in spawns:
        child_node = child.replace("-", "_")
        lines.append(f"    {self_node} -->|spawns| {child_node}")

    lines.append("```")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tests for _parse_card_spawn_edges
# ---------------------------------------------------------------------------

class TestParseCardSpawnEdges(unittest.TestCase):
    """Tests for _parse_card_spawn_edges() — the mermaid edge parser."""

    def setUp(self) -> None:
        self.module = _load_hook_module()

    def test_parses_spawn_edge(self) -> None:
        """parse returns the spawned child in spawn_allowlist_set."""
        card_text = _make_card_text(
            "python-coder",
            spawns=["sql-coder"],
            dispatched_by=["ticket-supervisor"],
        )
        spawn_set, _ = self.module._parse_card_spawn_edges(card_text, "python-coder")
        self.assertIn(
            "sql-coder",
            spawn_set,
            "sql-coder must appear in spawn_allowlist_set",
        )

    def test_parses_dispatches_edge(self) -> None:
        """parse returns the dispatcher in spawned_by_set."""
        card_text = _make_card_text(
            "python-coder",
            spawns=["research-agent"],
            dispatched_by=["ticket-supervisor", "sql-coder"],
        )
        _, spawned_by_set = self.module._parse_card_spawn_edges(card_text, "python-coder")
        self.assertIn("ticket-supervisor", spawned_by_set)
        self.assertIn("sql-coder", spawned_by_set)

    def test_empty_card_returns_empty_sets(self) -> None:
        """parse returns empty sets when there are no mermaid edges."""
        card_text = "# bare-agent\n\nNo mermaid block here.\n"
        spawn_set, spawned_by_set = self.module._parse_card_spawn_edges(card_text, "bare-agent")
        self.assertEqual(spawn_set, set())
        self.assertEqual(spawned_by_set, set())

    def test_does_not_pick_up_other_agents_edges(self) -> None:
        """parse only picks up edges involving the target agent."""
        # Card for python-coder, but we parse as if agent_id is sql-coder
        card_text = _make_card_text(
            "python-coder",
            spawns=["sql-coder"],
            dispatched_by=["ticket-supervisor"],
        )
        # Parsing as sql-coder — the python-coder edges should not be captured
        spawn_set, spawned_by_set = self.module._parse_card_spawn_edges(card_text, "sql-coder")
        self.assertNotIn("sql-coder", spawn_set)
        self.assertNotIn("ticket-supervisor", spawned_by_set)


# ---------------------------------------------------------------------------
# Tests for _check_card_registry_mirror
# ---------------------------------------------------------------------------

class TestCheckCardRegistryMirror(unittest.TestCase):
    """Tests for _check_card_registry_mirror() — the card vs. registry comparator.

    Covers AC INF-600l-1: card<->registry mirror mismatch detection in both
    directions for spawn_allowlist and spawned_by.
    """

    def setUp(self) -> None:
        self.module = _load_hook_module()

    # -- AC INF-600l-1 (direction 1a): card has spawn edge registry does not -----

    def test_card_spawn_edge_missing_from_registry_reported(self) -> None:
        # covers: INF-600l-1
        """Card shows python-coder spawning sql-coder, but registry has no such edge.

        Expected error names both agents and states which side is missing the edge.
        """
        agents = [
            {"id": "python-coder", "spawn_allowlist": ["research-agent"], "spawned_by": ["ticket-supervisor"]},
            {"id": "sql-coder", "spawn_allowlist": [], "spawned_by": []},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as cards_dir_str:
            cards_dir = Path(cards_dir_str)
            # Card for python-coder shows it spawning sql-coder (extra edge)
            card_text = _make_card_text(
                "python-coder",
                spawns=["research-agent", "sql-coder"],  # sql-coder is the extra edge
                dispatched_by=["ticket-supervisor"],
            )
            (cards_dir / "python-coder.card.md").write_text(card_text, encoding="utf-8")

            errors = self.module._check_card_registry_mirror(agents, cards_dir)

        self.assertTrue(
            any("python-coder" in e and "sql-coder" in e for e in errors),
            f"Expected error mentioning both python-coder and sql-coder, got: {errors}",
        )
        self.assertTrue(
            any("registry has no such edge" in e for e in errors),
            f"Expected 'registry has no such edge' in errors, got: {errors}",
        )

    # -- AC INF-600l-1 (direction 1b): registry has spawn edge card does not ----

    def test_registry_spawn_edge_missing_from_card_reported(self) -> None:
        # covers: INF-600l-1
        """Registry lists sql-coder in python-coder spawn_allowlist, but card does not show it.

        Expected error names both agents and states which side is missing the edge.
        """
        agents = [
            {"id": "python-coder", "spawn_allowlist": ["research-agent", "sql-coder"], "spawned_by": ["ticket-supervisor"]},
            {"id": "sql-coder", "spawn_allowlist": [], "spawned_by": []},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as cards_dir_str:
            cards_dir = Path(cards_dir_str)
            # Card for python-coder only shows research-agent (missing sql-coder)
            card_text = _make_card_text(
                "python-coder",
                spawns=["research-agent"],  # sql-coder missing from card
                dispatched_by=["ticket-supervisor"],
            )
            (cards_dir / "python-coder.card.md").write_text(card_text, encoding="utf-8")

            errors = self.module._check_card_registry_mirror(agents, cards_dir)

        self.assertTrue(
            any("python-coder" in e and "sql-coder" in e for e in errors),
            f"Expected error mentioning both python-coder and sql-coder, got: {errors}",
        )
        self.assertTrue(
            any("card does not show it" in e for e in errors),
            f"Expected 'card does not show it' in errors, got: {errors}",
        )

    # -- AC INF-600l-1 (agree case): card and registry agree → no mismatch ------

    def test_card_and_registry_agree_no_error(self) -> None:
        # covers: INF-600l-1
        """When card and registry agree on all spawn relationships, no errors are reported."""
        agents = [
            {"id": "python-coder", "spawn_allowlist": ["research-agent"], "spawned_by": ["ticket-supervisor"]},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as cards_dir_str:
            cards_dir = Path(cards_dir_str)
            # Card exactly matches registry
            card_text = _make_card_text(
                "python-coder",
                spawns=["research-agent"],
                dispatched_by=["ticket-supervisor"],
            )
            (cards_dir / "python-coder.card.md").write_text(card_text, encoding="utf-8")

            errors = self.module._check_card_registry_mirror(agents, cards_dir)

        self.assertEqual(
            errors,
            [],
            f"Expected no errors when card and registry agree, got: {errors}",
        )

    def test_no_card_file_silently_skipped(self) -> None:
        """Agents without a card file are silently skipped — no errors."""
        agents = [
            {"id": "nonexistent-agent", "spawn_allowlist": ["other-agent"], "spawned_by": []},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as cards_dir_str:
            cards_dir = Path(cards_dir_str)
            # No card file written for nonexistent-agent

            errors = self.module._check_card_registry_mirror(agents, cards_dir)

        self.assertEqual(
            errors,
            [],
            f"Expected no errors when card file is absent, got: {errors}",
        )

    def test_special_token_in_registry_skipped(self) -> None:
        """__ticket_phase_agents__ in registry spawn_allowlist is not reported as a mismatch."""
        agents = [
            {"id": "ticket-supervisor", "spawn_allowlist": ["__ticket_phase_agents__"], "spawned_by": ["user"]},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as cards_dir_str:
            cards_dir = Path(cards_dir_str)
            # Card has no spawns (special token not shown as individual edge)
            card_text = _make_card_text(
                "ticket-supervisor",
                spawns=[],
                dispatched_by=[],  # 'user' is external, skip
            )
            (cards_dir / "ticket-supervisor.card.md").write_text(card_text, encoding="utf-8")

            errors = self.module._check_card_registry_mirror(agents, cards_dir)

        # __ticket_phase_agents__ must not produce a mismatch error
        self.assertFalse(
            any("__ticket_phase_agents__" in e for e in errors),
            f"Special token must not cause mismatch errors, got: {errors}",
        )

    def test_external_caller_user_in_spawned_by_skipped(self) -> None:
        """'user' in registry spawned_by is skipped — not reported as a mismatch."""
        agents = [
            {"id": "some-agent", "spawn_allowlist": [], "spawned_by": ["user"]},
        ]

        import tempfile
        with tempfile.TemporaryDirectory() as cards_dir_str:
            cards_dir = Path(cards_dir_str)
            # Card does not show user as dispatcher (user is external, expect it to be skipped)
            card_text = _make_card_text(
                "some-agent",
                spawns=[],
                dispatched_by=[],
            )
            (cards_dir / "some-agent.card.md").write_text(card_text, encoding="utf-8")

            errors = self.module._check_card_registry_mirror(agents, cards_dir)

        self.assertEqual(
            errors,
            [],
            f"'user' in spawned_by must be skipped — no errors expected, got: {errors}",
        )


# ---------------------------------------------------------------------------
# Tests for main() with card-file trigger
# ---------------------------------------------------------------------------

class TestMainCardMirrorTrigger(unittest.TestCase):
    """Tests for the extended main() that also triggers on staged card files."""

    def setUp(self) -> None:
        self.module = _load_hook_module()

    def test_exits_0_when_neither_registry_nor_cards_staged(self) -> None:
        """main() exits 0 immediately when neither registry nor card files are staged."""
        staged = ["docs/some-doc.md", "scripts/build.py"]
        with patch.object(self.module, "_get_staged_files", return_value=staged):
            result = self.module.main()
        self.assertEqual(result, 0, "Expected exit 0 when nothing relevant is staged")

    def test_triggers_when_card_staged_without_registry(self) -> None:
        """main() does not skip immediately when a card file is staged (no registry staged)."""
        import tempfile
        staged = ["docs/agents/cards/python-coder.card.md"]
        # Registry with consistent state (fake agents so card check finds no cards)
        registry = _build_registry([
            _make_agent("fake-agent-only", spawn_allowlist=[], spawned_by=[]),
        ])
        registry_json = json.dumps(registry)

        with tempfile.TemporaryDirectory() as tmp:
            # Patch _get_repo_root to return temp dir (no card files → card check passes)
            with patch.object(self.module, "_get_staged_files", return_value=staged):
                with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                    with patch.object(
                        self.module,
                        "_get_repo_root",
                        return_value=Path(tmp),
                    ):
                        result = self.module.main()

        # Should proceed (not short-circuit on registry check) and pass with no errors
        self.assertEqual(result, 0, "Expected exit 0: cards staged, registry consistent")

    def test_main_reports_card_mirror_mismatch_on_registry_staged(self) -> None:
        """main() reports card<->registry mismatch when registry is staged and card disagrees."""
        import tempfile

        # Registry: python-coder can only spawn research-agent
        registry = _build_registry([
            _make_agent("python-coder", spawn_allowlist=["research-agent"], spawned_by=["ticket-supervisor"]),
            _make_agent("research-agent", spawn_allowlist=[], spawned_by=["python-coder"]),
            _make_agent("ticket-supervisor", spawn_allowlist=["python-coder"], spawned_by=["user"]),
            _make_agent("sql-coder", spawn_allowlist=[], spawned_by=[]),
        ])
        registry_json = json.dumps(registry)

        staged = [REGISTRY_PATH_IN_REPO]

        with tempfile.TemporaryDirectory() as tmp_root:
            tmp_root_path = Path(tmp_root)
            cards_dir = tmp_root_path / "docs" / "agents" / "cards"
            cards_dir.mkdir(parents=True)

            # Card for python-coder shows it spawning sql-coder (not in registry)
            card_text = _make_card_text(
                "python-coder",
                spawns=["research-agent", "sql-coder"],  # sql-coder is extra
                dispatched_by=["ticket-supervisor"],
            )
            (cards_dir / "python-coder.card.md").write_text(card_text, encoding="utf-8")

            with patch.object(self.module, "_get_staged_files", return_value=staged):
                with patch.object(self.module, "_read_registry_json", return_value=registry_json):
                    with patch.object(
                        self.module, "_get_repo_root", return_value=tmp_root_path
                    ):
                        import io
                        err_buf = io.StringIO()
                        with patch("sys.stderr", err_buf):
                            result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 on card<->registry mismatch")
        err_output = err_buf.getvalue()
        self.assertIn("python-coder", err_output)
        self.assertIn("sql-coder", err_output)
        self.assertIn("[check-agent-spawn-consistency]", err_output)
        self.assertIn("config/agent_registry.json", err_output)


if __name__ == "__main__":
    unittest.main()
