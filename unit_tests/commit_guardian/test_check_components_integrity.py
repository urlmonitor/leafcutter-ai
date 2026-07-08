"""
MODULE: test_check_components_integrity
GOAL: Unit tests for check_components_integrity.py pre-commit hook.
BUSINESS CONTEXT: Verifies the components.json integrity guard correctly blocks
    non-merge commits that add new components without a detail_ref, and correctly
    skips the new-component existence check when a git merge is in progress
    (MERGE_HEAD present). The merge-skip behaviour is AC ACS-300g-5.
ARCHITECTURE: Tests use a real temporary git repository (subprocess, cwd=temp)
    because the hook shells out to git commands that operate on CWD. Each test
    sets up an isolated git repo, stages a modified docs/components.json that
    adds a new component with NO detail_ref (the invalid case), then runs the
    hook as a subprocess and asserts on the returncode only.

    Two scenarios:
      1. MERGE_HEAD present → hook must exit 0 (merge-skip).  RED against
         current code (no merge-awareness implemented yet).
      2. No MERGE_HEAD → hook must exit 1 (full check runs).  GREEN regression
         guard; must stay green after the fix is applied.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path to the hook under test
# ---------------------------------------------------------------------------

HOOK_SCRIPT = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)

# ---------------------------------------------------------------------------
# JSON payloads used across tests
# ---------------------------------------------------------------------------

# Initial committed state — one valid existing component (no detail_ref required
# for existing components; the hook only checks newly-added keys).
_INITIAL_COMPONENTS_JSON = json.dumps(
    {
        "components": {
            "existing-component": {
                "name": "Existing Component",
                "description": "A component that was already in HEAD.",
            }
        }
    },
    indent=2,
)

# Staged state — adds "new-invalid-component" which has NO detail_ref.
# validate_new_component() returns an error immediately on missing detail_ref
# (before any disk-path resolution), so the test does not depend on
# REPO_ROOT pointing anywhere real.  This is intentional per AC ACS-300g-5.
_STAGED_COMPONENTS_JSON = json.dumps(
    {
        "components": {
            "existing-component": {
                "name": "Existing Component",
                "description": "A component that was already in HEAD.",
            },
            "new-invalid-component": {
                "name": "New Invalid Component",
                "description": "This component is missing the required detail_ref.",
                # Intentionally no 'detail_ref' key — triggers validate_new_component error.
            },
        }
    },
    indent=2,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git command in *cwd* and return the completed process.

    Args:
        args: List of git sub-command arguments (excluding the leading 'git').
        cwd: Working directory for the git invocation.

    Returns:
        CompletedProcess with stdout and stderr captured.
    """
    try:
        return subprocess.run(
            ["git"] + args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"git {args!r} failed in {cwd}: {exc}") from exc


def _setup_temp_repo(tmp_dir: Path) -> Path:
    """Initialise a fresh git repo in *tmp_dir* and return the repo root.

    Creates docs/components.json with a single existing component, makes the
    initial commit (HEAD), then stages a modified docs/components.json that
    adds an invalid new component (no detail_ref). The repo is left with:

      - HEAD: docs/components.json containing only 'existing-component'
      - Staged index: docs/components.json also containing 'new-invalid-component'

    The hook will diff HEAD vs staged and detect the added key.

    Args:
        tmp_dir: Temporary directory to initialise as a git repo.

    Returns:
        Path to the repo root (same as tmp_dir).
    """
    repo = tmp_dir

    # Initialise repo.
    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "test@example.com"], cwd=repo)
    _git(["config", "user.name", "Test User"], cwd=repo)

    # Create docs/ and write initial components.json.
    docs_dir = repo / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    components_path = docs_dir / "components.json"
    components_path.write_text(_INITIAL_COMPONENTS_JSON, encoding="utf-8")

    # Stage and commit as HEAD.
    _git(["add", "docs/components.json"], cwd=repo)
    _git(["commit", "-m", "chore: initial components.json"], cwd=repo)

    # Now write the modified staged version (adds invalid new component).
    components_path.write_text(_STAGED_COMPONENTS_JSON, encoding="utf-8")
    _git(["add", "docs/components.json"], cwd=repo)

    # Repo state: HEAD has only 'existing-component'; staged index has both.
    return repo


def _get_head_sha(repo: Path) -> str:
    """Return the current HEAD commit SHA in *repo*.

    Args:
        repo: Path to the git repository.

    Returns:
        The full 40-character HEAD commit SHA.
    """
    result = _git(["rev-parse", "HEAD"], cwd=repo)
    return result.stdout.strip()


def _run_hook(repo: Path) -> subprocess.CompletedProcess:
    """Run check_components_integrity.py as a subprocess with cwd=*repo*.

    The hook's git calls (git show, git diff --cached, git rev-parse) all
    operate on CWD, so cwd=repo is what scopes them to the temp repository.

    Args:
        repo: Path to the git repository to run the hook in.

    Returns:
        CompletedProcess with returncode, stdout, and stderr captured.
    """
    try:
        return subprocess.run(
            [sys.executable, str(HOOK_SCRIPT)],
            cwd=str(repo),
            capture_output=True,
            text=True,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        raise RuntimeError(f"hook subprocess failed: {exc}") from exc


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestMergeInProgressSkipsNewComponentCheck(unittest.TestCase):
    """AC ACS-300g-5: when MERGE_HEAD is present the hook must exit 0.

    This test is EXPECTED TO FAIL against the current unmodified hook because
    check_components_integrity.py has no merge-awareness today. The fix
    (not implemented here) is to detect MERGE_HEAD and return 0 early in main().
    """

    def test_merge_in_progress_skips_new_component_check(self) -> None:
        # covers: ACS-300g-5
        """Hook exits 0 when MERGE_HEAD is present, even with an invalid new component staged.

        Simulates a merge in progress by writing .git/MERGE_HEAD containing the
        HEAD SHA so that `git rev-parse -q --verify MERGE_HEAD` succeeds.
        With the invalid new component staged AND MERGE_HEAD present, the hook
        must skip the new-component existence check and exit 0.

        This test FAILS against the current code (exits 1) because the hook has
        no merge-awareness. It becomes green once main() detects MERGE_HEAD and
        returns 0 early.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _setup_temp_repo(repo)

            # Simulate a merge in progress by creating .git/MERGE_HEAD.
            # `git rev-parse -q --verify MERGE_HEAD` succeeds when this file exists
            # and contains a valid commit SHA.
            head_sha = _get_head_sha(repo)
            merge_head_path = repo / ".git" / "MERGE_HEAD"
            merge_head_path.write_text(head_sha + "\n", encoding="utf-8")

            result = _run_hook(repo)

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC ACS-300g-5: hook must exit 0 (skip new-component check) when "
                "MERGE_HEAD is present. Current code exits 1 because it has no "
                f"merge-awareness. Stderr: {result.stderr}"
            ),
        )


class TestNormalCommitStillBlocksInvalidNewComponent(unittest.TestCase):
    """Regression guard: without MERGE_HEAD the hook must still exit 1.

    This test documents the existing behaviour that must be preserved after the
    merge-skip fix is applied. A non-merge commit that adds a new component
    without a detail_ref must continue to be blocked (exit 1).
    """

    def test_normal_commit_still_blocks_invalid_new_component(self) -> None:
        # covers: ACS-300g-5
        """Hook exits 1 on a normal (non-merge) commit when a new component lacks detail_ref.

        No .git/MERGE_HEAD file is present. The staged docs/components.json adds
        'new-invalid-component' which has no detail_ref. The hook must run the
        full new-component existence check and exit 1.

        This test MUST stay green after the merge-skip fix is applied — the fix
        must be scoped to merge commits only and must not weaken the guard for
        normal commits.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            _setup_temp_repo(repo)

            # Confirm no MERGE_HEAD exists (belt-and-suspenders).
            merge_head_path = repo / ".git" / "MERGE_HEAD"
            self.assertFalse(
                merge_head_path.exists(),
                msg=".git/MERGE_HEAD must not exist for the normal-commit scenario.",
            )

            result = _run_hook(repo)

        self.assertEqual(
            result.returncode,
            1,
            msg=(
                "AC ACS-300g-5 regression guard: hook must exit 1 on a normal "
                "non-merge commit when a new component has no detail_ref. "
                f"Stderr: {result.stderr}"
            ),
        )


class TestRepoRootResolvesToGitToplevelForExistingDetailRef(unittest.TestCase):
    """AC ACS-300g-6: REPO_ROOT must be resolved via git rev-parse --show-toplevel,
    not via Path(__file__).parents[2].

    When the hook is invoked through the .leafcutter symlink install path,
    Path(__file__).resolve().parents[2] resolves to the real leafcutter-ai repo
    (or the .leafcutter install root), NOT to the committing repo's top-level.
    A new component whose detail_ref exists under the COMMITTING repo's docs/
    is then wrongly reported as "detail_ref file does not exist" because the
    existence check resolves against the wrong root.

    This test FAILS against the current code (REPO_ROOT = Path(__file__).parents[2])
    because docs/architecture/components/widget.md exists only in the temp repo,
    not in the leafcutter-ai repo that hosts the hook file.  Once the fix is applied
    (REPO_ROOT resolved via `git rev-parse --show-toplevel` in CWD), the hook finds
    the file in the temp repo and exits 0.
    """

    def test_repo_root_resolves_to_git_toplevel_for_existing_detail_ref(self) -> None:
        # covers: ACS-300g-6
        """Hook exits 0 when a new component's detail_ref exists under the committing repo.

        Sets up a temp git repo that contains:
          - docs/architecture/components/widget.md  (has flight_level frontmatter)
          - HEAD: docs/components.json with no 'widget' key
          - Staged index: docs/components.json that ADDS 'widget' with a valid detail_ref

        No MERGE_HEAD is present, so the new-component check runs.  The detail_ref
        file exists in the TEMP REPO.  With the current buggy REPO_ROOT derivation
        (Path(__file__).parents[2] → leafcutter-ai), the hook resolves the path
        against the wrong root and reports "detail_ref file does not exist" → exit 1.
        This test asserts returncode == 0 (the correct post-fix behaviour), so it
        FAILS (is RED) against the current unmodified hook.
        """
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)

            # --- Initialise the git repo ---
            _git(["init", "-b", "main"], cwd=repo)
            _git(["config", "user.email", "test@example.com"], cwd=repo)
            _git(["config", "user.name", "Test User"], cwd=repo)

            # --- Create the detail_ref doc in the temp repo ---
            doc_dir = repo / "docs" / "architecture" / "components"
            doc_dir.mkdir(parents=True, exist_ok=True)
            widget_doc = doc_dir / "widget.md"
            widget_doc.write_text(
                "---\nflight_level: \"L2-Container\"\n---\n# Widget\n\n"
                "Widget component architecture doc.\n",
                encoding="utf-8",
            )

            # --- Write initial components.json (no 'widget' key) and commit as HEAD ---
            docs_dir = repo / "docs"
            components_path = docs_dir / "components.json"
            initial_json = json.dumps(
                {
                    "components": {
                        "existing-component": {
                            "name": "Existing Component",
                            "description": "Already in HEAD.",
                        }
                    }
                },
                indent=2,
            )
            components_path.write_text(initial_json, encoding="utf-8")
            _git(["add", "docs/components.json"], cwd=repo)
            _git(["commit", "-m", "chore: initial components.json"], cwd=repo)

            # Also commit the widget doc so the working tree is clean for the diff
            _git(["add", "docs/architecture/components/widget.md"], cwd=repo)
            _git(["commit", "-m", "docs: add widget architecture doc"], cwd=repo)

            # --- Stage the updated components.json that ADDS 'widget' with a valid detail_ref ---
            # The widget entry must satisfy all four schema validators now wired into main():
            # validate_component_minimum_schema, validate_agent_affinity,
            # validate_exposed_interfaces, validate_depends_on.
            staged_json = json.dumps(
                {
                    "components": {
                        "existing-component": {
                            "name": "Existing Component",
                            "description": "Already in HEAD.",
                        },
                        "widget": {
                            "id": "widget",
                            "name": "Widget",
                            "type": "utility",
                            "description": "The widget component for testing purposes.",
                            "detail_ref": "docs/architecture/components/widget.md",
                            "status": "active",
                            "primary_code": ["scripts/widget.py"],
                            "agent_affinity": [],
                            "exposed_interfaces": [],
                            "depends_on": [],
                        },
                    }
                },
                indent=2,
            )
            components_path.write_text(staged_json, encoding="utf-8")
            _git(["add", "docs/components.json"], cwd=repo)

            # Confirm no MERGE_HEAD (belt-and-suspenders — ensures the new-component check runs)
            merge_head_path = repo / ".git" / "MERGE_HEAD"
            self.assertFalse(
                merge_head_path.exists(),
                msg=".git/MERGE_HEAD must not exist for the normal-commit scenario.",
            )

            result = _run_hook(repo)

        # Primary assertion: the hook should exit 0 because the detail_ref exists
        # under the COMMITTING repo's docs/.  This FAILS against the current code
        # because REPO_ROOT = Path(__file__).parents[2] points at the leafcutter-ai
        # repo (not the temp repo), so the file is not found → exit 1.
        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "AC ACS-300g-6: hook must exit 0 when the new component's detail_ref "
                "exists under the committing repo's docs/.  Current buggy code resolves "
                "REPO_ROOT from Path(__file__).parents[2] (the leafcutter-ai repo root) "
                "instead of via git rev-parse --show-toplevel (the temp repo root), so "
                "the detail_ref path is not found and the hook exits 1. "
                f"Stderr: {result.stderr}"
            ),
        )

        # Soft secondary check: the failure mode is specifically the path-resolution one.
        # If (unexpectedly) the hook exits 1, verify the error is the detail_ref not-found
        # message, not something unrelated.
        if result.returncode != 0:
            self.assertIn(
                "detail_ref file does not exist",
                result.stderr,
                msg=(
                    "AC ACS-300g-6 diagnostic: expected exit-1 to be caused specifically "
                    "by the path-resolution bug (detail_ref file does not exist), not by "
                    f"an unrelated error.  Full stderr: {result.stderr}"
                ),
            )


# ---------------------------------------------------------------------------
# Unit tests for the new full-schema validators (ACS-300g-1, ACS-300h-1,
# ACS-300i-1, ACS-300i-2, ACS-300j-1) — loaded via importlib from the template.
# ---------------------------------------------------------------------------

import importlib.util

_TEMPLATE_HOOK = (
    Path(__file__).parent.parent.parent
    / "templates"
    / "scripts"
    / "commit_guardian"
    / "check_components_integrity.py"
)

try:
    _spec = importlib.util.spec_from_file_location(
        "_check_ci_schema_shim", str(_TEMPLATE_HOOK)
    )
    _schema_mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    _spec.loader.exec_module(_schema_mod)  # type: ignore[union-attr]

    _validate_minimum = _schema_mod.validate_component_minimum_schema
    _validate_affinity = _schema_mod.validate_agent_affinity
    _validate_interfaces = _schema_mod.validate_exposed_interfaces
    _validate_depends = _schema_mod.validate_depends_on
    _ALLOWED_TYPES = _schema_mod.ALLOWED_TYPES
    _ALLOWED_STATUSES = _schema_mod.ALLOWED_STATUSES
    _SCHEMA_MOD_OK = True
    _SCHEMA_MOD_ERR = ""
except Exception as _exc:  # noqa: BLE001
    _SCHEMA_MOD_OK = False
    _SCHEMA_MOD_ERR = str(_exc)


def _full_entry(overrides: dict | None = None) -> dict:
    """Return a complete, valid component entry dict.

    Args:
        overrides: Optional key-value pairs to replace in the base entry.

    Returns:
        A fully-populated component dict satisfying all validator constraints.
    """
    base: dict = {
        "id": "my_component",
        "name": "My Component",
        "type": "utility",
        "description": "A well-formed component used for testing purposes.",
        "detail_ref": None,
        "status": "active",
        "primary_code": ["scripts/my_component.py"],
        "agent_affinity": [],
        "exposed_interfaces": [],
        "depends_on": [],
    }
    if overrides:
        base.update(overrides)
    return base


@unittest.skipUnless(
    _SCHEMA_MOD_OK,
    f"schema module load failed: {_SCHEMA_MOD_ERR}",
)
class TestValidateComponentMinimumSchemaAcs300g1(unittest.TestCase):
    """Unit tests for validate_component_minimum_schema (ACS-300g-1).

    Verifies that a valid entry passes and that each missing required field
    causes an appropriate error.
    """

    def test_valid_entry_passes(self) -> None:
        """A fully valid component entry returns no errors."""
        errors = _validate_minimum("my_component", _full_entry())
        self.assertEqual(errors, [], f"Unexpected errors: {errors}")

    def test_detail_ref_null_passes(self) -> None:
        """detail_ref null is accepted as per ACS-300g-1."""
        errors = _validate_minimum("my_component", _full_entry({"detail_ref": None}))
        self.assertEqual(errors, [])

    def test_missing_id_fails(self) -> None:
        """A component entry missing 'id' is rejected."""
        entry = _full_entry()
        del entry["id"]
        errors = _validate_minimum("my_component", entry)
        self.assertTrue(
            any("'id'" in e for e in errors),
            f"Expected id error in: {errors}",
        )

    def test_missing_name_fails(self) -> None:
        """A component entry missing 'name' is rejected."""
        entry = _full_entry()
        del entry["name"]
        errors = _validate_minimum("my_component", entry)
        self.assertTrue(
            any("'name'" in e for e in errors),
            f"Expected name error in: {errors}",
        )

    def test_missing_type_fails(self) -> None:
        """A component entry missing 'type' is rejected."""
        entry = _full_entry()
        del entry["type"]
        errors = _validate_minimum("my_component", entry)
        self.assertTrue(
            any("'type'" in e for e in errors),
            f"Expected type error in: {errors}",
        )

    def test_missing_description_fails(self) -> None:
        """A component entry missing 'description' is rejected."""
        entry = _full_entry()
        del entry["description"]
        errors = _validate_minimum("my_component", entry)
        self.assertTrue(
            any("'description'" in e for e in errors),
            f"Expected description error in: {errors}",
        )

    def test_missing_status_fails(self) -> None:
        """A component entry missing 'status' is rejected."""
        entry = _full_entry()
        del entry["status"]
        errors = _validate_minimum("my_component", entry)
        self.assertTrue(
            any("'status'" in e for e in errors),
            f"Expected status error in: {errors}",
        )

    def test_missing_primary_code_fails(self) -> None:
        """A component entry missing 'primary_code' is rejected."""
        entry = _full_entry()
        del entry["primary_code"]
        errors = _validate_minimum("my_component", entry)
        self.assertTrue(
            any("'primary_code'" in e for e in errors),
            f"Expected primary_code error in: {errors}",
        )

    def test_invalid_type_value_fails(self) -> None:
        """A 'type' value not in ALLOWED_TYPES is rejected."""
        errors = _validate_minimum("my_component", _full_entry({"type": "not_valid"}))
        self.assertTrue(
            any("'type'" in e for e in errors),
            f"Expected type-enum error in: {errors}",
        )

    def test_all_allowed_types_pass(self) -> None:
        """Every value in ALLOWED_TYPES passes type validation."""
        for t in _ALLOWED_TYPES:
            errors = _validate_minimum("my_component", _full_entry({"type": t}))
            type_errs = [e for e in errors if "'type'" in e]
            self.assertEqual(
                type_errs,
                [],
                f"Type '{t}' was unexpectedly rejected: {type_errs}",
            )

    def test_description_too_short_fails(self) -> None:
        """A description shorter than DESCRIPTION_MIN_LEN is rejected."""
        errors = _validate_minimum("my_component", _full_entry({"description": "Short"}))
        self.assertTrue(
            any("'description'" in e for e in errors),
            f"Expected description-length error in: {errors}",
        )

    def test_invalid_status_fails(self) -> None:
        """A 'status' value not in ALLOWED_STATUSES is rejected."""
        errors = _validate_minimum("my_component", _full_entry({"status": "unknown"}))
        self.assertTrue(
            any("'status'" in e for e in errors),
            f"Expected status-enum error in: {errors}",
        )

    def test_detail_ref_nonexistent_file_fails(self) -> None:
        """detail_ref pointing to a non-existent file is rejected."""
        errors = _validate_minimum(
            "my_component",
            _full_entry({"detail_ref": "docs/does_not_exist_ever.md"}),
        )
        self.assertTrue(
            any("'detail_ref'" in e and "does not exist" in e for e in errors),
            f"Expected detail_ref path error in: {errors}",
        )

    def test_id_not_snake_case_fails(self) -> None:
        """An 'id' value that is not snake_case is rejected (ACS-300g-1, M-2)."""
        # camelCase "myComponent" violates the snake_case constraint
        errors = _validate_minimum("myComponent", _full_entry({"id": "myComponent"}))
        self.assertTrue(
            any("snake_case" in e for e in errors),
            f"Expected snake_case error in: {errors}",
        )

    def test_id_with_hyphen_fails(self) -> None:
        """An 'id' containing hyphens is rejected — only underscores are allowed."""
        errors = _validate_minimum("my_comp", _full_entry({"id": "my-comp"}))
        # id field does not match the top-level key either, so any id-related error suffices
        self.assertTrue(
            any("'id'" in e for e in errors),
            f"Expected id error in: {errors}",
        )

    def test_id_snake_case_with_digits_passes(self) -> None:
        """An 'id' with digits in snake_case format is accepted."""
        errors = _validate_minimum("my_comp2", _full_entry({"id": "my_comp2"}))
        id_errors = [e for e in errors if "'id'" in e]
        self.assertEqual(id_errors, [], f"snake_case id with digit should pass: {id_errors}")


@unittest.skipUnless(
    _SCHEMA_MOD_OK,
    f"schema module load failed: {_SCHEMA_MOD_ERR}",
)
class TestValidateAgentAffinityAcs300h1(unittest.TestCase):
    """Unit tests for validate_agent_affinity (ACS-300h-1).

    Every component entry must have agent_affinity as a JSON array.
    Null and absent are both invalid; empty array [] is valid.
    """

    def test_empty_array_passes(self) -> None:
        """agent_affinity: [] (empty array) is valid."""
        errors = _validate_affinity("my_component", {"agent_affinity": []})
        self.assertEqual(errors, [], f"Empty array should pass: {errors}")

    def test_non_empty_array_passes(self) -> None:
        """agent_affinity: [python-coder] (non-empty array) is valid."""
        errors = _validate_affinity(
            "my_component", {"agent_affinity": ["python-coder"]}
        )
        self.assertEqual(errors, [], f"Non-empty array should pass: {errors}")

    def test_missing_field_fails(self) -> None:
        """A component entry without agent_affinity is rejected."""
        errors = _validate_affinity("my_component", {})
        self.assertTrue(
            len(errors) > 0,
            "Expected an error for missing agent_affinity field.",
        )
        self.assertTrue(
            any("agent_affinity" in e for e in errors),
            f"Error should mention 'agent_affinity': {errors}",
        )

    def test_null_value_fails(self) -> None:
        """agent_affinity: null is rejected (must be an array)."""
        errors = _validate_affinity("my_component", {"agent_affinity": None})
        self.assertTrue(
            len(errors) > 0,
            "Expected an error for null agent_affinity.",
        )
        self.assertTrue(
            any("agent_affinity" in e for e in errors),
            f"Error should mention 'agent_affinity': {errors}",
        )

    def test_non_dict_input_returns_empty(self) -> None:
        """Non-dict component_data returns [] without raising."""
        errors = _validate_affinity("my_component", "not_a_dict")
        self.assertEqual(errors, [])


@unittest.skipUnless(
    _SCHEMA_MOD_OK,
    f"schema module load failed: {_SCHEMA_MOD_ERR}",
)
class TestValidateExposedInterfacesAcs300i1Acs300i2(unittest.TestCase):
    """Unit tests for validate_exposed_interfaces (ACS-300i-1, ACS-300i-2).

    exposed_interfaces must be a present array (never null, never absent).
    Each element must have all four fields: name, type, path, shape.
    All missing fields per element are reported in one error (not fail-on-first).
    """

    def test_empty_array_passes(self) -> None:
        """exposed_interfaces: [] is valid for internal components."""
        errors = _validate_interfaces("my_component", {"exposed_interfaces": []})
        self.assertEqual(errors, [], f"Empty array should pass: {errors}")

    def test_valid_interface_element_passes(self) -> None:
        """A fully-populated interface element passes validation."""
        entry = {
            "exposed_interfaces": [
                {
                    "name": "run_hook",
                    "type": "hook_protocol",
                    "path": "scripts/commit_guardian/run_hook.py",
                    "shape": "python callable",
                }
            ]
        }
        errors = _validate_interfaces("my_component", entry)
        self.assertEqual(errors, [], f"Valid element should pass: {errors}")

    def test_missing_field_fails_absent(self) -> None:
        """A component entry without exposed_interfaces is rejected (ACS-300i-2)."""
        errors = _validate_interfaces("my_component", {})
        self.assertTrue(
            len(errors) > 0,
            "Expected error for absent exposed_interfaces.",
        )
        self.assertTrue(
            any("exposed_interfaces" in e for e in errors),
            f"Error should mention 'exposed_interfaces': {errors}",
        )

    def test_null_value_fails(self) -> None:
        """exposed_interfaces: null is rejected (ACS-300i-2)."""
        errors = _validate_interfaces("my_component", {"exposed_interfaces": None})
        self.assertTrue(
            len(errors) > 0,
            "Expected error for null exposed_interfaces.",
        )

    def test_all_missing_fields_reported_in_one_pass(self) -> None:
        """An element missing multiple fields reports ALL of them in one error (ACS-300i-1)."""
        entry = {
            "exposed_interfaces": [
                # name and shape are missing; type and path are present
                {
                    "type": "file_contract",
                    "path": "docs/schema.md",
                }
            ]
        }
        errors = _validate_interfaces("my_component", entry)
        # There should be exactly one error for element[0] listing both missing fields.
        iface_errors = [e for e in errors if "exposed_interfaces[0]" in e and "missing" in e]
        self.assertEqual(
            len(iface_errors),
            1,
            f"Expected a single error listing all missing fields: {errors}",
        )
        self.assertIn(
            "name",
            iface_errors[0],
            f"Error should mention missing 'name': {iface_errors[0]}",
        )
        self.assertIn(
            "shape",
            iface_errors[0],
            f"Error should mention missing 'shape': {iface_errors[0]}",
        )

    def test_single_missing_field_reported(self) -> None:
        """An element missing only one field is rejected with an error naming it."""
        entry = {
            "exposed_interfaces": [
                {
                    "name": "my_func",
                    "type": "function_signature",
                    "path": "scripts/my.py",
                    # shape is missing
                }
            ]
        }
        errors = _validate_interfaces("my_component", entry)
        iface_errors = [e for e in errors if "exposed_interfaces[0]" in e and "missing" in e]
        self.assertGreater(len(iface_errors), 0, f"Expected missing-field error: {errors}")
        self.assertIn("shape", iface_errors[0])

    def test_invalid_interface_type_fails(self) -> None:
        """An element with an unsupported type value is rejected."""
        entry = {
            "exposed_interfaces": [
                {
                    "name": "my_func",
                    "type": "not_a_valid_type",
                    "path": "scripts/my.py",
                    "shape": "dict",
                }
            ]
        }
        errors = _validate_interfaces("my_component", entry)
        type_errors = [e for e in errors if "type" in e and "not_a_valid_type" in e]
        self.assertGreater(
            len(type_errors),
            0,
            f"Expected interface-type-enum error: {errors}",
        )


@unittest.skipUnless(
    _SCHEMA_MOD_OK,
    f"schema module load failed: {_SCHEMA_MOD_ERR}",
)
class TestValidateDependsOnAcs300j1(unittest.TestCase):
    """Unit tests for validate_depends_on (ACS-300j-1).

    depends_on references must only name IDs that exist in the same file.
    Error messages must name the invalid reference, the declaring component,
    and the list of valid IDs.
    """

    def test_valid_depends_on_reference_passes(self) -> None:
        """A depends_on referencing a known component ID passes."""
        all_ids = {"my_component", "other_component"}
        entry = {"depends_on": ["other_component"]}
        errors = _validate_depends("my_component", entry, all_ids)
        self.assertEqual(errors, [], f"Valid reference should pass: {errors}")

    def test_empty_depends_on_passes(self) -> None:
        """An empty depends_on list produces no errors."""
        errors = _validate_depends("my_component", {"depends_on": []}, {"my_component"})
        self.assertEqual(errors, [])

    def test_absent_depends_on_passes(self) -> None:
        """A component without depends_on produces no errors."""
        errors = _validate_depends("my_component", {}, {"my_component"})
        self.assertEqual(errors, [])

    def test_unknown_id_fails(self) -> None:
        """A depends_on referencing an unknown ID is rejected."""
        all_ids = {"my_component", "known_component"}
        entry = {"depends_on": ["unknown_component"]}
        errors = _validate_depends("my_component", entry, all_ids)
        self.assertGreater(len(errors), 0, "Expected an error for unknown ID.")
        self.assertIn(
            "unknown_component",
            errors[0],
            f"Error should name the invalid reference: {errors[0]}",
        )
        self.assertIn(
            "my_component",
            errors[0],
            f"Error should name the declaring component: {errors[0]}",
        )

    def test_error_lists_valid_ids(self) -> None:
        """The error message for an invalid reference includes the valid IDs."""
        all_ids = {"alpha", "beta", "gamma"}
        entry = {"depends_on": ["nonexistent"]}
        errors = _validate_depends("check_dep_test", entry, all_ids)
        self.assertGreater(len(errors), 0)
        # The sorted valid IDs should appear somewhere in the error message.
        for valid_id in sorted(all_ids):
            self.assertIn(
                valid_id,
                errors[0],
                f"Expected valid ID '{valid_id}' in error: {errors[0]}",
            )

    def test_multiple_invalid_ids_each_reported(self) -> None:
        """Each invalid depends_on entry produces a separate error."""
        all_ids = {"my_component"}
        entry = {"depends_on": ["bad_one", "bad_two"]}
        errors = _validate_depends("my_component", entry, all_ids)
        self.assertEqual(
            len(errors),
            2,
            f"Expected one error per invalid reference: {errors}",
        )


if __name__ == "__main__":
    unittest.main()
