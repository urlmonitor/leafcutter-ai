"""
MODULE: _ge_120f_1_ii_fixtures
AC: GE-120f-1-ii -- shared fixture helpers for test_ge_120f_1_ii.py.
GOAL: -ii-specific fixture-authoring apparatus, split out proactively per
    architect-review's own file-placement direction (fb_2026-09-25_33c1543f,
    Q5): new helpers only, importing `_ge_120f_1_fixtures.py` (as `fx`) and
    `_ge_120f_1_i_fixtures.py` (as `fxi`) rather than duplicating their
    primitives.

    Builds hooks_manifest.hooks[]-shaped entries carrying BOTH declared
    inputs this AC requires: the existing `negative_control.command`
    (known-bad input, built via `fxi.hook_with`) and a NEW top-level
    `command` + `pass_criteria` pair -- SIBLINGS of `negative_control`, per
    the coordinator's binding design (fb_2026-09-25_33c1543f /
    fb_2026-09-25_83f0382e Q1) -- for the acceptable input this AC's own
    pairing logic must also put through the entry point.

    `entry` is always set to the SAME literal command as
    `negative_control.command` for every "healthy" (discriminating)
    fixture, so that once GE-120f-1-i's own `demonstration` classification
    lands, these fixtures' `demonstration` resolves to `"entry_point"` --
    this ticket's `passing` gate requires `discrimination == "discriminates"`
    AND `demonstration == "entry_point"` in the SAME record (see
    fb_2026-09-25_83f0382e's "passing gate" note).

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/03,
  GE-120f-1-ii]: Initial red fixtures, written before python-coder
  implements the acceptable-input pairing/discrimination logic
  (fb_2026-09-25_33c1543f, amended by fb_2026-09-25_83f0382e).
- 2026-09-25 [test-writer, coordinator rework for pr-reviewer's
  fb_2026-09-25_bb6a7c1d finding 2]: Added `failed_acceptable_hook()` for
  the new `test_ge_120f_1_ii_b.py` module (`test_ge_120f_1_ii.py` itself is
  at 393/400 counted lines, no room left). Builds a hook whose bad input
  genuinely rejects through the entry point but whose acceptable-input
  `command` names an executable token that cannot be launched at all -- the
  real `subprocess.run` OSError path (`_examine()`'s `accept_exit is None`
  branch), never a tokenizing failure (that is the declaration-level
  `pair_cannot_discriminate` path `identical_pair_hook()`/
  `missing_acceptable_hook()` already exercise).
====================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path

import _ge_120f_1_i_fixtures as fxi  # type: ignore[import]  # noqa: E402


def always_reject_script(marker: str) -> str:
    """A fixture check that rejects EVERY input, regardless of argv --
    the "refuses without discriminating" shape: it never accepts the work
    it is meant to accept because it never accepts anything."""
    return (
        f'"""Fixture check for GE-120f-1-ii ({marker}): rejects every '
        'declared input, discriminating or not."""\n'
        "import sys\n"
        f'print("{marker}:REJECTED")\n'
        "sys.exit(1)\n"
    )


def counting_script(marker: str, log_path: Path) -> str:
    """A fixture check that appends one line to `log_path` per invocation
    (so invocation COUNT can be measured independent of any single
    invocation's exit code) and rejects iff argv[1] == "BADINPUT"."""
    return (
        f'"""Fixture check for GE-120f-1-ii ({marker}): logs every '
        'invocation to a shared file, then genuinely discriminates."""\n'
        "import sys\n"
        f"with open({str(log_path)!r}, 'a', encoding='utf-8') as _f:\n"
        "    _f.write((sys.argv[1] if len(sys.argv) > 1 else '') + chr(10))\n"
        'if len(sys.argv) > 1 and sys.argv[1] == "BADINPUT":\n'
        f'    print("{marker}:REJECTED")\n'
        "    sys.exit(1)\n"
        f'print("{marker}:ALLOWED")\n'
        "sys.exit(0)\n"
    )


def bad_command_for(script_path: Path) -> str:
    """The known-bad-input invocation this AC's `negative_control.command`
    (unchanged from GE-120f-1) declares."""
    return f"{sys.executable} {script_path} BADINPUT"


def acceptable_command_for(script_path: Path) -> str:
    """The acceptable-input invocation this AC's new top-level `command`
    declares -- a DIFFERENT arg on the SAME script, so `reject_script`'s
    argv[1] == "BADINPUT" branch is what makes a check genuinely
    discriminate between the two declared inputs."""
    return f"{sys.executable} {script_path} GOODINPUT"


def with_acceptable(hook: dict, accept_command: str, pass_criteria: str = "zero exit") -> dict:
    """Add this AC's new hook-level `command` + `pass_criteria` keys as
    SIBLINGS of `negative_control` -- never nested inside it, never a
    second declaration store (fb_2026-09-25_33c1543f's binding design)."""
    hook["command"] = accept_command
    hook["pass_criteria"] = pass_criteria
    return hook


def discriminating_hook(check_id: str, script_path: Path) -> dict:
    """Bad input genuinely rejected, acceptable input genuinely accepted --
    a check that DOES discriminate. `entry` == the bad-input command, so
    GE-120f-1-i's `demonstration` resolves to `entry_point` once it lands."""
    bad_command = bad_command_for(script_path)
    hook = fxi.hook_with(check_id, entry=bad_command, command=bad_command)
    return with_acceptable(hook, acceptable_command_for(script_path))


def refuses_both_hook(check_id: str, script_path: Path) -> dict:
    """Bad input AND acceptable input both rejected -- refuses without
    discriminating: `script_path` must be built with `always_reject_script`."""
    bad_command = bad_command_for(script_path)
    hook = fxi.hook_with(check_id, entry=bad_command, command=bad_command)
    return with_acceptable(hook, acceptable_command_for(script_path))


def refuses_neither_hook(check_id: str, script_path: Path) -> dict:
    """Bad input AND acceptable input both accepted -- the existing
    "declared rejection not observed" case: `script_path` must be built
    with `fx.always_allow_script` (imported by the caller as `fx`)."""
    bad_command = bad_command_for(script_path)
    hook = fxi.hook_with(check_id, entry=bad_command, command=bad_command)
    return with_acceptable(hook, acceptable_command_for(script_path))


def identical_pair_hook(check_id: str, script_path: Path) -> dict:
    """The SAME literal command declared for both the bad and the
    acceptable input -- "a check declaring the same input twice"."""
    command = bad_command_for(script_path)
    hook = fxi.hook_with(check_id, entry=command, command=command)
    return with_acceptable(hook, command)


def tokenize_equal_pair_hook(check_id: str, script_path: Path) -> dict:
    """Two DECLARED commands that are textually different (extra
    whitespace) but tokenize to the IDENTICAL argv -- "differ in no way
    the check can act on", per architect-review's mechanical Q2 test
    (`shlex.split(a) == shlex.split(b)`)."""
    bad_command = bad_command_for(script_path)
    textually_different_same_tokens = f"{sys.executable}   {script_path}   BADINPUT"
    hook = fxi.hook_with(check_id, entry=bad_command, command=bad_command)
    return with_acceptable(hook, textually_different_same_tokens)


def missing_acceptable_hook(check_id: str, script_path: Path) -> dict:
    """No top-level `command` declared at all -- the acceptable-input side
    of the pair is simply absent, never a second store elsewhere."""
    bad_command = bad_command_for(script_path)
    return fxi.hook_with(check_id, entry=bad_command, command=bad_command)


def failed_acceptable_hook(check_id: str, script_path: Path, missing_executable_path: Path) -> dict:
    """Bad input genuinely rejected through the entry point; the
    acceptable-input `command` names an executable token that cannot be
    launched at all (`missing_executable_path` must not exist on disk) --
    a real `subprocess.run` OSError, never a tokenizing failure (that is
    `pair_disposition()`'s own declaration-level finding, a different
    path). `expected_result` and the bad-input script are unchanged from
    every other -ii fixture; the only new shape is the acceptable side's
    own unrunnable executable."""
    bad_command = bad_command_for(script_path)
    hook = fxi.hook_with(check_id, entry=bad_command, command=bad_command)
    return with_acceptable(hook, str(missing_executable_path))
