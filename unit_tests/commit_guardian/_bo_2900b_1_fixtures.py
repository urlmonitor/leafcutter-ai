"""
MODULE: unit_tests/commit_guardian/_bo_2900b_1_fixtures.py
GOAL: Shared real-artifact fixture builders for BO-2900b-1 (`check-reachability`,
    forward direction: a registered capability nothing runs is reported and
    refuses the change).

Not a test file itself (does not match test_*.py) so pytest never collects it
directly.

DESIGN NOTE (test-writer, 2026-09-25): scripts/commit_guardian/check_reachability.py
does not exist yet in this worktree -- confirmed by direct check
(``ls scripts/commit_guardian/check_reachability.py`` -> No such file or
directory) after running ``python scripts/build.py --target-dir .`` fresh, so
this is not a stale-build false negative. Neither does
``registered_capabilities()`` / ``collected_invocations()`` on the existing
``_reachability_inventory.py`` (grep confirmed zero hits for either name).
BO-2900b-1's own it_requirements.constraints mandate the CLI shape
(``check_reachability.py`` with ``--mode precommit`` / ``--mode ci``,
registered in commit_guardian.json's hooks_manifest per the check_done_proof.py
two-layer precedent) but do not fully specify how a caller selects WHICH
surfaces/automation scripts to inventory for a given run (BO-2900c-4 owns that
derivation and is out of scope here). Because these tests must be able to
target FIXTURE surfaces deterministically (never the real, evolving
scripts/build_orchestration/fast_lane.py -- whose real automation coverage
could drift and make a fixed assertion flaky), this fixture module DEFINES the
override CLI contract check_reachability.py's main() must accept:

    --mode {precommit,ci}          (as mandated by the AC)
    --surface MODULE_PATH:BUILDER  repeatable; MODULE_PATH is a filesystem
                                    path to a .py file, BUILDER is the name of
                                    a zero-arg callable in that module
                                    returning a built argparse.ArgumentParser
                                    (mirrors fast_lane.py's own
                                    ``_build_cli_parser()`` convention named in
                                    the AC's constraints).
    --automation SCRIPT_PATH        repeatable; a filesystem path to a script
                                    file to scan for invocations of the
                                    surface's registered capabilities.

This is a DECLARED CONTRACT this test-writer phase is handing to python-coder,
not a guess at pre-existing behaviour -- there is no pre-existing behaviour to
observe. python-coder MAY additionally support a no-argument "derive from the
real repo" default path (per BO-2900c-4), but MUST support these three flags
so the fixtures below produce a deterministic, non-flaky verdict.

REWORK (2026-09-25, ticket-supervisor 14:07 handoff): pr-reviewer (12:22) and
ac-validator (12:32) found the shipped check_reachability.py never consults
the BO-2900d-1 exemption registry (``load_exemptions`` / ``is_exempt`` /
``exemptions_in_force`` on ``_reachability_inventory.py``) even though this
AC's own constraints name a recorded exemption as "the only sanctioned
relief" from a refusal. ``init_fixture_reachability_project()`` and
``write_exemptions_registry()`` below extend this fixture module to cover
that wiring. Because ``check_reachability.py`` resolves the exemption
registry path as ``find_project_root() / config / reachability_exemptions.yaml``
(mirroring ``_bo_2900d_fixtures.init_fixture_project``'s own resolution, which
relies on ``find_project_root()`` preferring ``git rev-parse
--show-toplevel`` with the subprocess's own cwd), the fixture project root
must itself be a real git repository, and the CLI must be invoked with
``cwd=root`` -- exactly how ``run_check_reachability`` below already accepts
an optional ``cwd`` override.

DECLARED CONTRACT (exemption ``item`` format, test-writer hands to
python-coder): an ``uncalled_capability_finding``'s exemption ``item`` is
``f"{surface_label}:{capability}"`` -- the exact ``surface_label`` string this
module's ``_format_finding`` already prints (the literal ``--surface``
``MODULE_PATH`` text) joined to the capability name with a colon, matching
``is_exempt()``'s own docstring ("the exact repo-relative path (or
``surface:capability`` id) being checked"). This is the only reading
consistent with that docstring; no other separator or ordering is a
conforming implementation.

FILE SPLIT (2026-09-25, test-writer, re-dispatched from python-coder's
handoff): test_bo_2900b_1.py grew past check-file-size's 400-line .py limit
after the REWORK round above added three tests. The original five tests
(the forward Gherkin scenario, the called-capabilities-are-silent
counterpart, the built-parser-not-source-text seam test, the
no-bypass-flag-named test, and the required subprocess reachability test)
stay in test_bo_2900b_1.py; the three REWORK tests (the two
exemption-registry seam tests and the CI-job continue-on-error test) move to
the new test_bo_2900b_1_exemptions.py. Both files import this module. The
``fixture_tmp_dir()`` context manager below (previously duplicated as a
private ``_fixture_tmp_dir`` in the single pre-split file) now lives here
once, shared by both.
"""
from __future__ import annotations

import contextlib
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CHECK_REACHABILITY_SCRIPT = (
    REPO_ROOT / "scripts" / "commit_guardian" / "check_reachability.py"
)

_FIXTURE_SURFACE_BASIC = '''"""Fixture command surface: registers claim, release, mark-done, and report.

Mirrors BO-2900b-1's own Gherkin literally -- four registered actions, one
(``report``) that no automation below ever invokes.
"""
import argparse


def build_parser() -> argparse.ArgumentParser:
    """Return the built argparse parser -- the ONLY source of truth for what
    this surface registers (never source-scan this file's text)."""
    parser = argparse.ArgumentParser(prog="fixture-surface-basic")
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("claim")
    sub.add_parser("release")
    sub.add_parser("mark-done")
    sub.add_parser("report")
    return parser


if __name__ == "__main__":
    build_parser().parse_args()
'''

_FIXTURE_SURFACE_CONDITIONAL = '''"""Fixture command surface for
test_inventory_comes_from_the_built_parser_not_the_source_text.

Contains a ``sub.add_parser("ghost")`` call inside a branch that is FALSE at
build time -- ``ghost`` must NEVER appear in the built inventory, only in the
source text a naive regex scan would find. Also registers a capability
(``table-driven``) via a loop over a table rather than a literal
``add_parser(...)`` call, so a source-text regex scan would miss it while the
BUILT parser resolves it trivially.
"""
import argparse

_ENABLE_GHOST = False  # False at build time: "ghost" text is present, never registered.

_TABLE_DRIVEN_ACTIONS = ["claim", "table-driven"]


def build_parser() -> argparse.ArgumentParser:
    """Return the built argparse parser for the conditional/loop fixture."""
    parser = argparse.ArgumentParser(prog="fixture-surface-conditional")
    sub = parser.add_subparsers(dest="action", required=True)
    if _ENABLE_GHOST:
        sub.add_parser("ghost")
    for name in _TABLE_DRIVEN_ACTIONS:
        sub.add_parser(name)
    return parser


if __name__ == "__main__":
    build_parser().parse_args()
'''

_FIXTURE_AUTOMATION_CALLS_THREE = '''"""Fixture automation script: drives a build by invoking claim, release, and
mark-done on the fixture surface via subprocess -- never invokes "report".
Mirrors how a real automation script (templates/workflows-js/fast-lane-ship.js)
drives scripts/build_orchestration/fast_lane.py's subcommands one at a time.
"""
import subprocess
import sys
from pathlib import Path

_SURFACE = str(Path(__file__).resolve().parent / "fixture_surface_basic.py")


def run_build() -> None:
    """Invoke claim, release, and mark-done in sequence. "report" is
    deliberately never invoked anywhere in this file."""
    subprocess.run([sys.executable, _SURFACE, "claim"], check=False)
    subprocess.run([sys.executable, _SURFACE, "release"], check=False)
    subprocess.run([sys.executable, _SURFACE, "mark-done"], check=False)
'''

_FIXTURE_AUTOMATION_CALLS_CLAIM_ONLY = '''"""Fixture automation script for the conditional/loop surface: invokes only
"claim". "table-driven" is deliberately never invoked anywhere in this file,
so it must be reported as an uncalled registered capability.
"""
import subprocess
import sys
from pathlib import Path

_SURFACE = str(Path(__file__).resolve().parent / "fixture_surface_conditional.py")


def run_build() -> None:
    """Invoke only claim."""
    subprocess.run([sys.executable, _SURFACE, "claim"], check=False)
'''


def write_fixture_surface_basic(src_dir: Path) -> Path:
    """Write the real, on-disk, importable basic fixture surface module
    (claim/release/mark-done/report) via a verbatim on-disk file -- never a
    hand-typed in-memory literal the test body constructs at assertion time.
    """
    src_dir.mkdir(parents=True, exist_ok=True)
    path = src_dir / "fixture_surface_basic.py"
    path.write_text(_FIXTURE_SURFACE_BASIC, encoding="utf-8")
    return path


def write_fixture_surface_conditional(src_dir: Path) -> Path:
    """Write the real, on-disk, importable conditional/loop fixture surface
    module (ghost behind a false branch, table-driven registration)."""
    src_dir.mkdir(parents=True, exist_ok=True)
    path = src_dir / "fixture_surface_conditional.py"
    path.write_text(_FIXTURE_SURFACE_CONDITIONAL, encoding="utf-8")
    return path


def write_fixture_automation_calls_three(automation_dir: Path) -> Path:
    """Write the fixture automation script that invokes claim/release/mark-done
    against the basic fixture surface, and never invokes report."""
    automation_dir.mkdir(parents=True, exist_ok=True)
    path = automation_dir / "fixture_automation_calls_three.py"
    path.write_text(_FIXTURE_AUTOMATION_CALLS_THREE, encoding="utf-8")
    return path


def write_fixture_automation_calls_claim_only(automation_dir: Path) -> Path:
    """Write the fixture automation script that invokes only claim against the
    conditional/loop fixture surface."""
    automation_dir.mkdir(parents=True, exist_ok=True)
    path = automation_dir / "fixture_automation_calls_claim_only.py"
    path.write_text(_FIXTURE_AUTOMATION_CALLS_CLAIM_ONLY, encoding="utf-8")
    return path


def run_check_reachability(
    *,
    mode: str = "precommit",
    surfaces: list[str],
    automation_scripts: list[str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess:
    """Run the REAL deployed check_reachability.py CLI via subprocess.

    Mirrors _bo_2900d_fixtures.run_check_done_proof's shape: never imports the
    module directly, so a change to the CLI wiring itself is caught, not just
    a change to an internal helper. ``surfaces`` entries are
    ``"<module_path>:<builder_function_name>"`` strings (see this module's
    docstring for the declared --surface contract).

    Args:
        mode: "precommit" or "ci" -- passed through as --mode.
        surfaces: One or more "<module_path>:<builder>" specs, each passed as
            its own --surface flag.
        automation_scripts: One or more script file paths to scan for
            invocations, each passed as its own --automation flag.
        cwd: Working directory for the subprocess. Defaults to REPO_ROOT.

    Returns:
        The completed subprocess result (never raises on non-zero exit).
    """
    assert CHECK_REACHABILITY_SCRIPT.is_file(), (
        f"deployed guard script not found: {CHECK_REACHABILITY_SCRIPT} -- "
        f"this is the expected RED state before python-coder implements "
        f"BO-2900b-1's check_reachability.py; if you see this after "
        f"implementation, run `python scripts/build.py --target-dir .` first"
    )
    argv = [sys.executable, str(CHECK_REACHABILITY_SCRIPT), "--mode", mode]
    for surface_spec in surfaces:
        argv += ["--surface", surface_spec]
    for automation_path in automation_scripts:
        argv += ["--automation", automation_path]
    return subprocess.run(
        argv,
        cwd=str(cwd) if cwd is not None else str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )


def init_fixture_reachability_project(tmp_path: Path) -> Path:
    """Create a git-initialised fixture project root for exemption-wiring tests.

    check_reachability.py's own exemption-registry resolution is expected to
    be ``find_project_root() / config / reachability_exemptions.yaml`` --
    ``find_project_root()`` (``_resolve_root.py``) prefers ``git rev-parse
    --show-toplevel`` run with the CALLING PROCESS's cwd, exactly the same
    mechanism ``_bo_2900d_fixtures.init_fixture_project`` already relies on
    for ``check_done_proof.py``'s own exemption-registry reads. A bare temp
    directory (no ``.git``) would NOT resolve to *tmp_path*: git would walk
    up to this real repository's own root instead, and the fixture's
    ``config/reachability_exemptions.yaml`` would never be the file actually
    read. The CLI subprocess MUST be invoked with ``cwd=root`` (see
    ``run_check_reachability``'s own ``cwd`` parameter) for this to hold.
    """
    root = tmp_path
    subprocess.run(
        ["git", "init", "-q"], cwd=str(root), check=True, capture_output=True
    )
    (root / "config").mkdir(parents=True, exist_ok=True)
    write_exemptions_registry(root, [])
    return root


def write_exemptions_registry(root: Path, entries: list[dict]) -> Path:
    """Write config/reachability_exemptions.yaml under *root* via the real
    YAML serializer.

    ``entries`` follows BO-2900d-1's own schema
    (``{item, kind, reason, recorded, recorded_by}`` dicts under a
    top-level ``exemptions`` key). Produced with ``yaml.safe_dump`` -- never a
    hand-typed literal -- per the Fixture Authenticity Rule (test-writer
    skill 2h.2): a hand-typed exemption-registry fixture would reproduce
    exactly the author's own mental model of the YAML shape, the same blind
    spot EPIC-PhantomDoneFilesTouched shipped on for a different guard's
    fixtures. Mirrors ``_bo_2900d_fixtures.write_exemptions`` exactly.
    """
    path = root / "config" / "reachability_exemptions.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump({"exemptions": entries}, sort_keys=False),
        encoding="utf-8",
    )
    return path


@contextlib.contextmanager
def fixture_tmp_dir():
    """Yield a fresh temporary directory for one test's fixture tree.

    Shared by test_bo_2900b_1.py and test_bo_2900b_1_exemptions.py (the two
    files BO-2900b-1's own tests were split across, per the check-file-size
    400-line limit -- see both files' module docstrings) so the tmp-dir
    creation/cleanup logic exists exactly once rather than being duplicated
    across both. unittest.TestCase does not offer pytest's ``tmp_path``
    fixture, so each test creates and cleans up its own isolated temp tree
    via ``tempfile.TemporaryDirectory`` (never a project directory), per this
    repo's test_output_rules ("Never write to project dirs; use tmp_path or
    %TEMP%").
    """
    with tempfile.TemporaryDirectory(prefix="bo_2900b_1_") as tmp_dir:
        yield Path(tmp_dir)


def exemption_item_for(surface_label: str, capability: str) -> str:
    """Return the exemption ``item`` string for *capability* on *surface_label*.

    Per this module's DECLARED CONTRACT (see module docstring's REWORK
    note): ``f"{surface_label}:{capability}"`` -- the exact ``--surface``
    ``MODULE_PATH`` text (the same string ``_format_finding`` already prints
    as the finding's ``surface``) joined to the capability name with a
    colon, matching ``is_exempt()``'s own docstring
    ("... or ``surface:capability`` id ...").
    """
    return f"{surface_label}:{capability}"
