"""
MODULE: unit_tests/commit_guardian/_ge_127f_1_fixture.py
COVERS: GE-127f-1 (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders shared by test_ge_127f_1_refusal_and_allow.py,
    test_ge_127f_1_cap_and_free_arms.py, test_ge_127f_1_mutations.py, and
    test_ge_127f_1_reachability_and_deployed.py -- the descriptors proving
    ``required = max(limit, previous - added)`` (architect-review's 2026-09-30
    11:27 ruling 2, this ticket's own comment): the "less demanding of" the
    permitted length and the previous length minus what the change added.

WHY REAL `git commit` THROUGH A SINGLE-HOOK `.pre-commit-config.yaml`, FOR
    EVERY DESCRIPTOR, RATHER THAN `_ge_127f_2_fixture.py`'s bare
    `run_check()` subprocess call. Architect-review's ruling 4 on this ticket
    binds explicitly: "Every descriptor must run a real `git commit` through
    the established `.pre-commit-config.yaml` fixture pattern
    (`_ge_127a_1_ordinary_commit_fixture.py`'s shape) ... never a source-grep
    or a direct call to the threshold arithmetic." This module therefore
    builds on `_ge_127a_1_ordinary_commit_fixture` (imported as ``fx1``) for
    the real-commit-through-pre-commit machinery, and reuses
    `_ge_127f_2_fixture` (imported as ``fx2``) only for its whole
    -constituent-definition content builders (``function_lines``,
    ``replace_leading_lines``, ``drop_trailing_lines``) and its two output
    -reading assertion helpers -- never for its bare-subprocess `run_check`.

WHY WHOLE CONSTITUENT DEFINITIONS, NEVER BLANK LINES OR '#' COMMENTS. Same
    reasoning as `_ge_127f_2_fixture.py`'s own module docstring:
    ``count_content_lines`` counts blank lines and `#` comments, so deleting
    or inserting either is the cheapest, and forbidden, route to any arm
    whose commit must complete. ``replace_leading_span`` below generalises
    `_ge_127f_2_fixture.py`'s own ``replace_leading_lines`` to an unequal
    remove/insert count, which is what most of this record's arms need (a
    same-length replacement is only one of seven shapes here).

THE ARITHMETIC BEHIND EVERY ARM, WORKED ONCE HERE RATHER THAN PER TEST.
    ``replace_leading_span(base, remove_count, insert_count, tag)`` removes
    exactly ``remove_count`` leading lines and inserts exactly
    ``insert_count`` freshly tagged lines in their place, in one contiguous
    block. Because the untouched remainder is byte-identical before and
    after, ``difflib.SequenceMatcher`` (the real gross-added counter,
    ``count_added_measured_lines`` in `_file_size_ratchet.py`) reports this
    as a single "replace" opcode: gross added = ``insert_count``, and the
    resulting length = ``previous - remove_count + insert_count``. Every
    arm's ``remove_count`` is solved from the AC's own three pinned numbers
    (previous, added, after) by that one identity.

REUSED, NOT REINVENTED. The two NAMED MUTATION appliers below patch
    `_classify_file`'s oversized-file branch in a fixture-owned copy of
    `check_file_size.py` on disk, exactly mirroring
    `_ge_127a_1_ordinary_commit_fixture.py`'s own
    ``apply_mutation_refuse_regardless_of_length`` /
    ``restore_check_file_size`` shape: locate a known source target and
    replace it, raising loudly if not found rather than silently turning
    the injection into a no-op. THE CAP injection (``apply_cap_injection``)
    targets an exact, known full line (``_FIXED_REQUIRED_LINE``), which is
    correct because that line's own shape IS the fact under test. THE
    MULTIPLIER injection (``apply_multiplier_injection``) instead targets
    just the `previous - added` OPERAND wherever it appears inside a
    `required = ...` assignment, because an exact-line target for it went
    stale once already (see that function's own docstring for the full
    reasoning and the correctness argument for why an operand-level
    substitution remains exactly equivalent under any wrapper).

DECISION HISTORY
- 2026-09-30 [GE-127f-1/test-writer]: Initial authoring.
- 2026-09-30 [GE-127f-1/test-writer, round 2]: python-coder's fix (`required
  = previous - added` -> `required = max(limit, previous - added)`)
  hardcoded `apply_multiplier_injection`'s patch target, pinned to the
  PRE-fix line, stale. Rewrote it to match the `previous - added` operand
  generically via ``_REQUIRED_ASSIGNMENT_WITH_OPERAND_RE`` rather than a
  hardcoded full line, so it continues to find and patch the live
  comparison regardless of which side of GE-127f-1's fix the fixture's copy
  reflects. Classification: test_drift (production is correct per
  architect-review's ruling 2; only this fixture's target was stale).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127a_1_ordinary_commit_fixture as fx1  # noqa: E402
import _ge_127f_2_fixture as fx2  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parents[2]
_COMMIT_GUARDIAN_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"

PYTHON = fx1.PYTHON
BUILD_PY = fx1._BUILD_PY
PERMITTED_LENGTH = 400

# The AC's own pinned baselines (GE-127f-1.yaml's worked arithmetic, and this
# ticket's Gherkin), never re-derived.
OVERSIZED_BASELINE = 2677
CAPPED_BASELINE = 410
UNDER_LIMIT_BASELINE = 380


# ---------------------------------------------------------------------------
# Single-hook fixture repo -- an ordinary `git commit` reaches ONLY the real
# check-file-size gate, per `_ge_127a_1_ordinary_commit_fixture.py`'s own
# GE-127a-1 coverage-gap fix.
# ---------------------------------------------------------------------------


def build_hook_repo(root: Path, line_limit: int = PERMITTED_LENGTH) -> None:
    """Build (but do NOT yet install) a single-hook pre-commit fixture at
    *root*. Callers MUST establish any HEAD baseline via
    ``establish_baseline``/``establish_baselines`` BEFORE calling
    ``install_hook`` -- see this module's ``install_hook`` docstring for why.
    """
    fx1.copy_production_modules(root)
    fx1.write_config_json(root, line_limit)
    fx1.write_precommit_config(root)
    fx1.init_repo(root)


def build_hook_repo_verbose(root: Path, line_limit: int = PERMITTED_LENGTH) -> None:
    """Like ``build_hook_repo``, but with `verbose: true` on the one hook,
    and likewise NOT yet installed -- see ``install_hook``.

    `pre-commit` suppresses a passing hook's own stdout by default -- see
    this ticket's sign-off comment for the empirical confirmation
    (test_ge_127a_1's own under-limit descriptor relies on exactly this
    suppression). The two-injection proof needs to read per-file output
    regardless of whether the OVERALL commit passes or fails, so it alone
    uses this verbose variant.
    """
    fx1.copy_production_modules(root)
    fx1.write_config_json(root, line_limit)
    body = (
        "repos:\n"
        "  - repo: local\n"
        "    hooks:\n"
        "      - id: check-file-size\n"
        "        name: Check File Size\n"
        "        entry: python scripts/commit_guardian/run_hook.py "
        "scripts/commit_guardian/check_file_size.py\n"
        "        language: system\n"
        "        pass_filenames: false\n"
        "        always_run: true\n"
        "        verbose: true\n"
    )
    (root / ".pre-commit-config.yaml").write_text(body, encoding="utf-8")
    fx1.init_repo(root)


def install_hook(root: Path) -> None:
    """Install the real pre-commit git hook at *root*, AFTER any oversized
    baseline has already entered HEAD.

    THE GRANDFATHER PROBLEM, AND WHY THIS ORDERING IS CORRECT, NOT A
    WORKAROUND. `check_file_size.py` has no "already exists, exempt it"
    clause for a file with no previous-length history at all (a HEAD blob
    that does not exist -- see `_classify_file`: the oversized-comparison
    branch only fires when ``previous is not None``) -- a BRAND NEW file
    over its permitted length is refused exactly like any other growth, via
    the plain `too_large` branch. So an already-oversized "previous" state
    can only ever enter this fixture's HEAD BEFORE the hook exists to guard
    it -- which is the faithful, real-world shape of "already-oversized" in
    the first place: every one of this actual repository's 212 oversized
    tracked files (architect-review's own census, this ticket's
    Implementation Notes) pre-dates `check-file-size` ever being installed
    on it, or was added by a commit made before the file grew past the
    limit. Installing the hook only after the baseline commit models that
    history precisely; it does not weaken "a REAL, ordinary `git commit`"
    for the CHANGE under test, which is the only commit any descriptor here
    ever asserts on.
    """
    fx1.install_precommit(root)


def establish_baseline(root: Path, content: str, filename: str = "big.py") -> Path:
    """Write *content* to *filename* and commit it as the repo's HEAD state
    via a REAL, ordinary `git commit`."""
    target = root / filename
    target.write_text(content, encoding="utf-8")
    fx1.stage(root, [filename])
    result = fx1.commit(root, f"establish baseline for {filename}")
    assert result.returncode == 0, (
        f"baseline commit for {filename} failed: {result.stdout}{result.stderr}"
    )
    return target


def establish_baselines(root: Path, contents_by_filename: dict[str, str]) -> None:
    """Write every (filename -> content) pair and commit them ALL together
    in one REAL, ordinary `git commit` -- one shared HEAD for every named
    arm in a combined-repo descriptor."""
    for filename, content in contents_by_filename.items():
        (root / filename).write_text(content, encoding="utf-8")
    fx1.stage(root, list(contents_by_filename))
    result = fx1.commit(root, "establish baselines for combined arms")
    assert result.returncode == 0, f"combined baseline commit failed: {result.stdout}{result.stderr}"


def build_repo_with_baseline(
    root: Path, baseline_content: str, filename: str = "big.py", line_limit: int = PERMITTED_LENGTH
) -> None:
    """Compose a fresh single-hook fixture repo, commit *baseline_content*
    as HEAD, THEN install the real git hook -- see ``install_hook``'s
    docstring for why an oversized baseline must precede hook installation.
    """
    build_hook_repo(root, line_limit)
    establish_baseline(root, baseline_content, filename)
    install_hook(root)


def build_repo_with_baselines(
    root: Path, contents_by_filename: dict[str, str], line_limit: int = PERMITTED_LENGTH, verbose: bool = False
) -> None:
    """Like ``build_repo_with_baseline``, for several named-arm files
    committed together as one shared HEAD before the hook is installed."""
    if verbose:
        build_hook_repo_verbose(root, line_limit)
    else:
        build_hook_repo(root, line_limit)
    establish_baselines(root, contents_by_filename)
    install_hook(root)


def stage_change_and_commit(root: Path, filename: str, new_content: str, message: str):
    """Overwrite *filename* with *new_content* and perform a REAL, ordinary
    `git commit` -- the production entry point every arm here exercises."""
    (root / filename).write_text(new_content, encoding="utf-8")
    fx1.stage(root, [filename])
    return fx1.commit(root, message)


def stage_changes_and_commit(root: Path, contents_by_filename: dict[str, str], message: str):
    """Like ``stage_change_and_commit``, for several files staged and
    committed together in one REAL, ordinary `git commit`."""
    for filename, content in contents_by_filename.items():
        (root / filename).write_text(content, encoding="utf-8")
    fx1.stage(root, list(contents_by_filename))
    return fx1.commit(root, message)


# ---------------------------------------------------------------------------
# Content builders -- whole constituent definitions, never blank/'#' lines.
# ---------------------------------------------------------------------------


def replace_leading_span(base_content: str, remove_count: int, insert_count: int, new_tag: str) -> str:
    """Remove *remove_count* leading lines of *base_content* and insert
    *insert_count* freshly tagged lines in their place, as ONE contiguous
    block -- so the real gross-added counter
    (``count_added_measured_lines``) reports a single replace opcode:
    added = insert_count, and the result's length =
    ``len(base_content) - remove_count + insert_count``. ``remove_count=0``
    is a pure insertion at the front; both are genuine, unambiguous content
    changes under any line-oriented diff, never a blank-line or '#'-comment
    manoeuvre.
    """
    lines = base_content.splitlines()
    lines[:remove_count] = fx2.function_lines(insert_count, tag=new_tag).splitlines()
    return "\n".join(lines) + "\n"


def function_lines(n_lines: int, tag: str = "v") -> str:
    """Re-exported from `_ge_127f_2_fixture` for callers that only need this
    one builder, so they need not import both fixture modules by name."""
    return fx2.function_lines(n_lines, tag=tag)


def drop_trailing_lines(content: str, count: int) -> str:
    """Re-exported from `_ge_127f_2_fixture` -- see that module's docstring."""
    return fx2.drop_trailing_lines(content, count)


# ---------------------------------------------------------------------------
# The seven named arms, expressed once, in the AC's own pinned quantities.
#
# Each triple is (previous, added, after); remove_count solves from the
# identity previous - remove_count + insert_count(=added) == after, i.e.
# remove_count = previous + added - after. Worked in this module's own
# docstring's "THE ARITHMETIC BEHIND EVERY ARM" section.
# ---------------------------------------------------------------------------


def arm_content(previous: int, added: int, after: int, tag: str = "w") -> tuple[str, str]:
    """Return (baseline_content, after_content) for one named arm, built
    from ``function_lines``/``replace_leading_span`` per this module's own
    worked arithmetic. ``added == 0`` with ``after < previous`` is a pure
    trailing deletion (never a replace with insert_count=0, which would
    still be a valid but needlessly different shape)."""
    baseline = fx2.function_lines(previous, tag="v")
    if added == 0:
        after_content = fx2.drop_trailing_lines(baseline, previous - after)
        return baseline, after_content
    remove_count = previous + added - after
    after_content = replace_leading_span(baseline, remove_count, added, tag)
    return baseline, after_content


# The AC's own seven pinned (previous, added, after) triples.
ARM_A_2628_REFUSED = (OVERSIZED_BASELINE, 50, 2628)  # refused, required=2627
ARM_B_EXACTLY_2677_REFUSED = (OVERSIZED_BASELINE, 50, OVERSIZED_BASELINE)  # refused, required=2627
ARM_C_2627_COMMITS = (OVERSIZED_BASELINE, 50, 2627)  # commits, required=2627
ARM_D_CAPPED_AT_400_COMMITS = (CAPPED_BASELINE, 50, 400)  # commits, required=max(400,360)=400
ARM_E_401_REFUSED = (CAPPED_BASELINE, 50, 401)  # refused, required=400
ARM_F_ZERO_ADD_2674_COMMITS = (OVERSIZED_BASELINE, 0, 2674)  # commits, required=2677
ARM_G_UNDER_LIMIT_392_SILENT = (UNDER_LIMIT_BASELINE, 12, 392)  # not in this population at all


assert ARM_A_2628_REFUSED[0] + ARM_A_2628_REFUSED[1] - ARM_A_2628_REFUSED[2] == 99, "fixture sanity: arm A remove_count"
assert ARM_C_2627_COMMITS[0] + ARM_C_2627_COMMITS[1] - ARM_C_2627_COMMITS[2] == 100, "fixture sanity: arm C remove_count"
assert (
    ARM_D_CAPPED_AT_400_COMMITS[0] + ARM_D_CAPPED_AT_400_COMMITS[1] - ARM_D_CAPPED_AT_400_COMMITS[2] == 60
), "fixture sanity: arm D remove_count (the Gherkin's own '60 lines leaving the file')"
assert ARM_E_401_REFUSED[0] + ARM_E_401_REFUSED[1] - ARM_E_401_REFUSED[2] == 59, "fixture sanity: arm E remove_count"


# ---------------------------------------------------------------------------
# NAMED MUTATIONS -- patched on the fixture's OWN on-disk copy of
# check_file_size.py, never templates/scripts/commit_guardian/ itself.
# ---------------------------------------------------------------------------

# BA's injection 2, THE MULTIPLIER, carried verbatim: "judge the file against
# its previous length alone -- GE-127b's shipped comparison, unchanged."
# Drops the added-line term entirely.
#
# TARGETS THE OPERAND, NOT A HARDCODED FULL LINE -- DELIBERATE, NOT THE
# FIRST THING THAT WORKED. python-coder's 2026-09-30 12:26 handoff found
# this injection's original target -- the exact PRE-fix line
# `        required = previous - added\n` -- stale the moment GE-127f-1's
# fix landed and rewrote that line to
# `        required = max(limit, previous - added)\n`. Two fixes were
# offered: hardcode the new full line (what the CAP injection's own
# `_FIXED_REQUIRED_LINE` below already does), or match just the
# `previous - added` operand regardless of what wraps it. This module
# chooses the operand match for THE MULTIPLIER specifically because a
# full-line target is a recurring tax -- this is the SECOND time in this
# epic an injection has gone stale against its own target (the first was
# ticket 07/GE-127f-2's inverted-polarity injection) -- while the operand
# match survives the next reformulation of the wrapper (a renamed `limit`,
# a helper function, a different clamp shape) as long as `previous - added`
# remains a literal subexpression of the `required = ...` assignment.
#
# WHY THE SUBSTITUTION IS STILL CORRECT UNDER ANY SUCH WRAPPER: the
# oversized-branch this line lives in only executes when
# `previous > limit` (see `_classify_file`'s own guard). So
# `max(limit, previous)` and the bare `previous` this substitution produces
# are the SAME value at every call site this branch ever reaches --
# replacing only the operand, leaving any `max(limit, ...)` wrapper
# untouched, is therefore exactly equivalent to "judge the file against its
# previous length alone," not merely an approximation of it.
_REQUIRED_ASSIGNMENT_WITH_OPERAND_RE = re.compile(
    r"^([ \t]*required = .*previous - added.*)$",
    re.MULTILINE,
)
_MULTIPLIER_OPERAND = "previous - added"
_MULTIPLIER_OPERAND_REPLACEMENT = "previous"

# The FIXED formula this ticket's implementation is expected to land
# (architect-review ruling 2, verbatim): `required = max(limit, previous -
# added)`. Only present in the fixture's copy AFTER python-coder's fix has
# landed and been copied in by `fx1.copy_production_modules` -- absent
# before that, which is the TRUE, honest pre-implementation red state for
# the CAP injection (see this ticket's sign-off comment).
_FIXED_REQUIRED_LINE = "        required = max(limit, previous - added)\n"

# BA's injection 1, THE CAP, carried verbatim: "judge the file against the
# previous length minus the lines added, unconditionally, ignoring the
# permitted length -- drop the 'less demanding of' and keep only the
# subtraction." Applied to the FIXED formula, this recovers the CURRENT,
# uncapped line above.
_CAP_REPLACEMENT = "        required = previous - added\n"


def check_file_size_path(root: Path) -> Path:
    """Return the path to the fixture's own copy of check_file_size.py."""
    return root / "scripts" / "commit_guardian" / "check_file_size.py"


def apply_multiplier_injection(root: Path) -> str:
    """BA's injection 2: drop the added-line term, judge only the previous
    length -- GE-127b's shipped comparison, unchanged.

    Locates the `required = ...` assignment statement generically (via
    ``_REQUIRED_ASSIGNMENT_WITH_OPERAND_RE``) and replaces only its
    `previous - added` operand with the bare `previous`, leaving any
    surrounding wrapper (e.g. `max(limit, ...)`) untouched -- see this
    module's constant-block comment above for why that is exactly
    equivalent to "judge the file against its previous length alone,"
    and more durable than hardcoding the current full line. Patches the
    fixture's own on-disk copy and returns the original text for revert.

    Raises AssertionError LOUDLY -- never silently applying nothing -- if
    no matching assignment line exists at all, or if more than one does
    (an ambiguous target is as dangerous as a missing one), mirroring
    `_ge_127a_1_ordinary_commit_fixture.py`'s own "raise loudly if the
    mutation target is absent" precedent.
    """
    path = check_file_size_path(root)
    original = path.read_text(encoding="utf-8")
    matches = _REQUIRED_ASSIGNMENT_WITH_OPERAND_RE.findall(original)
    assert matches, (
        "MULTIPLIER injection target not found -- no 'required = ...' "
        "assignment line containing the literal operand "
        f"{_MULTIPLIER_OPERAND!r} exists in check_file_size.py. "
        "_classify_file's oversized-branch comparison may have changed "
        "shape; update this fixture's target."
    )
    assert len(matches) == 1, (
        "MULTIPLIER injection target is ambiguous -- found "
        f"{len(matches)} 'required = ...' assignment lines containing "
        f"{_MULTIPLIER_OPERAND!r}, expected exactly one:\n" + "\n".join(matches)
    )
    target_line = matches[0]
    mutated_line = target_line.replace(_MULTIPLIER_OPERAND, _MULTIPLIER_OPERAND_REPLACEMENT, 1)
    mutated = original.replace(target_line, mutated_line, 1)
    path.write_text(mutated, encoding="utf-8")
    return original


def apply_cap_injection(root: Path) -> str:
    """BA's injection 1: drop the 'less demanding of' and keep only the
    uncapped subtraction. Patches the fixture's own on-disk copy and returns
    the original text for revert.

    EXPECTED TO RAISE AssertionError before python-coder's fix has landed --
    the fixture's copy does not yet contain the capped
    `required = max(limit, previous - added)` line this injection targets,
    because `_classify_file` has no cap at all yet (architect-review's
    verified, corrected red baseline). This is itself a valid, honest RED
    result for this record's pre-implementation baseline; see this ticket's
    sign-off comment.
    """
    path = check_file_size_path(root)
    original = path.read_text(encoding="utf-8")
    assert _FIXED_REQUIRED_LINE in original, (
        "CAP injection target snippet not found -- EXPECTED before "
        "python-coder lands GE-127f-1's `required = max(limit, previous - "
        "added)` fix (architect-review ruling 2); _classify_file does not "
        f"yet compute a capped required length. Looked for:\n{_FIXED_REQUIRED_LINE!r}"
    )
    path.write_text(original.replace(_FIXED_REQUIRED_LINE, _CAP_REPLACEMENT), encoding="utf-8")
    return original


def restore_check_file_size(root: Path, original_text: str) -> None:
    """Revert a mutation applied above, restoring the exact original text."""
    check_file_size_path(root).write_text(original_text, encoding="utf-8")
