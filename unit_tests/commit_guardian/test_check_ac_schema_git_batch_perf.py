"""
MODULE: test_check_ac_schema_git_batch_perf
GOAL: Performance regression test for the _load_head_yaml batching bug.

BUSINESS CONTEXT:
    _load_head_yaml() is called once per staged-modified AC file (Phase 2
    field-preservation check).  Current code spawns a separate
    ``git show HEAD:<path>`` subprocess per file — O(N) process overhead that
    contributes to pre-commit timeouts on large batches.

    The fix (tracked on branch fix/ac-schema-git-batch) fetches all HEAD blobs
    in ONE batched ``git cat-file --batch`` call.

RED/GREEN CONTRACT:
    - RED  (current code):  N=3 spawns 3 git-fetch subprocesses;
                            N=9 spawns 9 git-fetch subprocesses.  The two
                            counts differ → FAIL.
    - GREEN (after fix):    Both N=3 and N=9 spawn exactly 1 batched call.
                            The counts are equal and within [1, small_bound].

ARCHITECTURE:
    The test imports check_ac_schema directly (not via subprocess) so it can
    monkey-patch subprocess.run in the module under test.  sys.path is wired
    via Path(__file__).resolve().parents[...] — deterministic, cwd-independent.
    Missing imports raise loudly (no skipTest fallback).

    Env seams used:
        HOOK_ROOT              — temp dir acting as project root.
        HOOK_TEST_FILES_MODIFIED  — colon-separated list of repo-relative paths
                                    that Phase 2 treats as staged-modified files.
        HOOK_NO_GIT            — must be UNSET so the code actually calls git
                                  (intercepted by the patch).

    The staged files on disk contain valid YAML *without* implements_pattern so
    the HEAD comparison can detect a "drop" only when HEAD YAML has it.  To
    ensure _load_head_yaml is actually exercised (not short-circuited by a
    None return before the git call), the patched subprocess.run returns a
    HEAD YAML blob that CONTAINS implements_pattern: "PTN-001".  That makes
    head_has_it=True, staged_has_it=False → violation detected.  The
    correctness sub-test verifies the violation is still reported post-fix.
"""

from __future__ import annotations

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# sys.path setup — deterministic, cwd-independent
# ---------------------------------------------------------------------------
# This file is:  unit_tests/commit_guardian/test_check_ac_schema_git_batch_perf.py
# Hook is at:   templates/scripts/commit_guardian/check_ac_schema.py
# parents[0] = unit_tests/commit_guardian/
# parents[1] = unit_tests/
# parents[2] = <repo-root>/ (worktree root)
_THIS_FILE = Path(__file__).resolve()
_REPO_ROOT = _THIS_FILE.parents[2]
_HOOK_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

if str(_HOOK_DIR) not in sys.path:
    sys.path.insert(0, str(_HOOK_DIR))

# Import loudly — a missing import is a real signal, not something to hide.
try:
    import check_ac_schema as _hook_mod
except ImportError as _exc:
    raise ImportError(
        f"Cannot import check_ac_schema from {_HOOK_DIR}: {_exc}. "
        "Ensure the templates/scripts/commit_guardian/ directory exists and "
        "contains check_ac_schema.py."
    ) from _exc

# ---------------------------------------------------------------------------
# Shared fixture YAML
# ---------------------------------------------------------------------------

# A minimal valid AC YAML WITHOUT implements_pattern.
# This represents the *staged* (working-tree) version of the file.
_STAGED_AC_YAML = textwrap.dedent("""\
    id: {ac_id}
    title: "Test AC {ac_id}"
    component: finalize
    status: active
    created_by: "tickets/test.md"
    criteria: |
      Given something
      When something
      Then something
    priority: medium
    readiness: draft
""")

# A minimal AC YAML WITH implements_pattern — returned by the mocked git show.
# This represents the *HEAD* (committed) version of the file that had
# implements_pattern set.  Dropping it in the staged version → violation.
_HEAD_AC_YAML_WITH_PATTERN = textwrap.dedent("""\
    id: {ac_id}
    title: "Test AC {ac_id}"
    component: finalize
    status: active
    created_by: "tickets/test.md"
    criteria: |
      Given something
      When something
      Then something
    priority: medium
    readiness: draft
    implements_pattern: "PTN-001"
""")

# Rel-path template for constructing the staged-modified file list.
_REL_PATH_TMPL = "docs/acceptance-criteria/{ac_id}.yaml"


def _make_ac_files(
    root: Path,
    ac_ids: list[str],
    staged_yaml_tpl: str = _STAGED_AC_YAML,
) -> list[str]:
    """Write staged AC YAML files under root/docs/acceptance-criteria/.

    Returns the list of repo-relative path strings (used for
    HOOK_TEST_FILES_MODIFIED).

    Args:
        root: Temp dir acting as the project root.
        ac_ids: List of AC id strings (e.g. ["FIN-001", "FIN-002"]).
        staged_yaml_tpl: YAML template; ``{ac_id}`` is substituted.

    Returns:
        List of repo-relative path strings.
    """
    ac_dir = root / "docs" / "acceptance-criteria"
    ac_dir.mkdir(parents=True, exist_ok=True)
    rel_paths: list[str] = []
    for ac_id in ac_ids:
        content = staged_yaml_tpl.format(ac_id=ac_id)
        (ac_dir / f"{ac_id}.yaml").write_text(content, encoding="utf-8")
        rel_paths.append(_REL_PATH_TMPL.format(ac_id=ac_id))
    return rel_paths


def _make_mock_subprocess_run(head_yaml_tpl: str = _HEAD_AC_YAML_WITH_PATTERN):
    """Return a mock for subprocess.run that intercepts git-show / cat-file calls.

    The mock returns a CompletedProcess with returncode=0 and stdout set to
    HEAD YAML content for any git call that fetches HEAD AC blob content.
    All other subprocess.run calls (e.g. git diff --cached) return returncode=1
    so that the git enumeration paths short-circuit (we control the file list
    via env seams).

    Args:
        head_yaml_tpl: YAML template for the HEAD blob response;
            ``{ac_id}`` is substituted from the path in the argv.

    Returns:
        A callable suitable for use as ``subprocess.run`` mock.
    """
    def _run(args, **kwargs):
        mock_result = MagicMock()
        mock_result.returncode = 0

        # Detect a HEAD-content-fetch call.
        # Current code:  ["git", "-C", root, "show", "HEAD:<rel_path>"]
        # Fixed code:    ["git", "-C", root, "cat-file", "--batch"]
        argv = list(args) if hasattr(args, "__iter__") else []
        is_head_fetch = any(
            (isinstance(a, str) and a.startswith("HEAD:")) for a in argv
        ) or (
            "cat-file" in argv and "--batch" in argv
        )

        if is_head_fetch:
            # Extract ac_id from the path for template substitution.
            # For "git show HEAD:docs/.../FIN-001.yaml", the HEAD:... token
            # contains the ac_id.
            ac_id = "FIN-XXX"
            for token in argv:
                if isinstance(token, str) and token.startswith("HEAD:"):
                    # e.g. HEAD:docs/acceptance-criteria/FIN-001.yaml
                    ac_id = Path(token.split("HEAD:", 1)[1]).stem
                    break
            mock_result.stdout = head_yaml_tpl.format(ac_id=ac_id)
        else:
            # Non-HEAD-fetch git calls (e.g. git diff --cached) → no files.
            mock_result.returncode = 1
            mock_result.stdout = ""

        mock_result.stderr = ""
        return mock_result

    return _run


# ---------------------------------------------------------------------------
# Small AC id sets for the two batch sizes
# ---------------------------------------------------------------------------
_BATCH_3 = [f"FIN-{i:03d}" for i in range(1, 4)]    # FIN-001, FIN-002, FIN-003
_BATCH_9 = [f"FIN-{i:03d}" for i in range(1, 10)]   # FIN-001 … FIN-009

# Maximum allowed git-subprocess count (constant, post-fix).
# The batch fix collapses all HEAD fetches into ONE cat-file --batch call.
# We allow up to 2 to leave room for a minor implementation variant (e.g.
# one cat-file --batch per hook invocation + one for fallback detection).
_MAX_GIT_CALLS = 2


def _count_head_fetch_calls(mock_calls: list) -> int:
    """Count how many subprocess.run calls fetched HEAD AC blob content.

    Args:
        mock_calls: List of ``unittest.mock.call`` objects recorded by the mock.

    Returns:
        Number of calls whose argv contains a ``HEAD:`` token or
        uses ``cat-file --batch``.
    """
    count = 0
    for c in mock_calls:
        # call objects: c.args[0] is the argv list passed to subprocess.run
        try:
            argv = list(c.args[0])
        except (IndexError, TypeError):
            continue
        is_head_fetch = any(
            isinstance(a, str) and a.startswith("HEAD:") for a in argv
        ) or ("cat-file" in argv and "--batch" in argv)
        if is_head_fetch:
            count += 1
    return count


class TestLoadHeadYamlGitCallCountIsConstant(unittest.TestCase):
    """Performance regression: HEAD-blob git subprocess count must be O(1) not O(N).

    The invariant: the number of git subprocesses that fetch HEAD AC content
    is CONSTANT regardless of how many staged-modified AC files there are.

    Failure mode of the bug (current code):
        N=3 staged-modified files → 3 separate ``git show HEAD:<path>`` calls.
        N=9 staged-modified files → 9 separate ``git show HEAD:<path>`` calls.
        The counts differ (3 ≠ 9) → RED.

    Expected behaviour after fix:
        N=3 staged-modified files → 1 ``git cat-file --batch`` call.
        N=9 staged-modified files → 1 ``git cat-file --batch`` call.
        The counts are equal (1 == 1) → GREEN.
    """

    def _run_phase2_with_n_files(
        self,
        n: int,
        mock_run_fn,
    ) -> tuple[int, list]:
        """Run the hook's main() with N staged-modified AC files; return git call count.

        Sets up:
          - Temp project root with N valid AC YAML files on disk.
          - HOOK_ROOT pointing to the temp root.
          - HOOK_TEST_FILES_MODIFIED with N repo-relative paths (one per file).
          - HOOK_TEST_STAGED_FILES set to empty string so Phase 1 is skipped
            and Phase 2 runs in isolation.
          - HOOK_NO_GIT unset so _get_modified_ac_paths / _load_head_yaml actually
            execute (they're intercepted by the patch, not real git).
          - Patches subprocess.run in the hook module with mock_run_fn.

        Args:
            n: Number of staged-modified AC files to simulate.
            mock_run_fn: Replacement for subprocess.run (callable).

        Returns:
            Tuple of (head_fetch_git_call_count, all_mock_calls).
        """
        ac_ids = [f"FIN-{i:03d}" for i in range(1, n + 1)]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel_paths = _make_ac_files(root, ac_ids)

            env_backup = {
                "HOOK_ROOT": os.environ.get("HOOK_ROOT"),
                "HOOK_TEST_FILES_MODIFIED": os.environ.get("HOOK_TEST_FILES_MODIFIED"),
                "HOOK_TEST_STAGED_FILES": os.environ.get("HOOK_TEST_STAGED_FILES"),
                "HOOK_NO_GIT": os.environ.get("HOOK_NO_GIT"),
                "HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED": os.environ.get(
                    "HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED"
                ),
            }
            try:
                os.environ["HOOK_ROOT"] = str(root)
                os.environ["HOOK_TEST_FILES_MODIFIED"] = os.pathsep.join(rel_paths)
                # Phase 1 is irrelevant to this test — skip it.
                os.environ["HOOK_TEST_STAGED_FILES"] = ""
                # HOOK_NO_GIT must be UNSET so the code reaches subprocess.run
                os.environ.pop("HOOK_NO_GIT", None)
                # Do NOT use the simulation shortcut — we need real code flow.
                os.environ.pop("HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED", None)

                # project_root inside the hook is resolved from HOOK_ROOT env.
                # The mock intercepts all subprocess.run calls in the module.
                mock_obj = MagicMock(side_effect=mock_run_fn)
                with patch.object(_hook_mod.subprocess, "run", mock_obj):
                    _hook_mod.main()

                all_calls = list(mock_obj.call_args_list)
            finally:
                # Restore environment
                for key, val in env_backup.items():
                    if val is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = val

        return _count_head_fetch_calls(all_calls), all_calls

    def test_ac_perf_head_fetch_count_constant_across_batch_sizes(self) -> None:
        # covers: UNKNOWN
        """HEAD-blob git subprocess count must be constant (O(1)) for N=3 and N=9.

        The invariant: count_for_N3 == count_for_N9 AND
                       1 <= count_for_N3 <= _MAX_GIT_CALLS.

        FAILS against current code: count_for_N3=3, count_for_N9=9 (one git
        show per file).  After the batch fix: both are 1 (one cat-file --batch).

        To make this test green:
            Replace the per-file ``git show HEAD:<path>`` calls in
            _load_head_yaml() with a single batched ``git cat-file --batch``
            invocation that fetches all N blob contents in one subprocess call.
        """
        mock_fn = _make_mock_subprocess_run()

        count_n3, _ = self._run_phase2_with_n_files(3, mock_fn)
        count_n9, _ = self._run_phase2_with_n_files(9, mock_fn)

        self.assertEqual(
            count_n3,
            count_n9,
            msg=(
                f"HEAD-blob git call count must be constant regardless of batch size, "
                f"but got {count_n3} for N=3 and {count_n9} for N=9. "
                f"Current code spawns one 'git show HEAD:<path>' per file (O(N)). "
                f"The fix must batch all fetches into one 'git cat-file --batch' call."
            ),
        )
        self.assertGreaterEqual(
            count_n3,
            1,
            msg=(
                f"HEAD-blob git call count must be >= 1 (at least one fetch happened), "
                f"but got {count_n3}.  A count of 0 means _load_head_yaml was never "
                f"called — check that the test fixture (HOOK_TEST_FILES_MODIFIED, "
                f"staged files on disk, HEAD mock response) correctly exercises Phase 2."
            ),
        )
        self.assertLessEqual(
            count_n3,
            _MAX_GIT_CALLS,
            msg=(
                f"HEAD-blob git call count must be <= {_MAX_GIT_CALLS} (constant bound), "
                f"but got {count_n3} for N=3.  This bound enforces the O(1) contract."
            ),
        )

    def test_ac_perf_correctness_violation_still_detected_after_batch(self) -> None:
        # covers: UNKNOWN
        """After batching, field-preservation correctness must be preserved.

        Regression guard: the batch fix must NOT silently return empty/wrong
        HEAD content.  When HEAD has implements_pattern set and the staged
        version drops it, the violation must still be detected (exit 1 or
        error reported).

        Setup: HEAD YAML (mock) contains implements_pattern: "PTN-001".
               Staged YAML (on disk) has no implements_pattern.
               → _check_implements_pattern_preserved should detect the drop.

        Because main() collects violations and returns 1, we verify that
        at least one violation was recorded for a 3-file batch.

        NOTE: The test monkey-patches subprocess.run and calls main() directly,
        so violations are detected in-process.  We capture the return code of
        main() to assert the drop was detected.
        """
        mock_fn = _make_mock_subprocess_run()
        ac_ids = _BATCH_3

        violation_detected = False
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Staged files: valid YAML WITHOUT implements_pattern.
            rel_paths = _make_ac_files(root, ac_ids, staged_yaml_tpl=_STAGED_AC_YAML)

            env_backup = {
                "HOOK_ROOT": os.environ.get("HOOK_ROOT"),
                "HOOK_TEST_FILES_MODIFIED": os.environ.get("HOOK_TEST_FILES_MODIFIED"),
                "HOOK_TEST_STAGED_FILES": os.environ.get("HOOK_TEST_STAGED_FILES"),
                "HOOK_NO_GIT": os.environ.get("HOOK_NO_GIT"),
                "HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED": os.environ.get(
                    "HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED"
                ),
            }
            try:
                os.environ["HOOK_ROOT"] = str(root)
                os.environ["HOOK_TEST_FILES_MODIFIED"] = os.pathsep.join(rel_paths)
                os.environ["HOOK_TEST_STAGED_FILES"] = ""
                os.environ.pop("HOOK_NO_GIT", None)
                os.environ.pop("HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED", None)

                mock_obj = MagicMock(side_effect=mock_fn)
                with patch.object(_hook_mod.subprocess, "run", mock_obj):
                    return_code = _hook_mod.main()

                violation_detected = return_code == 1
            finally:
                for key, val in env_backup.items():
                    if val is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = val

        self.assertTrue(
            violation_detected,
            msg=(
                "Correctness regression: when HEAD YAML has implements_pattern: 'PTN-001' "
                "and the staged version drops it, _check_implements_pattern_preserved must "
                "detect the violation and main() must return 1.  "
                "A return code of 0 means the batch fix silently returned empty/wrong "
                "HEAD content (correctness regressed)."
            ),
        )

    def test_ac_perf_no_violation_when_implements_pattern_preserved(self) -> None:
        # covers: UNKNOWN
        """After batching, a file that preserves implements_pattern must pass.

        Complementary correctness guard: when the staged file still has
        implements_pattern: "PTN-001" (same as HEAD), no violation must be
        reported and main() must return 0.
        """
        # Both HEAD and staged have implements_pattern: "PTN-001".
        _STAGED_WITH_PATTERN = textwrap.dedent("""\
            id: {ac_id}
            title: "Test AC {ac_id}"
            component: finalize
            status: active
            created_by: "tickets/test.md"
            criteria: |
              Given something
              When something
              Then something
            priority: medium
            readiness: draft
            implements_pattern: "PTN-001"
        """)
        mock_fn = _make_mock_subprocess_run()
        ac_ids = _BATCH_3

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rel_paths = _make_ac_files(root, ac_ids, staged_yaml_tpl=_STAGED_WITH_PATTERN)

            env_backup = {
                "HOOK_ROOT": os.environ.get("HOOK_ROOT"),
                "HOOK_TEST_FILES_MODIFIED": os.environ.get("HOOK_TEST_FILES_MODIFIED"),
                "HOOK_TEST_STAGED_FILES": os.environ.get("HOOK_TEST_STAGED_FILES"),
                "HOOK_NO_GIT": os.environ.get("HOOK_NO_GIT"),
                "HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED": os.environ.get(
                    "HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED"
                ),
            }
            try:
                os.environ["HOOK_ROOT"] = str(root)
                os.environ["HOOK_TEST_FILES_MODIFIED"] = os.pathsep.join(rel_paths)
                os.environ["HOOK_TEST_STAGED_FILES"] = ""
                os.environ.pop("HOOK_NO_GIT", None)
                os.environ.pop("HOOK_SIMULATE_IMPLEMENTS_PATTERN_DROPPED", None)

                mock_obj = MagicMock(side_effect=mock_fn)
                with patch.object(_hook_mod.subprocess, "run", mock_obj):
                    return_code = _hook_mod.main()
            finally:
                for key, val in env_backup.items():
                    if val is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = val

        self.assertEqual(
            return_code,
            0,
            msg=(
                "When staged files PRESERVE implements_pattern (same value as HEAD), "
                "no violation should be reported and main() must return 0.  "
                "A non-zero return code means the batch fix incorrectly parsed "
                "the HEAD content or staged content."
            ),
        )


if __name__ == "__main__":
    unittest.main()
