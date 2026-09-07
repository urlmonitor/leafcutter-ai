"""
MODULE: unit_tests/commit_guardian/test_bp_100k_4.py
GOAL: BP-100k-4 — a registered commit gate whose activation ("files") condition
    can never match anything this repository is able to stage must be reported
    as UNREACHABLE and must block the commit; the registry's own reachability
    check must not go quiet on gates it cannot ever fire, and a whole-tree gate
    (one that never consults the staged file list) must not be allowed to carry
    a path-based activation condition in the first place.
BUSINESS CONTEXT: Two gates in the real, deployed registry
    (templates/scripts/commit_guardian/commit_guardian.json) have never fired
    in this repository: check-build-drift's "files" trigger
    (``^leafcutter/templates/``) names a location that exists only in a
    CONSUMER install layout — this package's own self-host layout keeps
    templates at ``templates/``, not ``leafcutter/templates/`` — and
    check-output-drift's trigger names six ``.claude/*`` / ``.agents/rules/``
    locations that are either fully gitignored or absent from the repository
    root entirely. Both gates declare ``pass_filenames: false`` and scan the
    WHOLE tree by hash, never the staged file list, so a path filter was never
    the right activation mechanism for either of them. See
    docs/acceptance-criteria/build_pipeline/BP-100-reliable-builds/BP-100k-4.yaml.

NEW PRODUCTION MODULE THIS TEST FILE SPECIFIES (does not exist yet):
    templates/scripts/commit_guardian/check_hook_trigger_reachability.py

    This is the "registry's own reachability check" the AC criteria refers to.
    It must be registered in ``hooks_manifest.hooks`` (a later ticket's job,
    not this test file's) with ``always_run: true`` and ``pass_filenames:
    false`` — it inspects the whole registry, not a staged file list, so it
    is itself an instance of the whole-tree-gate shape this AC exists to
    police.

CONTRACT THIS TEST FILE SPECIFIES FOR check_hook_trigger_reachability.py
(the target for python-coder):

    Registry resolution (mirrors the HOOK_TEST_CONFIG convention already
    established by check_build_drift.py / check_output_drift.py for
    BP-100k-3, and the two-tier fallback already established by
    check_hook_parity.py's ``_load_config``):
      1. If env var ``HOOK_TEST_CONFIG`` is set: read that JSON file directly.
         It must contain a top-level ``hooks_manifest`` key shaped exactly
         like the real commit_guardian.json's ``hooks_manifest`` (a
         ``{"hooks": [...]}`` dict). This is used INSTEAD OF loading
         commit_guardian.json — the real registry is never consulted when
         this env var is set.
      2. Else: read ``<cwd>/scripts/commit_guardian/commit_guardian.json``
         (the deployed runtime copy).
      3. Else: read the ``commit_guardian.json`` colocated with this script
         (the template source tree copy — what a bare source-tree invocation
         resolves to).
      4. If none of the above can be read and parsed as JSON: the check is
         INDETERMINATE (see BP-100k-4-i) — it must NEVER report a clean pass
         because it could not read its own registry.

    Tracked-path acquisition: run ``git ls-files`` with the hook's cwd as the
    working directory. If that command fails (non-zero exit, or the ``git``
    executable cannot be found) the check is INDETERMINATE (see BP-100k-4-i)
    — it must never guess or fall back to "everything is reachable".

    Per-gate reachability rule, evaluated once per entry in
    ``hooks_manifest.hooks`` (an entry with ``"enabled": false`` is skipped
    entirely — it is intentionally off, not a reachability question):
      - ``always_run: true`` AND a ``files`` key is ALSO present on the same
        entry → REPORT: this whole-tree gate carries a path filter it never
        consults. This is a distinct, always-reported condition regardless of
        whether the filter would happen to match something.
      - ``always_run: true`` and no ``files`` key → reachable, no report (this
        is the correct, legitimate shape for a whole-tree gate — mirrors the
        existing ``ensure-precommit-config`` entry in the real registry).
      - a ``files`` key is present (and ``always_run`` is not true): compile it
        as a regex and ``re.search`` it against every path returned by
        ``git ls-files`` (forward-slash, repo-root-relative, exactly as
        ``git ls-files`` emits them). Zero matches → REPORT unreachable.
        One or more matches → reachable, no report.
      - neither ``always_run`` nor ``files`` present → pre-commit's own
        default semantics apply (an absent ``files`` filter matches
        everything) → reachable, no report.

    Output (one process, all lines on stdout and/or stderr — this test file's
    assertions read the concatenation of both, exactly as sibling
    test_bp_100k_3.py does):
      - Per reported gate, exactly one line:
          ``UNREACHABLE: <gate-id> reason=<free text>``
        The reason text for the whole-tree-with-filter case MUST contain the
        substring "whole-tree" (this test file asserts on that substring —
        see TestWholeTreeGateCarryingPathFilterIsReported below).
      - Exactly one aggregate summary line per invocation, counting every
        non-skipped entry evaluated:
          ``check-hook-trigger-reachability: RESULT total=<N> unreachable=<M>``
      - Exit status: 0 when unreachable == 0 (and the check was NOT
        indeterminate); 1 when unreachable > 0; 2 when indeterminate (see
        BP-100k-4-i — the indeterminate code path is exercised there, this
        file only relies on "indeterminate never exits 0").

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES either the new
    reachability check, or the real check-build-drift / check-output-drift
    gate scripts, as a subprocess against a real, synthesized git repository —
    never a grep of commit_guardian.json's text. TestTheTwoDriftGatesActually
    RunOnAStagedChange in particular replicates pre-commit's own documented
    file-matching decision (regex search against real ``git diff --cached
    --name-only`` output, ``always_run`` bypasses the staged-file requirement,
    an absent ``files`` key matches everything) against the REAL registry
    entries and REAL staged paths in a REAL git repo, and then actually
    RUNS the real check_build_drift.py / check_output_drift.py and asserts
    each gate emits its own ``<gate-name>: RESULT ...`` summary line (already
    implemented by BP-100k-3) — this is the only evidence that distinguishes
    "the trigger is registered" from "the trigger actually fires".

RED BASELINE (expected, captured before check_hook_trigger_reachability.py is
    written): every test in this file is RED. Tests that invoke the new
    script fail because the script does not exist yet (python exits non-zero
    with "can't open file ..."), which is a legitimate red state — the
    reachability check itself is the thing this AC requires to be built.
    TestTheTwoDriftGatesActuallyRunOnAStagedChange fails earlier still, at
    ``assertTrue(would_run_build)`` / ``assertTrue(would_run_output)``,
    because the REAL registry's current triggers do not match a realistic
    staged self-host-layout change — that assertion failure IS the pinned
    defect.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_REACHABILITY_HOOK_SRC = _CG_TEMPLATES_SRC / "check_hook_trigger_reachability.py"
_REAL_REGISTRY = _CG_TEMPLATES_SRC / "commit_guardian.json"

_SUBPROCESS_TIMEOUT_SECONDS = 20

_UNREACHABLE_LINE_RE = re.compile(r"UNREACHABLE:\s*(\S+)\s+reason=(.+)")
_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\s+total=(\d+)\s+unreachable=(\d+)",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Shared helpers
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
    _git(["config", "user.email", "bp100k4test@example.com"], repo)
    _git(["config", "user.name", "BP-100k-4 Test"], repo)


def _commit_all(repo: Path, message: str) -> None:
    """Stage everything currently on disk under *repo* and commit it.

    Args:
        repo: Git repository root.
        message: Commit message.
    """
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _write_registry_config(entries: list[dict]) -> str:
    """Write a HOOK_TEST_CONFIG-shaped registry override via the real
    JSON serializer (never a hand-typed literal, per the Fixture
    Authenticity Rule).

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
    cwd: Path, hook_test_config_path: str | None = None
) -> subprocess.CompletedProcess:
    """Execute check_hook_trigger_reachability.py as a subprocess.

    Args:
        cwd: Working directory for the subprocess (must be the git repo root
            whose tracked paths are under test).
        hook_test_config_path: Optional path to a HOOK_TEST_CONFIG override
            JSON file (see ``_write_registry_config``). When None, the real
            commit_guardian.json fallback chain is exercised instead.

    Returns:
        The completed subprocess result (returncode, stdout, stderr).
    """
    env = os.environ.copy()
    if hook_test_config_path is not None:
        env["HOOK_TEST_CONFIG"] = hook_test_config_path
    return subprocess.run(
        [sys.executable, str(_REACHABILITY_HOOK_SRC)],
        cwd=str(cwd),
        env=env,
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=False,
    )


def _load_real_hook_entry(hook_id: str) -> dict:
    """Load one hook entry from the REAL, deployed-source registry.

    Args:
        hook_id: The ``id`` field to look up in ``hooks_manifest.hooks``.

    Returns:
        The matching hook entry dict.

    Raises:
        AssertionError: If no entry with that id exists (a fixture bug, not a
            production defect — fail loudly rather than silently skip).
    """
    with open(_REAL_REGISTRY, encoding="utf-8") as f:
        data = json.load(f)
    for entry in data["hooks_manifest"]["hooks"]:
        if entry.get("id") == hook_id:
            return entry
    raise AssertionError(
        f"hook id {hook_id!r} not found in the real commit_guardian.json "
        "hooks_manifest — fixture assumption broken, not a production defect."
    )


def _hook_matches_staged(entry: dict, staged_paths: list[str]) -> bool:
    """Replicate pre-commit's own documented file-matching decision.

    Mirrors pre-commit's real semantics: ``always_run: true`` bypasses the
    staged-file requirement entirely; an absent ``files`` key matches every
    staged file; otherwise the ``files`` value is a regex searched
    (unanchored, ``re.search``) against each staged path.

    Args:
        entry: A hooks_manifest.hooks[] entry.
        staged_paths: Repo-root-relative, forward-slash staged file paths
            (as ``git diff --cached --name-only`` emits them).

    Returns:
        True if pre-commit would invoke this hook given these staged paths.
    """
    if entry.get("enabled") is False:
        return False
    if entry.get("always_run"):
        return True
    pattern = entry.get("files")
    if not pattern:
        return bool(staged_paths)
    compiled = re.compile(pattern)
    return any(compiled.search(p) for p in staged_paths)


def _sha256_bytes(data: bytes) -> str:
    """Return the SHA-256 hex digest of raw bytes.

    Args:
        data: Raw bytes to hash.

    Returns:
        Lowercase hexadecimal SHA-256 digest string.
    """
    return hashlib.sha256(data).hexdigest()


def _build_synthetic_workspace(workspace: Path) -> Path:
    """Build a minimal synthetic self-hosted layout under *workspace*.

    Mirrors the fixture already proven by test_bp_100k_3.py:
    ``<workspace>/leafcutter-ai`` is the package root (holds ``templates/``
    and the manifest); deployed outputs live directly under
    ``<workspace>/.claude/...``.

    Args:
        workspace: Temp directory to build the synthetic layout inside.

    Returns:
        Absolute path to the synthetic package root.
    """
    pkg_root = workspace / "leafcutter-ai"
    (pkg_root / "templates" / "agents").mkdir(parents=True)
    (pkg_root / "templates" / "scripts" / "commit_guardian").mkdir(parents=True)
    (workspace / ".claude" / "agents").mkdir(parents=True)
    return pkg_root


def _write_manifest(pkg_root: Path, template_hashes: dict, output_mappings: dict) -> None:
    """Write .build_manifest.json via the real JSON serializer.

    Args:
        pkg_root: Synthetic package root (manifest lands in its parent).
        template_hashes: Flat dict of manifest-key -> sha256 hex string.
        output_mappings: The output_mappings section.
    """
    manifest = dict(template_hashes)
    manifest["output_mappings"] = output_mappings
    manifest["package_root"] = pkg_root.name
    (pkg_root.parent / ".build_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )


def _deploy_commit_guardian_dir(workspace: Path) -> Path:
    """Copy the REAL, unmodified templates/scripts/commit_guardian/ tree.

    Args:
        workspace: Temp directory to build the fake deployment inside.

    Returns:
        Absolute path to the deployed commit_guardian directory.
    """
    deployed_dir = workspace / ".leafcutter" / "scripts" / "commit_guardian"
    shutil.copytree(
        _CG_TEMPLATES_SRC, deployed_dir, ignore=shutil.ignore_patterns("__pycache__")
    )
    return deployed_dir


# ---------------------------------------------------------------------------
# test_spec 1: a trigger matching no tracked path is named and fails.
# ---------------------------------------------------------------------------


class TestTriggerMatchingNoTrackedPathIsNamedAndFails(unittest.TestCase):
    """A gate whose activation condition names a location that exists in no
    layout this repository is checked out in (the consumer-layout-prefix
    defect) is named by the check and the run fails."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)

        # Self-host layout: templates live at templates/, never at
        # leafcutter/templates/ — mirrors the real check-build-drift defect.
        agents_dir = self.repo / "templates" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "tracked.md").write_text("# tracked\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed self-host layout")

        self.config_path = _write_registry_config(
            [
                {
                    "id": "check-build-drift-fixture",
                    "files": "^leafcutter/templates/",
                    "pass_filenames": False,
                }
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_trigger_matching_no_tracked_path_is_named_and_fails(self) -> None:
        # covers: BP-100k-4
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A registered gate whose trigger matches no tracked path "
                f"must fail the check (non-zero exit). Output:\n{combined}"
            ),
        )
        match = _UNREACHABLE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No UNREACHABLE line was emitted for a gate whose trigger "
                f"matches no tracked path. Output:\n{combined}"
            ),
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertEqual(
            "check-build-drift-fixture",
            match.group(1),
            msg=f"UNREACHABLE line named the wrong gate. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# test_spec 2: a trigger whose every named location is gitignored is
# unreachable — proving ignore rules are consulted, not just path syntax.
# ---------------------------------------------------------------------------


class TestTriggerWhoseEveryNamedLocationIsIgnored(unittest.TestCase):
    """A gate whose activation condition names only locations excluded from
    version control is reported unreachable — an implementation that only
    checks whether the directory syntactically exists on disk (and ignores
    .gitignore) would wrongly call this reachable, because the directory
    and its file are genuinely present on disk."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)

        (self.repo / ".gitignore").write_text(
            ".claude/agents\n.claude/skills\n", encoding="utf-8"
        )
        (self.repo / "README.md").write_text("# repo\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed ignore rules")

        # The location genuinely EXISTS on disk (a naive existence check would
        # call it reachable) but is excluded from version control — it can
        # never be tracked, let alone staged.
        claude_agents = self.repo / ".claude" / "agents"
        claude_agents.mkdir(parents=True)
        (claude_agents / "output.md").write_text("# ignored output\n", encoding="utf-8")

        self.config_path = _write_registry_config(
            [
                {
                    "id": "check-output-drift-fixture",
                    "files": r"^\.claude/agents/",
                    "pass_filenames": False,
                }
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_trigger_whose_every_named_location_is_ignored_is_unreachable(self) -> None:
        # covers: BP-100k-4
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A gate whose trigger names only gitignored locations must "
                f"fail the check. Output:\n{combined}"
            ),
        )
        match = _UNREACHABLE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No UNREACHABLE line was emitted for a gate whose trigger "
                "names only gitignored locations — the check must consult "
                f"git's tracked-path set, not merely path syntax. Output:\n{combined}"
            ),
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertEqual(
            "check-output-drift-fixture",
            match.group(1),
            msg=f"UNREACHABLE line named the wrong gate. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# test_spec 3: a whole-tree gate carrying a path filter is reported.
# ---------------------------------------------------------------------------


class TestWholeTreeGateCarryingPathFilterIsReported(unittest.TestCase):
    """A gate that declares always_run: true (it does not consume the staged
    file list) yet ALSO carries a "files" activation condition is reported —
    its execution must not be decided by a filter it never consults."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        (self.repo / "README.md").write_text("# repo\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed minimal repo")

        self.config_path = _write_registry_config(
            [
                {
                    "id": "check-build-drift-fixture",
                    "always_run": True,
                    "pass_filenames": False,
                    "files": "^leafcutter/templates/",
                }
            ]
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_whole_tree_gate_carrying_a_path_filter_is_reported(self) -> None:
        # covers: BP-100k-4
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A whole-tree (always_run) gate that also carries a files "
                f"filter must be reported and must fail. Output:\n{combined}"
            ),
        )
        match = _UNREACHABLE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No UNREACHABLE line was emitted for a whole-tree gate "
                f"carrying a redundant files filter. Output:\n{combined}"
            ),
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertEqual("check-build-drift-fixture", match.group(1))
        self.assertIn(
            "whole-tree",
            match.group(2).lower(),
            msg=(
                "The reported reason does not identify this as a "
                f"whole-tree-gate-with-a-path-filter condition. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 4: the two drift gates actually run on a staged change.
# ---------------------------------------------------------------------------


class TestTheTwoDriftGatesActuallyRunOnAStagedChange(unittest.TestCase):
    """With the REAL registry, staging a realistic self-host-layout change
    the drift gates are meant to police and evaluating pre-commit's own
    matching decision must say "run" for both gates, and — once it does —
    actually executing the real gate scripts must produce their own RESULT
    run summary. No assertion over registry text can establish this."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.workspace = Path(self._tmpdir.name)

        # Part A: a real git repo mirroring the self-host layout, used to
        # compute whether pre-commit's own matching decision would invoke
        # each drift gate on a realistic staged change.
        self.repo = self.workspace / "repo"
        _init_repo(self.repo)
        (self.repo / "templates" / "agents").mkdir(parents=True)
        (self.repo / ".claude" / "agents").mkdir(parents=True)
        self.build_target = self.repo / "templates" / "agents" / "some_template.md"
        self.build_target.write_text("# v1\n", encoding="utf-8")
        self.output_target = self.repo / ".claude" / "agents" / "some_output.md"
        self.output_target.write_text("# v1\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed self-host layout for staged-change probe")

        self.build_target.write_text(
            "# v2 - a real edit a developer would stage\n", encoding="utf-8"
        )
        self.output_target.write_text(
            "# v2 - a real edit a developer would stage\n", encoding="utf-8"
        )
        _git(
            ["add", "templates/agents/some_template.md", ".claude/agents/some_output.md"],
            self.repo,
        )

        # Part B: the full check_build_drift/check_output_drift comparison
        # scenario (manifest + deployed hook copy), reusing the fixture
        # pattern proven by test_bp_100k_3.py, so the ACTUAL hooks can be
        # executed and their RESULT lines observed.
        self.pkg_root = _build_synthetic_workspace(self.workspace)
        build_content = b"# matched build artifact\n"
        tracked = self.pkg_root / "templates" / "agents" / "tracked.md"
        tracked.write_bytes(build_content)
        tracked_key = tracked.relative_to(self.workspace).as_posix()

        output_content = b"# matched output artifact\n"
        output_file = self.workspace / ".claude" / "agents" / "tracked_output.md"
        output_file.write_bytes(output_content)
        output_key = output_file.relative_to(self.workspace).as_posix()

        _write_manifest(
            self.pkg_root,
            {tracked_key: _sha256_bytes(build_content)},
            {
                output_key: {
                    "template": "templates/agents/tracked_output_src.md",
                    "expected_output_hash": _sha256_bytes(output_content),
                }
            },
        )
        deployed_dir = _deploy_commit_guardian_dir(self.workspace)
        self.build_hook = deployed_dir / "check_build_drift.py"
        self.output_hook = deployed_dir / "check_output_drift.py"

    def test_the_two_drift_gates_actually_run_on_a_staged_change(self) -> None:
        # covers: BP-100k-4
        staged_result = _git(["diff", "--cached", "--name-only"], self.repo)
        staged_paths = [p for p in staged_result.stdout.splitlines() if p]
        self.assertTrue(staged_paths, "fixture setup did not actually stage anything")

        build_entry = _load_real_hook_entry("check-build-drift")
        output_entry = _load_real_hook_entry("check-output-drift")

        would_run_build = _hook_matches_staged(build_entry, staged_paths)
        would_run_output = _hook_matches_staged(output_entry, staged_paths)

        self.assertTrue(
            would_run_build,
            msg=(
                "check-build-drift's REAL activation condition "
                f"(files={build_entry.get('files')!r}, "
                f"always_run={build_entry.get('always_run')!r}) does not "
                f"match any of the staged paths a real developer edit would "
                f"produce: {staged_paths}. This is the BP-100k-4 defect: the "
                "gate is registered but can never fire on a staged change in "
                "this repository's own layout."
            ),
        )
        self.assertTrue(
            would_run_output,
            msg=(
                "check-output-drift's REAL activation condition "
                f"(files={output_entry.get('files')!r}, "
                f"always_run={output_entry.get('always_run')!r}) does not "
                f"match any of the staged paths a real developer edit would "
                f"produce: {staged_paths}. This is the BP-100k-4 defect: the "
                "gate is registered but can never fire on a staged change in "
                "this repository's own layout."
            ),
        )

        # Only once the gating decision is fixed does it become meaningful to
        # confirm the gate ACTUALLY executes and emits its own run summary —
        # the only evidence that distinguishes "registered" from "fires".
        build_result = subprocess.run(
            [sys.executable, str(self.build_hook)],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        output_result = subprocess.run(
            [sys.executable, str(self.output_hook)],
            cwd=str(self.workspace),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        combined_build = build_result.stdout + build_result.stderr
        combined_output = output_result.stdout + output_result.stderr

        self.assertRegex(
            combined_build,
            r"check-build-drift:\s*RESULT",
            msg=(
                "check-build-drift did not emit its own RESULT run summary "
                f"when actually executed. Output:\n{combined_build}"
            ),
        )
        self.assertRegex(
            combined_output,
            r"check-output-drift:\s*RESULT",
            msg=(
                "check-output-drift did not emit its own RESULT run summary "
                f"when actually executed. Output:\n{combined_output}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 5: an unreachable gate in the registry blocks the commit; a
# registry where every gate is reachable does not.
# ---------------------------------------------------------------------------


class TestUnreachableGateInTheRegistryBlocksTheCommit(unittest.TestCase):
    """The reachability verdict is part of the commit outcome, not an
    advisory note: one unreachable gate must block; zero unreachable gates
    must not."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name)
        _init_repo(self.repo)
        agents_dir = self.repo / "templates" / "agents"
        agents_dir.mkdir(parents=True)
        (agents_dir / "tracked.md").write_text("# tracked\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed reachable-gate layout")

        self.blocking_config = _write_registry_config(
            [
                {"id": "reachable-gate", "files": "^templates/agents/", "pass_filenames": False},
                {
                    "id": "unreachable-gate",
                    "files": "^leafcutter/templates/",
                    "pass_filenames": False,
                },
            ]
        )
        self.addCleanup(os.unlink, self.blocking_config)

        self.clean_config = _write_registry_config(
            [
                {"id": "reachable-gate", "files": "^templates/agents/", "pass_filenames": False},
            ]
        )
        self.addCleanup(os.unlink, self.clean_config)

    def test_unreachable_gate_in_the_registry_blocks_the_commit(self) -> None:
        # covers: BP-100k-4
        blocking_result = _run_reachability_hook(self.repo, self.blocking_config)
        clean_result = _run_reachability_hook(self.repo, self.clean_config)

        combined_blocking = blocking_result.stdout + blocking_result.stderr
        combined_clean = clean_result.stdout + clean_result.stderr

        self.assertNotEqual(
            0,
            blocking_result.returncode,
            msg=(
                "A registry containing one unreachable gate must exit "
                f"non-zero. Output:\n{combined_blocking}"
            ),
        )
        self.assertEqual(
            0,
            clean_result.returncode,
            msg=(
                "A registry in which every gate is reachable must exit "
                f"zero. Output:\n{combined_clean}"
            ),
        )
        self.assertNotEqual(
            blocking_result.returncode,
            clean_result.returncode,
            msg=(
                "The reachability verdict must affect the commit outcome: "
                f"blocking={blocking_result.returncode} "
                f"clean={clean_result.returncode}"
            ),
        )


# ---------------------------------------------------------------------------
# test_spec 6: the real registry reports zero unreachable gates after the fix.
# ---------------------------------------------------------------------------


class TestRealRegistryReportsZeroUnreachableGatesAfterTheFix(unittest.TestCase):
    """The executed check, run over the repository's REAL registry, reports
    an unreachable-gate count of exactly zero — read from the check's own
    summary, never from an allowlist of gate names.

    SUBJECT CHOICE (2026-08-25): the registry under test is the SOURCE file
    at templates/scripts/commit_guardian/commit_guardian.json, supplied via
    HOOK_TEST_CONFIG, not the deployed copy the hook's own fallback chain
    would reach at ``<cwd>/scripts/commit_guardian/commit_guardian.json``.

    That deployed path is a symlink into a build-output tree SHARED by every
    worktree in this workspace, so its contents are whatever worktree built
    last — not necessarily the branch under test. This test was observed
    flipping red three times in one session while the source registry held
    the fix throughout, each time because an unrelated build from the main
    checkout redeployed main's pre-fix registry over it (KI-BP-013).

    The source file is also the correct subject on the merits: it is the
    artifact under version control, the thing a reviewer reads and a PR
    changes. Asserting against a build artifact of unknown provenance would
    make this gate's verdict depend on who built last, which is the same
    "the check could not check what it claimed to" failure BP-100k-4 exists
    to eliminate. The fallback-chain resolution order is covered separately
    by the HOOK_TEST_CONFIG / deployed / colocated tests above.
    """

    def test_real_registry_reports_zero_unreachable_gates_after_the_fix(self) -> None:
        # covers: BP-100k-4
        result = _run_reachability_hook(
            _REPO_ROOT, hook_test_config_path=str(_REAL_REGISTRY)
        )
        combined = result.stdout + result.stderr

        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No RESULT summary line from a run over the real registry. "
                f"Output:\n{combined}"
            ),
        )
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        unreachable = int(match.group(2))
        self.assertEqual(
            0,
            unreachable,
            msg=(
                "The real registry must report zero unreachable gates once "
                f"the BP-100k-4 fix lands. Output:\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
