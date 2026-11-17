"""
MODULE: unit_tests/commit_guardian/_ge_127f_3_fixture.py
COVERS: GE-127f-3 (shared fixture module -- carries no tests of its own)

GOAL: Helpers shared by test_ge_127f_3.py and test_ge_127f_3_mutations.py: the
    named arms in the AC's own measured lines, a reader that pulls ONE refused
    file's block out of a real commit's output, the two disposition phrases
    the refusal states, and the two named mutations applied to a fixture-owned
    copy of check_file_size.py (never the tracked template).

REUSED, NOT REINVENTED. Every repo is a real single-hook pre-commit fixture
    from `_ge_127f_1_fixture` (itself built on
    `_ge_127a_1_ordinary_commit_fixture`), and every content change removes
    or inserts whole one-statement definitions via its `replace_leading_span`,
    never blank lines or '#' comments.

THE ARITHMETIC, ONCE. ``replace_leading_span(base, remove, insert)`` adds
    ``insert`` measured lines and leaves ``previous - remove + insert``. The
    demand a refusal states is the refused length less the length required:
    ``max(limit, previous - added)`` for an already-oversized file, the limit
    for a file that crosses it.

DECISION HISTORY
- 2026-11-17 [GE-127f-3]: Initial authoring.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
import _ge_127f_1_fixture as fx  # noqa: E402

OVERSIZED = fx.OVERSIZED_BASELINE  # 2,677 measured lines
NEAR = fx.CAPPED_BASELINE  # 410 measured lines
LIMIT = fx.PERMITTED_LENGTH  # 400

AUTHOR = "the author may take it out inside this change"
SPECIALIST = "handed to a restructuring specialist"

# (filename, previous length, lines removed, lines inserted) -> demand stated.
ARMS = {
    "big_one.py": ((OVERSIZED, 1, 1), 1),  # 2677 -> 2677, added 1, required 2676
    "big_fifty.py": ((OVERSIZED, 50, 50), 50),  # 2677 -> 2677, added 50, required 2627
    "near_one.py": ((NEAR, 1, 1), 1),  # 410 -> 410, added 1, required 409
    "near_ten.py": ((NEAR, 10, 10), 10),  # 410 -> 410, added 10, required max(400, 400)
    "crossing.py": ((395, 0, 15), 10),  # 395 -> 410: crosses the limit, too_large path
}


def contents(filename: str) -> tuple[str, str]:
    """Return (baseline, staged change) for one named arm."""
    (previous, removed, inserted), _ = ARMS[filename]
    baseline = fx.function_lines(previous, tag="v")
    return baseline, fx.replace_leading_span(baseline, removed, inserted, "w")


def build_repo(root: Path, filenames: list[str], verbose: bool = True) -> None:
    """Commit each arm's baseline as HEAD, then install the real hook."""
    baselines = {name: contents(name)[0] for name in filenames}
    fx.build_repo_with_baselines(root, baselines, verbose=verbose)


def commit_arms(root: Path, filenames: list[str], message: str):
    """Stage every named arm's change and run one REAL, ordinary git commit."""
    return fx.stage_changes_and_commit(root, {name: contents(name)[1] for name in filenames}, message)


def block_for(output: str, filename: str) -> str:
    """Return the refusal block whose first named path is *filename*, or ''."""
    for chunk in output.split("❌ ")[1:]:
        lines = chunk.splitlines()
        if len(lines) > 1 and lines[1].strip() == filename:
            return chunk
    return ""


def demand_line(lines_to_remove: int) -> str:
    """The sentence a refusal uses to state how much must leave the file."""
    return f"Must leave the file: {lines_to_remove} measured line(s)."


def check_file_size_copy(root: Path) -> Path:
    """The fixture's own copy of the hook (never the tracked template)."""
    return fx1.check_file_size_path(root)


def mutate(root: Path, target: str, replacement: str) -> str:
    """Replace one exact, unique *target* in the fixture copy; return the original.

    Raises AssertionError when the target is absent or ambiguous, so an
    injection can never silently become a no-op.
    """
    path = check_file_size_copy(root)
    original = path.read_text(encoding="utf-8")
    count = original.count(target)
    if count != 1:
        message = f"mutation target found {count} times (expected 1): {target!r}"
        raise AssertionError(message)
    path.write_text(original.replace(target, replacement), encoding="utf-8")
    return original


# THE LOOPHOLE: exempt a change from the end-state rule when what it added is
# at or below the threshold, instead of only routing the work to the author.
LOOPHOLE_TARGET = "        if lines > required:\n"
LOOPHOLE_REPLACEMENT = "        if lines > required and added > AUTHOR_CLEARABLE_DEMAND:\n"

# THE BAND: hand every demand to the restructuring specialist.
BAND_TARGET = "AUTHOR_CLEARABLE_DEMAND = 5\n"
BAND_REPLACEMENT = "AUTHOR_CLEARABLE_DEMAND = 0\n"


def discard_uncommitted(root: Path) -> None:
    """Drop a refused change from the fixture's index and tracked files (temp repo only)."""
    fx1.git(["reset", "-q", "--hard", "HEAD"], root)


def restore(root: Path, original: str) -> None:
    """Put the fixture copy back exactly as it was before a mutation."""
    check_file_size_copy(root).write_text(original, encoding="utf-8")


def copy_deployed_guardian(deployed: Path, root: Path) -> None:
    """Copy the DEPLOYED commit_guardian directory into a fresh fixture repo."""
    shutil.copytree(deployed, root / "scripts" / "commit_guardian", ignore=shutil.ignore_patterns("__pycache__"))
