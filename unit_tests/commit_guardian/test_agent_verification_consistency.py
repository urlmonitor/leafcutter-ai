"""
MODULE: test_agent_verification_consistency
GOAL: Unit and integration tests for the check_agent_verification_consistency
    pre-commit hook (GE-116a-1 and related ACs). Runs BEFORE implementation so
    that the python-coder phase has explicit red-baseline tests to make green.
BUSINESS CONTEXT: A commit_guardian hook must block any commit that stages an
    agent template declaring requires_verification: true while its tools list
    contains neither Edit nor Write — an incoherent configuration that promises
    verification the agent cannot deliver. These tests enforce the fail-closed
    behavior, the block message format, the scope rules (staged templates only),
    and the registration of the new hook in the source manifest.
ARCHITECTURE: Tests import the hook module from its DEPLOYED path
    (scripts/commit_guardian/hooks/check_agent_verification_consistency.py),
    consistent with the sibling test test_check_agent_spawn_consistency.py.
    All git I/O is patched via _get_staged_files() and _read_staged_file() so
    tests remain self-contained without real git operations. The integration
    test (test_hook_registered_in_manifest_and_generated_config) reads the
    SOURCE commit_guardian.json manifest directly.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import types
import unittest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path constants
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_PATH = (
    REPO_ROOT
    / "scripts"
    / "commit_guardian"
    / "hooks"
    / "check_agent_verification_consistency.py"
)
SOURCE_MANIFEST_PATH = (
    REPO_ROOT
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "commit_guardian.json"
)

# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------


def _load_hook_module() -> types.ModuleType:
    """Dynamically load the hook module from its deployed script path.

    Raises ImportError if the file does not exist yet — expected during the
    red-baseline phase so that setUp raises ImportError in every test class.
    """
    if not HOOK_PATH.exists():
        _msg = (
            f"Hook script not found at {HOOK_PATH}. "
            "python-coder must implement it at "
            "templates/scripts/commit_guardian/hooks/check_agent_verification_consistency.py "
            "and rebuild so the deployed copy lands here."
        )
        raise ImportError(_msg)
    spec = importlib.util.spec_from_file_location(
        "check_agent_verification_consistency", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _make_agent_md(
    name: str = "test-agent",
    requires_verification: bool | None = None,
    tools: list[str] | None = None,
) -> str:
    """Build a minimal agent template markdown string with specified frontmatter.

    Args:
        name: The agent name used in the frontmatter and heading.
        requires_verification: If given, emits the field; if None, omits it.
        tools: If given, emits the tools list; if None, omits the field.

    Returns:
        A markdown string suitable for use as a ``templates/agents/*.md`` file.
    """
    lines = ["---", f"name: {name}"]
    if requires_verification is not None:
        lines.append(
            f"requires_verification: {'true' if requires_verification else 'false'}"
        )
    if tools is not None:
        if tools:
            lines.append("tools:")
            for tool in tools:
                lines.append(f"  - {tool}")
        else:
            lines.append("tools: []")
    lines += ["---", "", f"# {name}", "", "This is a test agent template."]
    return "\n".join(lines)


def _make_malformed_md() -> str:
    """Return a markdown string whose frontmatter is not valid YAML."""
    return "---\nname: broken\ntools: [unclosed\n---\n\n# broken\n"


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3 / AC-4 core blocking tests
# ---------------------------------------------------------------------------


class TestVerificationConsistencyBlocking(unittest.TestCase):
    """Tests covering the core block/allow rule.

    Red-baseline: all tests raise ImportError until python-coder implements
    the hook at templates/scripts/commit_guardian/hooks/check_agent_verification_consistency.py.
    """

    def setUp(self) -> None:
        """Load the hook module; raises ImportError if not yet implemented."""
        self.module = _load_hook_module()

    # ── test_ac1_tools_lacks_edit_and_write ──────────────────────────────

    def test_ac1_tools_lacks_edit_and_write(self) -> None:
        # covers: GE-116a-1
        # covers: AC-1
        """AC-1: that agent's declared abilities include neither Edit nor Write.

        Given a staged agent template with requires_verification: true and tools
        of only Read and Bash, the hook must exit non-zero (fail-closed).
        """
        agent_path = "templates/agents/read-only-agent.md"
        content = _make_agent_md(
            name="read-only-agent",
            requires_verification=True,
            tools=["Read", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertNotEqual(
            result,
            0,
            "Hook must exit non-zero when requires_verification=true and tools "
            "lack both Edit and Write (fail-closed block).",
        )

    # Alias: same scenario, named per Test Requirements table
    def test_blocks_when_requires_verification_true_and_no_edit_or_write(self) -> None:
        # covers: GE-116a-1
        # covers: AC-2
        """AC-2: the commit is blocked fail-closed.

        Staged agent template with requires_verification: true and tools of only
        Read/Bash -> hook exits non-zero (commit blocked fail-closed).
        """
        agent_path = "templates/agents/blocked-agent.md"
        content = _make_agent_md(
            name="blocked-agent",
            requires_verification=True,
            tools=["Read", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            1,
            "Hook must exit 1 (commit blocked fail-closed) when requires_verification "
            "is true and tools has only read-and-inspect abilities.",
        )

    def test_allows_when_requires_verification_true_and_has_edit(self) -> None:
        # covers: GE-116a-2
        """requires_verification: true + tools includes Edit -> hook exits 0 (allowed)."""
        agent_path = "templates/agents/editor-agent.md"
        content = _make_agent_md(
            name="editor-agent",
            requires_verification=True,
            tools=["Read", "Edit", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 when requires_verification=true and tools includes Edit.",
        )

    def test_allows_read_only_agent_with_requires_verification_false(self) -> None:
        # covers: GE-116a-3
        """Read-only tools + requires_verification: false -> exits 0 (allowed)."""
        agent_path = "templates/agents/safe-read-agent.md"
        content = _make_agent_md(
            name="safe-read-agent",
            requires_verification=False,
            tools=["Read", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 when requires_verification=false, even with read-only tools.",
        )

    def test_absent_requires_verification_treated_as_not_required(self) -> None:
        # covers: GE-116a-4
        """requires_verification absent -> treated as not-required -> exits 0."""
        agent_path = "templates/agents/no-verif-flag.md"
        # Omit requires_verification entirely
        content = _make_agent_md(
            name="no-verif-flag",
            requires_verification=None,
            tools=["Read", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 when requires_verification is absent "
            "(treated as not-required, never blocked).",
        )

    def test_empty_tools_list_blocks(self) -> None:
        # covers: GE-116a-1-i
        """requires_verification: true + tools: [] (present but empty) -> blocked fail-closed."""
        agent_path = "templates/agents/empty-tools-agent.md"
        content = _make_agent_md(
            name="empty-tools-agent",
            requires_verification=True,
            tools=[],  # present but empty
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            1,
            "Hook must exit 1 when tools is present but empty and "
            "requires_verification=true (tools: [] cannot include Edit or Write).",
        )

    def test_write_only_satisfies_requirement(self) -> None:
        # covers: GE-116a-2-i
        """requires_verification: true + tools includes Write but not Edit -> exits 0.

        The rule is Edit OR Write — either satisfies the requirement.
        """
        agent_path = "templates/agents/writer-agent.md"
        content = _make_agent_md(
            name="writer-agent",
            requires_verification=True,
            tools=["Read", "Write", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 when requires_verification=true and tools includes "
            "Write (Write satisfies the Edit-OR-Write requirement).",
        )

    def test_multiple_offenders_block_commit(self) -> None:
        # covers: GE-116a-1-ii
        """Two+ offending templates staged -> commit blocked; one offender is enough."""
        path_a = "templates/agents/offender-alpha.md"
        path_b = "templates/agents/offender-beta.md"
        content_a = _make_agent_md(
            name="offender-alpha",
            requires_verification=True,
            tools=["Read"],
        )
        content_b = _make_agent_md(
            name="offender-beta",
            requires_verification=True,
            tools=["Bash"],
        )

        def _fake_read(path: str) -> str:
            if path == path_a:
                return content_a
            if path == path_b:
                return content_b
            raise FileNotFoundError(path)  # noqa: TRY003

        with patch.object(
            self.module, "_get_staged_files", return_value=[path_a, path_b]
        ):
            with patch.object(self.module, "_read_staged_file", side_effect=_fake_read):
                result = self.module.main()

        self.assertEqual(
            result,
            1,
            "Hook must exit 1 when multiple offending agent templates are staged.",
        )

    def test_unparseable_frontmatter_fails_open(self) -> None:
        # covers: GE-116a-1-iii
        """Malformed/absent frontmatter on a staged agent template -> hook fails OPEN.

        A parse error must never hard-block the commit; the hook must exit 0
        (fail-open) and emit a non-blocking warning. Exceptions must not propagate
        out of the hook.
        """
        agent_path = "templates/agents/malformed-agent.md"
        content = _make_malformed_md()

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                # Fail-open: must exit 0, never raise
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 (fail-open) on malformed frontmatter; "
            "parse errors must never hard-block the commit.",
        )


# ---------------------------------------------------------------------------
# AC-3 / GE-116b-1 block message format tests
# ---------------------------------------------------------------------------


class TestVerificationConsistencyBlockMessage(unittest.TestCase):
    """Tests covering the block message content (GE-116b-1 / GE-116b-1-i).

    Red-baseline: all tests raise ImportError until the hook is implemented.
    """

    def setUp(self) -> None:
        """Load the hook module; raises ImportError if not yet implemented."""
        self.module = _load_hook_module()

    def test_block_message_names_offender_and_both_fixes(self) -> None:
        # covers: GE-116b-1
        # covers: AC-3
        # covers: AC-4
        """AC-3: block reported as failure of the consistency guard.
        AC-4: the offending agent definition is not committed.

        On block, the message must name the offending template path AND state
        BOTH fixes (add Edit/Write to tools, OR set requires_verification false).
        """
        agent_path = "templates/agents/needs-edit-or-false.md"
        content = _make_agent_md(
            name="needs-edit-or-false",
            requires_verification=True,
            tools=["Read", "Bash"],
        )

        err_buf = io.StringIO()
        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                with patch("sys.stderr", err_buf):
                    result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 (hook must block)")
        err_output = err_buf.getvalue()

        # Message must name the offending template path
        self.assertIn(
            "needs-edit-or-false",
            err_output,
            "Block message must name the offending agent template.",
        )
        # Message must mention adding Edit or Write (fix 1)
        has_edit_fix = (
            "Edit" in err_output or "Write" in err_output
        )
        self.assertTrue(
            has_edit_fix,
            "Block message must state fix: add Edit or Write to tools.",
        )
        # Message must mention setting requires_verification: false (fix 2)
        has_verif_fix = (
            "requires_verification" in err_output
            or "requires_verification: false" in err_output
        )
        self.assertTrue(
            has_verif_fix,
            "Block message must state fix: set requires_verification: false.",
        )

    def test_block_message_names_all_offenders(self) -> None:
        # covers: GE-116b-1-i
        """With multiple offenders, the block message must enumerate EVERY offending
        template, not just the first — each with both fixes.
        """
        path_a = "templates/agents/alpha-offender.md"
        path_b = "templates/agents/beta-offender.md"
        content_a = _make_agent_md(
            name="alpha-offender",
            requires_verification=True,
            tools=["Read"],
        )
        content_b = _make_agent_md(
            name="beta-offender",
            requires_verification=True,
            tools=["Bash"],
        )

        def _fake_read(path: str) -> str:
            if path == path_a:
                return content_a
            if path == path_b:
                return content_b
            raise FileNotFoundError(path)  # noqa: TRY003

        err_buf = io.StringIO()
        with patch.object(
            self.module, "_get_staged_files", return_value=[path_a, path_b]
        ):
            with patch.object(self.module, "_read_staged_file", side_effect=_fake_read):
                with patch("sys.stderr", err_buf):
                    result = self.module.main()

        self.assertEqual(result, 1, "Expected exit 1 with multiple offenders")
        err_output = err_buf.getvalue()

        self.assertIn(
            "alpha-offender",
            err_output,
            "Block message must name the first offending template.",
        )
        self.assertIn(
            "beta-offender",
            err_output,
            "Block message must name the second offending template (not just the first).",
        )


# ---------------------------------------------------------------------------
# GE-116c scope tests
# ---------------------------------------------------------------------------


class TestVerificationConsistencyScope(unittest.TestCase):
    """Tests covering the scope rules (GE-116c-1 / GE-116c-2 / GE-116c-3).

    Red-baseline: all tests raise ImportError until the hook is implemented.
    """

    def setUp(self) -> None:
        """Load the hook module; raises ImportError if not yet implemented."""
        self.module = _load_hook_module()

    def test_noop_when_no_agent_templates_staged(self) -> None:
        # covers: GE-116c-1
        """A commit staging no templates/agents/*.md -> hook is a no-op, exits 0."""
        # Staged files are real project files but no agent templates
        staged = [
            "scripts/build.py",
            "docs/architecture/adrs/ADR-001.md",
            "unit_tests/commit_guardian/test_something.py",
        ]

        with patch.object(self.module, "_get_staged_files", return_value=staged):
            result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must be a no-op (exit 0) when no agent template files are staged.",
        )

    def test_non_agent_files_not_inspected(self) -> None:
        # covers: GE-116c-2
        """Staged non-agent files containing trigger keywords are not inspected.

        The hook triggers by file identity (templates/agents/*.md), not by
        content grep. A non-agent file with requires_verification: true must
        not trigger a block.
        """
        # This is a non-agent file with contradictory content keywords
        non_agent_path = "docs/some-doc.md"
        contradictory_content = _make_agent_md(
            name="sneaky",
            requires_verification=True,
            tools=["Read"],  # would block if this were an agent template
        )

        with patch.object(
            self.module, "_get_staged_files", return_value=[non_agent_path]
        ):
            with patch.object(
                self.module, "_read_staged_file", return_value=contradictory_content
            ):
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 for non-agent files; trigger by file identity only "
            "(templates/agents/*.md), never by content grep.",
        )

    def test_only_staged_agent_templates_checked(self) -> None:
        # covers: GE-116c-3
        """A pre-existing UNSTAGED contradictory agent template must not block the commit.

        Only staged (git diff --cached) agent templates are inspected. If the
        hook's staged-file list does not include the contradictory file, it must
        exit 0 regardless of what lives on disk.
        """
        # Simulates: contradictory file exists on disk but is NOT staged.
        # _get_staged_files returns empty list (nothing staged from templates/agents/).
        with patch.object(self.module, "_get_staged_files", return_value=[]):
            result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Hook must exit 0 when the contradictory agent template is on disk "
            "but not staged; only staged files (git diff --cached) are checked.",
        )

    def test_consistent_agent_template_staged_does_not_block(self) -> None:
        # covers: GE-116a-2
        """A staged agent template that is internally consistent must not block.

        requires_verification: true + tools includes Edit -> allowed (exit 0).
        This verifies the scope boundary: consistent staged templates pass through.
        """
        agent_path = "templates/agents/consistent-verif-agent.md"
        content = _make_agent_md(
            name="consistent-verif-agent",
            requires_verification=True,
            tools=["Read", "Edit", "Bash"],
        )

        with patch.object(self.module, "_get_staged_files", return_value=[agent_path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                result = self.module.main()

        self.assertEqual(
            result,
            0,
            "Consistent requires_verification=true agent (with Edit) must not block.",
        )


# ---------------------------------------------------------------------------
# GE-116a-5 integration: manifest registration
# ---------------------------------------------------------------------------


class TestVerificationConsistencyRegistration(unittest.TestCase):
    """Integration tests verifying the hook is registered in the source manifest.

    These tests do NOT require the hook module to be implemented — they read
    the SOURCE commit_guardian.json directly. They will be RED (AssertionError)
    until python-coder registers the hook entry in the manifest.
    """

    def test_hook_registered_in_manifest_and_generated_config(self) -> None:
        # covers: GE-116a-5
        """Hook must be registered in commit_guardian.json SOURCE manifest.

        Checks that:
        1. The SOURCE manifest at templates/scripts/commit_guardian/commit_guardian.json
           contains an entry with id='check-agent-verification-consistency'.
        2. The hook's files pattern scopes to templates/agents/*.md (agent templates).
        3. The hook script file at the source path exists (once implemented).

        This is the BP-300e guard: a NEW commit_guardian hook script must be added
        to ALL build deployable-set/parity lists or the source-paths guard fails.
        """
        self.assertTrue(
            SOURCE_MANIFEST_PATH.exists(),
            f"SOURCE commit_guardian.json not found at {SOURCE_MANIFEST_PATH}",
        )

        with SOURCE_MANIFEST_PATH.open(encoding="utf-8") as fh:
            manifest_data = json.load(fh)

        hooks = manifest_data.get("hooks_manifest", {}).get("hooks", [])
        hook_ids = [h.get("id") for h in hooks]

        self.assertIn(
            "check-agent-verification-consistency",
            hook_ids,
            "check-agent-verification-consistency not found in SOURCE commit_guardian.json "
            "hooks_manifest. python-coder must register the hook in the manifest "
            "(BP-300e: register in hooks_manifest before build so it lands in "
            ".pre-commit-config.yaml).",
        )

        # Verify files pattern scopes to agent templates
        hook_entry = next(
            h for h in hooks if h.get("id") == "check-agent-verification-consistency"
        )
        files_pattern = hook_entry.get("files", "")
        self.assertTrue(
            "templates/agents" in files_pattern or "agents" in files_pattern,
            f"Hook 'files' pattern must scope to templates/agents/*.md; "
            f"got: {files_pattern!r}",
        )
        self.assertFalse(
            hook_entry.get("pass_filenames", True),
            "pass_filenames must be false (hook uses git diff --cached internally).",
        )

    def test_hook_source_file_exists_at_template_path(self) -> None:
        # covers: GE-116a-5
        """The hook source file must exist at its template path.

        Once python-coder creates the file, this test turns green. Until then,
        this is a red-baseline signal that the implementation is missing.
        """
        source_path = (
            REPO_ROOT
            / "templates"
            / "scripts"
            / "commit_guardian"
            / "hooks"
            / "check_agent_verification_consistency.py"
        )
        self.assertTrue(
            source_path.exists(),
            f"Hook source file not found at {source_path}. "
            "python-coder must create it at this location (mirrors "
            "templates/scripts/commit_guardian/hooks/check_agent_spawn_consistency.py).",
        )

    def test_hook_deployable_via_source_paths_guard(self) -> None:
        # covers: GE-116a-5
        """The hook file at templates/scripts/commit_guardian/hooks/ is included in the
        build deployable-set via _get_source_paths_for_guard().

        _get_source_paths_for_guard() scans templates/scripts/commit_guardian/ recursively
        for *.py files, so adding the hook at that path is sufficient — no additional
        list entry is needed. This test verifies the rglob picks it up once the file exists.
        """
        # Import build.py to call _get_source_paths_for_guard
        try:
            import scripts.build as _build
        except ImportError as exc:
            self.skipTest(f"scripts.build not importable: {exc}")

        if not hasattr(_build, "_get_source_paths_for_guard"):
            self.fail(
                "AttributeError: scripts.build does not expose _get_source_paths_for_guard(). "
                "This guard function must exist (it was added to protect against BP-300e)."
            )

        source_paths = _build._get_source_paths_for_guard(REPO_ROOT)

        expected_path = (
            "templates/scripts/commit_guardian/hooks/check_agent_verification_consistency.py"
        )
        self.assertIn(
            expected_path,
            source_paths,
            f"Expected path '{expected_path}' not found in _get_source_paths_for_guard() output. "
            "This means the hook file does not yet exist at the template source path. "
            "Create it there — the rglob will pick it up automatically.",
        )


# ---------------------------------------------------------------------------
# Module-level structure tests (once implemented)
# ---------------------------------------------------------------------------


class TestVerificationConsistencyModuleStructure(unittest.TestCase):
    """Tests that the hook module follows the established documentation conventions.

    Red-baseline: all tests raise ImportError until the hook is implemented.
    """

    def setUp(self) -> None:
        """Load the hook module; raises ImportError if not yet implemented."""
        self.module = _load_hook_module()

    def test_hook_has_module_docstring(self) -> None:
        # covers: GE-116a-5
        """Hook script must have a module-level docstring with required sections.

        Mirrors the check in test_check_agent_spawn_consistency.py (AC-8).
        """
        docstring = self.module.__doc__
        self.assertIsNotNone(docstring, "Hook module must have a module-level docstring")
        assert docstring is not None
        for field in ("MODULE", "GOAL", "BUSINESS CONTEXT", "ARCHITECTURE"):
            self.assertIn(
                field,
                docstring,
                f"Module docstring is missing required field: {field}",
            )

    def test_hook_exposes_main_function(self) -> None:
        # covers: GE-116a-1
        """Hook must expose a main() callable that returns an integer exit code."""
        self.assertTrue(
            callable(getattr(self.module, "main", None)),
            "Hook module must expose a main() callable.",
        )

    def test_hook_exposes_get_staged_files(self) -> None:
        # covers: GE-116a-1
        """Hook must expose _get_staged_files() so tests can patch git I/O."""
        self.assertTrue(
            callable(getattr(self.module, "_get_staged_files", None)),
            "Hook module must expose _get_staged_files() (patchable in tests).",
        )

    def test_hook_exposes_read_staged_file(self) -> None:
        # covers: GE-116a-1
        """Hook must expose _read_staged_file(path) so tests can patch file I/O."""
        self.assertTrue(
            callable(getattr(self.module, "_read_staged_file", None)),
            "Hook module must expose _read_staged_file(path) (patchable in tests).",
        )

    def test_hook_has_decision_history_block(self) -> None:
        # covers: GE-116a-5
        """Hook script must contain a DECISION HISTORY block at the bottom."""
        source_code = HOOK_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "DECISION HISTORY",
            source_code,
            "Hook script must contain a '# DECISION HISTORY' block at the bottom.",
        )


# ---------------------------------------------------------------------------
# Real on-disk format (scalar tools) + requires_verification parsing.
# Every real templates/agents/*.md uses a scalar comma-separated `tools:` string
# with an optional trailing `# comment`, NOT a YAML list. The list-format
# fixtures above never drive the hook's scalar branch — the branch every real
# commit actually hits. These tests close that gap
# (feedback_spotcheck_real_data_format) and guard the requires_verification
# truthiness fix (a quoted "false" must NOT false-block).
# ---------------------------------------------------------------------------


def _make_agent_md_scalar(
    name: str = "test-agent",
    requires_verification: str | None = None,
    tools_scalar: str | None = None,
) -> str:
    """Build an agent template using the REAL scalar frontmatter format.

    Args:
        name: The agent name.
        requires_verification: Raw scalar emitted verbatim after the field name
            (e.g. ``true`` or ``"false"``); omitted when None.
        tools_scalar: Raw scalar emitted verbatim after ``tools:`` (e.g.
            ``Read, Bash  # Read-only.``); the field is omitted when None.

    Returns:
        A markdown string in the real scalar frontmatter format.
    """
    lines = ["---", f"name: {name}"]
    if requires_verification is not None:
        lines.append(f"requires_verification: {requires_verification}")
    if tools_scalar is not None:
        lines.append(f"tools: {tools_scalar}")
    lines += ["---", "", f"# {name}", "", "This is a test agent template."]
    return "\n".join(lines)


class TestVerificationConsistencyRealFormat(unittest.TestCase):
    """Tests driving the scalar `tools:` branch and requires_verification parsing.

    Red-baseline: all tests raise ImportError until the hook is implemented.
    """

    def setUp(self) -> None:
        """Load the hook module; raises ImportError if not yet implemented."""
        self.module = _load_hook_module()

    def _run(self, path: str, content: str) -> int:
        with patch.object(self.module, "_get_staged_files", return_value=[path]):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                return self.module.main()

    def test_scalar_tools_lacking_edit_write_blocks(self) -> None:
        # covers: GE-116a-1
        """Real scalar format `tools: Read, Bash  # comment` + rv true -> BLOCK.

        Drives the isinstance(tools, str) branch — the format 100% of real
        agent templates use — including a trailing inline `#` comment.
        """
        content = _make_agent_md_scalar(
            name="read-only-agent",
            requires_verification="true",
            tools_scalar="Read, Bash  # Read-only. No Write/Edit.",
        )
        result = self._run("templates/agents/read-only-agent.md", content)
        self.assertNotEqual(
            result, 0, "Scalar tools with only Read/Bash + rv true must block."
        )

    def test_scalar_tools_with_write_allows(self) -> None:
        # covers: GE-116a-2-i
        """Scalar `tools: Read, Write, Bash  # comment` + rv true -> ALLOW (Write satisfies)."""
        content = _make_agent_md_scalar(
            name="writer-agent",
            requires_verification="true",
            tools_scalar="Read, Write, Bash  # can create files",
        )
        result = self._run("templates/agents/writer-agent.md", content)
        self.assertEqual(
            result, 0, "Scalar tools containing Write must be allowed (Edit OR Write)."
        )

    def test_scalar_tools_with_edit_allows(self) -> None:
        # covers: GE-116a-2
        """Scalar `tools: Read, Edit, Bash` + rv true -> ALLOW (Edit satisfies)."""
        content = _make_agent_md_scalar(
            name="editor-agent",
            requires_verification="true",
            tools_scalar="Read, Edit, Bash",
        )
        result = self._run("templates/agents/editor-agent.md", content)
        self.assertEqual(result, 0, "Scalar tools containing Edit must be allowed.")

    def test_absent_tools_field_blocks(self) -> None:
        # covers: GE-116a-1-i
        """rv true with NO tools field at all -> BLOCK (empty tool set)."""
        content = _make_agent_md_scalar(
            name="no-tools-agent",
            requires_verification="true",
            tools_scalar=None,
        )
        result = self._run("templates/agents/no-tools-agent.md", content)
        self.assertNotEqual(
            result, 0, "An absent tools field with rv true must block (no edit capability)."
        )

    def test_quoted_requires_verification_false_allows(self) -> None:
        # covers: GE-116a-3
        # covers: GE-116a-4
        """Quoted `requires_verification: "false"` + read-only tools -> ALLOW.

        Regression guard: a quoted scalar parses to the string "false", which is
        truthy by non-emptiness. The hook must interpret it as falsy, not block a
        valid read-only agent. This test FAILS against the naive truthiness check.
        """
        content = _make_agent_md_scalar(
            name="quoted-false-agent",
            requires_verification='"false"',
            tools_scalar="Read, Bash  # Read-only",
        )
        result = self._run("templates/agents/quoted-false-agent.md", content)
        self.assertEqual(
            result,
            0,
            'A quoted requires_verification: "false" must be treated as not-required '
            "(read-only agent allowed), not truthy-by-non-emptiness.",
        )

    def test_quoted_requires_verification_true_blocks(self) -> None:
        # covers: GE-116a-1
        """Quoted `requires_verification: "true"` + read-only tools -> BLOCK."""
        content = _make_agent_md_scalar(
            name="quoted-true-agent",
            requires_verification='"true"',
            tools_scalar="Read, Bash",
        )
        result = self._run("templates/agents/quoted-true-agent.md", content)
        self.assertNotEqual(
            result, 0, 'A quoted requires_verification: "true" read-only agent must block.'
        )

    def test_absent_frontmatter_fails_open(self) -> None:
        # covers: GE-116a-1-iii
        """A staged agent template with NO YAML frontmatter -> FAIL OPEN (exit 0)."""
        content = "# just-a-heading\n\nNo frontmatter here at all.\n"
        err_buf = io.StringIO()
        with patch.object(
            self.module, "_get_staged_files", return_value=["templates/agents/no-fm.md"]
        ):
            with patch.object(self.module, "_read_staged_file", return_value=content):
                with patch("sys.stderr", err_buf):
                    result = self.module.main()
        self.assertEqual(
            result, 0, "Absent frontmatter must fail open (exit 0), never hard-block."
        )


if __name__ == "__main__":
    unittest.main()
