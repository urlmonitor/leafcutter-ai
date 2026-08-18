"""
MODULE: unit_tests/commit_guardian/test_ge_120_doc_types_deployed_resolution.py
GOAL: GE-120 — doc_type_validators.py's ``_DOC_TYPES_JSON`` must resolve to the
    real ``config/doc_types.json`` when running from the DEPLOYED
    ``.leafcutter/scripts/commit_guardian/`` layout, not a doubled
    ``.leafcutter/leafcutter/config/...`` segment produced by a hand-counted
    ``parents[2]``. A silent ``.exists()`` fallthrough must stop being silent:
    an absent or malformed declaring file must fail observably, never
    substitute the narrower ``DOC_FM_ALLOWED_TYPES`` constant without saying so.
BUSINESS CONTEXT: config/doc_types.json declares TEN doc types (including
    ``card`` and the canonical ``how_to`` spelling); the unread file means only
    the SEVEN types in the hardcoded fallback are honoured, so every generated
    agent card and every doc using ``how_to`` (rather than the deprecated
    ``how-to`` alias) is rejected by check-doc-frontmatter.
ARCHITECTURE: Not needed.

ROOT CAUSE, verified empirically (see AC GE-120 and the docstring of
    doc_type_validators.py):

        _DOC_TYPES_JSON = Path(__file__).resolve().parents[2] / "leafcutter" / "config" / "doc_types.json"

    From the deployed location ``.leafcutter/scripts/commit_guardian/``,
    ``parents[2]`` is ``.leafcutter``, so this resolves to
    ``.leafcutter/leafcutter/config/doc_types.json`` — a doubled segment that
    has never existed. ``_load_doc_types()`` falls through
    ``if _DOC_TYPES_JSON.exists():`` (never raising) and returns the
    ``DOC_FM_ALLOWED_TYPES`` fallback silently.

EXERCISE STRATEGY (documented per test-writer instructions):

    This repo is self-hosted (ADR-001): ``.leafcutter/scripts/commit_guardian/``
    already contains the REAL deployed copy of this template, at the correct
    relative depth from THIS repo's actual root, which is a real git
    repository with a real ``config/doc_types.json``. Tests 1 and 4 (angles
    "deployed" and "boundary") exercise that REAL deployed copy directly in a
    fresh subprocess — this is the literal "deployed .leafcutter/scripts/
    commit_guardian/ path" the AC test_spec names, and it needs no synthesized
    fixture tree because the self-hosted layout already IS a faithful
    production instance. ``importlib.reload`` is intentionally never used, per
    the AC — it masks cold-import behaviour; each probe runs in a brand-new
    ``sys.executable`` subprocess instead.

    Tests 2 and 3 (angles "reachability" and "failure") invoke the PRODUCTION
    ENTRY POINT — ``run_hook.py <check_doc_frontmatter.py> <files...>`` — as a
    subprocess, exactly as pre-commit does, per the AC test_spec. Because that
    entry point also reads the git working-tree top-level and
    ``docs/components.json`` (via ``_resolve_worktree_root()`` /
    ``load_components_registry()``), those two tests build an ISOLATED, real,
    throwaway git repository (mirroring the existing GE-115 test pattern in
    ``test_check_doc_frontmatter_worktree_pathbase.py``) rather than writing
    temp fixtures into this repo's own real ``docs/`` tree. This keeps the
    tests hermetic while still exercising the REAL deployed
    ``run_hook.py``/``check_doc_frontmatter.py``/``doc_type_validators.py``
    trio unmodified — only the staged *documents* and the *cwd* are
    synthetic; the code under test is the genuine on-disk deployed copy.
    ``doc_type_validators.py``'s own ``_DOC_TYPES_JSON`` computation is keyed
    off its own ``__file__`` (the real deployed path), so it is unaffected by
    which cwd the hook is invoked from — the isolated-repo cwd only supplies
    the staged-file base and the components registry.

RED BASELINE — see the test-writer sign-off comment on ticket GE-120 for the
    exact captured subprocess output. Expected per test_rationale:
    - Test 1 (deployed/resolves): RED — resolved path does not exist; loaded
      key set is the 7-entry fallback, not config/doc_types.json's 10 keys.
    - Test 2 (reachability/accepts card+how_to): RED — both docs are rejected
      today ("unknown doc type: card" + "Missing required field: 'components'"
      for the card; "unknown doc type: how_to" for the how_to doc).
    - Test 3 (failure/rejects undeclared type): may already be GREEN — an
      undeclared type is rejected by both the fallback AND the real file, so
      this is a regression guard rather than a red-phase test. See the
      sign-off comment for the observed result.
    - Test 4 (boundary/unreadable file fails observably): RED — both the
      absent-file and malformed-file cases fall through silently today with
      no exception raised and no path named anywhere.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module-level constants
# ---------------------------------------------------------------------------

# unit_tests/commit_guardian/test_*.py -> unit_tests/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]

_DEPLOYED_DIR = _REPO_ROOT / ".leafcutter" / "scripts" / "commit_guardian"
_DEPLOYED_DOC_TYPE_VALIDATORS = _DEPLOYED_DIR / "doc_type_validators.py"
_DEPLOYED_CHECK_DOC_FRONTMATTER = _DEPLOYED_DIR / "check_doc_frontmatter.py"
_DEPLOYED_RUN_HOOK = _DEPLOYED_DIR / "run_hook.py"

_REAL_DOC_TYPES_JSON = _REPO_ROOT / "config" / "doc_types.json"

_SUBPROCESS_TIMEOUT_SECONDS = 20

# Minimal components registry for the isolated throwaway repos used by
# tests 2 and 3. Registers "commit_guardian" — a real component id in this
# repo's own docs/components.json — so validate_components() passes
# regardless of which project_root the fix ultimately resolves.
_COMPONENTS_JSON = """\
{
  "components": {
    "commit_guardian": {
      "name": "Commit Guardian",
      "description": "Pre-commit hook suite used by GE-120 regression tests."
    }
  }
}
"""

# A generated agent card per config/doc_types.json's own description:
# "Generated by generate_agent_cards.py. Not component-linked." Deliberately
# omits `components` — the AC says a card must NOT be additionally rejected
# for lacking one.
_CARD_DOC_FRONTMATTER = """\
---
title: "GE-120 temp agent card"
type: card
status: active
created: "2026-08-18"
last_updated: "2026-08-18"
---

Temporary agent-card fixture for GE-120.
"""

# A doc using the CANONICAL how_to spelling (not the deprecated how-to alias).
_HOWTO_DOC_FRONTMATTER = """\
---
title: "GE-120 temp how_to doc"
type: how_to
status: active
created: "2026-08-18"
last_updated: "2026-08-18"
components:
  - commit_guardian
---

Temporary how_to fixture for GE-120.
"""

# A `type` value absent from BOTH config/doc_types.json and the
# DOC_FM_ALLOWED_TYPES fallback. Carries a valid `components` entry so the
# only failure signal is the type rejection itself (isolates the assertion).
_BOGUS_TYPE_DOC_FRONTMATTER = """\
---
title: "GE-120 temp undeclared-type doc"
type: ge120-totally-undeclared-type
status: active
created: "2026-08-18"
last_updated: "2026-08-18"
components:
  - commit_guardian
---

Temporary undeclared-type fixture for GE-120.
"""

# ---------------------------------------------------------------------------
# Helper script bodies run in fresh `sys.executable` subprocesses.
#
# Each script receives the deployed commit_guardian directory as argv[1],
# inserts it at sys.path[0] (so `import doc_type_validators` / `import config`
# resolve against the REAL deployed copy), and prints a JSON payload to
# stdout. A fresh subprocess is used per AC GE-120's explicit instruction
# that `importlib.reload()` masks cold-import behaviour (the module caches
# results in `_DOC_TYPES_CACHE` at first import).
# ---------------------------------------------------------------------------

_RESOLVE_PROBE_SCRIPT = """\
import json
import sys

deployed_dir = sys.argv[1]
sys.path.insert(0, deployed_dir)

import doc_type_validators as dtv  # noqa: E402

result = {
    "resolved_path": str(dtv._DOC_TYPES_JSON),
    "exists": dtv._DOC_TYPES_JSON.exists(),
    "loaded_keys": sorted(dtv._load_doc_types().keys()),
}
print(json.dumps(result))
"""

_BOUNDARY_PROBE_SCRIPT = """\
import json
import sys
import tempfile
from pathlib import Path

deployed_dir = sys.argv[1]
sys.path.insert(0, deployed_dir)

import doc_type_validators as dtv  # noqa: E402

results = {}

# Case 1: declaring file absent entirely.
missing_path = Path(tempfile.gettempdir()) / "ge120_absent_doc_types_probe.json"
if missing_path.exists():
    missing_path.unlink()
dtv._DOC_TYPES_JSON = missing_path
dtv._DOC_TYPES_CACHE = None
try:
    dtv._load_doc_types()
except Exception as exc:  # noqa: BLE001
    results["absent_raised"] = True
    results["absent_error"] = str(exc)
else:
    results["absent_raised"] = False
    results["absent_error"] = None

# Case 2: declaring file present but malformed JSON.
malformed_path = Path(tempfile.gettempdir()) / "ge120_malformed_doc_types_probe.json"
malformed_path.write_text("{not valid json!!", encoding="utf-8")
dtv._DOC_TYPES_JSON = malformed_path
dtv._DOC_TYPES_CACHE = None
try:
    dtv._load_doc_types()
except Exception as exc:  # noqa: BLE001
    results["malformed_raised"] = True
    results["malformed_error"] = str(exc)
else:
    results["malformed_raised"] = False
    results["malformed_error"] = None
finally:
    malformed_path.unlink(missing_ok=True)

results["missing_path_str"] = str(missing_path)
results["malformed_path_str"] = str(malformed_path)
print(json.dumps(results))
"""


def _run_probe_script(script_text: str, args: list[str]) -> subprocess.CompletedProcess:
    """Write *script_text* to a fresh temp .py file and run it as a subprocess.

    Args:
        script_text: Full Python source to execute.
        args: Extra argv entries appended after the script path.

    Returns:
        CompletedProcess with stdout/stderr captured as text.
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix="_ge120_probe.py", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(script_text)
        script_path = fh.name

    try:
        return subprocess.run(
            [sys.executable, script_path, *args],
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        )
    finally:
        Path(script_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Helpers for the isolated throwaway git repos (tests 2 and 3).
# ---------------------------------------------------------------------------


def _git_available() -> bool:
    """Return True if git is reachable on PATH."""
    try:
        result = subprocess.run(["git", "--version"], capture_output=True, text=True)
    except (FileNotFoundError, OSError):
        return False
    else:
        return result.returncode == 0


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git subcommand in *cwd* with captured output."""
    return subprocess.run(
        ["git", *args], cwd=str(cwd), capture_output=True, text=True
    )


def _init_temp_repo(base: Path) -> Path:
    """Create a fresh, isolated git repo with a docs/components.json registry.

    Mirrors the GE-115 `_setup_primary_repo` pattern in
    `test_check_doc_frontmatter_worktree_pathbase.py`: a real `git init`
    repo (not a mock) so `_resolve_worktree_root()` inside the real deployed
    `check_doc_frontmatter.py` resolves `git rev-parse --show-toplevel` to
    this directory when the hook is invoked with cwd=repo.

    Args:
        base: Parent temp directory under which `repo/` is created.

    Returns:
        Path to the repo root.
    """
    repo = base / "repo"
    repo.mkdir(parents=True, exist_ok=True)

    _git(["init", "-b", "main"], cwd=repo)
    _git(["config", "user.email", "ge120test@example.com"], cwd=repo)
    _git(["config", "user.name", "GE-120 Test"], cwd=repo)

    docs_dir = repo / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "components.json").write_text(_COMPONENTS_JSON, encoding="utf-8")

    _git(["add", "-A"], cwd=repo)
    _git(["commit", "-m", "chore: ge120 test scaffold"], cwd=repo)

    return repo


def _run_deployed_hook(cwd: Path, filenames: list[str]) -> subprocess.CompletedProcess:
    """Invoke the REAL deployed hook via the REAL deployed run_hook.py wrapper.

    Reproduces the exact production entry point named by the AC test_spec:
    ``python run_hook.py check_doc_frontmatter.py <files...>``. Passing
    *filenames* as positional CLI args activates the ``args.filenames``
    branch of ``get_files_to_check()`` (bypassing the git index), the same
    branch pre-commit itself uses when it forwards staged file paths.

    Args:
        cwd: Working directory for the subprocess — must be a real git repo
            top-level so `_resolve_worktree_root()` resolves correctly.
        filenames: Staged file paths relative to *cwd*.

    Returns:
        CompletedProcess with returncode, stdout, stderr captured.
    """
    return subprocess.run(
        [
            sys.executable,
            str(_DEPLOYED_RUN_HOOK),
            str(_DEPLOYED_CHECK_DOC_FRONTMATTER),
            *filenames,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Test 1 — angle: deployed
# ---------------------------------------------------------------------------


class TestGe120DeployedValidatorResolvesRealDocTypesFile(unittest.TestCase):
    """AC GE-120: the deployed module's _DOC_TYPES_JSON must resolve to a file
    that actually exists, with the same key set as the real declaring file."""

    def test_ge_120_deployed_validator_resolves_the_real_doc_types_file(self) -> None:
        # covers: GE-120
        """PRODUCTION LAYOUT: import doc_type_validators from the DEPLOYED
        .leafcutter/scripts/commit_guardian/ path in a fresh subprocess and
        assert _DOC_TYPES_JSON resolves to a file that exists, with a loaded
        key set matching config/doc_types.json's real keys.

        FAILS TODAY: _DOC_TYPES_JSON resolves to
        '.leafcutter/leafcutter/config/doc_types.json' (a doubled segment
        that has never existed) because of the hand-counted
        `parents[2]` computation. `_load_doc_types()` falls through to the
        7-entry DOC_FM_ALLOWED_TYPES fallback instead of the real 10-entry
        file.

        What must be implemented to make this green: derive the config path
        via the existing `_resolve_root.find_project_root()` resolver (per
        AC GE-120 it_requirements), not a hand-counted `parents[N]` walk.
        """
        if not _DEPLOYED_DOC_TYPE_VALIDATORS.exists():
            self.skipTest(f"Deployed module not found: {_DEPLOYED_DOC_TYPE_VALIDATORS}")
        if not _REAL_DOC_TYPES_JSON.exists():
            self.skipTest(f"Real declaring file not found: {_REAL_DOC_TYPES_JSON}")

        proc = _run_probe_script(_RESOLVE_PROBE_SCRIPT, [str(_DEPLOYED_DIR)])
        self.assertEqual(
            proc.returncode,
            0,
            msg=(
                f"Probe script crashed unexpectedly.\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            ),
        )
        payload = json.loads(proc.stdout)

        real_doc_types = json.loads(_REAL_DOC_TYPES_JSON.read_text(encoding="utf-8"))
        expected_keys = sorted(real_doc_types["doc_types"].keys())

        self.assertTrue(
            payload["exists"],
            msg=(
                "GE-120 RED: the deployed doc_type_validators._DOC_TYPES_JSON "
                f"resolved to '{payload['resolved_path']}', which does not "
                f"exist. The real declaring file is at {_REAL_DOC_TYPES_JSON}. "
                "This is the doubled-segment defect described in AC GE-120."
            ),
        )
        self.assertEqual(
            payload["loaded_keys"],
            expected_keys,
            msg=(
                "GE-120 RED: _load_doc_types() loaded "
                f"{payload['loaded_keys']} instead of the real declaring "
                f"file's keys {expected_keys}. This means the silent "
                "DOC_FM_ALLOWED_TYPES fallback fired instead of reading "
                f"{_REAL_DOC_TYPES_JSON}."
            ),
        )


# ---------------------------------------------------------------------------
# Test 2 — angle: reachability
# ---------------------------------------------------------------------------


class TestGe120DeployedGuardAcceptsCardAndHowTo(unittest.TestCase):
    """AC GE-120: the real hook, via the real run_hook.py entry point, must
    accept a `type: card` doc (no components) and a `type: how_to` doc."""

    def setUp(self) -> None:
        if not _git_available():
            self.skipTest("git not on PATH — skipping deployed-guard tests")
        if not _DEPLOYED_RUN_HOOK.exists() or not _DEPLOYED_CHECK_DOC_FRONTMATTER.exists():
            self.skipTest("Deployed run_hook.py / check_doc_frontmatter.py not found")

        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)
        self.repo = _init_temp_repo(self.base)

    def test_ge_120_deployed_guard_accepts_a_card_and_a_how_to_document(self) -> None:
        # covers: GE-120
        """PRODUCTION ENTRY POINT: stage a `type: card` doc (no components,
        per doc_types.json's own "Not component-linked" description) and a
        `type: how_to` doc (with components), then run the deployed hook via
        `python run_hook.py check_doc_frontmatter.py <paths>` as a subprocess.
        Assert exit zero.

        FAILS TODAY on BOTH docs simultaneously:
          - the card doc fails with 'unknown doc type: card' AND
            'Missing required field: 'components'' (two independent errors —
            asserting only the type enum accepts 'card' would leave this
            second arm uncaught).
          - the how_to doc fails with 'unknown doc type: how_to' (the
            canonical spelling; only the deprecated 'how-to' alias currently
            works).

        What must be implemented to make this green: read config/doc_types.json
        (test 1's fix) AND exempt doc types the file itself marks as not
        component-linked (e.g. 'card') from the components required-field
        check, per AC GE-120's third criterion.
        """
        card_dir = self.repo / "docs" / "agents" / "cards"
        card_dir.mkdir(parents=True, exist_ok=True)
        (card_dir / "ge120_temp.card.md").write_text(_CARD_DOC_FRONTMATTER, encoding="utf-8")

        (self.repo / "docs" / "ge120_temp_howto.md").write_text(
            _HOWTO_DOC_FRONTMATTER, encoding="utf-8"
        )

        result = _run_deployed_hook(
            cwd=self.repo,
            filenames=[
                "docs/agents/cards/ge120_temp.card.md",
                "docs/ge120_temp_howto.md",
            ],
        )

        self.assertEqual(
            result.returncode,
            0,
            msg=(
                "GE-120 RED: expected the deployed hook to accept a `type: "
                "card` doc (no components) and a `type: how_to` doc, but got "
                f"a non-zero exit.\n\nstdout:\n{result.stdout}\n\n"
                f"stderr:\n{result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 3 — angle: failure (must_block negative control)
# ---------------------------------------------------------------------------


class TestGe120DeployedGuardRejectsUndeclaredType(unittest.TestCase):
    """AC GE-120 must_block negative control: an undeclared `type` value must
    still be rejected by name through the SAME production entry point."""

    def setUp(self) -> None:
        if not _git_available():
            self.skipTest("git not on PATH — skipping deployed-guard tests")
        if not _DEPLOYED_RUN_HOOK.exists() or not _DEPLOYED_CHECK_DOC_FRONTMATTER.exists():
            self.skipTest("Deployed run_hook.py / check_doc_frontmatter.py not found")

        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.base = Path(self._tmpdir.name)
        self.repo = _init_temp_repo(self.base)

    def test_ge_120_deployed_guard_still_rejects_an_undeclared_type(self) -> None:
        # covers: GE-120
        """must_block negative control through the SAME deployed entry point:
        a document whose `type` is absent from BOTH config/doc_types.json and
        the DOC_FM_ALLOWED_TYPES fallback must exit non-zero and NAME the
        offending value. Without this, a fix that reads the real file is
        indistinguishable from a fix that disables the check entirely.

        This may already be GREEN against unmodified code (rejecting an
        unknown type is existing behaviour regardless of which type list is
        consulted) — see the sign-off comment for the observed result. If so,
        it stands as a regression guard rather than a red-phase assertion.
        """
        (self.repo / "docs" / "ge120_temp_bogus.md").write_text(
            _BOGUS_TYPE_DOC_FRONTMATTER, encoding="utf-8"
        )

        result = _run_deployed_hook(cwd=self.repo, filenames=["docs/ge120_temp_bogus.md"])

        self.assertNotEqual(
            result.returncode,
            0,
            msg=(
                "GE-120: expected the deployed hook to reject a doc with an "
                "undeclared `type` value, but it exited 0.\n\n"
                f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            ),
        )
        self.assertIn(
            "ge120-totally-undeclared-type",
            result.stdout + result.stderr,
            msg=(
                "GE-120: the rejection must NAME the offending type value, "
                "not just report a generic failure — otherwise a disabled "
                "check and a working one are indistinguishable.\n\n"
                f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
            ),
        )


# ---------------------------------------------------------------------------
# Test 4 — angle: boundary
# ---------------------------------------------------------------------------


class TestGe120UnreadableDeclaringFileFailsObservably(unittest.TestCase):
    """AC GE-120: an absent or malformed declaring file must fail observably,
    naming the file — never fall back silently to the built-in list."""

    def test_ge_120_unreadable_declaring_file_fails_observably(self) -> None:
        # covers: GE-120
        """Point the resolver at an absent and then at a malformed
        doc_types.json and assert each produces an observable failure naming
        the file — not a silent fallback to DOC_FM_ALLOWED_TYPES.

        FAILS TODAY: `_load_doc_types()` reaches
        `if _DOC_TYPES_JSON.exists():` before any exception can be raised for
        the absent-file case (so the `except (json.JSONDecodeError, OSError):
        pass` arm never runs), and for the malformed-file case it silently
        swallows the exception via a bare `pass`. Both cases return the
        7-entry fallback with no error surfaced anywhere.

        What must be implemented to make this green: raise (or otherwise
        surface, e.g. via a hard failure the caller cannot ignore) an
        observable error that names the declaring file path in both cases.
        """
        if not _DEPLOYED_DOC_TYPE_VALIDATORS.exists():
            self.skipTest(f"Deployed module not found: {_DEPLOYED_DOC_TYPE_VALIDATORS}")

        proc = _run_probe_script(_BOUNDARY_PROBE_SCRIPT, [str(_DEPLOYED_DIR)])
        self.assertEqual(
            proc.returncode,
            0,
            msg=(
                f"Probe script crashed unexpectedly.\n"
                f"stdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
            ),
        )
        payload = json.loads(proc.stdout)

        self.assertTrue(
            payload["absent_raised"],
            msg=(
                "GE-120 RED: an absent declaring file did not produce any "
                "observable failure — _load_doc_types() silently fell back "
                f"to the built-in list. Probed path: {payload['missing_path_str']}"
            ),
        )
        self.assertIn(
            payload["missing_path_str"],
            payload["absent_error"] or "",
            msg=(
                "GE-120: the failure for an absent declaring file must name "
                f"the file path ({payload['missing_path_str']}); got: "
                f"{payload['absent_error']!r}"
            ),
        )

        self.assertTrue(
            payload["malformed_raised"],
            msg=(
                "GE-120 RED: a malformed declaring file did not produce any "
                "observable failure — _load_doc_types() silently swallowed "
                f"the JSONDecodeError. Probed path: {payload['malformed_path_str']}"
            ),
        )
        self.assertIn(
            payload["malformed_path_str"],
            payload["malformed_error"] or "",
            msg=(
                "GE-120: the failure for a malformed declaring file must "
                f"name the file path ({payload['malformed_path_str']}); got: "
                f"{payload['malformed_error']!r}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
