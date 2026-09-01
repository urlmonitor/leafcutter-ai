"""
MODULE: test_bp_900g_8_ii
GOAL: Red-baseline specification tests for AC BP-900g-8-ii -- widen the
    deployed-dependency closure BP-900g-8 introduced so it treats a NON-CODE
    file a deployed script reads at runtime (a schema, a vocabulary, a
    registry, a data table) as the SAME kind of dependency as a module
    import, with the SAME enforcement force.
BUSINESS CONTEXT: AC BP-900g-8-ii, child of BP-900g-8. The binding three-set
    model BP-900g-8 established (Set A resolved_closure / Set B
    deploy_declaration / Set C guard_manifest) is unchanged; this AC widens
    what counts as a member of Set A and Set B, and forbids a second,
    parallel notion of "data dependency" bolted alongside the module one.

TDD REWORK (2026-09-01): a prior pass on this branch left a hole in the
CENTRAL case this AC exists for. ``build.py::_source_file_for_deploy_path``
returns ``root=<package_root>/templates`` (prefix ``""``) for the entire
commit-guardian family. A repo-root-relative read such as
``config/doc_types.json`` therefore resolves against ``<package_root>/templates/config/...``,
which never exists, and is silently dropped -- every data dependency of
every commit-guardian hook is invisible to the guard. ``config/doc_types.json``
happens to be deployed anyway (a second, unrelated reader --
``scripts/injection_builders.py``, whose root IS the package root -- put it
in the manifest by luck). ``config/diagram_types.json`` has no such second
reader: it is still undeployed, and its reader
(``diagram_type_validators.py::_find_diagram_types_json``) degrades SILENTLY
to a built-in constant on failure, so nothing ever crashes to reveal it. A
clean ``python scripts/build.py --target-dir /tmp/x`` on this branch, as of
this rework, still exits 0.

The pre-rework version of ``unit_tests/test_bp_900g_8_ii.py`` missed this
because its own test 1 called ``compute_intra_package_closure(script,
_REPO_ROOT)`` -- production never passes ``_REPO_ROOT`` for these scripts;
it passes ``templates/``. The test exercised the function through a
namespace the guard does not use. This rework adds a dedicated regression
test that exercises the REAL ``python scripts/build.py`` subprocess entry
point instead, and restores three ``test_spec`` entries (2, 3, 4) that a
prior pass weakened from a real ``build.py`` subprocess / three-state
demonstration down to direct function calls / a single combined run, in
order to fit a 60-second fast-lane gate timeout that does not bind this
authoring pass.

TDD REWORK (2026-09-01, defect-fix pass): the production fix landed and was
independently verified -- ``compute_intra_package_closure_with_deploy_root_relative``
now splits ``root``/``data_root`` correctly, all three core-config deploy
tuples (two in ``scripts/build.py``, one in ``scripts/build_phases.py``) name
``config/diagram_types.json`` and ``config/skill_registry.json`` alongside
``config/doc_types.json``, and a clean ``python scripts/build.py
--target-dir /tmp/x`` exits 0 and deploys all of them. This pass found and
fixed two remaining defects in THIS FILE, both pre-dating the production fix
verification above:
    (a) Test 1 ("criterion") still called
    ``compute_intra_package_closure(script, _REPO_ROOT)`` -- the exact
    phantom-green namespace mismatch this module's earlier TDD REWORK note
    (above) already diagnosed for the OLD test 1, reintroduced. Fixed by
    resolving every case through ``build._source_file_for_deploy_path`` (the
    guard's own resolver) and asserting on the resulting NAMESPACED closure,
    plus a non-vacuity assertion (an empty closure was the actual historical
    bug) and an explicit discriminating control proving the fixture would
    fail under the pre-fix (no-``data_root``) call shape. A fourth case
    (``doc_type_validators.py`` itself, not just an importer of it) was added
    since it is the reader that was silently empty end-to-end.
    (b) Test 2 Half 1 (this test) asserted an UNMODIFIED copy must FAIL --
    true only while the production defect was live, and directly
    CONTRADICTING test 3's State 1 (which correctly asserts an unmodified
    copy must PASS). No production code could satisfy both. Fixed by
    rewriting Half 1 as a withhold-then-restore round trip: withhold
    ``config/diagram_types.json`` from all three core-config tuples in a temp
    copy (must block, naming the file and its reader), then restore an
    unmodified copy (must clear AND the file must be verifiably present
    under ``.leafcutter/config/`` in the deployed output -- exit 0 alone
    cannot distinguish "shipped" from "guard stopped looking"). Half 2 (the
    generalisation control) is UNCHANGED -- it was already correct and is the
    most valuable assertion in the file.

ARCHITECTURE: Five tests.
    (1) angle: criterion -- pure unit test of
    ``build_referential_integrity.compute_intra_package_closure_with_deploy_root_relative``
    / ``find_uncovered_closure_dependencies`` against four real deployed
    guardrails, resolved through the guard's own ``build._source_file_for_deploy_path``.
    (2) angle: reachability -- the central-case regression, now a
    withhold-then-restore round trip against a real ``python scripts/build.py
    --target-dir <tmp>`` subprocess: withholding ``config/diagram_types.json``
    from all three core-config deploy tuples must block and name it and its
    reader; restoring an unmodified copy must clear AND the file must be
    verifiably deployed. Paired with a GENERALISATION CONTROL: a brand-new,
    never-before-existing data file read injected into a DIFFERENT
    commit-guardian script (``check_hook_parity.py``, chosen because it is
    unrelated to either ``*_types.json`` file) must ALSO be flagged -- so a
    fix scoped to the two named files in this AC's own doc_links would still
    fail this test.
    (3) angle: reachability, must_block -- RESTORED to a real ``build.py``
    subprocess, in THREE separate states (unmodified / non-code withheld /
    module withheld) rather than the prior pass's single combined run, per
    the AC's own test_spec: "State (1) is not optional -- a positive-path
    build alone cannot tell a working guard from an absent one."
    (4) angle: failure -- RESTORED to a real ``build.py`` subprocess (the
    prior pass called ``compute_intra_package_closure`` directly). THE
    DERIVED-NOT-HARDCODED CONTROL: injects a config file under a name that
    has never existed in this repository into a deployed script, asserts the
    subprocess build blocks naming it, then declares it through the SAME
    core-config mechanism ``scripts/build.py`` already uses for
    ``config/doc_types.json`` et al. and asserts the SAME subprocess clears.
    (5) angle: boundary -- RESTORED to a real ``build.py`` subprocess. An
    absolute OS path and an external-tool path added to a deployed script
    must not be named and must not block the build; a package-owned,
    undeclared config file added to the SAME script in a second run MUST be
    named and MUST block -- the required positive control, so the exclusion
    cannot be satisfied by a rule that excludes everything.

TEMP-COPY DISCIPLINE (mandatory, see rework notes): every mutating test in
this file operates on a ``shutil.copytree`` copy of the package tree under
``tmp_path``, NEVER on the real ``scripts/``, ``config/``, or
``templates/scripts/commit_guardian/`` trees of this worktree. The prior
pass mutated the REAL ``scripts/injection_builders.py``,
``scripts/build_phases.py``, and ``scripts/build.py`` in place (with a
try/finally restore), and a real interruption during that window left
``injection_builders.py`` modified with a stray marker-reading block for
over four minutes with no pytest running, requiring a manual ``git
restore``. Every test below copies first and mutates the copy only; nothing
in this file ever calls ``.write_text()`` on a path under ``_REPO_ROOT``
except to READ its content (`.read_text()`) as the copy source. Test 1 is
the sole exception in the sense that it never mutates anything at all (real
files are only read, never written) -- it needs no copy.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup -- make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 -- after sys.path setup
import build_referential_integrity as _bri  # noqa: E402 -- after sys.path setup

# ---------------------------------------------------------------------------
# Shared helpers -- temp-copy + subprocess-build plumbing used by every
# reachability/failure/boundary test in this file (see TEMP-COPY DISCIPLINE
# above the module docstring's ARCHITECTURE section).
# ---------------------------------------------------------------------------

_COPY_IGNORE = shutil.ignore_patterns(
    ".git", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules", ".next"
)

# The exact anchor text (byte-for-byte, confirmed present twice in
# scripts/build.py at authoring time -- once in _get_source_deployable_scripts,
# once in _get_source_paths_for_guard) that declares a "core config" file
# through the SAME ordinary mechanism config/doc_types.json etc. already use.
# Used by test 4's round-trip half to declare a brand-new marker file.
_CORE_CONFIG_TUPLE_ANCHOR = '        "paths.json",\n    ):'

# The exact line (byte-for-byte) that declares config/diagram_types.json in
# each of the THREE core-config tuples this AC's fix added it to: TWO in
# scripts/build.py (_get_source_deployable_scripts' Set-B manifest and
# _get_source_paths_for_guard's tracked-source set) and ONE in
# scripts/build_phases.py (build_ac_store's own deploy tuple, the one that
# actually WRITES the file). Used by test 2 Half 1's withhold-then-restore
# round trip.
_DIAGRAM_TYPES_TUPLE_LINE = '        "diagram_types.json",\n'


def _withhold_diagram_types_from_deploy_declaration(copy_root: Path) -> None:
    """Remove config/diagram_types.json from all three core-config deploy tuples in the copy.

    Withholds it from BOTH of build.py's Set-B declarations
    (``_get_source_deployable_scripts`` and ``_get_source_paths_for_guard``)
    AND from build_phases.py's ``build_ac_store`` deploy tuple in the SAME
    call, so the three stay mutually consistent -- keeping
    ``test_guard_source_paths_match_deployable_set``'s cardinality parity
    check from firing for the wrong reason (see TEMP-COPY DISCIPLINE above).
    Withholding from build_phases.py also means the file is genuinely never
    WRITTEN to the deployed target, not merely un-declared -- needed for the
    "restore" half's deployed-file assertion to be a meaningful contrast.
    """
    build_py = copy_root / "scripts" / "build.py"
    original_build = build_py.read_text(encoding="utf-8")
    build_count = original_build.count(_DIAGRAM_TYPES_TUPLE_LINE)
    assert build_count == 2, (
        "Fixture assumption broken: expected exactly 2 occurrences of "
        f"{_DIAGRAM_TYPES_TUPLE_LINE!r} in scripts/build.py (one in "
        "_get_source_deployable_scripts, one in _get_source_paths_for_guard); "
        f"found {build_count}. build.py's core-config declaration shape may "
        "have changed -- update this helper's anchor."
    )
    build_py.write_text(
        original_build.replace(_DIAGRAM_TYPES_TUPLE_LINE, ""), encoding="utf-8"
    )

    build_phases_py = copy_root / "scripts" / "build_phases.py"
    original_phases = build_phases_py.read_text(encoding="utf-8")
    phases_count = original_phases.count(_DIAGRAM_TYPES_TUPLE_LINE)
    assert phases_count == 1, (
        "Fixture assumption broken: expected exactly 1 occurrence of "
        f"{_DIAGRAM_TYPES_TUPLE_LINE!r} in scripts/build_phases.py's "
        f"build_ac_store deploy tuple; found {phases_count}. "
        "build_phases.py's core-config declaration shape may have changed -- "
        "update this helper's anchor."
    )
    build_phases_py.write_text(
        original_phases.replace(_DIAGRAM_TYPES_TUPLE_LINE, ""), encoding="utf-8"
    )


def _copy_package_tree(dest: Path) -> Path:
    """Copy the whole package tree into *dest* so mutation never touches the real tree.

    Excludes ``.git`` -- this worktree's ``.git`` is a plain gitlink file, and
    a destination lacking ``.git`` entirely makes
    ``_check_tracked_source_guard`` gracefully no-op via its own documented
    "not a git repository" skip (H-3), exactly the behaviour a genuine
    non-git consumer install already exercises -- so nothing about the guard
    under test is weakened by copying this way. Also excludes local
    cache/build-artifact directories a fresh checkout would never carry
    (``__pycache__``, ``.pytest_cache``, ``.ruff_cache``, ``node_modules``,
    ``.next``) purely so each of this file's several copies stays fast; none
    of the excluded paths are read by ``build.py``'s closure guard or any
    deploy phase this file exercises.
    """
    shutil.copytree(_REPO_ROOT, dest, ignore=_COPY_IGNORE, symlinks=True)
    return dest


def _run_build_in_copy(
    copy_root: Path, target_dir: Path, timeout: int = 180
) -> subprocess.CompletedProcess:
    """Run `python <copy_root>/scripts/build.py --target-dir <target_dir>` as a real subprocess."""
    return subprocess.run(
        [sys.executable, str(copy_root / "scripts" / "build.py"), "--target-dir", str(target_dir)],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(copy_root),
    )


def _inject_marker_read_into_injection_builders(copy_root: Path, marker_name: str) -> None:
    """Append a synthetic module-level read of ``config/<marker_name>`` to the copy's injection_builders.py.

    ``scripts/injection_builders.py`` resolves via the "everything else"
    fallback in ``_source_file_for_deploy_path`` -- root=package_root,
    prefix="" -- so a ``config/``-relative read from it resolves correctly
    even before this AC's fix lands (this is the SAME script the prior pass's
    test 2/3 used, and the SAME reason ``config/doc_types.json`` happens to
    be deployed today: this script, not the commit-guardian family, is what
    actually declares it). Used to exercise the SAME-FORCE / round-trip
    assertions independently of the commit-guardian root-namespace defect,
    which is covered separately by the dedicated regression test.
    """
    injection_builders_py = copy_root / "scripts" / "injection_builders.py"
    injected_block = textwrap.dedent(
        f'''

        # >>> BP-900g-8-ii TEST INJECTION (temp copy only) >>>
        _BP900G8II_MARKER = Path(__file__).resolve().parent.parent / "config" / "{marker_name}"


        def _bp900g8ii_load_marker() -> dict:
            with open(_BP900G8II_MARKER, encoding="utf-8") as f:
                return json.load(f)
        # <<< BP-900g-8-ii TEST INJECTION <<<
        '''
    )
    original = injection_builders_py.read_text(encoding="utf-8")
    injection_builders_py.write_text(original + injected_block, encoding="utf-8")
    (copy_root / "config" / marker_name).write_text("{}\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Test 1 -- angle: criterion. UNCHANGED from the prior pass. Three REAL
# deployed guardrails, three REAL non-code files, against the SAME two
# functions BP-900g-8 introduced. Reads real files only; never mutates
# anything, so it needs no temp copy.
# ---------------------------------------------------------------------------


def test_bp_900g_8_ii_derived_closure_for_a_deployed_guardrail_contains_the_non_code_files_it_reads():
    # covers: BP-900g-8-ii
    # angle: criterion
    """AC BP-900g-8-ii criterion: the derived set contains non-code files the
    same way it contains module imports, and the containment/coverage verdict
    fires the same way for both.

    TDD REWORK (2026-09-01, defect 2 fix): the prior version of this test
    called ``compute_intra_package_closure(script, _REPO_ROOT)`` directly --
    production NEVER passes ``_REPO_ROOT`` for the commit-guardian family; it
    passes ``root=<package_root>/templates`` via
    ``_source_file_for_deploy_path``. That made the test a PHANTOM GREEN: it
    passed even during the period this family's closure was genuinely EMPTY
    in production, because ``_REPO_ROOT`` (unlike ``templates/``) happens to
    contain ``config/doc_types.json`` directly, so the wrong root accidentally
    found the right answer for the wrong reason. Confirmed empirically before
    this rework: ``compute_intra_package_closure(doc_type_validators.py,
    root=templates)`` (no data_root -- the pre-fix call shape) returns
    ``set()``, while the SAME call through
    ``compute_intra_package_closure_with_deploy_root_relative(..., data_root=
    package_root)`` (what the guard actually calls today) returns
    ``{"config/doc_types.json"}``. This test now resolves every case through
    ``build._source_file_for_deploy_path`` -- the SAME resolver
    ``build.py::_check_intra_package_closure_guard`` calls -- so it exercises
    the real root/data_root/prefix triple rather than a namespace the guard
    never uses.

    Uses four real, currently-deployed guardrails. Three are the guardrails
    this AC's own doc_links name as a confirmed 2026-08-18 regression
    instance; the fourth (``doc_type_validators.py`` itself) is the ADDED
    case for the family whose closure was silently empty end-to-end before
    this AC's fix -- see the module docstring's TDD REWORK note:
      - scripts/commit_guardian/check_doc_frontmatter.py (imports
        doc_type_validators.py, which reads doc_types.json via
        ``_find_doc_types_json`` / ``_load_doc_types``) -> config/doc_types.json
      - scripts/ac_store/validate_ac_schema.py (via ``_default_schema_path``)
        -> config/ac_store_schema.json
      - scripts/injection_builders.py (via ``_PACKAGE_ROOT`` +
        ``build_agent_priority_table``) -> config/agent_registry.json
      - scripts/commit_guardian/doc_type_validators.py itself (the direct
        reader, not just an importer of it) -> config/doc_types.json
    """
    cases = [
        ("scripts/commit_guardian/check_doc_frontmatter.py", "config/doc_types.json"),
        ("scripts/ac_store/validate_ac_schema.py", "config/ac_store_schema.json"),
        ("scripts/injection_builders.py", "config/agent_registry.json"),
        ("scripts/commit_guardian/doc_type_validators.py", "config/doc_types.json"),
    ]

    for deploy_path, data_dep in cases:
        # ---- Resolve exactly the way the real guard resolves (defect 2 fix):
        # via _source_file_for_deploy_path from the DEPLOY path, never a
        # hand-picked root.
        resolved = _build._source_file_for_deploy_path(_REPO_ROOT, deploy_path)
        assert resolved is not None, (
            f"build._source_file_for_deploy_path() returned None for "
            f"{deploy_path!r} -- the guard's own resolver could not locate a "
            "source file for a script this test assumes is deployed. Fixture "
            "assumption broken (AC BP-900g-8-ii)."
        )
        source_file, root, deploy_prefix = resolved
        assert source_file.is_file(), (
            f"Fixture assumption broken: resolved source file {source_file} "
            f"for deploy path {deploy_path!r} does not exist."
        )

        closure, deploy_root_relative = _bri.compute_intra_package_closure_with_deploy_root_relative(
            source_file, root, _REPO_ROOT
        )
        # Non-vacuity (mandatory): an EMPTY closure was the actual historical
        # bug (doc_type_validators.py's own closure was `[]` before this AC's
        # fix) -- a resolver/closure pairing that silently produces nothing
        # must fail THIS test loudly, not read as "nothing to check".
        assert closure, (
            f"compute_intra_package_closure_with_deploy_root_relative() returned "
            f"an EMPTY closure for {deploy_path!r} (root={root}, "
            f"data_root={_REPO_ROOT}). An empty closure for a script known to "
            "read non-code files is the exact silent-drop defect AC "
            "BP-900g-8-ii exists to catch -- it must never pass silently."
        )
        namespaced = {
            dep if dep in deploy_root_relative else f"{deploy_prefix}{dep}"
            for dep in closure
        }
        assert namespaced, "namespaced closure must not be empty when closure is non-empty."

        assert data_dep in namespaced, (
            f"The namespaced closure (what the guard actually compares against "
            f"Set B) did not include {data_dep!r} for {deploy_path!r}. "
            f"Namespaced closure: {sorted(namespaced)!r}. A non-code file a "
            "deployed script reads must be in the SAME derived set a module "
            "import would be (AC BP-900g-8-ii)."
        )

        declared_without = namespaced - {data_dep}
        uncovered = _bri.find_uncovered_closure_dependencies(
            deploy_path, root, declared_without, data_root=_REPO_ROOT
        )
        assert data_dep in uncovered, (
            f"find_uncovered_closure_dependencies() did not report {data_dep!r} as "
            f"uncovered for {deploy_path} when the declared set withheld it. "
            f"Uncovered: {sorted(uncovered)!r} (AC BP-900g-8-ii)."
        )

        declared_with = set(namespaced)
        still_uncovered = _bri.find_uncovered_closure_dependencies(
            deploy_path, root, declared_with, data_root=_REPO_ROOT
        )
        assert data_dep not in still_uncovered, (
            f"find_uncovered_closure_dependencies() reported {data_dep!r} as "
            f"uncovered for {deploy_path} even though the declared set explicitly "
            f"included it. Uncovered: {sorted(still_uncovered)!r} (AC BP-900g-8-ii)."
        )

    # ---- Discriminating control (defect 2 proof): the SAME script, resolved
    # through the SAME real root, WITHOUT the data_root split, must produce a
    # DIFFERENT (empty) answer -- this is the exact pre-fix call shape and
    # proves the assertions above are not a phantom green. If a future change
    # collapses data_root back into root (or removes it), this sub-assertion
    # is what catches it, independently of the namespaced-closure assertions
    # above which would also then fail.
    doc_type_validators_resolved = _build._source_file_for_deploy_path(
        _REPO_ROOT, "scripts/commit_guardian/doc_type_validators.py"
    )
    assert doc_type_validators_resolved is not None
    dtv_source, dtv_root, _dtv_prefix = doc_type_validators_resolved
    pre_fix_style_closure = _bri.compute_intra_package_closure(dtv_source, dtv_root)
    assert "config/doc_types.json" not in pre_fix_style_closure, (
        "compute_intra_package_closure(source_file, root) -- i.e. WITHOUT "
        "data_root, the pre-AC-BP-900g-8-ii-fix call shape -- unexpectedly "
        "included config/doc_types.json. This sub-assertion exists to prove "
        "the fixture is discriminating: it must be EMPTY here (root=templates "
        "has no templates/config/doc_types.json) precisely because production "
        "only finds it by ALSO passing data_root=package_root, which the "
        "cases above verify it does. "
        f"Got: {sorted(pre_fix_style_closure)!r} (AC BP-900g-8-ii)."
    )


# ---------------------------------------------------------------------------
# Test 2 -- angle: reachability. NEW in this rework. The central-case
# regression against a REAL subprocess, plus a generalisation control.
# ---------------------------------------------------------------------------


def test_bp_900g_8_ii_diagram_types_json_and_a_generalisation_control_are_flagged_by_the_real_build_subprocess(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8-ii
    # angle: reachability
    """THE CENTRAL-CASE REGRESSION -- withhold-then-restore round trip.

    ``build.py::_source_file_for_deploy_path`` returns ``root=<package_root>/templates``
    for the entire commit-guardian family. A ``config/``-relative read from
    that family resolves against ``<package_root>/templates/config/...``,
    which never exists unless the read is ALSO resolved against the deploy
    root -- ``config/diagram_types.json`` (read by
    ``diagram_type_validators.py::_find_diagram_types_json``, which degrades
    SILENTLY to a built-in constant on failure) was the confirmed instance:
    genuinely undeployed and genuinely unflagged before this AC's fix landed.

    TDD REWORK (2026-09-01, defect 1 fix): the prior version of Half 1
    asserted an UNMODIFIED copy must FAIL (``returncode != 0``) -- that was
    true only while the production defect was live. The production fix is
    now DONE and verified (confirmed directly: a clean ``python
    scripts/build.py --target-dir /tmp/x`` exits 0 and deploys
    ``diagram_types.json`` alongside ``doc_types.json`` and
    ``skill_registry.json``), so asserting non-zero on an unmodified tree
    directly CONTRADICTS test 3's State 1 (which correctly asserts an
    unmodified tree exits 0) -- no production code could satisfy both at
    once. Half 1 is rewritten as a withhold-then-restore round trip instead:
    state (1) WITHHOLDS ``config/diagram_types.json`` from all three
    core-config deploy tuples and asserts the build correctly blocks and
    names the gap; state (2) restores an UNMODIFIED copy and asserts the
    build clears AND that the file is ACTUALLY present in the deployed
    output -- exit 0 alone cannot distinguish "the file shipped" from "the
    guard stopped looking".

    GENERALISATION CONTROL (Half 2, UNCHANGED): naming ``diagram_types.json``
    (or the other four files in this AC's own doc_links) in a list would
    satisfy the assertions above without fixing the actual defect -- the
    closure must be DERIVED, not looked up. Proven by injecting a read of a
    config file that has NEVER existed before into a DIFFERENT
    commit-guardian script (``check_hook_parity.py``, chosen because it
    shares nothing with either ``*_types.json`` reader) and asserting it is
    ALSO flagged. If a fix only special-cases the two named ``*_types.json``
    files, this half stays red even after Half 1 goes green.
    """
    # ---- Half 1a: withhold config/diagram_types.json from all three
    # core-config deploy tuples -- must block, naming the file and its reader.
    copy_withheld = tmp_path / "diagram_types_copy_withheld"
    _copy_package_tree(copy_withheld)
    _withhold_diagram_types_from_deploy_declaration(copy_withheld)

    target_dir_withheld = tmp_path / "diagram_types_target_withheld"
    result_withheld = _run_build_in_copy(copy_withheld, target_dir_withheld)
    combined_withheld = result_withheld.stdout + result_withheld.stderr

    assert result_withheld.returncode != 0, (
        "build.py --target-dir exited 0 after config/diagram_types.json was "
        "withheld from all three core-config deploy tuples (scripts/build.py's "
        "_get_source_deployable_scripts and _get_source_paths_for_guard, plus "
        "scripts/build_phases.py's build_ac_store deploy tuple) in a temp "
        "copy, but templates/scripts/commit_guardian/diagram_type_validators.py "
        "still reads it. The widened closure guard must name this gap.\n"
        f"stdout:\n{result_withheld.stdout}\nstderr:\n{result_withheld.stderr}\n"
        "(AC BP-900g-8-ii)."
    )
    assert "config/diagram_types.json" in combined_withheld, (
        "build.py's output did not name config/diagram_types.json as an "
        "undeployed non-code dependency after it was withheld. This is the "
        "central case this AC exists for: the commit-guardian family's "
        "closure root (<package_root>/templates) makes every config/-relative "
        "read in that family resolve against a path that never exists unless "
        f"the deploy-root split is also applied. Output:\n{combined_withheld}\n"
        "(AC BP-900g-8-ii)."
    )
    assert "diagram_type_validators.py" in combined_withheld, (
        "build.py's failure output did not name "
        "diagram_type_validators.py -- the script that actually reads the "
        f"withheld dependency. Output:\n{combined_withheld}\n"
        "(AC BP-900g-8-ii)."
    )

    # ---- Half 1b: restore to a genuinely UNMODIFIED copy -- must clear, AND
    # the file must actually be present in the deployed output (exit 0 alone
    # cannot distinguish "shipped" from "guard stopped looking").
    copy_restored = tmp_path / "diagram_types_copy_restored"
    _copy_package_tree(copy_restored)

    target_dir_restored = tmp_path / "diagram_types_target_restored"
    result_restored = _run_build_in_copy(copy_restored, target_dir_restored)
    assert result_restored.returncode == 0, (
        "build.py --target-dir exited non-zero on a genuinely UNMODIFIED "
        "copy of the package tree. The production fix for AC BP-900g-8-ii is "
        "verified done: config/diagram_types.json is declared in all three "
        "core-config deploy tuples and actually deployed, so a clean build "
        f"must succeed.\nstdout:\n{result_restored.stdout}\n"
        f"stderr:\n{result_restored.stderr}\n(AC BP-900g-8-ii)."
    )
    deployed_diagram_types = target_dir_restored / ".leafcutter" / "config" / "diagram_types.json"
    assert deployed_diagram_types.is_file(), (
        f"build.py exited 0 but did not actually deploy "
        f"config/diagram_types.json to {deployed_diagram_types}. Exit 0 alone "
        "cannot distinguish the file having genuinely shipped from the guard "
        "having simply stopped looking for it (AC BP-900g-8-ii)."
    )

    # ---- Half 2: generalisation control (fresh unmodified copy -- this half
    # is independent of Half 1's withhold, and must run against the SAME
    # otherwise-clean deploy declaration Half 1b just proved is complete) ----
    copy_gen = tmp_path / "diagram_types_copy_generalisation"
    _copy_package_tree(copy_gen)

    marker_name = "__bp900g8ii_generalisation_control__.json"
    target_script = (
        copy_gen / "templates" / "scripts" / "commit_guardian" / "check_hook_parity.py"
    )
    assert target_script.is_file(), (
        f"Fixture assumption broken: {target_script} does not exist."
    )
    marker_config = copy_gen / "config" / marker_name
    assert not marker_config.exists(), (
        f"Fixture assumption broken: {marker_config} already exists in the copy."
    )
    marker_config.write_text("{}\n", encoding="utf-8")

    injected_block = textwrap.dedent(
        f'''

        # >>> BP-900g-8-ii GENERALISATION CONTROL (temp copy only) >>>
        _BP900G8II_GEN_MARKER = (
            Path(__file__).resolve().parent.parent.parent.parent / "config" / "{marker_name}"
        )


        def _bp900g8ii_gen_control_load_marker() -> dict:
            with open(_BP900G8II_GEN_MARKER, encoding="utf-8") as f:
                return json.load(f)
        # <<< BP-900g-8-ii GENERALISATION CONTROL <<<
        '''
    )
    original_script = target_script.read_text(encoding="utf-8")
    target_script.write_text(original_script + injected_block, encoding="utf-8")

    target_dir_gen = tmp_path / "diagram_types_target_generalisation"
    result_gen = _run_build_in_copy(copy_gen, target_dir_gen)
    combined_gen = result_gen.stdout + result_gen.stderr

    assert result_gen.returncode != 0, (
        f"build.py --target-dir exited 0 after injecting a read of a "
        f"NEVER-BEFORE-EXISTING config file ({marker_name}) into "
        "check_hook_parity.py -- a commit-guardian script unrelated to "
        "either *_types.json reader. A fix scoped to the two named files in "
        "this AC's own doc_links would incorrectly pass this build.\n"
        f"stdout:\n{result_gen.stdout}\nstderr:\n{result_gen.stderr}\n"
        "(AC BP-900g-8-ii)."
    )
    assert marker_name in combined_gen, (
        f"build.py's output did not name {marker_name!r} as an undeployed "
        f"non-code dependency of check_hook_parity.py. Output:\n{combined_gen}\n"
        "(AC BP-900g-8-ii): the derivation must generalise to ANY "
        "commit-guardian script, not just the two files this AC's own "
        "doc_links happen to name."
    )


# ---------------------------------------------------------------------------
# Test 3 -- angle: reachability, must_block. RESTORED to a real build.py
# subprocess, in THREE separate states, per the AC's own test_spec entry 2.
# ---------------------------------------------------------------------------


def test_bp_900g_8_ii_build_subprocess_blocks_when_a_non_code_read_is_withheld_from_the_deploy_manifest_with_the_same_force_as_a_module(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8-ii
    # angle: reachability
    """AC BP-900g-8-ii: three states, each a real `python scripts/build.py
    --target-dir <tmp>` subprocess against its own temp copy.

    (1) unmodified tree -- exit 0. NOT OPTIONAL: a positive-path build alone
        cannot tell a working guard from an absent one (the AC's own
        test_rationale). The prior pass on this branch dropped this state to
        fit a 60-second gate budget that does not bind this authoring pass.
    (2) ONE non-code dependency of a deployed script withheld from every
        deploy manifest -- non-zero, naming the file, the reading script,
        and the deploy phase.
    (3) ONE module dependency withheld instead (BP-900g-8's own already-green
        case, reproduced here as the comparison baseline) -- non-zero with
        the same three elements named.

    Then the same-force clause: (2) and (3) are compared directly -- both
    non-zero, both carrying the SAME "[CLOSURE GUARD]" enforcement marker --
    so a data-file gap cannot be a warning while a module gap is an error.
    """
    marker_name = "__bp900g8ii_test3_marker__.json"

    # ---- State 1: unmodified tree -----------------------------------------
    copy_clean = tmp_path / "state1_clean"
    _copy_package_tree(copy_clean)
    result_clean = _run_build_in_copy(copy_clean, tmp_path / "state1_target")
    assert result_clean.returncode == 0, (
        "build.py --target-dir exited non-zero on an UNMODIFIED copy of the "
        "package tree. A positive-path build alone cannot tell a working "
        "guard from an absent one if this state is not itself green.\n"
        f"stdout:\n{result_clean.stdout}\nstderr:\n{result_clean.stderr}\n"
        "(AC BP-900g-8-ii)."
    )

    # ---- State 2: one non-code dependency withheld -------------------------
    copy_data = tmp_path / "state2_data_withheld"
    _copy_package_tree(copy_data)
    _inject_marker_read_into_injection_builders(copy_data, marker_name)

    result_data = _run_build_in_copy(copy_data, tmp_path / "state2_target")
    combined_data = result_data.stdout + result_data.stderr
    assert result_data.returncode != 0, (
        "build.py --target-dir exited 0 while a withheld non-code dependency "
        f"(config/{marker_name}, read by injection_builders.py) was present. "
        f"stdout:\n{result_data.stdout}\nstderr:\n{result_data.stderr}\n"
        "(AC BP-900g-8-ii): a missing non-code file must fail the build with "
        "the same force as a missing module."
    )
    assert marker_name in combined_data, (
        f"build.py's failure output did not name the missing non-code "
        f"dependency {marker_name!r}. Output:\n{combined_data} (AC BP-900g-8-ii)."
    )
    assert "injection_builders.py" in combined_data, (
        "build.py's failure output did not name the deployed script that reads "
        f"the missing non-code dependency ('injection_builders.py'). Output:\n"
        f"{combined_data} (AC BP-900g-8-ii)."
    )
    assert "[CLOSURE GUARD]" in combined_data, (
        "build.py's failure output for the withheld non-code dependency did "
        "not carry the '[CLOSURE GUARD]' enforcement marker -- the SAME "
        f"marker the module case already uses. Output:\n{combined_data}\n"
        "(AC BP-900g-8-ii)."
    )

    # ---- State 3: one module dependency withheld (BP-900g-8's own case) ---
    copy_module = tmp_path / "state3_module_withheld"
    _copy_package_tree(copy_module)
    build_phases_py = copy_module / "scripts" / "build_phases.py"
    withhold_re = re.compile(
        r"^[ \t]*\([^\n]*_component_migration_map\.py[^\n]*\),?[ \t]*$",
        re.MULTILINE,
    )
    original_phases = build_phases_py.read_text(encoding="utf-8")
    assert withhold_re.search(original_phases), (
        "Fixture assumption broken: could not find the "
        "_component_migration_map.py deploy_map entry in "
        "scripts/build_phases.py to withhold."
    )
    build_phases_py.write_text(withhold_re.sub("", original_phases), encoding="utf-8")

    result_module = _run_build_in_copy(copy_module, tmp_path / "state3_target")
    combined_module = result_module.stdout + result_module.stderr
    assert result_module.returncode != 0, (
        "build.py --target-dir exited 0 while _component_migration_map.py "
        "was withheld from build_ac_store's deploy_map (the BP-900g-8 module "
        f"case).\nstdout:\n{result_module.stdout}\nstderr:\n{result_module.stderr}"
    )
    assert "_component_migration_map.py" in combined_module, (
        "build.py's failure output did not name the withheld MODULE "
        f"dependency '_component_migration_map.py'. Output:\n{combined_module}."
    )
    assert "[CLOSURE GUARD]" in combined_module, (
        "build.py's failure output for the withheld module dependency did "
        f"not carry the '[CLOSURE GUARD]' marker. Output:\n{combined_module}."
    )

    # ---- Same-force comparison ---------------------------------------------
    assert result_data.returncode != 0 and result_module.returncode != 0, (
        "Expected BOTH the withheld non-code dependency (state 2) and the "
        "withheld module dependency (state 3) to fail the build with the "
        f"same force. Got returncodes data={result_data.returncode!r}, "
        f"module={result_module.returncode!r} (AC BP-900g-8-ii)."
    )
    assert "[CLOSURE GUARD]" in combined_data and "[CLOSURE GUARD]" in combined_module, (
        "Expected the SAME '[CLOSURE GUARD]' enforcement marker to appear in "
        "both the withheld-non-code-dependency output and the "
        "withheld-module-dependency output -- falsifying an implementation "
        "that reports the data case through a second, parallel (e.g. "
        "WARNING-only) code path.\n"
        f"data output:\n{combined_data}\nmodule output:\n{combined_module}\n"
        "(AC BP-900g-8-ii)."
    )


# ---------------------------------------------------------------------------
# Test 4 -- angle: failure. RESTORED to a real build.py subprocess (the
# prior pass called compute_intra_package_closure directly). THE
# DERIVED-NOT-HARDCODED CONTROL.
# ---------------------------------------------------------------------------


def test_bp_900g_8_ii_a_non_code_read_added_after_the_guard_exists_fails_the_build_without_any_change_to_the_guard(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8-ii
    # angle: failure
    """AC BP-900g-8-ii: a config file under a name that has NEVER existed in
    this repository, added to a deployed script AFTER the guard exists, is
    reported as an uncovered dependency by a real `build.py` subprocess --
    and clears once the SAME core-config mechanism is told about it --
    proving the closure is DERIVED from the code, not a hand-maintained list
    of the files named in this AC's own doc_links.

    A guard hardcoded to {doc_types.json, ac_store_schema.json,
    agent_registry.json, ...} would pass every other test in this file
    completely (they name exactly those files) and only die here.
    """
    copy_root = tmp_path / "test4_copy"
    _copy_package_tree(copy_root)

    marker_name = "__bp900g8ii_test4_never_before_seen__.json"
    marker_config = copy_root / "config" / marker_name
    assert not marker_config.exists(), (
        f"Fixture assumption broken: {marker_config} already exists in the copy."
    )
    _inject_marker_read_into_injection_builders(copy_root, marker_name)

    target_before = tmp_path / "test4_target_before"
    result_before = _run_build_in_copy(copy_root, target_before)
    combined_before = result_before.stdout + result_before.stderr

    assert result_before.returncode != 0, (
        "build.py --target-dir exited 0 in a temp copy where "
        f"injection_builders.py reads a NEW config file (config/{marker_name}) "
        "declared in NO deploy map.\n"
        f"stdout:\n{result_before.stdout}\nstderr:\n{result_before.stderr}\n"
        "(AC BP-900g-8-ii): a non-code dependency introduced AFTER the guard "
        "exists must fail the build without any change to the guard itself."
    )
    assert marker_name in combined_before, (
        f"build.py's failure output did not name the new, never-before-existing "
        f"config file {marker_name!r}. Output:\n{combined_before} (AC BP-900g-8-ii)."
    )
    assert "injection_builders.py" in combined_before, (
        "build.py's failure output did not name the deployed script that "
        f"reads the new dependency. Output:\n{combined_before} (AC BP-900g-8-ii)."
    )

    # ---- Round trip: declare the SAME dependency through the SAME ordinary
    # mechanism (the core-config tuple scripts/build.py already uses for
    # config/doc_types.json et al.) and assert the SAME subprocess clears.
    build_py = copy_root / "scripts" / "build.py"
    original_build = build_py.read_text(encoding="utf-8")
    anchor_count = original_build.count(_CORE_CONFIG_TUPLE_ANCHOR)
    assert anchor_count == 2, (
        "Fixture assumption broken: expected the core-config tuple anchor "
        "(the block ending '\"paths.json\",\\n    ):') to appear exactly "
        "twice in scripts/build.py (once in _get_source_deployable_scripts, "
        f"once in _get_source_paths_for_guard); found {anchor_count}. "
        "build.py's core-config declaration shape may have changed -- "
        "update this test's anchor."
    )
    declared = original_build.replace(
        _CORE_CONFIG_TUPLE_ANCHOR,
        f'        "paths.json",\n        "{marker_name}",\n    ):',
    )
    build_py.write_text(declared, encoding="utf-8")

    target_after = tmp_path / "test4_target_after"
    result_after = _run_build_in_copy(copy_root, target_after)
    assert result_after.returncode == 0, (
        f"build.py --target-dir still exited non-zero after declaring "
        f"config/{marker_name} through the SAME core-config mechanism the "
        "module case already uses. Declaring the SAME dependency through the "
        f"SAME mechanism must clear the finding.\n"
        f"stdout:\n{result_after.stdout}\nstderr:\n{result_after.stderr}\n"
        "(AC BP-900g-8-ii)."
    )


# ---------------------------------------------------------------------------
# Test 5 -- angle: boundary. RESTORED to a real build.py subprocess (the
# prior pass called compute_intra_package_closure directly against a
# throwaway fake-root fixture tree).
# ---------------------------------------------------------------------------


def test_bp_900g_8_ii_a_read_of_an_operating_system_or_external_tool_path_is_not_added_to_the_derived_set(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8-ii
    # angle: boundary
    """AC BP-900g-8-ii: the closure does not demand the build deploy things
    it does not own -- demonstrated against a real `build.py` subprocess in
    TWO states against the same injected script.

    (1) A deployed script reads ONLY an absolute operating-system path and a
        path owned by an external tool the package does not ship -- exit 0,
        and neither path is named anywhere in the build's output. Also
        asserts the "reported as underivable, never silently dropped" clause:
        each unresolvable read is disclosed via a WARNING naming the script,
        never silently absorbed into a clean closure.
    (2) THE REQUIRED POSITIVE CONTROL: the SAME script, with a package-owned,
        undeclared config file read ALSO added -- non-zero, and the
        package-owned file IS named, while the OS/external-tool paths are
        STILL not named. Without this half, the exclusion in (1) would be
        satisfiable by a rule that excludes everything, which is the same
        defect as no rule at all.
    """
    copy_root = tmp_path / "test5_copy"
    _copy_package_tree(copy_root)

    target_script = (
        copy_root / "templates" / "scripts" / "commit_guardian" / "check_hook_parity.py"
    )
    assert target_script.is_file(), (
        f"Fixture assumption broken: {target_script} does not exist."
    )
    original_script = target_script.read_text(encoding="utf-8")

    os_path = os.path.join(os.sep, "etc", "hostname")
    external_tool_path = os.path.expanduser(os.path.join("~", ".gitconfig"))

    boundary_only_block = textwrap.dedent(
        f'''

        # >>> BP-900g-8-ii TEST-5 BOUNDARY (OS / external-tool only, temp copy) >>>
        _BP900G8II_OS_PATH = {os_path!r}
        _BP900G8II_EXTERNAL_TOOL_PATH = {external_tool_path!r}


        def _bp900g8ii_test5_boundary_probe() -> None:
            with open(_BP900G8II_OS_PATH, encoding="utf-8") as f:
                f.read()
            with open(_BP900G8II_EXTERNAL_TOOL_PATH, encoding="utf-8") as f:
                f.read()
        # <<< BP-900g-8-ii TEST-5 BOUNDARY <<<
        '''
    )
    target_script.write_text(original_script + boundary_only_block, encoding="utf-8")

    result_os_only = _run_build_in_copy(copy_root, tmp_path / "test5_target_os_only")
    combined_os_only = result_os_only.stdout + result_os_only.stderr

    assert result_os_only.returncode == 0, (
        f"build.py --target-dir exited non-zero after adding ONLY an "
        f"operating-system path read ({os_path}) and an external-tool path "
        f"read ({external_tool_path}) to a deployed script. Neither path is "
        "owned by this package; the guard must not demand the build deploy "
        f"things it does not own.\nstdout:\n{result_os_only.stdout}\n"
        f"stderr:\n{result_os_only.stderr}\n(AC BP-900g-8-ii)."
    )
    assert os_path not in combined_os_only, (
        f"build.py's output named the operating-system path {os_path!r}. "
        f"Output:\n{combined_os_only} (AC BP-900g-8-ii)."
    )
    assert external_tool_path not in combined_os_only, (
        f"build.py's output named the external-tool path "
        f"{external_tool_path!r}. Output:\n{combined_os_only} (AC BP-900g-8-ii)."
    )
    assert "unresolvable data-file read" in combined_os_only, (
        "Expected the OS-path / external-tool-path reads to be disclosed as "
        "underivable (a WARNING naming the script), never silently absorbed "
        f"into a clean closure. Output:\n{combined_os_only} (AC BP-900g-8-ii)."
    )
    assert "check_hook_parity.py" in combined_os_only, (
        "Expected the underivable-read warning to name check_hook_parity.py "
        f"(the script carrying the OS/external-tool reads). Output:\n"
        f"{combined_os_only} (AC BP-900g-8-ii)."
    )

    # ---- Positive control: package-owned, undeclared file added to the SAME
    # script. If it is not named, the exclusion above is satisfiable by a
    # rule that excludes everything (AC BP-900g-8-ii).
    marker_name = "__bp900g8ii_test5_package_marker__.json"
    marker_config = copy_root / "config" / marker_name
    marker_config.write_text("{}\n", encoding="utf-8")

    package_block = textwrap.dedent(
        f'''

        # >>> BP-900g-8-ii TEST-5 POSITIVE CONTROL (package-owned, undeclared) >>>
        _BP900G8II_PACKAGE_MARKER = (
            Path(__file__).resolve().parent.parent.parent.parent / "config" / "{marker_name}"
        )


        def _bp900g8ii_test5_package_probe() -> None:
            with open(_BP900G8II_PACKAGE_MARKER, encoding="utf-8") as f:
                f.read()
        # <<< BP-900g-8-ii TEST-5 POSITIVE CONTROL <<<
        '''
    )
    target_script.write_text(
        original_script + boundary_only_block + package_block, encoding="utf-8"
    )

    result_with_package = _run_build_in_copy(
        copy_root, tmp_path / "test5_target_with_package"
    )
    combined_with_package = result_with_package.stdout + result_with_package.stderr

    assert result_with_package.returncode != 0, (
        f"build.py --target-dir exited 0 even after adding a package-owned, "
        f"undeclared config file read (config/{marker_name}) to the SAME "
        "script that also reads the OS/external-tool paths. An exclusion "
        "rule that excludes the OS/external paths by excluding EVERYTHING "
        f"would incorrectly pass here too.\nstdout:\n{result_with_package.stdout}\n"
        f"stderr:\n{result_with_package.stderr}\n(AC BP-900g-8-ii)."
    )
    assert marker_name in combined_with_package, (
        f"build.py's failure output did not name the package-owned, "
        f"undeclared config file {marker_name!r} -- the required positive "
        f"control. Output:\n{combined_with_package} (AC BP-900g-8-ii)."
    )
    assert os_path not in combined_with_package, (
        f"build.py's output named the operating-system path {os_path!r} "
        f"even in the positive-control run. Output:\n{combined_with_package} "
        "(AC BP-900g-8-ii)."
    )
    assert external_tool_path not in combined_with_package, (
        f"build.py's output named the external-tool path "
        f"{external_tool_path!r} even in the positive-control run. Output:\n"
        f"{combined_with_package} (AC BP-900g-8-ii)."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-09-01 [test-writer/BP-900g-8-ii]: Initial red-baseline test authoring.
#   Test 1 is pure-unit against compute_intra_package_closure() /
#   find_uncovered_closure_dependencies(). Tests 2-4 (original numbering)
#   mutated REAL source files in place inside try/finally blocks.
# - 2026-09-01 [test-writer/BP-900g-8-ii, TDD REWORK]: A hand-review found the
#   prior pass's own test 1 used compute_intra_package_closure(script,
#   _REPO_ROOT) -- production never passes _REPO_ROOT for the commit-guardian
#   family, it passes <package_root>/templates, so test 1 could not see the
#   central defect (a config/-relative read in that family resolves against
#   a root where config/ never exists and is silently dropped). Confirmed by
#   direct inspection that config/diagram_types.json is genuinely undeployed
#   and genuinely unflagged: `python scripts/build.py --target-dir /tmp/x`
#   exits 0 on this branch as of this rework. This rework:
#     (a) adds a new reachability test exercising the REAL build.py subprocess
#         against an UNMODIFIED temp copy, asserting config/diagram_types.json
#         is named -- RED today -- plus a generalisation control (a
#         never-before-existing data file injected into a DIFFERENT
#         commit-guardian script) so a fix scoped to the AC's own named files
#         cannot pass;
#     (b) restores the AC's test_spec entry 2 to its full THREE-state
#         build.py-subprocess shape (unmodified / non-code withheld / module
#         withheld + same-force comparison), which the prior pass had
#         collapsed into one combined run to fit a 60-second fast-lane gate
#         budget that does not bind this authoring pass;
#     (c) restores test_spec entries 3 and 4 to real build.py subprocesses
#         (the prior pass called compute_intra_package_closure()/a fake-root
#         fixture tree directly for both);
#     (d) switches EVERY mutating test from in-place mutation of the real
#         scripts/config/templates trees (restored via try/finally) to a
#         shutil.copytree'd temp copy per test, because a hard kill during
#         the prior pass's window left scripts/injection_builders.py modified
#         with a stray marker-reading block on disk for over four minutes
#         with no pytest running, requiring a manual `git restore`.
#   Verified RED for the intended reason (not a typo/import error) by running
#   this file directly against the current implementation before sign-off;
#   see the test-writer sign-off comment for the exact captured failures and
#   measured wall time. (#BP-900g-8-ii)
# - 2026-09-01 [test-writer/BP-900g-8-ii, DEFECT-FIX PASS]: the production fix
#   (root/data_root split in compute_intra_package_closure_with_deploy_root_relative,
#   plus config/diagram_types.json and config/skill_registry.json added to all
#   three core-config deploy tuples) landed and was independently confirmed:
#   a clean `python scripts/build.py --target-dir /tmp/x` exits 0 and deploys
#   diagram_types.json and skill_registry.json alongside doc_types.json. Two
#   defects remained in THIS FILE from the prior pass, both fixed here without
#   touching scripts/build.py, scripts/build_phases.py, or
#   scripts/build_referential_integrity.py:
#     (1) Test 1 still called compute_intra_package_closure(script, _REPO_ROOT)
#         -- the same phantom-green namespace mismatch the file's own TDD
#         REWORK note above already diagnosed and was meant to prevent.
#         Confirmed empirically: compute_intra_package_closure(
#         doc_type_validators.py, root=templates) (no data_root) returns
#         `set()`, while the SAME call via
#         compute_intra_package_closure_with_deploy_root_relative(...,
#         data_root=package_root) (what the guard actually calls) returns
#         {"config/doc_types.json"}. Fixed by resolving every case through
#         build._source_file_for_deploy_path (the guard's own resolver),
#         asserting on the resulting namespaced closure, adding a non-vacuity
#         assertion, adding a fourth case (doc_type_validators.py itself --
#         the reader that was silently empty end-to-end), and adding an
#         explicit discriminating control proving the no-data_root call shape
#         gives a DIFFERENT (empty) answer for the same script/root.
#     (2) Test 2 Half 1 asserted an UNMODIFIED copy must exit non-zero --
#         correct only while the production defect was live, and directly
#         contradicting test 3's State 1 (unmodified copy must exit 0). Fixed
#         by rewriting Half 1 as a withhold-then-restore round trip: withhold
#         config/diagram_types.json from all three core-config deploy tuples
#         (two in build.py, one in build_phases.py) via the new
#         _withhold_diagram_types_from_deploy_declaration() helper -- must
#         block, naming the file and diagram_type_validators.py as the reader
#         -- then restore an unmodified copy -- must clear AND the file must
#         be verifiably present at <target>/.leafcutter/config/diagram_types.json,
#         since exit 0 alone cannot distinguish "shipped" from "guard stopped
#         looking". Half 2 (the generalisation control) was already correct
#         and is unchanged.
#   Every mutating operation still runs against a fresh shutil.copytree per
#   test (TEMP-COPY DISCIPLINE); nothing in this pass touched the real
#   scripts/, config/, or templates/ trees. All 5 tests pass under
#   AC_ENFORCE_STRICT=1 as of this pass; see the test-writer sign-off comment
#   for the exact strict-mode run and measured wall time. (#BP-900g-8-ii)
# ====================================================================
