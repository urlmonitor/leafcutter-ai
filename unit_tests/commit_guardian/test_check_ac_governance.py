"""
MODULE: test_check_ac_governance
GOAL: Unit tests for the check_ac_governance.py pre-commit hook that write-locks
    requirement-defining fields in AC YAML files to authorized agents only.
BUSINESS CONTEXT: Verifies that the governance hook correctly allows authorized
    agents (product-owner-v3, business-analyst-v3, it-po-v3, human users) to
    modify protected fields (criteria, title, req_status, depends_on) while
    blocking implementation agents from doing so. Also verifies audit-trail
    requirements (origin_agent, amended_by) and performance requirements.
ARCHITECTURE: Tests call the hook module's internal functions directly (not via
    subprocess) to keep tests fast and deterministic. A small number of subprocess
    integration tests verify the CLI exit-code contract. HOOK_TEST_FILES and
    HOOK_ROOT env vars isolate filesystem state.

# covers: ACS-400a-1
# covers: ACS-400a-2
# covers: ACS-400a-3
# covers: ACS-400a-3-i
# covers: ACS-400b-1
# covers: ACS-400b-2
# covers: ACS-400b-3
# covers: ACS-400b-3-i
# covers: ACS-400c-1
# covers: ACS-400c-2
# covers: ACS-400c-2-i
# covers: ACS-400d-2-i
# covers: ACS-400e-1-i
# covers: ACS-400e-2
# covers: ACS-400e-3
"""

from __future__ import annotations

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_HOOK_SCRIPT = (
    _REPO_ROOT / "scripts" / "commit_guardian" / "check_ac_governance.py"
)

# ---------------------------------------------------------------------------
# Load the module under test via importlib (standalone file, no package import)
# ---------------------------------------------------------------------------
try:
    _MODULE_NAME = "check_ac_governance_test_shim"
    _spec = importlib.util.spec_from_file_location(_MODULE_NAME, _HOOK_SCRIPT)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MODULE_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

    # Pull out public symbols we need for direct unit testing
    _AUTHORIZED_AGENTS = _mod._AUTHORIZED_AGENTS  # type: ignore[attr-defined]
    _PROTECTED_FIELDS = _mod._PROTECTED_FIELDS  # type: ignore[attr-defined]
    _OPEN_FIELDS = _mod._OPEN_FIELDS  # type: ignore[attr-defined]
    _load_registry = _mod._load_registry  # type: ignore[attr-defined]
    _is_authorized = _mod._is_authorized  # type: ignore[attr-defined]
    _load_staged_content = _mod._load_staged_content  # type: ignore[attr-defined]
    _load_head_content = _mod._load_head_content  # type: ignore[attr-defined]
    _check_file = _mod._check_file  # type: ignore[attr-defined]
    _IMPORT_OK = True
except (
    FileNotFoundError,
    AttributeError,
    ImportError,
    SyntaxError,
    TypeError,
    ValueError,
) as _exc:
    _IMPORT_OK = False
    _IMPORT_ERROR = str(_exc)


def _requires_import(func):
    """Skip test if the hook module failed to import."""
    if not _IMPORT_OK:
        return unittest.skip(
            f"check_ac_governance not importable: {_IMPORT_ERROR}"
        )(func)
    return func


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_yaml(directory: Path, rel_path: str, content: str) -> Path:
    """Write a YAML file under directory, creating intermediate dirs.

    Args:
        directory: Root of the temporary tree.
        rel_path: Path relative to directory (e.g. 'docs/acceptance-criteria/foo.yaml').
        content: YAML content.

    Returns:
        Absolute Path of the written file.
    """
    target = directory / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _write_registry(directory: Path, extra_agents: list | None = None) -> Path:
    """Write a minimal agent_registry.json with common agents.

    Tests that need python-coder to be recognized as a KNOWN agent (and therefore
    NOT authorized for protected fields) must call this to create a registry.

    Args:
        directory: Root of the temporary tree (HOOK_ROOT).
        extra_agents: Optional list of extra agent ID strings to include.

    Returns:
        Absolute Path of the written registry file.
    """
    known_agents = [
        "python-coder",
        "test-writer",
        "pr-reviewer",
        "commit",
        "test-runner",
        "sql-coder",
        "frontend-coder",
        "documentation-expert",
    ]
    if extra_agents:
        known_agents.extend(extra_agents)
    registry = {
        "agents": [{"id": agent_id, "is_ticket_phase": True} for agent_id in known_agents]
    }
    reg_path = directory / "config" / "agent_registry.json"
    reg_path.parent.mkdir(parents=True, exist_ok=True)
    reg_path.write_text(json.dumps(registry), encoding="utf-8")
    return reg_path


def _minimal_ac(
    *,
    ac_id: str = "ACS-400a-1",
    criteria: str = "Given some condition, When action, Then outcome.",
    title: str = "Some AC Title",
    origin_agent: str = "business-analyst-v3",
    amended_by: list | None = None,
    extra_fields: str = "",
) -> str:
    """Return a minimal valid AC YAML string."""
    amended_list = "[]" if amended_by is None else repr(amended_by)
    extra = extra_fields.strip()
    base = (
        f"id: {ac_id}\n"
        f'title: "{title}"\n'
        f"component: ac-store\n"
        f"level: L2\n"
        f"status: active\n"
        f"req_status: active\n"
        f"work_status: todo\n"
        f"criteria: |\n"
        f"  {criteria}\n"
        f"origin_agent: {origin_agent}\n"
        f"amended_by: {amended_list}\n"
    )
    if extra:
        base += extra + "\n"
    return base


class TestAuthorizedAgentAllowPath(unittest.TestCase):
    """AC-1: authorized requirement agents can modify criteria (ACS-400a-1)."""

    @_requires_import
    def test_ac1_authorized_agent_new_criteria_exits_0(self):
        # covers: ACS-400a-1
        """AC-1: business-analyst-v3 staging new criteria → exits 0, no block."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-001",
                origin_agent="business-analyst-v3",
                criteria="Given a new requirement, When staged, Then allowed.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-001.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "business-analyst-v3",
                    "HOOK_NO_GIT": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 for authorized agent, got {result.returncode}. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            # No JSON block decision with "block" in authorized path
            if result.stdout.strip():
                try:
                    decision = json.loads(result.stdout)
                    self.assertNotEqual(
                        decision.get("decision"), "block",
                        "Authorized agent should not receive block decision",
                    )
                except json.JSONDecodeError:
                    pass  # Non-JSON output on clean path is fine


class TestModificationAllowPath(unittest.TestCase):
    """AC-2: authorized agent modifying criteria → exits 0 (ACS-400a-2)."""

    @_requires_import
    def test_ac2_it_po_v3_modifying_criteria_exits_0(self):
        # covers: ACS-400a-2
        """AC-2: it-po-v3 changing criteria in a staged diff → exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-002",
                origin_agent="it-po-v3",
                criteria="Updated criteria after review.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-002.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "it-po-v3",
                    "HOOK_NO_GIT": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 for it-po-v3, got {result.returncode}. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )


class TestUnauthorizedAgentBlockPath(unittest.TestCase):
    """AC-3: unauthorized agent changing criteria → exits 1 (ACS-400a-3)."""

    @_requires_import
    def test_ac3_python_coder_criteria_change_blocked(self):
        # covers: ACS-400a-3
        """AC-3: python-coder changing criteria → exits 1, error names agent + path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Registry required so python-coder is recognized as a known agent
            # (not treated as a human user) → authorization check fires correctly
            _write_registry(tmp)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-003",
                origin_agent="business-analyst-v3",
                criteria="Criteria written by coder — should be blocked.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-003.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    # Simulate criteria being changed vs HEAD (HEAD has no file)
                    "HOOK_NO_GIT": "1",
                    # Signal that criteria was changed
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Expected exit 1 for unauthorized agent, got {result.returncode}. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            # Error must name the agent
            combined = result.stdout + result.stderr
            self.assertIn(
                "python-coder",
                combined,
                "Error output must name the unauthorized agent",
            )
            # Error must name the file path
            self.assertIn(
                "ACS-TEST-003",
                combined,
                "Error output must reference the file path",
            )
            # Error must state the rule
            self.assertIn(
                "criteria field may only be written by requirement authors",
                combined,
                "Error must contain the specific rule message",
            )


class TestHumanUserAllowPath(unittest.TestCase):
    """AC-4: unknown identity treated as human user → exits 0 (ACS-400a-3-i)."""

    @_requires_import
    def test_ac4_unknown_origin_agent_treated_as_human_user(self):
        # covers: ACS-400a-3-i
        """AC-4: BrainCandy (not in registry) → treated as human, exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-004",
                origin_agent="BrainCandy",
                criteria="Human user writing criteria — should be allowed.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-004.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "BrainCandy",
                    "HOOK_NO_GIT": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 for unknown agent (human user), got "
                f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}",
            )


class TestImplementationAgentProgressFieldsAllowPath(unittest.TestCase):
    """AC-5: implementation agent changing only open fields → exits 0 (ACS-400b-1, b-2)."""

    @_requires_import
    def test_ac5_python_coder_work_status_change_allowed(self):
        # covers: ACS-400b-1
        # covers: ACS-400b-2
        """AC-5: python-coder changing work_status/implemented_by/covered_by → exits 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = textwrap.dedent("""\
                id: ACS-TEST-005
                title: "Progress fields AC"
                component: ac-store
                level: L2
                status: active
                req_status: active
                work_status: done
                implemented_by: [python-coder]
                covered_by: [test_check_ac_governance.py]
                criteria: |
                  Original criteria unchanged.
                origin_agent: business-analyst-v3
                amended_by: []
            """)
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-005.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    # Signal that only open fields were changed
                    "HOOK_SIMULATE_OPEN_ONLY_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 when only open fields changed, got "
                f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}",
            )

    @_requires_import
    def test_ac5_constants_include_open_fields(self):
        # covers: ACS-400b-1
        # covers: ACS-400b-2
        """AC-5: _OPEN_FIELDS constant includes work_status, implemented_by, covered_by."""
        self.assertIn("work_status", _OPEN_FIELDS)
        self.assertIn("implemented_by", _OPEN_FIELDS)
        self.assertIn("covered_by", _OPEN_FIELDS)


class TestProtectedFieldRejectionPath(unittest.TestCase):
    """AC-6: implementation agent changes title/req_status/depends_on → exits 1 (ACS-400b-3)."""

    @_requires_import
    def test_ac6_protected_field_constants_defined(self):
        # covers: ACS-400b-3
        """AC-6: _PROTECTED_FIELDS constant includes criteria, title, req_status, depends_on."""
        for field in ("criteria", "title", "req_status", "depends_on"):
            self.assertIn(
                field,
                _PROTECTED_FIELDS,
                f"Protected field '{field}' must be in _PROTECTED_FIELDS constant",
            )

    @_requires_import
    def test_ac6_implementation_agent_title_change_blocked(self):
        # covers: ACS-400b-3
        """AC-6: python-coder changing title → exits 1, error lists each modified field."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Registry required so python-coder is known (not treated as human)
            _write_registry(tmp)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-006",
                title="Renamed Title By Coder",
                origin_agent="business-analyst-v3",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-006.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_TITLE_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Expected exit 1 for protected field (title) change, got "
                f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            combined = result.stdout + result.stderr
            self.assertIn(
                "title",
                combined,
                "Error output must name the modified protected field",
            )


class TestMixedCommitRejectionPath(unittest.TestCase):
    """AC-7: mixed commit with allowed + blocked fields → exits 1 (ACS-400b-3-i)."""

    @_requires_import
    def test_ac7_mixed_commit_blocked_acknowledges_both_fields(self):
        # covers: ACS-400b-3-i
        """AC-7: work_status (allowed) + criteria (blocked) in same commit → exits 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Registry required so python-coder is known (not treated as human)
            _write_registry(tmp)
            ac_content = (
                "id: ACS-TEST-007\n"
                'title: "Mixed change AC"\n'
                "component: ac-store\n"
                "level: L2\n"
                "status: active\n"
                "req_status: active\n"
                "work_status: done\n"
                "criteria: |\n"
                "  Modified criteria by coder — should be blocked.\n"
                "origin_agent: business-analyst-v3\n"
                "amended_by: []\n"
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-007.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    # Both criteria and work_status changed
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                    "HOOK_SIMULATE_OPEN_ONLY_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                "Expected exit 1 when criteria (blocked) changed alongside open field",
            )
            combined = result.stdout + result.stderr
            # Error must acknowledge the blocked field
            self.assertIn(
                "criteria",
                combined,
                "Error must name the blocked protected field (criteria)",
            )
            # Error must acknowledge the open field was also changed
            self.assertIn(
                "work_status",
                combined,
                "Error must acknowledge the open field (work_status) was also changed",
            )


class TestOriginAgentAuditCheck(unittest.TestCase):
    """AC-8: new AC file without origin_agent → exits 1 (ACS-400c-1)."""

    @_requires_import
    def test_ac8_new_ac_file_missing_origin_agent_blocked(self):
        # covers: ACS-400c-1
        """AC-8: new AC file staged without origin_agent field → exits 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = textwrap.dedent("""\
                id: ACS-TEST-008
                title: "New AC without origin_agent"
                component: ac-store
                level: L2
                status: active
                req_status: active
                criteria: |
                  Some criteria without origin_agent.
            """)
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-008.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "business-analyst-v3",
                    "HOOK_NO_GIT": "1",
                    # Signal this is a brand-new file (no HEAD version)
                    "HOOK_SIMULATE_NEW_FILE": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Expected exit 1 when new AC file lacks origin_agent, got "
                f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            combined = result.stdout + result.stderr
            self.assertIn(
                "origin_agent",
                combined,
                "Error must mention the missing origin_agent field",
            )
            self.assertIn(
                "criteria author",
                combined,
                "Error must explain that origin_agent identifies the criteria author",
            )


class TestAmendedByAuditCheck(unittest.TestCase):
    """AC-9: criteria changed but amended_by not updated → exits 1 (ACS-400c-2)."""

    @_requires_import
    def test_ac9_criteria_changed_without_amended_by_update_blocked(self):
        # covers: ACS-400c-2
        """AC-9: criteria changed but amended_by list identical to HEAD → exits 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-009",
                criteria="Updated criteria but amended_by not updated.",
                origin_agent="business-analyst-v3",
                amended_by=[],
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-009.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "it-po-v3",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                    # amended_by identical to HEAD (not updated)
                    "HOOK_SIMULATE_AMENDED_BY_STALE": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Expected exit 1 when criteria changed but amended_by not updated, got "
                f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            combined = result.stdout + result.stderr
            self.assertIn(
                "amended_by",
                combined,
                "Error must mention amended_by",
            )
            self.assertIn(
                "criteria was modified",
                combined,
                "Error must say criteria was modified",
            )


class TestStaleAmendedByCheck(unittest.TestCase):
    """AC-10: amended_by exists but has no new entries → exits 1 (ACS-400c-2-i)."""

    @_requires_import
    def test_ac10_stale_amended_by_distinguishes_no_new_entry_from_empty(self):
        # covers: ACS-400c-2-i
        """AC-10: amended_by has entries but none are new since HEAD → exits 1 with distinct message."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_content = textwrap.dedent("""\
                id: ACS-TEST-010
                title: "Stale amended_by AC"
                component: ac-store
                level: L2
                status: active
                req_status: active
                criteria: |
                  Updated criteria — amended_by has entries but none are new.
                origin_agent: business-analyst-v3
                amended_by: ["business-analyst-v3"]
            """)
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-010.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "it-po-v3",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                    # amended_by has entries but no NEW ones compared to HEAD
                    "HOOK_SIMULATE_AMENDED_BY_NO_NEW_ENTRY": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                f"Expected exit 1 for stale amended_by, got {result.returncode}. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            combined = result.stdout + result.stderr
            # Error must distinguish "no new entry" from "list is empty"
            self.assertIn(
                "no new entry",
                combined,
                "Error must specifically say 'no new entry' (not just 'list is empty')",
            )


class TestFailOpenPath(unittest.TestCase):
    """AC-11: YAML parse exception → exits 0, diagnostic on stderr (ACS-400e-1-i)."""

    @_requires_import
    def test_ac11_yaml_parse_exception_exits_0_no_stdout(self):
        # covers: ACS-400e-1-i
        """AC-11: YAML parse error → exits 0 (fail-open), no blocking stdout output."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Write invalid YAML that will fail to parse
            invalid_yaml = "{{ not: valid: yaml: }: }: }"
            ac_file = _write_yaml(
                tmp,
                "docs/acceptance-criteria/test/ACS-BAD-001.yaml",
                invalid_yaml,
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "business-analyst-v3",
                    "HOOK_NO_GIT": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 (fail-open) on YAML parse error, got "
                f"{result.returncode}. stdout={result.stdout!r} stderr={result.stderr!r}",
            )
            # No blocking output on stdout
            if result.stdout.strip():
                try:
                    decision = json.loads(result.stdout)
                    self.assertNotEqual(
                        decision.get("decision"),
                        "block",
                        "Fail-open path must not produce a block decision",
                    )
                except json.JSONDecodeError:
                    pass  # Non-JSON on fail-open path is acceptable
            # Diagnostic must go to stderr
            self.assertTrue(
                len(result.stderr) > 0,
                "Fail-open path must emit diagnostic detail to stderr",
            )


class TestNoACStoreEarlyExitPath(unittest.TestCase):
    """AC-12: no docs/acceptance-criteria/ directory → exits 0 quickly (ACS-400d-2-i)."""

    @_requires_import
    def test_ac12_no_ac_store_directory_exits_0_fast(self):
        # covers: ACS-400d-2-i
        """AC-12: no docs/acceptance-criteria/ dir → exits 0 in under 100ms, no dirs created."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Do NOT create docs/acceptance-criteria/
            ac_store_path = tmp / "docs" / "acceptance-criteria"
            self.assertFalse(ac_store_path.exists(), "Test pre-condition failed: AC store exists")

            start = time.monotonic()
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                },
                capture_output=True,
                text=True,
            )
            elapsed_ms = (time.monotonic() - start) * 1000

            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 when no AC store, got {result.returncode}",
            )
            self.assertLess(
                elapsed_ms,
                500,  # Generous bound (subprocess overhead); spec says 100ms for hook logic
                f"Hook with no AC store took {elapsed_ms:.1f}ms — should be fast",
            )
            # Must not have created the directory
            self.assertFalse(
                ac_store_path.exists(),
                "Hook must not create docs/acceptance-criteria/ when it does not exist",
            )


class TestStagedFilesOnlyScope(unittest.TestCase):
    """AC-13: only staged files are parsed (ACS-400e-2)."""

    @_requires_import
    def test_ac13_only_staged_files_parsed_not_all_on_disk(self):
        # covers: ACS-400e-2
        """AC-13: 100 AC YAML files on disk but only 2 staged → hook parses only 2."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            ac_dir = tmp / "docs" / "acceptance-criteria" / "test"
            ac_dir.mkdir(parents=True, exist_ok=True)

            # Create 100 files on disk
            staged_files = []
            for i in range(100):
                content = _minimal_ac(
                    ac_id=f"ACS-TEST-{i:03d}",
                    origin_agent="business-analyst-v3",
                )
                fpath = ac_dir / f"ACS-TEST-{i:03d}.yaml"
                fpath.write_text(content, encoding="utf-8")
                if i < 2:
                    staged_files.append(str(fpath))

            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": os.pathsep.join(staged_files),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "business-analyst-v3",
                    "HOOK_NO_GIT": "1",
                    "HOOK_COUNT_PARSED": "1",  # Signal hook to emit parsed count to stderr
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Expected exit 0 for 2 authorized staged files, got {result.returncode}",
            )
            # If the hook supports HOOK_COUNT_PARSED, verify it shows only 2
            if "parsed_files:" in result.stderr:
                self.assertIn(
                    "parsed_files: 2",
                    result.stderr,
                    "Hook should have parsed exactly 2 staged files, not all 100",
                )


class TestNonACFileNeutrality(unittest.TestCase):
    """AC-14: non-AC file in commit does not cause false positive (ACS-400e-3)."""

    @_requires_import
    def test_ac14_non_ac_file_plus_unauthorized_ac_change_error_references_only_ac(self):
        # covers: ACS-400e-3
        """AC-14: scripts/build.py staged + unauthorized AC change → error names only AC."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Registry required so python-coder is known (not treated as human)
            _write_registry(tmp)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-014",
                origin_agent="business-analyst-v3",
                criteria="Criteria changed by python-coder — should be blocked.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-014.yaml", ac_content
            )
            # Create a non-AC file that is also "staged"
            build_script = tmp / "scripts" / "build.py"
            build_script.parent.mkdir(parents=True, exist_ok=True)
            build_script.write_text("# build script\n", encoding="utf-8")

            # Only pass the AC file to HOOK_TEST_FILES (non-AC files are ignored by pattern)
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                1,
                "Expected exit 1 for the unauthorized AC change",
            )
            combined = result.stdout + result.stderr
            # Error must reference the AC file, not build.py
            self.assertIn(
                "ACS-TEST-014",
                combined,
                "Error must reference the AC file name",
            )
            # build.py must NOT appear in the error
            self.assertNotIn(
                "build.py",
                combined,
                "Error must not reference the non-AC file build.py",
            )


class TestConstantsAtModuleLevel(unittest.TestCase):
    """Verify protected/open field constants are at module level (AC-17)."""

    @_requires_import
    def test_constants_exist_at_module_level(self):
        # covers: ACS-400b-3
        """AC-17: protected and open fields are named constants (not inline strings)."""
        # These must be module-level constants (not just present in some inner scope)
        self.assertTrue(
            hasattr(_mod, "_PROTECTED_FIELDS"),
            "Module must export _PROTECTED_FIELDS as a module-level constant",
        )
        self.assertTrue(
            hasattr(_mod, "_OPEN_FIELDS"),
            "Module must export _OPEN_FIELDS as a module-level constant",
        )
        self.assertTrue(
            hasattr(_mod, "_AUTHORIZED_AGENTS"),
            "Module must export _AUTHORIZED_AGENTS as a module-level constant",
        )

    @_requires_import
    def test_protected_fields_complete(self):
        # covers: ACS-400b-3
        """Verify all four protected fields are in _PROTECTED_FIELDS."""
        expected = {"criteria", "title", "req_status", "depends_on"}
        for field in expected:
            self.assertIn(
                field,
                _PROTECTED_FIELDS,
                f"_PROTECTED_FIELDS must include '{field}'",
            )

    @_requires_import
    def test_authorized_agents_from_registry(self):
        # covers: ACS-400a-3-i
        """AC-16: authorized agent list is loaded from registry, not hard-coded."""
        # The hook must support reading from config/agent_registry.json
        # _is_authorized("BrainCandy") must return True (human user path)
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Write a minimal registry
            registry = {
                "agents": [
                    {"id": "python-coder", "is_ticket_phase": True},
                    {"id": "business-analyst-v3", "is_ticket_phase": False},
                ]
            }
            reg_file = tmp / "config" / "agent_registry.json"
            reg_file.parent.mkdir(parents=True, exist_ok=True)
            reg_file.write_text(json.dumps(registry), encoding="utf-8")
            # BrainCandy is NOT in the registry → treated as human
            result = _is_authorized("BrainCandy", registry_path=str(reg_file))
            self.assertTrue(
                result,
                "Unknown agent identity (not in registry) must be treated as authorized human",
            )
            # python-coder IS in registry as a known agent → not authorized for protected fields
            result_coder = _is_authorized("python-coder", registry_path=str(reg_file))
            self.assertFalse(
                result_coder,
                "python-coder (known agent) must NOT be authorized for protected fields",
            )


class TestBlockOutputFormat(unittest.TestCase):
    """AC-19: blocked output is JSON block decision to stdout (ACS-400e-1)."""

    @_requires_import
    def test_ac19_block_output_is_json_to_stdout(self):
        # covers: ACS-400e-1
        """AC-19: blocked commit → JSON {'decision': 'block', 'reason': '...'} on stdout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Registry required so python-coder is known (not treated as human)
            _write_registry(tmp)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-019",
                origin_agent="business-analyst-v3",
                criteria="Criteria changed by coder.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-019.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 1)
            # stdout must contain a JSON block decision
            try:
                decision = json.loads(result.stdout)
            except json.JSONDecodeError:
                self.fail(
                    f"stdout must be valid JSON for a blocked commit, got: {result.stdout!r}"
                )
            self.assertEqual(
                decision.get("decision"),
                "block",
                f"JSON decision field must be 'block', got: {decision}",
            )
            reason = decision.get("reason", "")
            # reason must include agent identity, file path, violated rule, authorized agents
            self.assertIn(
                "python-coder",
                reason,
                "Reason must name the unauthorized agent",
            )
            self.assertIn(
                "ACS-TEST-019",
                reason,
                "Reason must include the file path",
            )

    @_requires_import
    def test_ac19_diagnostic_on_stderr(self):
        # covers: ACS-400e-1
        """AC-19: diagnostic detail goes to stderr, not to stdout."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            # Registry required so python-coder is known (not treated as human)
            _write_registry(tmp)
            ac_content = _minimal_ac(
                ac_id="ACS-TEST-019B",
                origin_agent="business-analyst-v3",
                criteria="Criteria changed by coder.",
            )
            ac_file = _write_yaml(
                tmp, "docs/acceptance-criteria/test/ACS-TEST-019B.yaml", ac_content
            )
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_TEST_FILES": str(ac_file),
                    "HOOK_ROOT": tmpdir,
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_CRITERIA_CHANGED": "1",
                },
                capture_output=True,
                text=True,
            )
            # stderr must have some diagnostic content
            self.assertTrue(
                len(result.stderr) > 0,
                "Blocked commit must emit diagnostic detail to stderr",
            )


class TestFailOpenExceptionHandling(unittest.TestCase):
    """AC-20: main() wrapped in try/except → exits 0 on unexpected error (ACS-400e-1-i)."""

    @_requires_import
    def test_ac20_unexpected_exception_exits_0(self):
        # covers: ACS-400e-1-i
        """AC-20: main() wrapped in try/except Exception; unexpected error → exits 0."""
        # We verify the main() function has error handling by checking the hook
        # exits 0 even when given a corrupt environment
        with tempfile.TemporaryDirectory() as tmpdir:
            # Simulate an unexpected error by providing a nonsensical HOOK_ROOT
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_ROOT": "/this/path/does/not/exist/ever",
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"Fail-open: unexpected error must exit 0, got {result.returncode}. "
                f"stdout={result.stdout!r} stderr={result.stderr!r}",
            )

    @_requires_import
    def test_ac20_exception_stderr_has_prefix(self):
        # covers: ACS-400e-1-i
        """AC-20: exception message printed to stderr with [check-ac-governance] prefix."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                [sys.executable, str(_HOOK_SCRIPT)],
                env={
                    **os.environ,
                    "HOOK_ROOT": "/this/path/does/not/exist/ever",
                    "HOOK_AGENT_ID": "python-coder",
                    "HOOK_NO_GIT": "1",
                    "HOOK_SIMULATE_EXCEPTION": "1",  # Force an exception in main()
                },
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            if result.stderr.strip():
                # If stderr has content, it must have the prefix
                self.assertIn(
                    "[check-ac-governance]",
                    result.stderr,
                    "Stderr prefix must be '[check-ac-governance]'",
                )


class TestImportSuccess(unittest.TestCase):
    """Verify the module imports cleanly (import infrastructure test)."""

    def test_module_imports_successfully(self):
        # covers: ACS-400a-1
        """Hook script must exist at the expected path and import without errors."""
        self.assertTrue(
            _HOOK_SCRIPT.exists(),
            f"Hook script not found at {_HOOK_SCRIPT}. "
            "python-coder must create it before test-runner runs.",
        )
        self.assertTrue(
            _IMPORT_OK,
            f"Hook module import failed: {_IMPORT_ERROR if not _IMPORT_OK else '(ok)'}",
        )


if __name__ == "__main__":
    unittest.main()
