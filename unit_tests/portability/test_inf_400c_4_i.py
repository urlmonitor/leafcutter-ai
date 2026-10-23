"""
MODULE: test_inf_400c_4_i
GOAL: RED test stubs for AC INF-400c-4-i -- no shipped surface (the signoff
    skill's knowledge-capture section, or the knowledge-emission sections of
    product-owner, business-analyst, it-po) may carry a destination of its
    own for the knowledge_captured append. Each must instead tell an agent
    HOW TO OBTAIN the build-time-declared sink (config/knowledge_sink.json,
    written by build_knowledge_sink_declaration in scripts/build_phases.py,
    read via scripts/knowledge/harvest_learnings.py --print-sink, both of
    which already exist and are already wired into every real build.py run
    as of this writing -- see INF-400c-4-v, work_status: done).
AC: INF-400c-4-i (source_ac)
DEPENDS ON: INF-400c-4 (work_status: todo as of authoring) -- the parity
    check this file exercises directly (scripts/ci/check_sink_parity.py)
    does not exist yet in this worktree. The four surfaces themselves are
    ALSO unmodified as of authoring: all four still literally instruct an
    agent to append to `debugging/logs/agent_telemetry.jsonl` (the
    operational telemetry stream, not the declared knowledge sink). Every
    test below is expected to be RED at authoring time, via one of two
    genuinely different mechanisms -- see the module-level NOTE below and
    the per-test docstrings.

CHECK INTERFACE THIS FILE FIXES (test-writer's concrete reading of the AC's
    "no destination of its own" / "no literal to extract" wording --
    python-coder implements scripts/ci/check_sink_parity.py against this
    exact shape; mirrors the argv/exit-code/stdout conventions already
    established by scripts/ci/check_consumer_install.py):

    Usage::

        python scripts/ci/check_sink_parity.py --target-dir <deployed-project-root>

    ``--target-dir`` is the project root a real ``build.py`` run was pointed
    at (the same argument ``check_consumer_install.py --target-dir`` takes),
    NOT the deployed output root itself. The script derives the deployed
    root as ``<target-dir>/.leafcutter`` (this package's own
    ``output_root_name`` default -- the same convention
    ``test_inf_400c_4_v.py`` already relies on).

    Surfaces inspected -- exactly these four canonical Claude-format
    deployed files, never the mirrored ``.leafcutter/gemini/`` copies
    (a distinct concern this AC does not own):

        1. ``<deployed-root>/skills/signoff/SKILL.md``        id: "signoff"
        2. ``<deployed-root>/agents/product-owner.md``        id: "product-owner"
        3. ``<deployed-root>/agents/business-analyst.md``     id: "business-analyst"
        4. ``<deployed-root>/agents/it-po.md``                id: "it-po"

    For each surface, the check locates the knowledge-capture / knowledge-
    emission INSTRUCTION paragraph (the paragraph telling an agent to emit
    and append a record) as distinct from any paragraph that only DISCUSSES
    the telemetry stream historically (the signoff settlement/scope note),
    and determines -- by REAL EXECUTION, never a string comparison against
    the surface's own prose -- where an agent following that instruction
    literally would append:

    - If the instruction paragraph names a resolution INVOCATION (a fenced
      or inline code span containing both ``harvest_learnings.py`` and
      ``--print-sink``), the check runs that invocation for real against the
      DEPLOYED copy at ``<deployed-root>/scripts/knowledge/harvest_learnings.py``,
      with its ``cwd`` set to ``--target-dir``, and takes stdout (stripped)
      as the surface's resolved destination.
    - Otherwise, if the instruction paragraph names a literal path in
      backticks matching ``debugging/logs/*.jsonl``, that literal IS the
      surface's self-carried destination (the pre-AC / defective shape) --
      the check does NOT treat this as a resolution mechanism, and reports
      the surface as carrying a destination of its own.
    - Otherwise (neither found), the surface is reported as unparseable.

    The check compares every surface's resolved destination against the
    SAME install's own build-time declaration
    (``<deployed-root>/config/knowledge_sink.json`` -> key
    ``"knowledge_emission_sink"``). All four must resolve to exactly that
    value for the check to pass.

    Exit codes::

        0   Exactly four surfaces were inspected and every one resolves --
            via a real invocation, never a literal -- to the project's
            declared sink.
        1   At least one surface fails: it carries a literal destination of
            its own, its resolved value does not match the declared sink,
            or its instruction paragraph could not be parsed. stdout/stderr
            names every failing surface by the ids listed above.
        2   Usage/environment error: --target-dir does not exist, or the
            deployed tree is missing one or more of the four canonical
            surface files, the deployed harvest_learnings.py, or
            config/knowledge_sink.json (a target that was never actually
            built).

    Stdout contract (all modes): a line of the exact form
    ``Inspected N surfaces: <comma-separated ids>`` where N MUST equal 4
    whenever all four canonical files were found -- a check that silently
    found none must never report success (this file's first test pins
    exactly that). On failure, additionally one line per failing surface:
    ``FAIL <surface-id>: <reason>``.

NOTE -- two genuinely different RED mechanisms in this file, per the
    ticket's explicit request to distinguish them:

    (A) "errors because the check does not exist" -- tests 1, 2 (all four
        parametrised cases), and 5 invoke ``scripts/ci/check_sink_parity.py``
        directly and fail at ``_assert_check_script_exists()`` (a clear,
        informative AssertionError naming the missing file and this
        docstring) before any subprocess is even attempted.

    (B) "fails because the surfaces still carry the path" -- tests 3, 4, and
        6 need NO check script at all. They simulate literally following
        the CURRENTLY SHIPPED surface text (or, for test 6, the currently
        shipped ``harvest_learnings.py --print-sink`` behaviour directly)
        and assert on the REAL resulting file-system state -- these fail
        today for a genuine behavioural reason: the literal destination the
        surfaces currently name is CWD-relative and/or names the wrong file
        (the operational telemetry stream, not the declared knowledge
        sink), which is the exact corpus-split defect this AC exists to
        close.

REAL-ARTIFACT / REACHABILITY NOTE (BP-1100f-2 + BP-1100g-2): every test
    drives the REAL ``scripts/ci/check_consumer_install.py`` (which shells
    out to the REAL ``scripts/build.py``) against a REAL ``tmp_path``
    scratch directory, reads the REAL deployed surface files it produces,
    and (tests 3/4/6) performs REAL file appends and REAL subprocess
    invocations of the REAL deployed ``harvest_learnings.py``. Nothing here
    greps the four surfaces as its primary proof -- test_rationale in the
    AC YAML explicitly names that as the coverage this AC's Gherkin was
    rewritten to escape.
"""
# @ac-tag: INF-400c-4-i

from __future__ import annotations

import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

# Sibling-harness import, matching the idiom test_bp_1500g_2_i.py already
# uses for _bp1500g1_harness: this directory is NOT on sys.path at import
# time, so a bare import fails with ModuleNotFoundError without this.
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from _inf400c_harness import (  # noqa: E402
    copy_consumer_install as _consumer_install_copy,
    copy_consumer_install_with_fresh_sink as _consumer_install_copy_with_fresh_sink,
    deployed_root as _deployed_root,
)

# The module-level helpers and constants live in _inf_400c_4_i_support.py
# (file-size ratchet); the check interface they drive is documented above.
from _inf_400c_4_i_support import (  # noqa: E402
    _QUERY_TIMEOUT_SECONDS,
    _SURFACE_IDS,
    _assert_check_script_exists,
    _assert_revert_changed,
    _declared_sink,
    _deployed_harvester,
    _perform_described_append,
    _revert_to_literal_telemetry_path,
    _run_sink_parity_check,
    _surface_path,
)

# TQ-600a-9 COST CONTAINMENT lives in _inf400c_harness.py: ONE real build
# per process, handed to each test as a cheap content-identical COPY. Read
# that module's docstring for WHY copying is safe and which single deployed
# file is the exception.


# ---------------------------------------------------------------------------
# Test 1 -- deployed parity, all four surfaces
# ---------------------------------------------------------------------------


def test_all_four_deployed_emit_surfaces_resolve_to_the_declared_sink(tmp_path: Path) -> None:
    """AC INF-400c-4-i: a fresh, real build's four DEPLOYED emit surfaces all
    resolve to that same install's declared sink, and the check reports
    having inspected exactly four surfaces (never zero, silently agreeing).

    RED mode (A): fails at _assert_check_script_exists() -- the check does
    not exist yet.

    TQ-600a-9: reads a COPY of the one shared golden consumer-install
    build (see `_consumer_install_copy`'s own docstring) rather than
    spawning its own `build.py` run.
    """
    # covers: INF-400c-4-i
    # angle: deployed
    _assert_check_script_exists()

    target_dir = tmp_path / "project"
    _consumer_install_copy(target_dir)

    check_result = _run_sink_parity_check(target_dir)

    assert check_result.returncode == 0, (
        "Expected the sink-parity check to pass against a freshly deployed "
        f"install.\nstdout:\n{check_result.stdout}\nstderr:\n{check_result.stderr}"
    )
    assert "Inspected 4 surfaces" in check_result.stdout, (
        "Expected the check to report having inspected exactly four "
        "surfaces -- a check that silently found none must not be able to "
        f"report agreement.\nstdout:\n{check_result.stdout}"
    )
    for surface_id in _SURFACE_IDS:
        assert surface_id in check_result.stdout, (
            f"Expected surface id {surface_id!r} named in the inspected-"
            f"surfaces report.\nstdout:\n{check_result.stdout}"
        )


# ---------------------------------------------------------------------------
# Test 2 -- partial-repoint negative control, one surface at a time
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("surface_id", _SURFACE_IDS)
def test_one_unrepointed_surface_out_of_four_blocks_the_check(tmp_path: Path, surface_id: str) -> None:
    """AC INF-400c-4-i: reverting exactly ONE of the four deployed surfaces
    back to the literal telemetry-stream path must block the check and name
    that surface -- repeated for each of the four so none is left uncovered.

    RED mode (A): fails at _assert_check_script_exists() -- the check does
    not exist yet.

    TQ-600a-9: reads a COPY of the one shared golden consumer-install
    build (see `_consumer_install_copy`'s own docstring) rather than
    spawning its own `build.py` run -- one real build now serves this
    test's four parametrised instances AND the deployed-parity test above.
    """
    # covers: INF-400c-4-i
    # angle: failure
    _assert_check_script_exists()

    target_dir = tmp_path / "project"
    _consumer_install_copy(target_dir)

    surface_path = _surface_path(target_dir, surface_id)
    assert surface_path.is_file(), f"Expected a deployed surface at {surface_path}"
    original_text = surface_path.read_text(encoding="utf-8")
    reverted_text = _revert_to_literal_telemetry_path(original_text)
    _assert_revert_changed(original_text, reverted_text, surface_id)
    surface_path.write_text(reverted_text, encoding="utf-8")

    check_result = _run_sink_parity_check(target_dir)

    assert check_result.returncode != 0, (
        f"Expected the check to block once surface {surface_id!r} names the "
        "operational telemetry stream directly (a partial repoint splits "
        f"the corpus across two files).\nstdout:\n{check_result.stdout}\n"
        f"stderr:\n{check_result.stderr}"
    )
    combined = check_result.stdout + check_result.stderr
    assert surface_id in combined, (
        f"Expected the check to name the unrepointed surface ({surface_id!r}) "
        f"in its failure output.\nstdout:\n{check_result.stdout}\n"
        f"stderr:\n{check_result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 3 -- the seam: isolated working directory vs. project root
# ---------------------------------------------------------------------------


def test_a_surface_followed_from_an_isolated_working_directory_reaches_the_same_sink_as_from_the_project_root(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-i: performing the append a surface describes from an
    isolated working directory and from the project root must reach the
    SAME file, and the record written from the (now-removed) isolated
    directory must survive its removal.

    RED mode (B): fails on the real, resulting file-system state -- the
    surface's currently shipped literal destination
    (`debugging/logs/agent_telemetry.jsonl`) is CWD-relative, so following
    it literally from two different working directories produces two
    different files; the one written under the isolated directory is lost
    when that directory is removed. No check script is needed for this
    test to be meaningful.

    TQ-600a-9: reads a COPY of the one shared golden consumer-install
    build (see `_consumer_install_copy`'s own docstring). This test only
    checks that two cwd-relative resolutions of the SAME deployed tree
    agree with each other, never an absolute value specific to this
    particular target_dir, so a copy is indistinguishable from an
    independent build for what it proves. Named "project_seam" (not
    "project") so TQ-600a-9-i's write-group glob (`basetemp.rglob
    ("project")`, scoped to this file's test1 + test2's four variants)
    does not incidentally sweep this test's own copy in.
    """
    # covers: INF-400c-4-i
    # angle: seam
    target_dir = tmp_path / "project_seam"
    _consumer_install_copy(target_dir)

    isolated_dir = target_dir / "isolated_working_directory"
    isolated_dir.mkdir()

    # The four surfaces must state the resolution mechanism identically
    # (it_requirements), so any one of them is representative; signoff is
    # used here as it is the surface whose text this AC most directly edits.
    surface_text = _surface_path(target_dir, "signoff").read_text(encoding="utf-8")

    marker_from_isolated = f"seam-test-from-isolated-{uuid.uuid4().hex}"
    marker_from_root = f"seam-test-from-root-{uuid.uuid4().hex}"

    dest_from_isolated = _perform_described_append(
        surface_text, target_dir, isolated_dir, marker_from_isolated
    )
    dest_from_root = _perform_described_append(
        surface_text, target_dir, target_dir, marker_from_root
    )

    shutil.rmtree(isolated_dir)

    assert dest_from_isolated == dest_from_root, (
        "A surface followed from an isolated working directory "
        f"({isolated_dir}, now removed) resolved to a DIFFERENT destination "
        f"({dest_from_isolated}) than the SAME surface followed from the "
        f"project root ({dest_from_root}) -- the exact corpus split AC "
        "INF-400c-4-i exists to prevent. A surface that hands the agent a "
        "bare relative name passes every other test in this file and fails "
        "this one."
    )
    assert dest_from_root.exists(), f"Expected {dest_from_root} to exist."
    content = dest_from_root.read_text(encoding="utf-8")
    assert marker_from_isolated in content, (
        "Record emitted while standing in the isolated working directory "
        f"({isolated_dir}, now removed) is missing from the shared sink -- "
        "it was written to a directory-relative file that no longer exists."
    )
    assert marker_from_root in content, (
        "Record emitted from the project root is missing from the shared sink."
    )


# ---------------------------------------------------------------------------
# Test 4 -- two independent installs, no surface may carry its own path
# ---------------------------------------------------------------------------


def test_no_deployed_surface_carries_a_sink_path_of_its_own(tmp_path: Path) -> None:
    """AC INF-400c-4-i: the same package built into TWO temp projects at
    different absolute locations must have every surface reach ITS OWN
    project's declared sink, never the other project's, and never a shared
    hardcoded destination that happens to be correct for only one of them.

    RED mode (B): fails on the real, resulting file-system state -- every
    surface's currently shipped literal destination names the OPERATIONAL
    telemetry stream (`agent_telemetry.jsonl`), not the declared knowledge
    sink (`knowledge_emissions.jsonl`), in either project, independently of
    the CWD nuance test 3 exercises. No check script is needed for this
    test to be meaningful.

    TQ-600a-9: this is the ONE test in the file that genuinely needs
    target_dir-correct content (two installs' declared sinks must
    DIFFER), so a bare content copy of the golden tree is not enough on
    its own -- see `_consumer_install_copy_with_fresh_sink`'s own
    docstring for why re-deriving just the one location-dependent
    declaration file (rather than a second real `build.py` subprocess) is
    sufficient and does not weaken what this test proves.
    """
    # covers: INF-400c-4-i
    # angle: criterion
    project_a = tmp_path / "project_a"
    project_b = tmp_path / "project_b"
    _consumer_install_copy_with_fresh_sink(project_a)
    _consumer_install_copy_with_fresh_sink(project_b)

    declared_sink_a = Path(_declared_sink(project_a))
    declared_sink_b = Path(_declared_sink(project_b))
    assert declared_sink_a != declared_sink_b, (
        "Fixture assumption violated: two independent builds at different "
        "absolute locations declared the SAME sink -- adjust the fixture."
    )

    for surface_id in _SURFACE_IDS:
        text_a = _surface_path(project_a, surface_id).read_text(encoding="utf-8")
        text_b = _surface_path(project_b, surface_id).read_text(encoding="utf-8")

        marker_a = f"two-project-{surface_id}-a-{uuid.uuid4().hex}"
        marker_b = f"two-project-{surface_id}-b-{uuid.uuid4().hex}"

        dest_a = _perform_described_append(text_a, project_a, project_a, marker_a)
        dest_b = _perform_described_append(text_b, project_b, project_b, marker_b)

        assert dest_a == declared_sink_a, (
            f"Surface {surface_id!r} in project A resolved to {dest_a}, not "
            f"that project's own declared sink {declared_sink_a}. A "
            "destination written into a surface can only be correct in one "
            "of the two installs."
        )
        assert dest_b == declared_sink_b, (
            f"Surface {surface_id!r} in project B resolved to {dest_b}, not "
            f"that project's own declared sink {declared_sink_b}."
        )

        content_a = dest_a.read_text(encoding="utf-8") if dest_a.exists() else ""
        content_b = dest_b.read_text(encoding="utf-8") if dest_b.exists() else ""
        assert marker_a in content_a, f"Expected {marker_a!r} written into {dest_a}."
        assert marker_b in content_b, f"Expected {marker_b!r} written into {dest_b}."
        assert marker_a not in content_b, (
            f"Surface {surface_id!r}: project A's record leaked into "
            f"project B's file ({dest_b})."
        )
        assert marker_b not in content_a, (
            f"Surface {surface_id!r}: project B's record leaked into "
            f"project A's file ({dest_a})."
        )


# ---------------------------------------------------------------------------
# Test 5 -- the settlement scope note must not be read as an instruction
# ---------------------------------------------------------------------------


def test_the_settlement_scope_note_is_not_read_as_an_append_instruction(tmp_path: Path) -> None:
    """AC INF-400c-4-i: the signoff knowledge-capture section legitimately
    names the telemetry stream once more, in the paragraph recording what
    was settled -- the check must classify that paragraph as prose (and
    pass with it present) while still blocking on the actual append
    instruction being reverted.

    RED mode (A): fails at _assert_check_script_exists() -- the check does
    not exist yet.

    TQ-600a-9: reads a COPY of the one shared golden consumer-install
    build (see `_consumer_install_copy`'s own docstring). This test only
    compares a surface's resolution against ITS OWN tree's declaration, so
    a copy is indistinguishable from an independent build for what it
    proves. Named "project_settlement" (not "project") so TQ-600a-9-i's
    write-group glob (scoped to this file's test1 + test2's four variants)
    does not incidentally sweep this test's own copy in.
    """
    # covers: INF-400c-4-i
    # angle: criterion
    _assert_check_script_exists()

    target_dir = tmp_path / "project_settlement"
    _consumer_install_copy(target_dir)

    signoff_path = _surface_path(target_dir, "signoff")
    original_text = signoff_path.read_text(encoding="utf-8")

    # Baseline: the historical settlement paragraph is present, unmodified,
    # in the real deployed file -- the check must still be able to pass.
    baseline_result = _run_sink_parity_check(target_dir)
    assert baseline_result.returncode == 0, (
        "Expected the check to pass with the historical settlement "
        "paragraph present and unmodified -- it legitimately names the "
        "telemetry stream once, describing what was settled, and must not "
        "be mistaken for an append instruction.\n"
        f"stdout:\n{baseline_result.stdout}\nstderr:\n{baseline_result.stderr}"
    )

    # Now revert ONLY the actual append instruction (never the historical
    # paragraph) and confirm the check still blocks.
    reverted_text = _revert_to_literal_telemetry_path(original_text)
    _assert_revert_changed(original_text, reverted_text, "signoff")
    signoff_path.write_text(reverted_text, encoding="utf-8")

    blocked_result = _run_sink_parity_check(target_dir)
    assert blocked_result.returncode != 0, (
        "Expected the check to block once the actual append instruction "
        "(not the historical scope note) names the operational telemetry "
        f"stream directly.\nstdout:\n{blocked_result.stdout}\n"
        f"stderr:\n{blocked_result.stderr}"
    )
    assert "signoff" in (blocked_result.stdout + blocked_result.stderr), (
        "Expected the check to name the signoff surface as the one that "
        f"blocked it.\nstdout:\n{blocked_result.stdout}\n"
        f"stderr:\n{blocked_result.stderr}"
    )


# ---------------------------------------------------------------------------
# Test 6 -- an undeclared install must refuse, not fall back to CWD
# ---------------------------------------------------------------------------


def test_an_install_with_no_declaration_refuses_rather_than_resolving_against_the_current_directory(
    tmp_path: Path,
) -> None:
    """AC INF-400c-4-i: in an install that has no build-time sink
    declaration (e.g. built before this AC's build.py phase existed, or
    never rebuilt since), the resolution mechanism the four surfaces will
    depend on MUST refuse loudly rather than silently falling back to a
    plausible-looking, current-directory-derived absolute path. Verified
    from two different working directories, since a CWD fallback is
    specifically a "different answer depending on where the agent is
    standing" defect.

    RED mode (B): fails on the ALREADY-SHIPPED real behaviour of
    `harvest_learnings.py --print-sink` -- confirmed empirically before
    writing this test: with no config/knowledge_sink.json present it
    currently exits 0 and prints a CWD-relative fallback path (a DIFFERENT
    absolute-looking path from each of the two working directories used
    below). No check script is needed for this test to be meaningful --
    this pins a production behaviour change needed in harvest_learnings.py
    itself, independent of scripts/ci/check_sink_parity.py's existence.

    TQ-600a-9: reads a COPY of the one shared golden consumer-install
    build (see `_consumer_install_copy`'s own docstring). This test
    deletes the declaration file before exercising the refusal path, so
    whatever location that declaration originally named is irrelevant --
    a copy is indistinguishable from an independent build for what it
    proves. Named "project_undeclared" (not "project") so TQ-600a-9-i's
    write-group glob (scoped to this file's test1 + test2's four variants)
    does not incidentally sweep this test's own (sink-deleted) copy in.
    """
    # covers: INF-400c-4-i
    # angle: failure
    target_dir = tmp_path / "project_undeclared"
    _consumer_install_copy(target_dir)

    declaration_path = _deployed_root(target_dir) / "config" / "knowledge_sink.json"
    assert declaration_path.is_file(), (
        f"Fixture assumption violated: a fresh build must declare a sink at "
        f"{declaration_path}."
    )
    # Simulate an install that predates the build-time declaration (or has
    # not been rebuilt since #743): the declaration this AC's mechanism
    # depends on is simply absent.
    declaration_path.unlink()

    harvester = _deployed_harvester(target_dir)
    isolated_dir = tmp_path / "isolated_working_directory"
    isolated_dir.mkdir()

    result_from_root = subprocess.run(
        [sys.executable, str(harvester), "--print-sink"],
        capture_output=True,
        text=True,
        cwd=str(target_dir),
        timeout=_QUERY_TIMEOUT_SECONDS,
        check=False,
    )
    result_from_isolated = subprocess.run(
        [sys.executable, str(harvester), "--print-sink"],
        capture_output=True,
        text=True,
        cwd=str(isolated_dir),
        timeout=_QUERY_TIMEOUT_SECONDS,
        check=False,
    )

    assert result_from_root.returncode != 0, (
        "With no build-time sink declaration present, the resolution the "
        "four surfaces depend on must refuse rather than fall back to a "
        f"current-directory-derived path.\nstdout:\n{result_from_root.stdout}\n"
        f"stderr:\n{result_from_root.stderr}"
    )
    assert "declar" in (result_from_root.stdout + result_from_root.stderr).lower(), (
        "Expected the refusal to say the declaration is missing, rather "
        f"than silently printing a path.\nstdout:\n{result_from_root.stdout}\n"
        f"stderr:\n{result_from_root.stderr}"
    )
    assert str(target_dir) not in result_from_root.stdout, (
        "The refusal must not print a plausible-looking current-directory-"
        f"derived absolute path.\nstdout:\n{result_from_root.stdout}"
    )

    assert result_from_isolated.returncode != 0, (
        "Same refusal expected from a different working directory -- it "
        "must not silently succeed with yet another CWD-derived path.\n"
        f"stdout:\n{result_from_isolated.stdout}\n"
        f"stderr:\n{result_from_isolated.stderr}"
    )
    assert "declar" in (result_from_isolated.stdout + result_from_isolated.stderr).lower(), (
        "Expected the refusal (from the isolated working directory) to say "
        f"the declaration is missing.\nstdout:\n{result_from_isolated.stdout}\n"
        f"stderr:\n{result_from_isolated.stderr}"
    )
    assert str(isolated_dir) not in result_from_isolated.stdout, (
        "The refusal must not print a plausible-looking current-directory-"
        f"derived absolute path.\nstdout:\n{result_from_isolated.stdout}"
    )
