"""
MODULE: unit_tests/commit_guardian/test_bp_100k_4_ii.py
COVERS: BP-100k-4-ii

GOAL: RED test stubs for the "could-ever versus does-now" reachability
    distinction. ``check_hook_trigger_reachability.py`` today treats a
    kind-based ``files`` condition (e.g. ``\\.py$``) that matches zero
    currently-tracked paths exactly like a condition naming a location no
    checkout could ever produce: both are reported ``UNREACHABLE`` and both
    block the commit. This is wrong for the kind-based case — a project that
    simply has not yet acquired a file of that kind is not the same thing as
    a gate that could never fire. See
    docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/
    BP-100k-4-ii.yaml.

BUSINESS CONTEXT: KI-CG-20260831-0713 — a fresh TypeScript consumer (no
    Python tracked) cannot make its first commit at all, because two
    registered Python-kind gates (``check-placeholder-defaults``,
    ``check-exception-handling``) are misclassified UNREACHABLE. Confirmed
    live against the real deployed registry (probed 2026-09-07): a synthetic
    consumer git repo tracking a single non-Python file reports
    ``UNREACHABLE: check-placeholder-defaults ... RESULT total=1
    unreachable=1`` and exits 1 today.

ARCHITECTURE / EXERCISE STRATEGY: per CLAUDE.md's "Gate / Workflow ACs —
    Verify Behaviorally, Not by Grep" and this AC's own ``test_rationale``
    ("The descriptors therefore execute the check as a process inside a
    built consumer layout"), every test below EXECUTES
    check_hook_trigger_reachability.py as a real subprocess against a real,
    freshly synthesized git repository — never a grep of the check's source
    or of commit_guardian.json's text.

    Two fixture styles are used, deliberately:
      - Tests 1, 2, 3, 4, 5, 6 use a fresh temp git repo + the SOURCE-tree
        copy of the check (``_REACHABILITY_HOOK_SRC``) + a synthetic
        HOOK_TEST_CONFIG registry (mirrors test_bp_100k_4_i.py's own
        convention). This is the right scope for these six: each pins one
        precise classification rule (kind-based nothing-to-match vs.
        genuinely-unreachable; verdict stability; audit output; the
        mutation-proof control) and a minimal, hand-controlled registry
        keeps the assertion about exactly the rule under test, not about
        the ~90-gate real registry's own (separately-tracked, out-of-scope)
        population of un-exempted location-anchored conditions.
      - Test 7 (the mandatory reachability-angle descriptor) instead builds
        a REAL, freshly ``build.py``-deployed consumer layout and runs the
        REAL deployed ``check_hook_trigger_reachability.py`` against the
        REAL deployed ``commit_guardian.json`` — this is the literal "run
        as a process from a BUILT CONSUMER LAYOUT" entry point this AC's
        Test Requirements block declares, and the only way to observe the
        fix against the actual shipped registry rather than a hand-picked
        stand-in.

    SCOPE NOTE on "no file of any kind any registered condition selects"
    (AC-6/7): the REAL, ~90-gate commit_guardian.json also carries many
    LOCATION-anchored conditions (``^docs/.*\\.md$``, ``^tickets/.*\\.md$``,
    etc.) that are not exempted today because this package repository
    itself has docs/tickets tracked. Those are explicitly OUT OF this AC's
    scope (the Gherkin's own qualifier: "on the ground that the project has
    not yet acquired the KIND of file it watches for" — location-anchored
    conditions are a different, pre-existing, separately-governed
    classification this ticket's constraints explicitly forbid touching:
    "This constraint supplies the missing distinction; it does not
    overturn the parent."). Test 3 therefore uses a synthetic
    ALL-KIND-BASED registry to construct the literal "no file of any kind
    any registered condition selects" project the Gherkin describes; test 7
    instead probes the REAL registry but asserts only on the two
    Python-kind gates the AC's own ``notes`` field names, not on the whole
    run's exit code.

    MUTATION-PROOF CONTRACT (test 6): this test file requires the fix to be
    disableable via a test-only environment variable,
    ``HOOK_TRIGGER_DISABLE_KIND_DISTINCTION=1`` — mirroring the existing
    ``HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS`` test-only-override convention
    already established in _hook_trigger_reachability_helpers.py. When set,
    the check MUST behave exactly as it does today (pre-fix): a kind-based
    condition matching zero tracked paths is reported UNREACHABLE and blocks
    the run. This is the load-bearing check the AC's own test_rationale
    calls out: "without it, an implementation that simply never reports
    anything would satisfy every other assertion."

    NEW OUTPUT CONTRACT this file pins down (required for tests 1, 2, 4, 5,
    7 to be satisfiable):
      - A kind-based ``files`` condition (no location/path-segment anchor —
        e.g. ``\\.py$``, ``.*\\.(md|py|sql)$``) that matches zero tracked
        paths is classified NEITHER unreachable NOR exempt. It is reported
        on its own diagnostic line: ``NOTHING-TO-MATCH: <id>
        reason=<text>``, and does NOT block the run.
      - The RESULT summary line gains a fourth counter, appended after
        ``exempt``: ``RESULT total=<n> unreachable=<n> exempt=<n>
        nothing_to_match=<n>``.
      - A condition that is NOT kind-based-only (has a location anchor) is
        UNCHANGED by this AC — it keeps today's exempt/unreachable
        classification untouched.

RED BASELINE (captured 2026-09-07, against the real, unmodified deployed
    check, before any production-code change for this AC): a synthetic
    consumer git repo tracking a single non-Python file, evaluated against
    a registry containing only ``{"id": "check-placeholder-defaults",
    "files": "\\.py$"}``, reports::

        UNREACHABLE: check-placeholder-defaults reason=files pattern
        '\\.py$' matches none of the 1 path(s) this repository tracks
        check-hook-trigger-reachability: RESULT total=1 unreachable=1 exempt=0

    and exits 1 — every test below that asserts the opposite (not
    unreachable, exit 0, a NOTHING-TO-MATCH line, a stable verdict across
    file census, restoring the blocker under the disable flag) is RED today
    for that reason: the could-ever/does-now distinction does not exist yet.

H-1 REVIEW-FINDING COVERAGE (tests 8, 9, 10, added 2026-09-07): a
    high-confidence review found that ``has_location_anchor``'s could-ever/
    does-now heuristic ran BEFORE the exemption registry was consulted, so
    two real, audited exemption entries whose pattern carries no leading
    ``^`` — ``check-doc-types-agents`` and ``check-hook-parity`` — were
    silently reclassified NOTHING-TO-MATCH and their human-authored
    ``ground`` was never read. Fixed by reordering ``evaluate_gate`` to
    consult the exemption registry first. Tests 8-10 pin that fix down:
    test 8 uses the two real ids and their REAL patterns/ground (loaded at
    run time from the real commit_guardian.json, never hand-copied); test 9
    is the fail-closed pairing (an exempted location-based pattern stays
    EXEMPT, an un-exempted one stays UNREACHABLE) that proves the reorder
    is not a blanket pass; test 10 is a registry-driven regression guard —
    it enumerates every id in the real exemption registry AT RUN TIME
    (never a hardcoded list of today's 8 ids, which is exactly the kind of
    assumption that went stale here) and asserts each one is EXEMPT when
    its real pattern matches nothing.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_REACHABILITY_HOOK_SRC = _CG_TEMPLATES_SRC / "check_hook_trigger_reachability.py"
_SYNTHETIC_PACKAGE_HELPER_PATH = _REPO_ROOT / "unit_tests" / "build_guards" / "test_bp_100k_2.py"

_SUBPROCESS_TIMEOUT_SECONDS = 20
_BUILD_TIMEOUT_SECONDS = 180

_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\s+total=(\d+)\s+unreachable=(\d+)"
    r"\s+exempt=(\d+)(?:\s+nothing_to_match=(\d+))?",
    re.IGNORECASE,
)
_UNREACHABLE_LINE_RE = re.compile(r"UNREACHABLE:\s*(\S+)")
_NOTHING_TO_MATCH_LINE_RE = re.compile(r"NOTHING-TO-MATCH:\s*(\S+)")
# Captures (id, ground) pairs from "EXEMPT: <id> ground=<text>" lines. Used
# by the H-1 regression tests (8, 9, 10) to check BOTH that a gate was
# classified EXEMPT and that its real ground text was actually reported.
_EXEMPT_LINE_RE = re.compile(r"EXEMPT:\s*(\S+)\s+ground=(.*)")

# Test-only environment override this file's mutation-proof test (test 6)
# requires the fix to honor: forces the pre-fix (kind-based == unreachable)
# behavior so the test can prove its own assertions are capable of failing.
# See this module's docstring, "MUTATION-PROOF CONTRACT".
_DISABLE_DISTINCTION_ENV_VAR = "HOOK_TRIGGER_DISABLE_KIND_DISTINCTION"


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_4_i.py; duplicated per house
# convention of self-contained sibling test files)
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Run a git subcommand against *cwd* and return the completed process.

    Args:
        args: Git subcommand and its arguments (without the leading "git").
        cwd: Working directory to run git in.

    Returns:
        The completed subprocess result (never raises on non-zero exit).
    """
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _init_repo(repo: Path) -> None:
    """Initialize a fresh, minimally-configured git repo at *repo*.

    Args:
        repo: Directory to initialize as a git repository (created if absent).
    """
    repo.mkdir(parents=True, exist_ok=True)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "bp100k4iitest@example.com"], repo)
    _git(["config", "user.name", "BP-100k-4-ii Test"], repo)


def _add_and_commit(repo: Path, paths: list[str], message: str) -> None:
    """Stage exactly *paths* (never ``-A``) and commit them.

    Staging an explicit path list — rather than ``git add -A`` — is what
    lets these fixtures build a consumer repo that tracks precisely the
    files a scenario needs and nothing else (in particular: no Python file
    at all), which is the entire point under test.

    Args:
        repo: Git repository root.
        paths: Repo-root-relative paths to stage.
        message: Commit message.
    """
    _git(["add", *paths], repo)
    _git(["commit", "-m", message], repo)


def _write_registry_config(entries: list[dict]) -> str:
    """Write a HOOK_TEST_CONFIG-shaped registry override via the real JSON
    serializer (never a hand-typed literal, per the Fixture Authenticity
    Rule).

    Args:
        entries: The ``hooks_manifest.hooks`` list to embed.

    Returns:
        Absolute path to the temp JSON file written.
    """
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"hooks_manifest": {"hooks": entries}}, f)
    return path


def _run_reachability_hook(
    hook_path: Path,
    cwd: Path,
    hook_test_config_path: str | None = None,
    extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess:
    """Execute a check_hook_trigger_reachability.py copy as a subprocess.

    Args:
        hook_path: Absolute path to the script to execute (source-tree copy
            or a real deployed copy, depending on the test).
        cwd: Working directory for the subprocess.
        hook_test_config_path: Optional path to a HOOK_TEST_CONFIG override
            JSON file. When None, the real registry fallback chain (rooted
            at ``cwd``) is exercised instead.
        extra_env: Optional additional environment variables layered on top
            of the current process environment.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    env = os.environ.copy()
    if hook_test_config_path is not None:
        env["HOOK_TEST_CONFIG"] = hook_test_config_path
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        [sys.executable, str(hook_path)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _load_build_synthetic_full_package():
    """Load ``_build_synthetic_full_package`` from test_bp_100k_2.py.

    Loaded read-only via ``importlib`` under a private module name so this
    file never duplicates the copy-the-real-templates logic and never
    collides with pytest's own collection of test_bp_100k_2.py (mirrors the
    identical helper already used by test_bp_100k_5_i.py / test_bp_100k_5.py).

    Returns:
        The ``_build_synthetic_full_package(workspace: Path) -> Path``
        function object from that module.
    """
    spec = importlib.util.spec_from_file_location(
        "_bp100k4ii_synthetic_package_helper", _SYNTHETIC_PACKAGE_HELPER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module._build_synthetic_full_package


_REAL_REGISTRY_PATH = _CG_TEMPLATES_SRC / "commit_guardian.json"


def _load_real_registry() -> dict:
    """Load the real, source-tree ``commit_guardian.json`` registry.

    Used by the H-1 regression tests (8, 9, 10) so their real-id patterns
    and ground text are read at run time from the actual manifest — never
    hand-copied into a string literal here, which is exactly the kind of
    drift-prone duplication that let ``has_location_anchor``'s "every
    location-anchored condition carries a ``^``" docstring claim go stale.

    Returns:
        The parsed registry dict.
    """
    with open(_REAL_REGISTRY_PATH, encoding="utf-8") as f:
        return json.load(f)


def _real_hooks_manifest_hooks(registry: dict) -> list[dict]:
    """Return the real ``hooks_manifest.hooks`` list from a loaded registry.

    Args:
        registry: A registry dict as returned by ``_load_real_registry``.

    Returns:
        The list of hooks_manifest entries.
    """
    return registry["hooks_manifest"]["hooks"]


def _real_exemption_entries(registry: dict) -> list[dict]:
    """Return the real ``hook_trigger_reachability_exemption_registry`` list.

    Args:
        registry: A registry dict as returned by ``_load_real_registry``.

    Returns:
        The list of ``{"id": ..., "ground": ...}`` exemption entries.
    """
    return registry["hook_trigger_reachability_exemption_registry"]


def _find_hook_entry(hooks: list[dict], gate_id: str) -> dict:
    """Find one ``hooks_manifest`` entry by id, failing loudly if absent.

    Args:
        hooks: The ``hooks_manifest.hooks`` list to search.
        gate_id: The id to find.

    Returns:
        The matching entry dict.

    Raises:
        AssertionError: If no entry with that id exists — a setup bug
            meaning the real registry no longer defines an id this test
            depends on.
    """
    for entry in hooks:
        if isinstance(entry, dict) and entry.get("id") == gate_id:
            return entry
    raise AssertionError(
        "setup bug: real commit_guardian.json no longer defines a "
        f"hooks_manifest entry with id {gate_id!r}"
    )


def _build_consumer_layout_tracking_no_python(workspace: Path) -> Path:
    """Build a real, freshly ``build.py``-deployed consumer layout whose git
    history tracks exactly one placeholder file — no Python, no Markdown
    under docs/, nothing else the deployed registry's kind- or
    location-based conditions could match.

    Args:
        workspace: Temp directory to build the layout inside.

    Returns:
        Absolute path to the workspace root (also the git repo root).

    Raises:
        AssertionError (via the caller's setUp) if the build itself fails —
        callers are expected to check ``returncode`` before trusting the
        deployed tree.
    """
    build_synthetic_full_package = _load_build_synthetic_full_package()
    pkg_root = build_synthetic_full_package(workspace)
    build_script = pkg_root / "scripts" / "build.py"

    build_result = subprocess.run(
        [sys.executable, str(build_script), "--target-dir", str(workspace)],
        cwd=str(workspace),
        capture_output=True,
        text=True,
        timeout=_BUILD_TIMEOUT_SECONDS,
        check=False,
    )
    if build_result.returncode != 0:
        raise AssertionError(
            "setup bug: real build.py --target-dir failed against an "
            f"isolated synthetic package copy. stdout:\n{build_result.stdout}\n"
            f"stderr:\n{build_result.stderr}"
        )

    _init_repo(workspace)
    placeholder = workspace / "CONSUMER-NOTES.txt"
    placeholder.write_text(
        "Placeholder consumer-project file. Deliberately the ONLY file "
        "tracked by this repo's git history: everything build.py deployed "
        "(leafcutter-ai/, scripts/, docs/, .claude/, .leafcutter/, "
        "tickets/, unit_tests/) is left untracked on purpose, so this "
        "consumer tracks zero Python and zero docs/tickets Markdown.\n",
        encoding="utf-8",
    )
    _add_and_commit(workspace, ["CONSUMER-NOTES.txt"], "chore: seed bare consumer project")
    return workspace


# ---------------------------------------------------------------------------
# test_spec 1: a kind-based condition matching nothing yet does not block.
# ---------------------------------------------------------------------------


class TestKindBasedConditionMatchingNothingYetDoesNotBlockTheCommit(unittest.TestCase):
    """A files condition that selects by kind (pure extension, no location
    anchor) and matches zero currently-tracked paths must not be reported
    unreachable, and must not fail the run."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        self.config_path = _write_registry_config(
            [{"id": "check-placeholder-defaults", "files": "\\.py$", "pass_filenames": False}]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_kind_based_condition_matching_nothing_yet_does_not_block_the_commit(
        self,
    ) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A kind-based condition matching zero tracked paths must "
                f"not block the commit. Output:\n{combined}"
            ),
        )
        unreachable_ids = set(_UNREACHABLE_LINE_RE.findall(combined))
        self.assertNotIn(
            "check-placeholder-defaults",
            unreachable_ids,
            msg=(
                "A kind-based condition (no file of that kind tracked yet) "
                f"was wrongly reported UNREACHABLE. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 2: a genuinely structural misconfiguration still blocks, in the
# same run as a kind-based nothing-to-match gate.
# ---------------------------------------------------------------------------


class TestStructurallyUnreachableConditionStillBlocksInTheSameRun(unittest.TestCase):
    """Narrowing what counts as unreachable for kind-based conditions must
    not weaken the verdict for a gate that is genuinely, structurally
    unreachable — evaluated together in ONE run."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        self.config_path = _write_registry_config(
            [
                {
                    "id": "check-placeholder-defaults",
                    "files": "\\.py$",
                    "pass_filenames": False,
                },
                {
                    # A whole-tree gate (always_run: true) that ALSO carries
                    # a files filter it never consults — the existing,
                    # already-established "always a real authoring
                    # mistake" shape (see check_hook_trigger_reachability.py
                    # module docstring): a location this project's own
                    # activation mechanism could NEVER honor, regardless of
                    # what the checkout tracks. Genuinely, structurally
                    # unreachable — not merely "nothing to match yet".
                    "id": "structurally-broken-gate",
                    "always_run": True,
                    "files": "^this-filter-is-never-consulted/",
                    "pass_filenames": False,
                },
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_structurally_unreachable_condition_still_blocks_in_the_same_run(
        self,
    ) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A structurally unreachable gate in the same run must "
                f"still fail the run. Output:\n{combined}"
            ),
        )
        unreachable_ids = set(_UNREACHABLE_LINE_RE.findall(combined))
        self.assertIn(
            "structurally-broken-gate",
            unreachable_ids,
            msg=(
                "The genuinely unreachable gate must still be named "
                f"UNREACHABLE in the same run. Output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "check-placeholder-defaults",
            unreachable_ids,
            msg=(
                "The kind-based nothing-to-match gate must not be swept "
                "into UNREACHABLE just because a DIFFERENT gate in the "
                f"same run genuinely is. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 3: a first commit succeeds when nothing any registered
# (kind-based) condition selects is tracked.
# ---------------------------------------------------------------------------


class TestAFirstCommitSucceedsInAProjectHoldingNoWatchedFileKind(unittest.TestCase):
    """A project tracking no file of any kind any registered condition
    selects must be able to make its first commit — no registered gate may
    be reported unreachable on the ground that the kind of file it watches
    for has not been acquired yet."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        # Every condition here is PURELY kind-based (no location anchor) —
        # this is the synthetic stand-in for "a project that holds no file
        # of any kind that any registered condition selects" (see this
        # module's docstring, SCOPE NOTE, for why the real ~90-gate
        # registry's separately-governed location-anchored conditions are
        # out of scope for this specific descriptor).
        self.config_path = _write_registry_config(
            [
                {"id": "check-placeholder-defaults", "files": "\\.py$", "pass_filenames": False},
                {"id": "check-exception-handling", "files": "\\.py$", "pass_filenames": False},
                {
                    "id": "check-glossary-coverage",
                    "files": ".*\\.(md|py|sql)$",
                    "pass_filenames": False,
                },
                {"id": "ensure-precommit-config", "always_run": True, "pass_filenames": False},
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_a_first_commit_succeeds_in_a_project_holding_no_watched_file_kind(
        self,
    ) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertEqual(
            0,
            result.returncode,
            msg=(
                "A first commit in a project tracking no file of any kind "
                "any registered condition selects must complete (exit 0), "
                f"not be blocked by kind-based nothing-to-match gates. "
                f"Output:\n{combined}"
            ),
        )
        self.assertNotIn("UNREACHABLE:", combined, msg=f"Output:\n{combined}")


# ---------------------------------------------------------------------------
# test_spec 4: the verdict does not move with the file census of the day.
# ---------------------------------------------------------------------------


class TestTheVerdictDoesNotChangeWithTheFileCensus(unittest.TestCase):
    """The same registry, evaluated once in a project holding no file of
    the selected kind and once in a project that does, must yield the same
    non-blocking verdict for that gate — reachability is drawn from what a
    checkout could produce, not from today's tracked-path snapshot."""

    def setUp(self) -> None:
        self.config_path = _write_registry_config(
            [{"id": "check-placeholder-defaults", "files": "\\.py$", "pass_filenames": False}]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_the_verdict_does_not_change_with_the_file_census(self) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        with tempfile.TemporaryDirectory() as tmp_without:
            repo_without_py = Path(tmp_without)
            _init_repo(repo_without_py)
            (repo_without_py / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
            _add_and_commit(repo_without_py, ["NOTES.txt"], "chore: no python tracked")
            result_without = _run_reachability_hook(
                _REACHABILITY_HOOK_SRC, repo_without_py, self.config_path
            )

        with tempfile.TemporaryDirectory() as tmp_with:
            repo_with_py = Path(tmp_with)
            _init_repo(repo_with_py)
            (repo_with_py / "app.py").write_text("x = 1\n", encoding="utf-8")
            _add_and_commit(repo_with_py, ["app.py"], "chore: python tracked")
            result_with = _run_reachability_hook(
                _REACHABILITY_HOOK_SRC, repo_with_py, self.config_path
            )

        combined_without = result_without.stdout + result_without.stderr
        combined_with = result_with.stdout + result_with.stderr

        self.assertEqual(
            0,
            result_without.returncode,
            msg=f"No-python-tracked run must exit 0. Output:\n{combined_without}",
        )
        self.assertEqual(
            0,
            result_with.returncode,
            msg=f"Python-tracked run must exit 0. Output:\n{combined_with}",
        )
        self.assertNotIn(
            "check-placeholder-defaults",
            set(_UNREACHABLE_LINE_RE.findall(combined_without)),
            msg=(
                "The gate must not be UNREACHABLE when no .py is tracked "
                f"yet. Output:\n{combined_without}"
            ),
        )
        self.assertNotIn(
            "check-placeholder-defaults",
            set(_UNREACHABLE_LINE_RE.findall(combined_with)),
            msg=(
                "The SAME gate must also not be UNREACHABLE once a .py "
                f"file is tracked (it is a real match there). "
                f"Output:\n{combined_with}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 5: the nothing-to-match classification is stated in the output.
# ---------------------------------------------------------------------------


class TestTheNothingToMatchClassificationIsStatedInTheOutput(unittest.TestCase):
    """The run must name, by id, every gate it reclassified as having
    nothing to match — so the reclassification is auditable and cannot be
    confused with a gate that was never evaluated at all."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        self.config_path = _write_registry_config(
            [{"id": "check-placeholder-defaults", "files": "\\.py$", "pass_filenames": False}]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_the_nothing_to_match_classification_is_stated_in_the_output(self) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        nothing_to_match_ids = set(_NOTHING_TO_MATCH_LINE_RE.findall(combined))
        self.assertIn(
            "check-placeholder-defaults",
            nothing_to_match_ids,
            msg=(
                "The run must name the kind-based, zero-match gate under "
                "its own auditable classification (NOTHING-TO-MATCH: "
                f"<id>), not merely omit it from UNREACHABLE. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match, msg=f"No RESULT summary line was emitted. Output:\n{combined}"
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertIsNotNone(
            match.group(4),
            msg=(
                "The RESULT summary line must carry a nothing_to_match=<n> "
                f"counter alongside total/unreachable/exempt. Output:\n{combined}"
            ),
        )
        self.assertEqual(
            "1",
            match.group(4),
            msg=f"Expected exactly one nothing-to-match gate. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# test_spec 6 (mutation-proof, load-bearing per this AC's test_rationale):
# removing the distinction restores the blocker.
# ---------------------------------------------------------------------------


class TestRemovingTheDistinctionRestoresTheBlocker(unittest.TestCase):
    """With the could-ever/does-now distinction disabled (test-only
    HOOK_TRIGGER_DISABLE_KIND_DISTINCTION=1 — see this module's docstring,
    MUTATION-PROOF CONTRACT), the exact no-file-kind consumer scenario from
    test 1 must fail again. Without this test, an implementation that
    simply never reports anything would satisfy every other assertion in
    this file."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        self.config_path = _write_registry_config(
            [{"id": "check-placeholder-defaults", "files": "\\.py$", "pass_filenames": False}]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_removing_the_distinction_restores_the_blocker(self) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        fixed_result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        fixed_combined = fixed_result.stdout + fixed_result.stderr
        self.assertEqual(
            0,
            fixed_result.returncode,
            msg=(
                "Precondition for this mutation proof: WITHOUT the disable "
                "flag, the fix must be in effect and the commit must "
                f"succeed (this is test 1's own assertion). Output:\n{fixed_combined}"
            ),
        )

        mutated_result = _run_reachability_hook(
            _REACHABILITY_HOOK_SRC,
            self.repo,
            self.config_path,
            extra_env={_DISABLE_DISTINCTION_ENV_VAR: "1"},
        )
        mutated_combined = mutated_result.stdout + mutated_result.stderr

        self.assertNotEqual(
            0,
            mutated_result.returncode,
            msg=(
                "With the could-ever/does-now distinction disabled, the "
                "exact same no-file-kind scenario that passed above must "
                f"fail again (the blocker is restored). Output:\n{mutated_combined}"
            ),
        )
        self.assertIn(
            "check-placeholder-defaults",
            set(_UNREACHABLE_LINE_RE.findall(mutated_combined)),
            msg=(
                "Disabling the distinction must restore the pre-fix "
                f"UNREACHABLE classification. Output:\n{mutated_combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 7 (mandatory reachability angle): the real, deployed entry
# point, run from a built consumer layout, exhibits the fix for real.
# ---------------------------------------------------------------------------


class TestBp100k4iiReachableFromEntryPoint(unittest.TestCase):
    """REQUIRED reachability descriptor. Builds a REAL consumer layout via
    a real ``scripts/build.py --target-dir`` subprocess, then runs the REAL
    deployed ``scripts/commit_guardian/check_hook_trigger_reachability.py``
    against the REAL deployed ``commit_guardian.json`` with cwd inside that
    consumer, whose git history tracks zero Python files. This is the
    entry point named directly in this AC's own Test Requirements block —
    not a source-tree run, and not an import of any function."""

    _workspace: Path
    _hook: Path

    @classmethod
    def setUpClass(cls) -> None:
        tmpdir = tempfile.TemporaryDirectory()
        cls.addClassCleanup(tmpdir.cleanup)
        cls._workspace = Path(tmpdir.name)
        _build_consumer_layout_tracking_no_python(cls._workspace)
        cls._hook = cls._workspace / "scripts" / "commit_guardian" / "check_hook_trigger_reachability.py"

    def setUp(self) -> None:
        if not self._hook.is_file():
            self.fail(f"setup bug: deployed hook not found at {self._hook}")
        tracked = _git(["ls-files"], self._workspace).stdout.splitlines()
        py_tracked = [p for p in tracked if p.endswith(".py")]
        self.assertEqual(
            [],
            py_tracked,
            msg=(
                "setup bug: this consumer layout fixture must track zero "
                f"Python files (found: {py_tracked}) — otherwise the "
                "defect this AC exists to fix is not observable, exactly "
                "as this AC's own business context warns."
            ),
        )

    def test_bp_100k_4_ii_reachable_from_entry_point(self) -> None:
        # covers: BP-100k-4-ii
        # angle: reachability
        result = subprocess.run(
            [sys.executable, str(self._hook)],
            cwd=str(self._workspace),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        combined = result.stdout + result.stderr

        unreachable_ids = set(_UNREACHABLE_LINE_RE.findall(combined))
        for python_kind_gate_id in ("check-placeholder-defaults", "check-exception-handling"):
            self.assertNotIn(
                python_kind_gate_id,
                unreachable_ids,
                msg=(
                    f"Real deployed entry point: {python_kind_gate_id} is a "
                    "pure Python-kind condition and this consumer tracks "
                    "no Python — it must not be reported UNREACHABLE. "
                    f"Output:\n{combined}"
                ),
            )

        nothing_to_match_ids = set(_NOTHING_TO_MATCH_LINE_RE.findall(combined))
        self.assertTrue(
            {"check-placeholder-defaults", "check-exception-handling"} & nothing_to_match_ids,
            msg=(
                "The real deployed run must actually exercise the new "
                "classification for at least one of the two named "
                f"Python-kind gates (auditable, not merely silent). Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 8 (H-1 review finding): the two real, audited exemption-registry
# entries whose pattern carries no location anchor are classified EXEMPT —
# with their real ground text reported — never NOTHING-TO-MATCH.
# ---------------------------------------------------------------------------


class TestRealAuditedExemptionEntriesAreHonoredBeforeKindClassification(unittest.TestCase):
    """H-1 regression test. ``check-doc-types-agents`` and
    ``check-hook-parity`` are real, audited exemption-registry entries whose
    ``files`` patterns carry no leading ``^`` — ``has_location_anchor``
    alone would misclassify both as kind-based. ``evaluate_gate`` must
    consult the exemption registry BEFORE that heuristic, so both are
    reported EXEMPT with their real ground text, never NOTHING-TO-MATCH."""

    _GATE_IDS = ("check-doc-types-agents", "check-hook-parity")

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        registry = _load_real_registry()
        real_hooks = _real_hooks_manifest_hooks(registry)
        real_exemption_entries = _real_exemption_entries(registry)
        entries_under_test = [_find_hook_entry(real_hooks, gid) for gid in self._GATE_IDS]
        self.grounds_by_id = {
            entry["id"]: entry["ground"]
            for entry in real_exemption_entries
            if entry.get("id") in self._GATE_IDS
        }
        self.assertEqual(
            set(self._GATE_IDS),
            set(self.grounds_by_id),
            msg=(
                "setup bug: the real exemption registry no longer carries "
                "a ground for both ids this test depends on"
            ),
        )

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "hooks_manifest": {"hooks": entries_under_test},
                    "hook_trigger_reachability_exemption_registry": real_exemption_entries,
                },
                f,
            )
        self.config_path = path
        self.addCleanup(os.unlink, self.config_path)

    def test_real_audited_exemption_entries_are_honored_before_kind_classification(
        self,
    ) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        exempt_pairs = dict(_EXEMPT_LINE_RE.findall(combined))
        nothing_to_match_ids = set(_NOTHING_TO_MATCH_LINE_RE.findall(combined))

        for gate_id in self._GATE_IDS:
            self.assertIn(
                gate_id,
                exempt_pairs,
                msg=(
                    f"{gate_id} carries a real, audited exemption ground "
                    "and has no location anchor in its real pattern — it "
                    "must be classified EXEMPT (the registry consulted "
                    "before the kind-based check), never left "
                    f"unclassified. Output:\n{combined}"
                ),
            )
            self.assertEqual(
                self.grounds_by_id[gate_id].strip(),
                exempt_pairs.get(gate_id, "").strip(),
                msg=(
                    f"{gate_id}'s real ground text must appear verbatim in "
                    f"its EXEMPT line's ground= text. Output:\n{combined}"
                ),
            )
            self.assertNotIn(
                gate_id,
                nothing_to_match_ids,
                msg=(
                    f"{gate_id} has an audited exemption ground; the "
                    "exemption registry must be consulted BEFORE the "
                    "kind-based check, so it must never be reported "
                    f"NOTHING-TO-MATCH. Output:\n{combined}"
                ),
            )


# ---------------------------------------------------------------------------
# test_spec 9 (H-1 review finding, fail-closed property): consulting the
# exemption registry first must not turn every zero-match gate into a pass.
# ---------------------------------------------------------------------------


class TestFailClosedPropertyHoldsUnderTheNewOrdering(unittest.TestCase):
    """A location-based pattern WITH a stated exemption ground stays EXEMPT
    even when it matches nothing; a location-based pattern with NO
    exemption entry that nothing could ever match is still UNREACHABLE and
    the run still exits non-zero. Together these stop the H-1 ordering fix
    from becoming a blanket pass."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "hooks_manifest": {
                        "hooks": [
                            {
                                "id": "fake-location-exempt-gate",
                                "files": "^this/exact/path/never/exists\\.json$",
                                "pass_filenames": False,
                            },
                            {
                                "id": "fake-location-unreachable-gate",
                                "files": "^another/exact/path/never/exists\\.json$",
                                "pass_filenames": False,
                            },
                        ]
                    },
                    "hook_trigger_reachability_exemption_registry": [
                        {
                            "id": "fake-location-exempt-gate",
                            "ground": (
                                "test-only ground: this location-based "
                                "pattern is audited as context-dependent"
                            ),
                        }
                    ],
                },
                f,
            )
        self.config_path = path
        self.addCleanup(os.unlink, self.config_path)

    def test_fail_closed_property_holds_under_the_new_ordering(self) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A location-based gate with no exemption entry that "
                "nothing could ever match must still block the run. "
                f"Output:\n{combined}"
            ),
        )
        exempt_ids = {gate_id for gate_id, _ in _EXEMPT_LINE_RE.findall(combined)}
        unreachable_ids = set(_UNREACHABLE_LINE_RE.findall(combined))

        self.assertIn(
            "fake-location-exempt-gate",
            exempt_ids,
            msg=(
                "A location-based pattern carrying an exemption ground "
                f"must stay EXEMPT even though it matches nothing. "
                f"Output:\n{combined}"
            ),
        )
        self.assertIn(
            "fake-location-unreachable-gate",
            unreachable_ids,
            msg=(
                "A location-based pattern with NO exemption entry, "
                f"matching nothing, must still be UNREACHABLE. "
                f"Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 10 (H-1 review finding, regression guard): every id in the REAL
# hook_trigger_reachability_exemption_registry is classified EXEMPT when its
# real pattern matches nothing — driven from the registry itself at run
# time, never from a hardcoded list of today's 8 ids.
# ---------------------------------------------------------------------------


class TestEveryRealExemptionRegistryEntryStaysExemptOnZeroMatch(unittest.TestCase):
    """Regression guard for H-1. Loads the real exemption registry AND the
    real ``hooks_manifest.hooks`` pattern for every id it names, at run
    time, and asserts every one of them is classified EXEMPT (never
    NOTHING-TO-MATCH, never UNREACHABLE) in a repo tracking none of their
    targets. A hardcoded list of ids would go stale exactly the way
    ``has_location_anchor``'s '^' assumption did — this test cannot narrow
    back to that shape, because it enumerates the registry's own ids at
    run time and fails loudly (floor assertion) if the registry is ever
    empty."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "NOTES.txt").write_text("placeholder\n", encoding="utf-8")
        _add_and_commit(self.repo, ["NOTES.txt"], "chore: seed bare consumer repo")

        registry = _load_real_registry()
        real_hooks = _real_hooks_manifest_hooks(registry)
        exemption_entries = _real_exemption_entries(registry)
        self.exemption_ids = [entry["id"] for entry in exemption_entries]
        self.assertGreater(
            len(self.exemption_ids),
            0,
            msg=(
                "setup bug / vacuous-test guard: the real "
                "hook_trigger_reachability_exemption_registry is empty — "
                "this test would trivially pass over zero entries"
            ),
        )
        entries_under_test = [_find_hook_entry(real_hooks, gid) for gid in self.exemption_ids]

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "hooks_manifest": {"hooks": entries_under_test},
                    "hook_trigger_reachability_exemption_registry": exemption_entries,
                },
                f,
            )
        self.config_path = path
        self.addCleanup(os.unlink, self.config_path)

    def test_every_real_exemption_registry_entry_stays_exempt_on_zero_match(
        self,
    ) -> None:
        # covers: BP-100k-4-ii
        # angle: criterion
        result = _run_reachability_hook(_REACHABILITY_HOOK_SRC, self.repo, self.config_path)
        combined = result.stdout + result.stderr

        exempt_ids = {gate_id for gate_id, _ in _EXEMPT_LINE_RE.findall(combined)}
        nothing_to_match_ids = set(_NOTHING_TO_MATCH_LINE_RE.findall(combined))
        unreachable_ids = set(_UNREACHABLE_LINE_RE.findall(combined))

        for gate_id in self.exemption_ids:
            self.assertIn(
                gate_id,
                exempt_ids,
                msg=(
                    f"{gate_id} carries a real exemption ground and its "
                    "real pattern matches nothing this bare repo tracks — "
                    f"it must be classified EXEMPT. Output:\n{combined}"
                ),
            )
            self.assertNotIn(
                gate_id,
                nothing_to_match_ids,
                msg=f"{gate_id} must never be NOTHING-TO-MATCH. Output:\n{combined}",
            )
            self.assertNotIn(
                gate_id,
                unreachable_ids,
                msg=f"{gate_id} must never be UNREACHABLE. Output:\n{combined}",
            )


if __name__ == "__main__":
    unittest.main()
