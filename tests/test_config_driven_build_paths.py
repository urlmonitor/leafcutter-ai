"""Tests for config-driven build path fixes.

Covers three deliverables from TICKET-20260603-ConfigDrivenBuildPaths:
  1. build_ticket_lifecycle() derives tickets_root from config, adds skip guard
     and folder remap.
  2. build_project_paths_table() accepts a config overlay parameter.
  3. compile_agent_template() threads config through to _apply_registry_injection()
     so {{project_paths_table}} reflects config-overridden paths.
"""

from __future__ import annotations

import pathlib
import sys
import tempfile
import unittest

# Add scripts/ to path so imports work without packaging.
_SCRIPTS_DIR = pathlib.Path(__file__).parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))


class TestBuildTicketLifecycleConfigPath(unittest.TestCase):
    """build_ticket_lifecycle() derives tickets_root from config key."""

    def test_ticket_lifecycle_uses_config_inbox_path(self) -> None:
        """When tickets_inbox_path is set, scaffold goes under that parent, NOT 'tickets/'."""
        from build_phases import build_ticket_lifecycle  # type: ignore[import-untyped]

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            config = {"tickets_inbox_path": "sub/tickets/00_inbox"}
            build_ticket_lifecycle(root, config, dry_run=False, force=True)

            # The hardcoded 'tickets/' directory must NOT be the tickets root.
            # (It may exist if the remap fallback wrote todo/done there — but the
            # inbox specifically must live under 'sub/tickets/'.)
            inbox = root / "sub" / "tickets" / "00_inbox"
            self.assertTrue(
                inbox.exists(),
                f"Expected inbox at {inbox} but it was not created.",
            )

    def test_ticket_lifecycle_skip_guard_when_manifest_exists(self) -> None:
        """When ticket_lifecycle.json already exists and force=False, return 0."""
        from build_phases import build_ticket_lifecycle  # type: ignore[import-untyped]

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            config: dict = {}
            # First call creates the manifest.
            build_ticket_lifecycle(root, config, dry_run=False, force=True)
            # Second call with force=False must skip.
            result = build_ticket_lifecycle(root, config, dry_run=False, force=False)
            self.assertEqual(
                result,
                0,
                "Expected skip-guard to return 0 when manifest exists and force=False.",
            )

    def test_ticket_lifecycle_skip_guard_bypassed_by_force(self) -> None:
        """When force=True, the skip guard is bypassed and files are written.

        The skip guard returns 0 immediately when the manifest exists AND
        force=False.  With force=True, the guard is bypassed and the function
        proceeds to process all write candidates.  We verify bypass by
        pre-writing a *stale* manifest (different content) so the compare-
        before-write guard doesn't suppress the write — giving us a non-zero
        written count.
        """
        from build_phases import build_ticket_lifecycle  # type: ignore[import-untyped]

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            config: dict = {}
            tickets_root = root / "tickets"
            tickets_root.mkdir(parents=True)
            # Pre-create the manifest with stale content so force=True will
            # overwrite it (compare-before-write sees a difference → writes).
            stale_manifest = tickets_root / "ticket_lifecycle.json"
            stale_manifest.write_text('{"stale": true}', encoding="utf-8")

            # With force=True the skip guard is bypassed; the stale manifest is
            # overwritten, contributing at least 1 to the written count.
            result = build_ticket_lifecycle(root, config, dry_run=False, force=True)
            self.assertGreater(
                result,
                0,
                "Expected force=True to bypass skip guard and write at least the manifest.",
            )

    def test_ticket_lifecycle_default_path_for_consumer_project(self) -> None:
        """With empty config, tickets_root falls back to target_root/'tickets'."""
        from build_phases import build_ticket_lifecycle  # type: ignore[import-untyped]

        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            config: dict = {}
            build_ticket_lifecycle(root, config, dry_run=False, force=True)

            # Standard consumer project: inbox is under 'tickets/'.
            default_inbox = root / "tickets" / "00_inbox"
            self.assertTrue(
                default_inbox.exists(),
                f"Expected default inbox at {default_inbox} for empty config.",
            )


class TestBuildProjectPathsTableConfigOverlay(unittest.TestCase):
    """build_project_paths_table() applies config overlay over paths.json defaults."""

    def test_project_paths_table_overlays_config_values(self) -> None:
        """Config override replaces the matching paths.json entry in the table."""
        from injection_builders import build_project_paths_table  # type: ignore[import-untyped]

        override = "leafcutter-ai/tickets/00_inbox"
        result = build_project_paths_table(config={"tickets_inbox_path": override})
        self.assertIn(
            override,
            result,
            f"Expected '{override}' in table output but it was absent.",
        )

    def test_project_paths_table_no_config_uses_paths_json(self) -> None:
        """With config=None, table reflects the raw paths.json defaults."""
        from injection_builders import build_project_paths_table  # type: ignore[import-untyped]

        result_default = build_project_paths_table(config=None)
        # The static paths.json default for tickets.inbox is "tickets/00_inbox/".
        self.assertIn(
            "tickets/00_inbox",
            result_default,
            "Expected paths.json default 'tickets/00_inbox' in table without config.",
        )
        # And the self-hosting override must NOT appear when config is None.
        self.assertNotIn(
            "leafcutter-ai/tickets/00_inbox",
            result_default,
            "Self-hosting override must not appear when config=None.",
        )


class TestCompileAgentTemplateThreadsConfig(unittest.TestCase):
    """compile_agent_template() passes config to _apply_registry_injection()."""

    def _make_minimal_template(self, tmp_dir: pathlib.Path) -> pathlib.Path:
        """Write a minimal agent template that contains the paths placeholder."""
        tpl = tmp_dir / "test_agent.md"
        tpl.write_text(
            "---\nname: test-agent\ndescription: test\nmodel: sonnet\ntools: Bash\n---\n\n"
            "{{project_paths_table}}\n",
            encoding="utf-8",
        )
        return tpl

    def test_compile_agent_template_threads_config_to_paths_table(self) -> None:
        """{{project_paths_table}} in compiled output reflects the config override."""
        from template_compiler import compile_agent_template  # type: ignore[import-untyped]

        with tempfile.TemporaryDirectory() as td:
            tmp = pathlib.Path(td)
            tpl = self._make_minimal_template(tmp)
            override = "leafcutter-ai/tickets/00_inbox"
            config = {"tickets_inbox_path": override}
            # agents=[] keeps registry injection in the no-op path while still
            # triggering _apply_registry_injection (agents is not None).
            result = compile_agent_template(
                template_path=tpl,
                config=config,
                agents=[],
            )
            self.assertIn(
                override,
                result,
                f"Expected config override '{override}' to appear in compiled template.",
            )


if __name__ == "__main__":
    unittest.main()
