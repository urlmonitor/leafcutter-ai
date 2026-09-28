"""
MODULE: _ge_120f_1_i_fixtures
AC: GE-120f-1-i -- shared fixture helpers for test_ge_120f_1_i.py.
GOAL: -i-specific fixture-authoring apparatus, split out per
    architect-review's own Q3 direction (fb_2026-09-25_7560dc1f): shared,
    load-bearing parsing code (RESULT_LINE_RE / parse_results) stays in the
    sibling _ge_120f_1_fixtures.py (extended in place), while the
    reach-inside/entry-point SHAPES this record's own descriptors need live
    here so that module keeps headroom for GE-120f-1-ii.

    Two fixture check SHAPES this module builds real, deterministic
    subprocess scripts for:
      - `probe_script()`: the readme_read_guard shape -- a module-level
        `decide()` genuinely rejects the declared input, but the script's
        own entry point (`__main__`) never calls it, so the entry point
        never produces the rejection the deciding part is capable of.
      - `reach_inside_driver_script()`: literalises this AC's own NAMED
        MUTATION -- "obtain the observation by importing the check and
        calling the part of it that decides, rather than by invoking the
        entry point" -- as a REAL, separate fixture script (never a
        `python -c` snippet: `shlex.split(..., posix=False)` on this
        repo's own win32 host keeps embedded quotes literal, corrupting
        any quoted `-c` payload -- see check_negative_control_liveness.py's
        own WINDOWS NOTE precedent in test_ge_120f_1.py).

    `hook_with()` builds a hooks_manifest.hooks[]-shaped entry with
    INDEPENDENTLY controlled `entry` (ground truth per architect-review Q1)
    and `negative_control.command` (the invocation actually run), so a test
    can construct a matching pair (genuine entry-point demonstration) or a
    deliberately mismatched pair (reach-inside) on demand.

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/02,
  GE-120f-1-i]: Initial red fixtures, written before python-coder
  implements the `demonstration` classification (architect-review's Q1/Q2).
- 2026-09-25 [test-writer, rework for GE-120f-1-ii]: `hook_with()` gained
  two new OPTIONAL keyword params, `accept_command` (default None) and
  `pass_criteria` (default "zero exit"). When a caller passes
  `accept_command`, it is written as a top-level `command` sibling of
  `negative_control` (GE-120f-1-ii's acceptable-input pair) -- never added
  when omitted, so `_ge_120f_1_ii_fixtures.py`'s own `missing_acceptable_hook()`
  (which deliberately wants NO top-level `command`) and its `with_acceptable()`
  pattern (which adds its own `command`/`pass_criteria` afterward) are both
  unaffected. test_ge_120f_1_i.py's own call sites were updated to pass a
  discriminating `accept_command` (the same underlying script/driver with a
  "GOODINPUT" arg in place of "BADINPUT") -- no assertion in that file
  changed. Done because architect-review's literal design (a hook declaring
  negative_control with no top-level acceptable `command` reads
  state=blocked) would otherwise regress these fixtures the moment
  python-coder removes GE-120f-1-ii's temporary narrowing -- see
  check_negative_control_liveness.py's own DECISION HISTORY and that
  ticket's fb_2026-09-25_946dd180 comment.
====================================================================
"""

from __future__ import annotations

import sys
from pathlib import Path


def probe_script(marker: str) -> str:
    """The readme_read_guard SHAPE (this AC's own worked example, see this
    ticket's doc_links). `decide()` genuinely rejects "BADINPUT"; the
    script's own entry point (__main__) never calls it and always exits 0
    -- the declared rejection is reachable only from inside, never through
    the entry point the protected surface would invoke."""
    return (
        f'"""Fixture check for GE-120f-1-i ({marker}): decide() genuinely '
        'rejects BADINPUT; the entry point never reaches it -- the '
        'readme_read_guard shape."""\n'
        "import sys\n\n\n"
        "def decide(value):\n"
        '    """The part of this check reachable only from within it."""\n'
        '    return value == "BADINPUT"\n\n\n'
        'if __name__ == "__main__":\n'
        f'    print("{marker}:ALLOWED (entry point never checks)")\n'
        "    sys.exit(0)\n"
    )


def reach_inside_driver_script(target_dir: Path, target_module: str) -> str:
    """Literalises this AC's own NAMED MUTATION as a real fixture script:
    imports `target_module` (a sibling check written by `probe_script()`)
    and calls its `decide()` directly -- never through that check's own
    entry point. A DIFFERENT script identity than the check it drives, by
    design: this is what a reach-inside `negative_control.command` looks
    like on disk."""
    return (
        '"""Reach-inside driver for GE-120f-1-i: imports a sibling check '
        "module and calls its decide() directly -- never through that "
        'check\'s own entry point."""\n'
        "import sys\n"
        f"sys.path.insert(0, {str(target_dir)!r})\n"
        f"import {target_module} as _target\n"
        "sys.exit(1 if _target.decide(sys.argv[1]) else 0)\n"
    )


def launcher_script(target_script_path: Path) -> str:
    """A thin further-subprocess launcher: re-execs `target_script_path`,
    forwarding argv, and exits with its return code. Gives a LEGITIMATE
    invocation an extra process hop (a different literal *shape* from a
    bare direct call) while its target identity is unchanged -- so a
    process-boundary-counting implementation misjudges it. Mirrors the
    real repo's own run_hook.py wrapper shape (positional target after the
    wrapper), never an opaque re-exec."""
    return (
        '"""Fixture launcher for GE-120f-1-i: re-execs the target script '
        'as a further subprocess, forwarding argv."""\n'
        "import subprocess\n"
        "import sys\n"
        "raise SystemExit(subprocess.run("
        f"[sys.executable, {str(target_script_path)!r}, *sys.argv[1:]]"
        ").returncode)\n"
    )


def direct_command(script_path: Path, arg: str = "BADINPUT") -> str:
    """The plain, single-hop way this module's fixture scripts are run."""
    return f"{sys.executable} {script_path} {arg}"


def hook_with(
    check_id: str,
    entry: str,
    command: str,
    entry_point: str | None = None,
    expected_result: str = "non-zero exit",
    accept_command: str | None = None,
    pass_criteria: str = "zero exit",
) -> dict:
    """One hooks_manifest.hooks[]-shaped entry with INDEPENDENTLY
    controlled `entry` (ground truth, per architect-review's Q1 -- never
    `entry_point`, which is "human prose today" on the real registration
    surface) and `negative_control.command` (the invocation actually
    performed). `entry_point` defaults to the script-path token of `entry`
    (never the full multi-word command -- a real `\\S+`-shaped stdout
    value never contains spaces, so a multi-word default would corrupt
    RESULT_LINE_RE's own match for every caller that does not care about
    this field) when not given a deliberately-misleading value of its own.

    `accept_command` (default None) is GE-120f-1-ii's acceptable-input pair
    -- when given, written as a top-level `command` + `pass_criteria`
    sibling of `negative_control`, never nested inside it. Omitted (the
    default) leaves the returned dict with no top-level `command` at all,
    preserving every caller that deliberately wants that shape (e.g.
    `_ge_120f_1_ii_fixtures.missing_acceptable_hook()`, and every -ii
    fixture that adds its own acceptable command via `with_acceptable()`
    afterward)."""
    if entry_point is None:
        tokens = entry.split()
        entry_point = tokens[-2] if len(tokens) >= 2 else entry
    hook = {
        "id": check_id,
        "tier": "judgment",
        "name": f"GE-120f-1-i fixture check {check_id}",
        "entry": entry,
        "entry_point": entry_point,
        "negative_control": {
            "input": "BADINPUT",
            "command": command,
            "expected_result": expected_result,
        },
    }
    if accept_command is not None:
        hook["command"] = accept_command
        hook["pass_criteria"] = pass_criteria
    return hook
