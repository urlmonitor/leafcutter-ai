"""
MODULE: unit_tests/commit_guardian/_ge_127f_4_fixture.py
COVERS: GE-127f-4 (shared fixture module -- carries no tests of its own)

GOAL: Thin wrapper reusing `_ge_127d_2_fixture.py`'s generic fixture-building
    primitives (real git repo setup, production-module copy, the real
    "grew"-verdict commit choreography -- `commit_bypassing_hook` for the
    setup commit, `commit` for the real refused/accepted one) rather than
    re-deriving any of it, per this record's own `it_requirements` ("follow
    them"). Adds only what GE-127f-4 itself needs on top:

    1. TWO CONTENT GENERATORS. `plain_py_lines` -- a .py file of exactly N
       measured lines with no triple-quoted or block-comment region at all,
       so its measured length equals its physical line count exactly (kept
       deliberately simple; GE-127f-4 is about the closing-advice PROSE,
       not about the discard rule GE-127d-2 already covers).
       `build_plus_and_minus_change` -- produces a staged edit from a prior
       content string that registers an EXACT, KNOWN gross-added-measured-
       line count under `resolve_added_measured_lines`' own diff engine
       (`count_added_measured_lines`, in `_file_size_ratchet.py`): it
       REPLACES the first `lines_added` lines with that many brand-new,
       textually distinct lines (a difflib "replace" opcode, which that
       engine counts as `lines_added` inserted -- never as a net-zero no-op,
       the self-referential reading GE-127f-2's own Implementation Notes
       name as the likeliest wrong turn) and, when `lines_removed` exceeds
       `lines_added`, additionally DELETES that many further original lines
       outright (a pure deletion, contributing 0 to the added count, by
       construction).

    2. TWO NEW PARSERS for the two figures neither GE-127d-2's own fixture
       nor any of its existing parsers ever needed to read:
       `parse_required_length` ("Required length: N lines or below ...")
       and `parse_added_measured_lines` ("This change added N measured
       line(s).") -- both from `_print_grown_file`
       (check_file_size.py).

    3. THE PINNED PROSE VOCABULARY this record's own criteria turns on:
       `OLD_ONE_FOR_ONE_CLAIM` (the exact substring GE-127f-4 requires GONE
       from the refusal's closing advice) and `TWICE_MARKER` (the single
       robust substring -- not a hand-typed full sentence -- any correct
       replacement must contain, per this ticket's own instruction to pin
       MEANING over one exact wording; "twice" is also the word GE-127f's
       own parent criteria uses: "about twice what the change adds to it").

DECISION HISTORY
- 2026-10-07 [GE-127f-4/test-writer]: Initial authoring (quick-fix run, no
  ticket file). Reused `_ge_127d_2_fixture.py` wholesale for every generic
  piece rather than duplicating repo/git/commit plumbing a second time.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import _ge_127d_2_fixture as _base  # noqa: E402

# ---------------------------------------------------------------------------
# Re-exported generic helpers (unchanged) -- see _ge_127d_2_fixture.py for
# each one's own docstring.
# ---------------------------------------------------------------------------
build_fixture_tree = _base.build_fixture_tree
write_and_stage = _base.write_and_stage
combined_output = _base.combined_output
commit = _base.commit
commit_bypassing_hook = _base.commit_bypassing_hook
write_precommit_config = _base.write_precommit_config
install_precommit = _base.install_precommit
parse_grown_previous_and_new_length = _base.parse_grown_previous_and_new_length
parse_permitted_length = _base.parse_permitted_length
extract_measures_line = _base.extract_measures_line
git = _base.git

# ---------------------------------------------------------------------------
# Pinned refusal-prose vocabulary (GE-127f-4's own design decision).
# ---------------------------------------------------------------------------

# The exact claim this record requires GONE from the grown-file refusal's
# closing advice -- verbatim, case-sensitive, as it reads in the current,
# unmodified check_file_size.py.
OLD_ONE_FOR_ONE_CLAIM = "add no more than you remove"

# A single robust substring (checked case-insensitively) any correct
# replacement sentence must contain -- pinning MEANING (the two-for-one
# obligation), never one exact sentence the coder must reproduce verbatim.
# "twice" is the natural English word for a 2x ratio and is also the word
# GE-127f's own parent criteria uses ("about twice what the change adds to
# it").
TWICE_MARKER = "twice"

# ---------------------------------------------------------------------------
# New parsers for the two grown-file figures this record's descriptors read
# that neither GE-127d-2's fixture nor any of its existing parsers needed.
# Deliberately independent, narrow regexes -- each looks only for its own
# labeled number, anywhere in the block -- mirroring
# _ge_127d_2_fixture.py's own parser design (not pinning python-coder to one
# exact surrounding sentence beyond the label itself).
# ---------------------------------------------------------------------------
_REQUIRED_LENGTH_RE = re.compile(r"Required length:\s*(\d+)")
_ADDED_MEASURED_RE = re.compile(r"added (\d+) measured line")


def parse_required_length(text: str) -> int | None:
    """Extract the stated "Required length: N ..." figure, or None."""
    match = _REQUIRED_LENGTH_RE.search(text)
    return int(match.group(1)) if match else None


def parse_added_measured_lines(text: str) -> int | None:
    """Extract the stated "... added N measured line(s)." figure, or None."""
    match = _ADDED_MEASURED_RE.search(text)
    return int(match.group(1)) if match else None


# ---------------------------------------------------------------------------
# Content generators.
# ---------------------------------------------------------------------------


def plain_py_lines(total_lines: int) -> str:
    """.py content of exactly *total_lines* measured lines.

    No triple-quoted string or block-comment region at all -- every
    physical line is counted by count_content_lines -- so this file's
    measured length equals *total_lines* exactly, keeping every number in
    this record's scenarios simple to state and to verify independently.
    """
    return "\n".join(f"value_{i} = {i}" for i in range(total_lines)) + "\n"


def build_plus_and_minus_change(content: str, lines_added: int, lines_removed: int) -> str:
    """Produce a staged change from *content* registering an EXACT, KNOWN
    gross-added-measured-line count under resolve_added_measured_lines'
    own diff engine, while removing exactly *lines_removed* original lines
    in total.

    Replaces *content*'s first *lines_added* lines with that many brand-new,
    textually distinct lines -- a difflib "replace" opcode, which
    count_added_measured_lines (the real engine _print_grown_file's own
    `added = resolve_added_measured_lines(...)` call resolves to) counts as
    exactly *lines_added* lines inserted, never zero, since the two sides
    share no matching text. When *lines_removed* exceeds *lines_added*, the
    next ``lines_removed - lines_added`` original lines (immediately after
    the replaced span) are additionally deleted outright -- a pure
    deletion, which contributes 0 to the added count by construction.

    Args:
        content: The file's content at its previous revision (HEAD), BEFORE
            this change.
        lines_added: The number of brand-new lines this change puts in --
            and the gross added-measured-line count it must register.
        lines_removed: The total number of original lines this change takes
            out, counting both the ``lines_added`` replaced lines and any
            further lines deleted outright. Must be >= lines_added -- every
            scenario in this record is at or below the two-for-one
            boundary, never above it.

    Returns:
        The new content string, with a trailing newline.

    Raises:
        ValueError: lines_removed < lines_added. A pure function on
            caller-supplied arguments, not external I/O or shared state --
            per this repo's error-handling policy (Rule 4), this is a plain
            raise, never a try/except.
    """
    if lines_removed < lines_added:
        raise ValueError(
            f"lines_removed ({lines_removed}) must be >= lines_added ({lines_added}) "
            "-- this fixture only models scenarios at or below the two-for-one boundary."
        )
    extra_deleted = lines_removed - lines_added
    lines = content.splitlines()
    new_leading = [f"replaced_value_{i} = -({i} + 1)" for i in range(lines_added)]
    mutated = new_leading + lines[lines_added + extra_deleted :]
    return "\n".join(mutated) + "\n"
