"""
MODULE: unit_tests/commit_guardian/test_bp_100k_4_hardening.py
GOAL: Round-2 adversarial-review hardening for check_hook_trigger_reachability.py
    (BP-100k-4 / BP-100k-4-i). Five defects were found by an adversarial logic
    review that EXECUTED the gate rather than reading it — the exact defect
    class this epic exists to eliminate: a check that cannot perform its check
    reporting a pass. This file pins each one down independently so red->green
    evidence can be reported per finding, not as an aggregate.
BUSINESS CONTEXT: See /tmp/review_logic_round2.md (F5, F6, F7) and
    /tmp/review_code_round2.md (H-3/M-2 sibling findings) for the original
    reproductions. Findings covered here:
      1. F5  — one exemption entry keyed on the "<unknown>" sentinel silences
               EVERY id-less gate at once; a duplicated hooks-manifest id lets
               one exemption cover two distinct gates.
      2. F6  — a deployed registry that EXISTS but fails to parse is treated
               the same as an ABSENT one: the gate silently falls through to
               a different registry copy (the colocated source) and reports
               clean — verifying a registry that is not the one pre-commit
               would actually run.
      3. F7  — an empty (but present) hooks_manifest.hooks list, or one whose
               every entry is disabled/non-dict, is reported as a clean
               zero-unreachable pass. A run that inspected zero gates has
               established nothing.
      4. M   — a repository with zero tracked paths (a fresh clone before the
               first `git add`) produces confident UNREACHABLE verdicts for
               every files-triggered gate instead of INDETERMINATE — "no
               evidence" is being reported as "proof of unreachability".
      5. M   — a catastrophic-backtracking `files` regex hangs the process
               forever with no verdict at all, which for a developer running
               pre-commit is indistinguishable from a crash.

HARD CONSTRAINT (repo standing rule, "Gate / Workflow ACs — Verify
    Behaviorally, Not by Grep"): every test below EXECUTES
    check_hook_trigger_reachability.py as a subprocess against a real,
    synthesized registry and/or git repository, and asserts on the process's
    actual exit status and emitted output — never a grep of the source or of
    commit_guardian.json's text.

RED BASELINE (captured before this round's fix): see the per-class docstring
    below for the specific pre-fix behaviour each test pins.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_TEMPLATES_DIR = _REPO_ROOT / "templates"
_CG_TEMPLATES_SRC = _TEMPLATES_DIR / "scripts" / "commit_guardian"
_REACHABILITY_HOOK_SRC = _CG_TEMPLATES_SRC / "check_hook_trigger_reachability.py"

_SUBPROCESS_TIMEOUT_SECONDS = 30

_RESULT_LINE_RE = re.compile(
    r"check-hook-trigger-reachability:\s*RESULT\s+total=(\d+)\s+unreachable=(\d+)\s+exempt=(\d+)",
    re.IGNORECASE,
)
_INDETERMINATE_LINE_RE = re.compile(r"INDETERMINATE:\s*reason=(.+)")
_CLEAN_ZERO_UNREACHABLE_RE = re.compile(r"unreachable=0\b")


# ---------------------------------------------------------------------------
# Shared helpers (mirrors test_bp_100k_4.py / test_bp_100k_4_i.py; duplicated
# per house convention of self-contained sibling test files)
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
    _git(["config", "user.email", "bp100k4hardeningtest@example.com"], repo)
    _git(["config", "user.name", "BP-100k-4 Hardening Test"], repo)


def _commit_all(repo: Path, message: str) -> None:
    """Stage everything currently on disk under *repo* and commit it.

    Args:
        repo: Git repository root.
        message: Commit message.
    """
    _git(["add", "-A"], repo)
    _git(["commit", "-m", message], repo)


def _write_registry_config(payload: dict) -> str:
    """Write a HOOK_TEST_CONFIG-shaped registry override via the real JSON
    serializer (never a hand-typed literal, per the Fixture Authenticity Rule).

    Args:
        payload: The full top-level registry dict to embed (must contain at
            least a "hooks_manifest" key; may also carry
            "hook_trigger_reachability_exemption_registry").

    Returns:
        Absolute path to the temp JSON file written.
    """
    fd, path = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f)
    return path


def _run_reachability_hook(
    cwd: Path,
    hook_test_config_path: str | None = None,
    timeout: int = _SUBPROCESS_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess:
    """Execute check_hook_trigger_reachability.py as a subprocess.

    Args:
        cwd: Working directory for the subprocess.
        hook_test_config_path: Optional path to a HOOK_TEST_CONFIG override
            JSON file. When None, the real commit_guardian.json fallback
            chain is exercised instead.
        timeout: Wall-clock timeout for the subprocess itself (this is the
            TEST's own safety net, distinct from the production wall-clock
            guard finding #5 pins).

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
        timeout=timeout,
        check=False,
    )


def _minimal_repo(tmp_path: Path) -> Path:
    """Build a minimal git repo with one tracked file, for tests that only
    need a non-empty tracked-path set and don't care what it contains.

    Args:
        tmp_path: Temp directory to build the repo inside.

    Returns:
        Absolute path to the initialized repo.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _commit_all(repo, "chore: seed minimal repo")
    return repo


# ---------------------------------------------------------------------------
# Finding 1 (F5): the "<unknown>" sentinel and duplicate hooks-manifest ids
# ---------------------------------------------------------------------------


class TestUnknownSentinelExemptionCannotSilenceIdLessGates(unittest.TestCase):
    """F5, part A: an exemption entry whose "id" is the literal unknown-gate
    display sentinel ("<unknown>") must never be honoured — it must not
    silence any id-less hooks-manifest entry, no matter how many there are.

    RED BASELINE: pre-fix, ``_evaluate_gate`` defaults a missing "id" to the
    display string "<unknown>" and looks that same string up in the
    exemptions map, so a single ``{"id": "<unknown>", "ground": "..."}``
    entry exempts every id-less gate simultaneously: exit 0, all reported
    EXEMPT rather than UNREACHABLE.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = _minimal_repo(Path(self._tmpdir.name))

        self.config_path = _write_registry_config(
            {
                "hooks_manifest": {
                    "hooks": [
                        {"files": "^never/matches/anything/", "pass_filenames": False},
                        {"files": "^also/never/matches/", "pass_filenames": False},
                    ]
                },
                "hook_trigger_reachability_exemption_registry": [
                    {"id": "<unknown>", "ground": "one entry, stated ground"}
                ],
            }
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_unknown_sentinel_exemption_cannot_silence_id_less_gates(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "Two id-less gates whose files patterns match nothing must "
                "not be silenced by a single exemption entry keyed on the "
                f"'<unknown>' display sentinel. Output:\n{combined}"
            ),
        )
        self.assertNotIn(
            "EXEMPT: <unknown>",
            combined,
            msg=(
                "The '<unknown>' sentinel must never be usable as an "
                f"exemption lookup key. Output:\n{combined}"
            ),
        )
        match = _RESULT_LINE_RE.search(combined)
        self.assertIsNotNone(match, msg=f"No RESULT line emitted. Output:\n{combined}")
        assert match is not None  # narrowing for mypy; assertIsNotNone above is the real check
        self.assertGreaterEqual(
            int(match.group(2)),
            2,
            msg=(
                "Both id-less, non-matching gates must be counted as "
                f"unreachable, not silently exempted. Output:\n{combined}"
            ),
        )


class TestDuplicateHooksManifestIdDoesNotShareAnExemption(unittest.TestCase):
    """F5, part B: two distinct hooks-manifest entries sharing the same "id"
    must not be able to piggyback on a single exemption entry — a duplicate
    id is itself a reported condition, not a valid exemption lookup key.

    RED BASELINE: pre-fix, both entries share the exemptions dict key "twin",
    so one grounded exemption entry silences both simultaneously: exit 0,
    both reported EXEMPT.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = _minimal_repo(Path(self._tmpdir.name))

        self.config_path = _write_registry_config(
            {
                "hooks_manifest": {
                    "hooks": [
                        {
                            "id": "twin",
                            "files": "^never/matches/one/",
                            "pass_filenames": False,
                        },
                        {
                            "id": "twin",
                            "files": "^never/matches/two/",
                            "pass_filenames": False,
                        },
                    ]
                },
                "hook_trigger_reachability_exemption_registry": [
                    {"id": "twin", "ground": "one exemption, two distinct gates silenced"}
                ],
            }
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_duplicate_hooks_manifest_id_does_not_share_an_exemption(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "Two distinct hooks-manifest entries sharing one id must not "
                "both be silenced by a single grounded exemption for that "
                f"id. Output:\n{combined}"
            ),
        )
        self.assertNotRegex(
            combined,
            r"EXEMPT:\s*twin",
            msg=(
                "A duplicated id must never be honoured as an exemption "
                f"lookup key. Output:\n{combined}"
            ),
        )
        self.assertRegex(
            combined,
            r"(?i)duplicate",
            msg=(
                "A duplicated hooks-manifest id must itself be a reported "
                f"condition. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# Finding 2 (F6): a corrupt DEPLOYED registry must not fall through to source
# ---------------------------------------------------------------------------


class TestCorruptDeployedRegistryIsIndeterminateNotAFallthrough(unittest.TestCase):
    """F6: when the deployed registry candidate
    (``<cwd>/scripts/commit_guardian/commit_guardian.json``) EXISTS but is
    not valid JSON, the gate must report INDETERMINATE — it must not fall
    through to the colocated source-tree commit_guardian.json and report a
    clean pass against a registry that is not the one pre-commit would
    actually consume.

    RED BASELINE: pre-fix, ``_load_registry`` treats "exists but unreadable"
    identically to "does not exist" and tries the next candidate, so this
    scenario exits 0 with a clean RESULT line computed from the (unrelated)
    source registry.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = _minimal_repo(Path(self._tmpdir.name))

        deployed_dir = self.repo / "scripts" / "commit_guardian"
        deployed_dir.mkdir(parents=True)
        # Deliberately corrupt — not a hand-typed valid literal standing in
        # for real JSON, but genuinely unparseable content.
        (deployed_dir / "commit_guardian.json").write_text(
            "{ this is not valid json and never parses ", encoding="utf-8"
        )

    def test_corrupt_deployed_registry_is_indeterminate_not_a_fallthrough(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A deployed registry that exists but fails to parse must "
                f"fail the check, never fall through silently. Output:\n{combined}"
            ),
        )
        self.assertNotRegex(
            combined,
            _CLEAN_ZERO_UNREACHABLE_RE,
            msg=(
                "A corrupt deployed registry must never be reported as a "
                f"clean, all-reachable pass computed from a DIFFERENT "
                f"registry. Output:\n{combined}"
            ),
        )
        match = _INDETERMINATE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No INDETERMINATE verdict was emitted for an existing-but-"
                f"corrupt deployed registry. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# Finding 3 (F7): an empty hooks_manifest.hooks list is not a clean pass
# ---------------------------------------------------------------------------


class TestEmptyHooksListIsIndeterminateNotAcleanPass(unittest.TestCase):
    """F7: a present-but-empty ``hooks_manifest.hooks: []`` list must not be
    reported as a clean, zero-unreachable pass — a run that inspected zero
    gates has established nothing, exactly like the ``verified == 0`` floor
    the sibling drift gates already enforce.

    RED BASELINE: pre-fix, ``total`` ends the loop at 0 and ``return 1 if
    unreachable else 0`` returns 0 — a permanent green light for a registry
    (or a merge) that silently wrote an empty hooks list.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = _minimal_repo(Path(self._tmpdir.name))

        self.config_path = _write_registry_config({"hooks_manifest": {"hooks": []}})
        self.addCleanup(os.unlink, self.config_path)

    def test_empty_hooks_list_is_indeterminate_not_a_clean_pass(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "An empty hooks_manifest.hooks list must not exit 0 — a run "
                f"that inspected nothing proves nothing. Output:\n{combined}"
            ),
        )
        self.assertNotRegex(
            combined,
            r"RESULT\s+total=0\s+unreachable=0",
            msg=(
                "A zero-gates-inspected run must not present as a clean "
                f"RESULT line. Output:\n{combined}"
            ),
        )


# ---------------------------------------------------------------------------
# Finding 4 (M): zero tracked paths must be indeterminate, not confident
# ---------------------------------------------------------------------------


class TestZeroTrackedPathsIsIndeterminateNotConfidentUnreachable(unittest.TestCase):
    """M: a repository that genuinely tracks zero paths (a fresh ``git
    init`` with nothing ever added) must be reported INDETERMINATE — "no
    evidence either way" — never as a confident UNREACHABLE verdict for
    every files-triggered gate. This is the consumer-install blast radius:
    a fresh clone, a submodule checkout, or a shallow CI checkout can all
    present zero tracked paths, and confident UNREACHABLEs there would block
    every commit in that install.

    RED BASELINE: pre-fix, ``git ls-files`` exits 0 with empty output, so
    ``tracked_paths == []`` (not None), and the gate proceeds to evaluate
    every files-triggered gate as UNREACHABLE — exit 1, zero INDETERMINATE
    line, confidently asserting a structural defect on the basis of no
    evidence at all.
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name) / "repo"
        # Deliberately git-init with NOTHING ever added or committed — the
        # tracked-path set is genuinely, successfully empty, not a git
        # failure.
        _init_repo(self.repo)

        self.config_path = _write_registry_config(
            {
                "hooks_manifest": {
                    "hooks": [
                        {"id": "some-gate", "files": "\\.py$", "pass_filenames": False}
                    ]
                }
            }
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_zero_tracked_paths_is_indeterminate_not_confident_unreachable(self) -> None:
        # covers: BP-100k-4-i
        result = _run_reachability_hook(self.repo, self.config_path)
        combined = result.stdout + result.stderr

        self.assertNotRegex(
            combined,
            r"UNREACHABLE:\s*some-gate",
            msg=(
                "Zero tracked paths must never be reported as a confident "
                f"UNREACHABLE verdict. Output:\n{combined}"
            ),
        )
        match = _INDETERMINATE_LINE_RE.search(combined)
        self.assertIsNotNone(
            match,
            msg=(
                "No INDETERMINATE verdict was emitted for a repository that "
                f"tracks zero paths. Output:\n{combined}"
            ),
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=f"An indeterminate run must not exit 0. Output:\n{combined}",
        )


# ---------------------------------------------------------------------------
# Finding 5 (M): a catastrophic-backtracking files regex must not hang
# ---------------------------------------------------------------------------


class TestCatastrophicBacktrackingRegexIsBoundedNotAHang(unittest.TestCase):
    """M: a pathological ``files`` regex (classic catastrophic backtracking,
    ``^(a+)+$``) matched against a tracked path built to trigger worst-case
    behaviour must be bounded by a wall-clock guard and reported — never left
    to hang the pre-commit hook indefinitely, which is indistinguishable
    from a crash to a developer.

    RED BASELINE: pre-fix, ``re.search`` runs completely unbounded; the
    subprocess in this test would hit the TEST's own generous
    ``_SUBPROCESS_TIMEOUT_SECONDS`` and raise ``TimeoutExpired`` — no verdict
    of any kind is ever produced.

    The production wall-clock bound is exercised via
    ``HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS`` (an internal, undocumented test
    knob — analogous to HOOK_TEST_CONFIG — that shortens the bound so this
    test does not need to wait out a multi-second production default).
    """

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmpdir.cleanup)
        self.repo = Path(self._tmpdir.name) / "repo"
        _init_repo(self.repo)
        # A filename engineered to trigger catastrophic backtracking against
        # ^(a+)+$: many 'a' characters followed by one non-matching char.
        pathological_name = "a" * 30 + "b.md"
        (self.repo / pathological_name).write_text("# x\n", encoding="utf-8")
        _commit_all(self.repo, "chore: seed pathological filename")

        self.config_path = _write_registry_config(
            {
                "hooks_manifest": {
                    "hooks": [
                        {
                            "id": "catastrophic-gate",
                            "files": "^(a+)+$",
                            "pass_filenames": False,
                        }
                    ]
                }
            }
        )
        self.addCleanup(os.unlink, self.config_path)

    def test_catastrophic_backtracking_regex_is_bounded_not_a_hang(self) -> None:
        # covers: BP-100k-4-i
        env = os.environ.copy()
        env["HOOK_TEST_CONFIG"] = self.config_path
        env["HOOK_TRIGGER_REGEX_TIMEOUT_SECONDS"] = "1"

        start = time.monotonic()
        result = subprocess.run(
            [sys.executable, str(_REACHABILITY_HOOK_SRC)],
            cwd=str(self.repo),
            env=env,
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT_SECONDS,
            check=False,
        )
        elapsed = time.monotonic() - start
        combined = result.stdout + result.stderr

        self.assertLess(
            elapsed,
            10,
            msg=(
                "The gate must be bounded by its own wall-clock guard, not "
                f"left to run unbounded. Elapsed: {elapsed:.1f}s. "
                f"Output:\n{combined}"
            ),
        )
        self.assertNotEqual(
            0,
            result.returncode,
            msg=(
                "A regex that exceeds its time budget must never produce a "
                f"clean pass. Output:\n{combined}"
            ),
        )
        self.assertNotRegex(
            combined,
            _CLEAN_ZERO_UNREACHABLE_RE,
            msg=(
                "A regex timeout must never be reported as a clean, "
                f"all-reachable pass. Output:\n{combined}"
            ),
        )
        self.assertTrue(
            re.search(r"(?i)time.?out|time budget|INDETERMINATE", combined),
            msg=(
                "The regex-timeout condition must be named in the output, "
                f"not silently swallowed. Output:\n{combined}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
