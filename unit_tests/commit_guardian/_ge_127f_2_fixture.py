"""
MODULE: unit_tests/commit_guardian/_ge_127f_2_fixture.py
COVERS: GE-127f-2 (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders shared by test_ge_127f_2_arms.py,
    test_ge_127f_2_seam_and_mutation.py, and
    test_ge_127f_2_reachability_and_deployed.py -- the descriptors that
    distinguish GROSS added lines (what the change PUT INTO the file) from
    NET growth (current length minus previous length), per GE-127f-2's own
    Implementation Notes: "GROSS, NEVER NET, AND NEVER THE SUBTRACTION THAT
    IS ALREADY IN HAND."

WHY FUNCTION-DEFINITION LINES, NOT BLANK LINES OR '#' COMMENTS. Every
    fixture body here is built from ``function_lines`` -- one-line
    ``def tag_NNNNNN(): return NNNNNN`` statements, each a genuine
    constituent definition. GE-127f-2's own Implementation Notes forbid
    reaching the 560 arm or the delete-only arm by deleting blank lines or
    '#' comments (both counted by ``count_content_lines``, so that route
    would be cheap and would not exercise a real content change). Deleting
    or replacing a subset of these one-line function defs is a genuine,
    unambiguous content change under any line-oriented diff.

WHY A LEADING TRIPLE-QUOTED DOCSTRING FOR THE UNMEASURED-CONTENT ARM AND FOR
    GE-127b-1's NARROWED BOUNDARY DESCRIPTOR. ``count_content_lines`` strips
    triple-quoted regions entirely (see _file_size_ratchet.py), so content
    added or changed ONLY inside such a block contributes zero measured
    lines and zero measured "added" lines under ANY correct diff-based
    count. ``docstring_only_edit_content`` here and test_ge_127b_1.py's own
    local, in-file ``_content(..., docstring=...)`` build the SAME SHAPE
    (unmeasured docstring wrapper around otherwise-identical measured
    lines) -- kept as two small, independent definitions rather than one
    shared import, because importing this module into test_ge_127b_1.py
    would itself grow that file's own counted length past its ratcheted
    previous length (see that file's DECISION HISTORY). See this ticket's
    Implementation Notes, "GE-127b-1's DELIVERED BOUNDARY DESCRIPTOR IS
    RECONCILED IN THIS SAME CHANGE".

REUSED, NOT REINVENTED. The disposable-copy mutation harness
    (``build_mutated_disposable_repo``) imports
    ``_ge_127a_1_ordinary_commit_fixture`` (its ``PRODUCTION_MODULES``
    tuple and ``copy_production_modules`` -- architect-review confirmed by
    grep that this list already includes ``_file_size_ratchet.py`` and needs
    no edit under the expected implementation path) and
    ``_ge_127e_3_fixture``'s ``_insert_before_main_guard`` idiom (never an
    EOF append -- ``check_file_size.py`` ends in
    ``if __name__ == "__main__": sys.exit(main())``, so anything appended
    after that guard is dead code a real run never reaches).

DECISION HISTORY
- 2026-09-28 [GE-127f-2/test-writer]: Initial authoring.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
from _ge_127e_3_fixture import _insert_before_main_guard  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_CHECK_FILE_SIZE = _COMMIT_GUARDIAN_DIR / "check_file_size.py"
_RUN_HOOK = _COMMIT_GUARDIAN_DIR / "run_hook.py"
_BUILD_PY = _REPO_ROOT / "scripts" / "build.py"

_PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 180

# The Gherkin's own two pinned numbers: 600 measured lines standing against a
# 400-line permitted length -- not read from the real, tracked
# commit_guardian.json (which may drift), and not re-derived, so every
# descriptor in this record shares the exact numbers the AC states.
BASELINE_LENGTH = 600
PERMITTED_LENGTH = 400


# ---------------------------------------------------------------------------
# Git plumbing -- a real repo, real commits, real staging.
# ---------------------------------------------------------------------------


def git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def init_repo(root: Path) -> None:
    """Initialize a real git repository with a deterministic identity."""
    git(["init", "-q"], root)
    git(["config", "user.email", "test-writer@example.com"], root)
    git(["config", "user.name", "GE-127f-2 test fixture"], root)


def commit_all(root: Path, message: str) -> None:
    """Stage everything and make a real commit."""
    git(["add", "-A"], root)
    git(["commit", "-q", "-m", message], root)


def stage_all(root: Path) -> None:
    """Stage everything without committing."""
    git(["add", "-A"], root)


def establish_baseline(root: Path, content: str, filename: str = "big.py") -> Path:
    """Write *content* to *filename* and commit it as the repo's HEAD state."""
    target = root / filename
    target.write_text(content, encoding="utf-8")
    commit_all(root, "establish baseline covered file")
    return target


# ---------------------------------------------------------------------------
# Content builders -- whole constituent definitions, never blank/'#' lines.
# ---------------------------------------------------------------------------


def function_lines(n_lines: int, tag: str = "v", start: int = 0) -> str:
    """n_lines one-line function definitions, each a genuine constituent.

    No blank line, no '#' comment, no triple-quote or block-comment
    delimiter appears anywhere -- so the measured (count_content_lines)
    length of the result is EXACTLY n_lines, and deleting or replacing any
    subset removes/changes whole constituent definitions, never the
    cheap-route content this AC's Implementation Notes forbid.
    """
    return "\n".join(f"def {tag}_{i:06d}(): return {i}" for i in range(start, start + n_lines)) + "\n"


def replace_leading_lines(base_content: str, count: int, new_tag: str) -> str:
    """Replace the first *count* lines of *base_content* with *count* freshly
    tagged function definitions, leaving the total line count unchanged.

    Used for the two refused arms: replacing 5-for-5 or 40-for-40 leaves the
    file's measured length exactly where it stood, while the content of
    those lines is genuinely different -- a real, unambiguous diff.
    """
    lines = base_content.splitlines()
    lines[:count] = function_lines(count, tag=new_tag).splitlines()
    return "\n".join(lines) + "\n"


def drop_trailing_lines(content: str, count: int) -> str:
    """Remove the LAST *count* lines of *content* -- whole constituent
    definitions, never blank lines or '#' comments."""
    lines = content.splitlines()
    del lines[len(lines) - count : len(lines)]
    return "\n".join(lines) + "\n"


def docstring_only_edit_content(n_lines: int, tag: str, docstring_text: str) -> str:
    """*n_lines* measured function definitions, preceded by a triple-quoted
    docstring holding *docstring_text* -- entirely stripped by
    ``count_content_lines``, so changing ONLY this text between two
    revisions changes zero measured lines and adds zero measured lines
    under any correct diff-based count.

    Shared verbatim between this record's "adding only unmeasured content"
    arm and test_ge_127b_1.py's amended, narrowed boundary descriptor -- see
    this module's docstring for why sharing (not approximating twice)
    matters here.
    """
    return f'"""\n{docstring_text}\n"""\n' + function_lines(n_lines, tag=tag)


# ---------------------------------------------------------------------------
# Invocation -- the real, source-tree production script, never the added
# -count computation called in isolation.
# ---------------------------------------------------------------------------


def run_check(root: Path) -> subprocess.CompletedProcess:
    """Invoke the REAL check_file_size.py against staged content in *root*."""
    return subprocess.run(
        [_PYTHON, str(_CHECK_FILE_SIZE)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def run_check_via_hook(root: Path) -> subprocess.CompletedProcess:
    """Invoke check_file_size.py through the REAL, registered run_hook.py
    wrapper -- the production entry point a real commit dispatches through."""
    return subprocess.run(
        [_PYTHON, str(_RUN_HOOK), str(_CHECK_FILE_SIZE)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Outcome assertions -- read from the real process output, never a guess at
# an exact sentence python-coder has not written yet.
# ---------------------------------------------------------------------------


def assert_added_lines_stated(testcase, combined_output: str, added: int) -> None:
    """Assert the outcome states the change added *added* line(s), read from
    the process's own output near the word "added"."""
    pattern = rf"(?i)\badded\b(?:[^\n]{{0,60}})\b{added}\b|\b{added}\b(?:[^\n]{{0,60}})\badded\b"
    testcase.assertRegex(
        combined_output,
        pattern,
        msg=f"Outcome must state the change added {added} line(s). Got: {combined_output!r}",
    )


def assert_required_length_stated(testcase, combined_output: str, required: int) -> None:
    """Assert the outcome states the file is required to stand at *required*
    (or below), read from the process's own output."""
    pattern = (
        rf"(?i)\b{required}\b(?:[^\n]{{0,60}})\b(requir|stand|below|limit)|"
        rf"\b(requir|stand|below)(?:[^\n]{{0,60}})\b{required}\b"
    )
    testcase.assertRegex(
        combined_output,
        pattern,
        msg=(
            f"Outcome must state the file is required to stand at {required} "
            f"(or below). Got: {combined_output!r}"
        ),
    )


_REFUSAL_MARKER_RE = re.compile(r"(?i)(too large|grew|refused|❌)")


def assert_commits_cleanly_and_unreported(testcase, result: subprocess.CompletedProcess, filename: str) -> None:
    """Assert *result* is a clean commit (exit 0) and *filename* is never
    named near a refusal marker -- "nothing further is required" means no
    refusal block for this file at all, not merely a passing exit code."""
    testcase.assertEqual(
        0,
        result.returncode,
        msg=f"Expected a clean commit. stdout={result.stdout!r} stderr={result.stderr!r}",
    )
    for marker in _REFUSAL_MARKER_RE.finditer(result.stdout):
        window = result.stdout[max(0, marker.start() - 200) : marker.end() + 200]
        testcase.assertNotIn(
            filename,
            window,
            msg=f"{filename} must not be named near a refusal marker. Got: {window!r}",
        )


# ---------------------------------------------------------------------------
# Disposable-copy mutation harness -- the NAMED MUTATION, self-contained.
# ---------------------------------------------------------------------------

# The BA's injection, carried verbatim: "compute the number of lines the
# change added as the file's net growth -- the length after the change minus
# the length before it, floored at zero -- instead of reading it from what
# the change put into the file." This is a FULL, self-contained override of
# _classify_file that never string-matches or depends on python-coder's own
# added-count implementation -- it only uses count_lines/get_limit_for_extension,
# both stable, pre-existing module names -- so it exercises the forbidden
# formula regardless of how the correct gross count ends up wired in.
_NET_GROWTH_CLASSIFY_OVERRIDE = '''
# TEST-INJECTED NAMED MUTATION (GE-127f-2/test-writer): compute "added" as the
# file's net growth (current length minus previous length, floored at zero)
# instead of reading it from what the change put into the file.
def _classify_file(filepath, previous_lengths, *args, **kwargs):  # noqa: F811 -- intentional test override
    lines = count_lines(filepath)
    limit = get_limit_for_extension(filepath)
    previous = previous_lengths.get(filepath)
    if previous is not None and previous > limit:
        added = max(0, lines - previous)
        required = previous - added
        if lines > required:
            return "grew", lines, previous
        return "pass", lines, None
    if lines > limit:
        return "too_large", lines, limit
    return "pass", lines, None
'''


def build_mutated_disposable_repo(root: Path, line_limit: int = PERMITTED_LENGTH) -> None:
    """Build a disposable, git-repo-local copy of the production gate at
    *root*, with the NAMED MUTATION applied to its OWN copy of
    check_file_size.py -- never to templates/scripts/commit_guardian/ itself.

    Reuses _ge_127a_1_ordinary_commit_fixture's already-verified
    PRODUCTION_MODULES list and copy_production_modules -- architect-review
    confirmed by grep this list already includes _file_size_ratchet.py and
    needs no edit under the expected implementation path (the new
    added-count function lands beside count_content_lines in that same,
    already-copied module).
    """
    fx1.copy_production_modules(root)
    fx1.write_config_json(root, line_limit)
    _insert_before_main_guard(root / "scripts" / "commit_guardian", _NET_GROWTH_CLASSIFY_OVERRIDE)
    init_repo(root)


def run_check_in_disposable(root: Path) -> subprocess.CompletedProcess:
    """Invoke *root*'s own disposable, mutated copy of check_file_size.py."""
    script = root / "scripts" / "commit_guardian" / "check_file_size.py"
    return subprocess.run(
        [_PYTHON, str(script)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )
