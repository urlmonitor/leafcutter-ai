"""
MODULE: _ge_120f_1_fixtures
AC: GE-120f-1 -- shared fixture helpers for test_ge_120f_1.py.
GOAL: Test-only fixture-authoring apparatus split out of test_ge_120f_1.py
    per the file-size gate (scripts/commit_guardian/check_file_size.py,
    400-line limit) so the test module stays under the limit without
    weakening or splitting any of the 6 test functions themselves. Holds:
    (a) the runner's entry-shape constants and output-parsing regex, (b)
    deterministic fixture CHECK SCRIPTS the runner invokes as real
    subprocesses, and (c) fixture REGISTRATION-SURFACE (manifest) builders.

    None of this module's functions is a test. Every assertion that used to
    read these values inline still lives in test_ge_120f_1.py -- only the
    fixture construction moved.

DECISION HISTORY
====================================================================
- 2026-09-25 [test-writer/EPIC-AGuardThatHasNeverSaidNoIsNotCountedAs/01,
  GE-120f-1]: Split out of test_ge_120f_1.py after check_file_size.py
  refused the original single-file version at 515 counted lines (limit
  400): TestGE120f1NegativeControlLiveness alone counted 368, leaving no
  room for the module-level fixture helpers plus imports. Per the
  coordinator's explicit direction, splitting TEST FUNCTIONS across two
  modules was avoided (the AC's own test_spec and commit_guardian.json's
  done-proof read fixed test names inside test_ge_120f_1.py specifically);
  this fixtures module carries only non-test helper code, so the test_spec
  contract is unaffected. No assertion was removed or weakened -- every
  helper here is called from the same test bodies, unchanged, via
  `import _ge_120f_1_fixtures as fx`.
- 2026-09-25 [test-writer, rework for GE-120f-1-ii]: `fixture_hook()` now
  ALWAYS declares a discriminating top-level `command` + `pass_criteria`
  (siblings of `negative_control`, GE-120f-1-ii's acceptable-input pair) --
  the same script_path with a "GOODINPUT" arg instead of "BADINPUT". Every
  fixture check built via `reject_script()`/`always_allow_script()` accepts
  (exit 0) any arg other than "BADINPUT", so this is a safe, behavior
  -preserving default for every existing caller in test_ge_120f_1.py: it
  makes GE-120f-1-ii's literal "no acceptable input -> blocked" rule and
  today's narrowed rule agree for every one of these hooks (disposition is
  never MISSING any more), without changing any assertion in that file.
  Done because architect-review's literal design (a hook declaring
  negative_control with no top-level acceptable `command` reads
  state=blocked) would otherwise regress this AC's own single-sided
  fixtures the moment python-coder removes GE-120f-1-ii's temporary
  narrowing -- see check_negative_control_liveness.py's own DECISION
  HISTORY and that ticket's fb_2026-09-25_946dd180 comment.
- 2026-09-25 [test-writer, rework for pr-reviewer fb_2026-09-25_79587943
  H-1]: `fixture_hook()` now also declares `entry`, set to the SAME
  literal invocation as `negative_control.command` -- the real invocation
  `_run_negative_control_command` performs for this fixture. Before this
  entry, `fixture_hook()` never set `entry` at all, so every
  test_ge_120f_1.py hook rode `_classify_demonstration()`'s fail-open
  default for a hook with no declared `entry` (pr-reviewer's H-1 finding:
  that default silently certifies `demonstration=entry_point` with no
  ground truth). Once python-coder corrects that default to
  `state=blocked`/`demonstration=n/a`, an un-fixed `fixture_hook()` would
  regress every passing/failing assertion in test_ge_120f_1.py. No
  assertion in that file changed -- `entry` matching the real invocation
  by construction is what makes `demonstration` resolve to `entry_point`
  by genuine identity, exactly as it does for every real registered hook.
====================================================================
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Runner entry shapes (both real production entry shapes this repo's other
# commit_guardian hooks use -- see _WRAPPED_PROBE_HOOK/_CWD_PROBE_HOOK in
# GE-120c-1's own test file for precedent).
# ---------------------------------------------------------------------------
RUNNER_FILENAME = "check_negative_control_liveness.py"
RUNNER_ENTRY_DIRECT = f"python {{{{config.output_root}}}}/scripts/commit_guardian/{RUNNER_FILENAME}"
RUNNER_ENTRY_WRAPPED = (
    "python {{config.output_root}}/scripts/commit_guardian/run_hook.py "
    f"{{{{config.output_root}}}}/scripts/commit_guardian/{RUNNER_FILENAME}"
)

#: `demonstration=` (GE-120f-1-i) and `discrimination=` (GE-120f-1-ii) are
#: both inserted BEFORE `command=` and kept OPTIONAL in this regex -- never
#: required -- so this single shared parser matches the pre-GE-120f-1-i line
#: shape (neither token, emitted by today's runner), the GE-120f-1-i-only
#: shape (`demonstration=` present, `discrimination=` absent), and the
#: post-GE-120f-1-ii shape (both present), without ever corrupting the
#: pre-existing greedy `command` group. This is what keeps test_ge_120f_1.py
#: and test_ge_120f_1_i.py green across this extension: neither file's
#: assertions read `discrimination`, and every field they DO read
#: (`check_id`/`state`/`entry_point`/`demonstration`/`command`) parses
#: identically either way.
RESULT_LINE_RE = re.compile(
    r"^NEGATIVE_CONTROL_RESULT check_id=(?P<check_id>\S+) state=(?P<state>\S+) "
    r"entry_point=(?P<entry_point>\S+) (?:demonstration=(?P<demonstration>\S+) )?"
    r"(?:discrimination=(?P<discrimination>\S+) )?"
    r"command=(?P<command>.*)$"
)

VALID_STATES = {"passing", "failing", "blocked", "unverified"}

#: GE-120f-1-i's own field -- classifies the invocation `_run_negative_control_command`
#: actually performed against the hook's own declared `entry` (see
#: check_negative_control_liveness.py's DECISION HISTORY once python-coder
#: implements this). "n/a" is reserved for `blocked`/`unverified` records --
#: no completed invocation exists there to classify.
VALID_DEMONSTRATIONS = {"entry_point", "reach_inside", "n/a"}

#: GE-120f-1-ii's own field -- the three wordings the acceptable-input
#: pairing produces (fb_2026-09-25_83f0382e's replacement design), living
#: outside `currently` next to `demonstration`. "n/a" covers every state
#: this ticket's pairing logic does not classify (the existing
#: "declared rejection not observed" `failing` case, and the two `blocked`
#: reasons that are not a non-discriminating pair).
VALID_DISCRIMINATIONS = {"discriminates", "refuses_without_discriminating", "pair_cannot_discriminate", "n/a"}


# ---------------------------------------------------------------------------
# Fixture check scripts -- real, deterministic subprocess entry points
# actually executed by the runner under test, never imported.
# ---------------------------------------------------------------------------
def reject_script(marker: str) -> str:
    """A fixture check that genuinely rejects its declared bad input
    (BADINPUT): non-zero exit iff argv[1] == "BADINPUT"."""
    return (
        f'"""Fixture check for GE-120f-1 ({marker}): genuinely rejects its '
        'declared known-bad input."""\n'
        "import sys\n"
        'if len(sys.argv) > 1 and sys.argv[1] == "BADINPUT":\n'
        f'    print("{marker}:REJECTED")\n'
        "    sys.exit(1)\n"
        f'print("{marker}:ALLOWED")\n'
        "sys.exit(0)\n"
    )


def always_allow_script(marker: str) -> str:
    """A fixture check ALTERED to never reject anything -- simulates a check
    that has silently stopped enforcing its own negative control, while its
    declaration (elsewhere, in the manifest) is left untouched."""
    return (
        f'"""Fixture check for GE-120f-1 ({marker}): ALTERED to never reject '
        '(simulates a broken/regressed check).  """\n'
        "import sys\n"
        f'print("{marker}:ALLOWED")\n'
        "sys.exit(0)\n"
    )


def write_script(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ---------------------------------------------------------------------------
# Fixture registration-surface (manifest) helpers.
# ---------------------------------------------------------------------------
def fixture_hook(check_id: str, script_path: Path, expected_result: str = "non-zero exit") -> dict:
    """One hooks_manifest.hooks[]-shaped entry declaring a negative_control
    whose `command` is a REAL, literal, already-resolved command (no
    {{config.output_root}} token -- this file fully controls script_path, so
    resolving the token is python-coder's concern for REAL manifest entries,
    not something these fixtures need to exercise).

    Also always declares a discriminating top-level `command` + `pass_criteria`
    (GE-120f-1-ii's acceptable-input pair, siblings of `negative_control`) --
    the same script_path invoked with "GOODINPUT" instead of "BADINPUT".
    Every check built from `reject_script()`/`always_allow_script()` accepts
    (exit 0) any arg other than "BADINPUT", so this never changes which of
    the two scripts genuinely rejects its declared bad input; it only gives
    every fixture hook a real, checked-accepted acceptable input so it is
    never reported as a pair that cannot discriminate."""
    command = f"{sys.executable} {script_path} BADINPUT"
    accept_command = f"{sys.executable} {script_path} GOODINPUT"
    return {
        "id": check_id,
        "tier": "judgment",
        "name": f"GE-120f-1 fixture check {check_id}",
        "entry_point": f"direct-script:{script_path}",
        # GE-120f-1-i's own ground-truth field (never `entry_point`, human
        # prose above). Set to the SAME literal invocation as
        # `negative_control.command` -- the real invocation
        # `_run_negative_control_command` performs for this fixture -- so
        # `_classify_demonstration()` resolves `demonstration` to
        # `entry_point` by genuine identity match, exactly as a real
        # registered hook declaring both fields would. Never omitted: a
        # hook lacking `entry` reads `blocked`/`n/a` under the corrected
        # H-1 rule (pr-reviewer fb_2026-09-25_79587943), which would
        # silently break every one of this file's own passing/failing
        # assertions -- none of which exercise the no-entry case.
        "entry": command,
        "command": accept_command,
        "pass_criteria": "zero exit",
        "negative_control": {
            "input": "BADINPUT",
            "command": command,
            "expected_result": expected_result,
        },
    }


def write_fixture_manifest(path: Path, hooks: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"hooks_manifest": {"hooks": hooks}}, indent=2) + "\n", encoding="utf-8",
    )


def read_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def hook_by_id(manifest: dict, check_id: str) -> dict:
    for hook in manifest["hooks_manifest"]["hooks"]:
        if hook["id"] == check_id:
            return hook
    raise KeyError(check_id)


def declaration_only(hook: dict) -> str:
    """Serialize just the negative_control DECLARATION fields (input,
    command, expected_result) -- excluding `currently`, which the runner is
    required to write -- so byte-identity of the DECLARATION across runs can
    be asserted without the currently write invalidating the comparison."""
    nc = {k: v for k, v in hook["negative_control"].items() if k != "currently"}
    return json.dumps(nc, indent=2, sort_keys=True)


def parse_results(stdout: str) -> dict[str, dict[str, str]]:
    """Parse every NEGATIVE_CONTROL_RESULT line in `stdout` into
    {check_id: {"state":..., "entry_point":..., "demonstration":...,
    "discrimination":..., "command":...}}. `demonstration`/`discrimination`
    are "" when the line predates GE-120f-1-i / GE-120f-1-ii respectively
    (no such token)."""
    results: dict[str, dict[str, str]] = {}
    for line in stdout.splitlines():
        m = RESULT_LINE_RE.match(line.strip())
        if m:
            results[m.group("check_id")] = {
                "state": m.group("state"),
                "entry_point": m.group("entry_point"),
                "demonstration": m.group("demonstration") or "",
                "discrimination": m.group("discrimination") or "",
                "command": m.group("command"),
            }
    return results
