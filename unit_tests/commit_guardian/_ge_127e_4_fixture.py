"""
MODULE: unit_tests/commit_guardian/_ge_127e_4_fixture.py
COVERS: GE-127e-4 (shared fixture module -- carries no tests of its own)

GOAL: Fixture builders, mutation appliers, and extraction helpers for
    GE-127e-4's eight descriptors -- everything needed to choose a division
    arrives with the refusal itself (never a second artifact), the division
    is framed as a starting point taken from the file as it stands (and
    asserts nothing beyond that), and declining it costs nothing across a
    real two-commit sequence.

REUSED, NOT REINVENTED, PER ARCHITECT-REVIEW'S OWN INSTRUCTION. Imports the
    git/subprocess plumbing, disposable-copy machinery, snapshot helper, and
    ``_insert_before_main_guard`` from ``_ge_127e_3_fixture`` (itself
    re-exporting ``_ge_127e_1_fixture``/``_ge_127e_2_fixture``), and the
    wholesale ``main()``-override PRELUDE/TAIL from
    ``_ge_127e_3_i_fixture`` for the one mutation (injection 3) whose
    interception point is necessarily the classification loop rather than a
    print function -- verdict and the file's identity meet only there.

WHY INJECTIONS 1 AND 2 NEED NO "PROSPECTIVE FIX" BASELINE, UNLIKE
    GE-127e-3'S. This AC's first two arms are ALREADY true of today's real
    tree (architect-review ruling (a)); there is no pre-existing, unrelated
    defect to isolate away from, so the real, unmodified disposable copy is
    itself a valid, honest "revert" control -- the same reasoning
    ``_ge_127e_3_i_fixture.py`` already used for its own verdict-independence
    mutations.

WHY INJECTION 3 PERSISTS STATE TO DISK, DELIBERATELY. The forbidden
    behaviour this injection proves red is EXACTLY "the gate remembers what
    it advised between runs" -- so the mutation must genuinely carry a
    signature of the named division across two separate subprocess
    invocations (a JSON file beside the disposable copy's own
    ``check_file_size.py``), then compare it against the file's OWN new
    division on a later run where that file now passes. The real
    implementation carries no such file; the mutation exists so a
    regression that reintroduces this exact shape is caught by the SAME
    test that today proves its absence.

DECISION HISTORY
- 2026-09-28 [GE-127e-4/test-writer]: Initial authoring.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _ge_127e_1_fixture as e1  # noqa: E402
import _ge_127e_3_fixture as fx3  # noqa: E402
import _ge_127e_3_i_fixture as fx3i  # noqa: E402

# Re-exported so every test_ge_127e_4_*.py file can import ONE module.
fresh_repo_dir = fx3.fresh_repo_dir
init_repo = fx3.init_repo
commit_all = fx3.commit_all
stage_all = fx3.stage_all
run_check = fx3.run_check
run_check_via_hook = fx3.run_check_via_hook
build_into = fx3.build_into
make_part_source = fx3.make_part_source
make_multi_part_fixture = fx3.make_multi_part_fixture
PY_LIMIT = fx3.PY_LIMIT
fresh_disposable_repo = fx3.fresh_disposable_repo
build_disposable_commit_guardian = fx3.build_disposable_commit_guardian
run_check_in = fx3.run_check_in
extract_named_portions = fx3.extract_named_portions
extract_sides = fx3.extract_sides
has_no_division_marker = fx3.has_no_division_marker
snapshot_files = fx3.snapshot_files
_insert_before_main_guard = fx3._insert_before_main_guard

FORBIDDEN_DIVISION_CLAIM_WORDS = ("safe", "preserv", "examin", "best", "the only division", "no dependent")

# ---------------------------------------------------------------------------
# Staging -- a file whose parts fully account for its length (a REAL
# division), a single-part file (the honest no-division case), and the
# "decline it and fix differently" second edit.
# ---------------------------------------------------------------------------

_NAMED_DIVISION_PARTS = [
    ("north_module", 150),
    ("south_module", 140),
    ("east_module", 150),
]
_DIFFERENT_DIVISION_PART = ("solo_replacement", 80)


def stage_file_with_named_division(root: Path, name: str = "divisible.py") -> tuple[Path, str]:
    """Establish an under-limit file, then stage it over PY_LIMIT with parts
    that fully account for its length -- always a real Side A / Side B
    division, never the single-part or partial-coverage case."""
    target = root / name
    target.write_text(make_part_source("placeholder", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    content = make_multi_part_fixture(_NAMED_DIVISION_PARTS)
    target.write_text(content, encoding="utf-8")
    stage_all(root)
    return target, content


def stage_single_part_file(root: Path, name: str = "single_part.py") -> Path:
    """An oversized file with exactly ONE named part -- the honest
    "no division" case the framing sentence must never be printed for."""
    target = root / name
    target.write_text(make_part_source("placeholder", 10) + "\n", encoding="utf-8")
    commit_all(root, "establish under-limit file")
    target.write_text(make_part_source("whole_file_body", PY_LIMIT + 60), encoding="utf-8")
    stage_all(root)
    return target


def decline_named_division_and_fix_differently(target: Path, root: Path) -> str:
    """Rewrite *target* with an entirely different, single-part structure
    that brings it UNDER PY_LIMIT -- the author's own division, never the
    one the first refusal named. Stages but does not commit."""
    name, n_lines = _DIFFERENT_DIVISION_PART
    content = make_part_source(name, n_lines) + "\n"
    target.write_text(content, encoding="utf-8")
    stage_all(root)
    return content


def scrubbed_env() -> dict[str, str]:
    """A minimal environment (PATH only) for proving a run is reachable with
    nothing carried from an earlier run via an inherited env var."""
    return {"PATH": os.environ.get("PATH", "")}


def run_check_via_hook_with_env(root: Path, env: dict[str, str]):
    """``run_check_via_hook``, but with an explicitly SCRUBBED environment
    instead of the inherited one."""
    return subprocess.run(
        [e1._PYTHON, str(e1._RUN_HOOK), str(e1._CHECK_FILE_SIZE)],
        cwd=str(root),
        capture_output=True,
        text=True,
        timeout=e1._SUBPROCESS_TIMEOUT_SECONDS,
        env=env,
    )


def run_direct(script: Path, cwd: Path):
    """Invoke a deployed check script directly (not via run_hook.py)."""
    return subprocess.run(
        [e1._PYTHON, str(script)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=e1._SUBPROCESS_TIMEOUT_SECONDS,
    )


# ---------------------------------------------------------------------------
# Disposable-copy mutations -- never touch templates/scripts/commit_guardian/
# ---------------------------------------------------------------------------

DIVISION_REPORT_FILENAME = "division_report.txt"
PRESERVATION_CLAIM_MARKER = "preserves the file's current behavior and no dependents were examined"
DIVISION_FINDING_MARKER = "FILE FIXED BY A DIVISION OTHER THAN THE ONE NAMED"
_STATE_FILENAME = "_ge_127e_4_division_state.json"


def apply_relocate_division_to_report_injection(dest: Path) -> None:
    """BA injection 1: relocate the parts/division out of the refusal into a
    report file written elsewhere during the run, leaving the refusal
    carrying only a pointer sentence."""
    injected_code = f'''
# TEST-INJECTED MUTATION (GE-127e-4/test-writer, BA injection 1): relocate
# the parts/division into a second artifact, leaving only a pointer in the
# refusal itself.
def _print_file_description(filepath, quoted_length):  # noqa: F811 -- intentional test override
    content = _read_content_for_description(filepath)
    if content is None:
        return
    description = describe_file(filepath, content, quoted_length)
    if description is not None:
        report_path = Path(__file__).resolve().parent / "{DIVISION_REPORT_FILENAME}"
        with open(report_path, "w", encoding="utf-8") as handle:
            for line in format_description_lines(description):
                handle.write(line + "\\n")
        print("   See {DIVISION_REPORT_FILENAME} for this file's parts and division.")
        return
    reason = describe_file_failure_reason(filepath, content, quoted_length)
    if reason is not None:
        print(format_could_not_describe_line(reason))
'''
    _insert_before_main_guard(dest, injected_code)


def apply_claims_preservation_injection(dest: Path) -> None:
    """BA injection 2: append a sentence claiming the named division
    preserves the file's behaviour and that dependents were examined --
    exactly the claim this AC forbids beyond "starting point"."""
    injected_code = f'''
# TEST-INJECTED MUTATION (GE-127e-4/test-writer, BA injection 2): assert
# something about the division beyond it being a starting point.
_PRE_INJECTION_PRINT_FILE_DESCRIPTION = _print_file_description


def _print_file_description(filepath, quoted_length):  # noqa: F811 -- intentional test override
    _PRE_INJECTION_PRINT_FILE_DESCRIPTION(filepath, quoted_length)
    content = _read_content_for_description(filepath)
    if content is None:
        return
    description = describe_file(filepath, content, quoted_length)
    if description is not None and description.side_a is not None and description.side_b is not None:
        print("   This division {PRESERVATION_CLAIM_MARKER}.")
'''
    _insert_before_main_guard(dest, injected_code)


def apply_reports_alternate_division_finding_injection(dest: Path) -> None:
    """BA injection 3: persist which division was named for a refused file
    (to a JSON file beside the disposable copy), then on a LATER run where
    that same file now passes, compare its current content's own division
    against the stored one and refuse -- BY OUTCOME as well as by text --
    when they differ. Overrides ``main()`` wholesale (reusing
    ``_ge_127e_3_i_fixture``'s PRELUDE/TAIL) because the interception point
    is necessarily the classification loop, where verdict and the file's
    identity meet."""
    helpers = f'''
import json as _ge127e4_json


def _ge127e4_state_path():
    return Path(__file__).resolve().parent / "{_STATE_FILENAME}"


def _ge127e4_division_signature(description):
    if description is None:
        return None
    if description.side_a is not None and description.side_b is not None:
        return [sorted(description.side_a[0]), sorted(description.side_b[0])]
    if description.single_part_name is not None:
        return description.single_part_name
    return None


def _ge127e4_load_state():
    path = _ge127e4_state_path()
    if not path.exists():
        return {{}}
    return _ge127e4_json.loads(path.read_text(encoding="utf-8"))


def _ge127e4_save_state(state):
    _ge127e4_state_path().write_text(_ge127e4_json.dumps(state), encoding="utf-8")

'''
    body = f'''
            content = _read_content_for_description(filepath)
            description = describe_file(filepath, content, lines) if content is not None else None
            _ge127e4_state = _ge127e4_load_state()
            _ge127e4_signature = _ge127e4_division_signature(description)
            if verdict in ("too_large", "grew"):
                if _ge127e4_signature is not None:
                    _ge127e4_state[filepath] = _ge127e4_signature
                    _ge127e4_save_state(_ge127e4_state)
            elif verdict == "pass":
                _ge127e4_previous = _ge127e4_state.get(filepath)
                if _ge127e4_previous is not None and _ge127e4_signature != _ge127e4_previous:
                    print("{DIVISION_FINDING_MARKER}: " + filepath)
                    failed_files.append((filepath, lines, get_limit_for_extension(filepath)))
                    _ge127e4_state.pop(filepath, None)
                    _ge127e4_save_state(_ge127e4_state)
                    continue
'''
    injected_code = helpers + fx3i._VERDICT_INDEPENDENCE_PRELUDE + body + fx3i._VERDICT_INDEPENDENCE_TAIL
    _insert_before_main_guard(dest, injected_code)
