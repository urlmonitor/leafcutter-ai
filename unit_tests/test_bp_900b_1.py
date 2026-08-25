"""
MODULE: test_bp_900b_1
GOAL: RED test stubs for AC BP-900b-1 — a post-compile validation phase that
    scans the COMPILED ``agents/`` and ``skills/`` directories (the output of a
    real ``build.py --target-dir`` run) for script path references, returning
    ``set[tuple[str, str]]`` of ``(template_path, referenced_script_path)`` per
    the ticket's ``delivers_to`` contract.
TICKET: tickets/00_inbox/epics/EPIC-DeploymentCompleteness/05_TICKET-20260611-BP-900b-1.md
AC: BP-900b-1 (source_ac)

SOURCE-OF-TRUTH NOTE (Rule 1 classification: production_drift / genuine gap):
    ``build_referential_integrity.extract_script_path_refs()`` and its
    ``_with_sources`` variant already implement the SAME regex patterns this AC
    describes, but they are only ever invoked against ``templates_dir`` — the
    SOURCE template tree (``package_root / "templates"``) — by
    ``build._check_script_reference_guard()``, which runs BEFORE ``_run_phases``
    writes anything to the target directory. No production code path scans the
    COMPILED output (``<target>/.claude/agents/``, ``<target>/.claude/skills/``,
    or the ``.leafcutter`` mirror) AFTER compilation, which is the literal
    Gherkin: "Given build.py has compiled agent templates and skill files to the
    output directory, When the post-compile validation phase runs, Then it
    scans every .md file in the compiled agents/ and skills/ directories".

    A behavioral spot-check (test-writer, 2026-08-18) confirmed the extraction
    REGEX generalizes fine to a real compiled directory — calling the existing
    ``extract_script_path_refs()`` against a real ``<target>/.claude`` directory
    after a real ``build.py --target-dir`` run already recovers
    "scripts/ac_store/ac_prioritizer.py" and
    "scripts/ac_store/generate_ticket_from_ac.py" from real compiled agent
    templates (build-ac.md et al). The gap is a WIRING/CONTRACT gap, not a
    regex gap: there is no function that (a) targets the compiled output root
    specifically and (b) returns the ``set[tuple[str, str]]`` shape the
    ticket's ``delivers_to`` field specifies (paired with the referencing
    template path, not just a flat set of script paths as the existing
    ``extract_script_path_refs()`` returns).

    NOTE ON THE AC'S "goal_to_epic.py" EXAMPLE: the AC's illustrative minimum
    set includes "scripts/goal_to_epic.py", but the real compiled templates
    (e.g. build-ac.md) invoke it as
    "{{config.output_root}}/scripts/ac_store/goal_to_epic.py" — a different
    (already-deployable, per ``_get_source_deployable_scripts``) path. Per the
    AC's own "when those references exist in the compiled output" qualifier,
    this test accepts EITHER spelling for goal_to_epic.py rather than asserting
    a literal string that does not appear anywhere in the real compiled output
    today (Source-of-Truth Discipline Rule 5 — expand the test to match
    verified reality rather than hard-coding an AC illustration that may itself
    be stale).

CONTRACT (from ticket ``delivers_to``): a new function —
    ``extract_compiled_script_path_refs(compiled_root: Path) -> set[tuple[str, str]]``
    — added to ``scripts/build_referential_integrity.py`` (the file this AC's
    ``it_requirements.reference_file_path`` and ``doc_links`` name as the
    extension target). It must scan every ``.md`` file under
    ``compiled_root/agents/`` and ``compiled_root/skills/`` (recursive) and
    return the set of ``(relative_template_path, "scripts/<path>")`` tuples
    matching the three patterns already implemented for the pre-build scan:
    ``python3 scripts/<path>``, ``python scripts/<path>``,
    ``sys.path.insert(<N>, 'scripts/<path>')`` and the double-quoted variant.

    python-coder chooses the exact function name/location; this test pins the
    name above because it is the natural sibling of the two existing functions
    in the same module (``extract_script_path_refs`` /
    ``extract_script_path_refs_with_sources``). If python-coder implements the
    contract under a different name, update the import below to match — the
    BEHAVIORAL assertions (tuple shape, minimum-set membership on the REAL
    compiled tree) are the load-bearing part of this test, not the name.
"""
# @ac-tag: BP-900b-1

from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — make scripts/ importable regardless of working directory.
# ---------------------------------------------------------------------------
_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 — after sys.path setup
import build_referential_integrity as _bri  # noqa: E402 — after sys.path setup


def _write_md(directory: Path, name: str, body: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / name
    path.write_text(body, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Unit-level: the new function must exist and scan a synthetic compiled tree
# ---------------------------------------------------------------------------


def test_ac1_extract_compiled_script_path_refs_exists_and_scans_agents() -> None:
    """AC BP-900b-1: a compiled-output extractor must exist and find refs in agents/.

    RED at authoring time: ``extract_compiled_script_path_refs`` does not yet
    exist on ``build_referential_integrity`` — this raises AttributeError until
    python-coder implements it.
    """
    # covers: BP-900b-1
    extractor = getattr(_bri, "extract_compiled_script_path_refs", None)
    assert extractor is not None, (
        "build_referential_integrity.extract_compiled_script_path_refs does not "
        "exist. AC BP-900b-1 requires a post-compile validation function that "
        "scans the COMPILED agents/ and skills/ directories (not the source "
        "templates/ tree, which extract_script_path_refs() already covers) and "
        "returns set[tuple[str, str]] of (template_path, referenced_script_path)."
    )


def test_ac1_scans_compiled_agents_dir_for_python_invoke(tmp_path: Path) -> None:
    """The extractor must find a 'python3 scripts/<path>' reference under agents/."""
    # covers: BP-900b-1
    compiled_root = tmp_path / "compiled"
    agent_md = _write_md(
        compiled_root / "agents",
        "synthetic_agent.md",
        "python3 scripts/ac_store/ac_prioritizer.py --ac FOO-1\n",
    )

    result = _bri.extract_compiled_script_path_refs(compiled_root)

    expected_rel = agent_md.relative_to(compiled_root).as_posix()
    assert (expected_rel, "scripts/ac_store/ac_prioritizer.py") in result, (
        f"extract_compiled_script_path_refs({compiled_root}) did not return "
        f"({expected_rel!r}, 'scripts/ac_store/ac_prioritizer.py'). "
        f"Got: {sorted(result)!r}. The function must scan every .md file under "
        "compiled_root/agents/ (AC BP-900b-1)."
    )


def test_ac1_scans_compiled_skills_dir_for_python_invoke(tmp_path: Path) -> None:
    """The extractor must find a 'python scripts/<path>' reference under skills/."""
    # covers: BP-900b-1
    compiled_root = tmp_path / "compiled"
    skill_md = _write_md(
        compiled_root / "skills" / "some-skill",
        "SKILL.md",
        "python scripts/ac_store/generate_ticket_from_ac.py --ac FOO-2\n",
    )

    result = _bri.extract_compiled_script_path_refs(compiled_root)

    expected_rel = skill_md.relative_to(compiled_root).as_posix()
    assert (expected_rel, "scripts/ac_store/generate_ticket_from_ac.py") in result, (
        f"extract_compiled_script_path_refs({compiled_root}) did not return "
        f"({expected_rel!r}, 'scripts/ac_store/generate_ticket_from_ac.py'). "
        f"Got: {sorted(result)!r}. The function must scan every .md file under "
        "compiled_root/skills/ (recursively, including nested skill dirs) "
        "(AC BP-900b-1)."
    )


def test_ac1_handles_single_and_double_quoted_syspath_insert(tmp_path: Path) -> None:
    """Both sys.path.insert quote variants must be extracted from compiled output."""
    # covers: BP-900b-1
    compiled_root = tmp_path / "compiled"
    single_md = _write_md(
        compiled_root / "agents",
        "single_quote.md",
        "sys.path.insert(0, 'scripts/ac_store')\n"
        "python3 scripts/ac_store/ac_prioritizer.py\n",
    )
    double_md = _write_md(
        compiled_root / "agents",
        "double_quote.md",
        'sys.path.insert(0, "scripts/commit_guardian")\n',
    )

    result = _bri.extract_compiled_script_path_refs(compiled_root)
    script_paths = {script for _template, script in result}

    assert "scripts/ac_store/ac_prioritizer.py" in script_paths, (
        f"Expected 'scripts/ac_store/ac_prioritizer.py' among extracted script "
        f"paths from {single_md.name}. Got: {sorted(script_paths)!r} "
        "(AC BP-900b-1)."
    )
    assert "scripts/commit_guardian" in script_paths, (
        f"Expected 'scripts/commit_guardian' (double-quoted sys.path.insert) "
        f"among extracted script paths from {double_md.name}. Got: "
        f"{sorted(script_paths)!r}. AC BP-900b-1 requires BOTH single- and "
        "double-quoted sys.path.insert() variants to be extracted."
    )


def test_ac1_returns_tuple_of_two_strings(tmp_path: Path) -> None:
    """The contract requires set[tuple[str, str]] — (template_path, script_path)."""
    # covers: BP-900b-1
    compiled_root = tmp_path / "compiled"
    agent_md = _write_md(
        compiled_root / "agents",
        "shape_check.md",
        "python3 scripts/ac_store/ac_prioritizer.py --ac FOO-3\n",
    )

    result = _bri.extract_compiled_script_path_refs(compiled_root)

    assert isinstance(result, set), (
        f"extract_compiled_script_path_refs({compiled_root}) must return a "
        f"set, got {type(result)!r} (AC BP-900b-1)."
    )
    assert result, (
        f"extract_compiled_script_path_refs({compiled_root}) returned an "
        "empty set against a fixture containing a real python3 invocation "
        "(AC BP-900b-1)."
    )
    for item in result:
        assert isinstance(item, tuple) and len(item) == 2, (
            f"Expected every element to be a 2-tuple, got {item!r} from "
            f"result {sorted(result)!r} (AC BP-900b-1)."
        )
        template_path, script_path = item
        assert isinstance(template_path, str) and isinstance(script_path, str), (
            f"Expected (str, str) tuple, got ({type(template_path)!r}, "
            f"{type(script_path)!r}) for {item!r} (AC BP-900b-1)."
        )

    expected_rel = agent_md.relative_to(compiled_root).as_posix()
    assert (expected_rel, "scripts/ac_store/ac_prioritizer.py") in result, (
        f"Expected the first element of the tuple to resolve to the "
        f"referencing template path ({expected_rel!r}) and the second to the "
        f"script path ('scripts/ac_store/ac_prioritizer.py'). Got: "
        f"{sorted(result)!r} (AC BP-900b-1)."
    )


# ---------------------------------------------------------------------------
# Real-artifact behavioral test: run the REAL build.py, scan the REAL
# compiled output, assert the minimum-set membership the AC names.
# ---------------------------------------------------------------------------


def _find_compiled_root(target_dir: Path) -> Path:
    """Return the compiled directory holding real agents/ and skills/ subdirs.

    Keyed on ``.claude`` because that is the Claude-Code-native compiled
    output; the ``.leafcutter`` mirror carries the same content.
    """
    candidate = target_dir / ".claude"
    assert candidate.is_dir(), (
        f"Expected a compiled '.claude' directory under {target_dir} after a "
        "real build.py run."
    )
    return candidate


def test_ac1_real_compiled_output_includes_minimum_set(tmp_path: Path) -> None:
    """AC BP-900b-1: scanning the REAL compiled output finds the named minimum set.

    Real-artifact behavioral test (no mocking of the build or the extractor):
    runs the actual ``build.py --target-dir`` into a fresh temp directory, then
    calls the new extractor against the REAL compiled ``.claude`` tree it wrote
    to disk. Confirms at least two of the AC's three named scripts —
    ``ac_prioritizer.py`` and ``generate_ticket_from_ac.py`` — are present in
    the extracted set (verified present in the real compiled output by a
    test-writer spot-check on 2026-08-18). goal_to_epic.py is checked
    leniently (either the AC's literal spelling or the real
    'scripts/ac_store/goal_to_epic.py' spelling that build-ac.md actually
    uses) since the AC's own wording only requires it "when that reference
    exists" in the compiled output.
    """
    # covers: BP-900b-1
    target_dir = tmp_path / "consumer"
    target_dir.mkdir()
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. The "
        "compiled-output scan below cannot run against a failed build."
    )

    compiled_root = _find_compiled_root(target_dir)
    result = _bri.extract_compiled_script_path_refs(compiled_root)
    script_paths = {script for _template, script in result}

    assert script_paths, (
        f"extract_compiled_script_path_refs({compiled_root}) returned an empty "
        "set against a real compiled output tree. The real build deploys agent "
        "templates (e.g. build-ac.md) with multiple script invocations — an "
        "empty result means the scan is not reaching the compiled .md files "
        "(AC BP-900b-1)."
    )

    required = {
        "scripts/ac_store/ac_prioritizer.py",
        "scripts/ac_store/generate_ticket_from_ac.py",
    }
    missing_required = required - script_paths
    assert not missing_required, (
        f"extract_compiled_script_path_refs({compiled_root}) is missing "
        f"{sorted(missing_required)!r} from the real compiled output. AC "
        "BP-900b-1 requires the extracted set to include at minimum "
        "'scripts/ac_store/ac_prioritizer.py', "
        "'scripts/ac_store/generate_ticket_from_ac.py', and 'scripts/goal_to_epic.py' "
        f"when those references exist in the compiled output. Found: "
        f"{sorted(script_paths)!r}."
    )

    goal_to_epic_variants = {
        "scripts/goal_to_epic.py",
        "scripts/ac_store/goal_to_epic.py",
    }
    assert script_paths & goal_to_epic_variants, (
        f"Neither 'scripts/goal_to_epic.py' nor 'scripts/ac_store/goal_to_epic.py' "
        f"was found in the real compiled output ({sorted(script_paths)!r}). The "
        "AC names goal_to_epic.py as part of the minimum set 'when that reference "
        "exists in the compiled output' — build-ac.md is known to reference it "
        "(AC BP-900b-1)."
    )

    # Non-vacuity: at least one tuple must actually name a real referencing
    # template (not just an empty template_path), so this test cannot pass on
    # a stub that returns (script_path, script_path) or similar degenerate shape.
    templates_naming_ac_prioritizer = {
        template
        for template, script in result
        if script == "scripts/ac_store/ac_prioritizer.py"
    }
    assert templates_naming_ac_prioritizer, (
        "No (template_path, script_path) tuple named a referencing template "
        "for 'scripts/ac_store/ac_prioritizer.py'. The contract requires "
        "set[tuple[str, str]] of (template_path, referenced_script_path) — a "
        "flat set of script paths only (matching the shape of the existing "
        "extract_script_path_refs(), not this ticket's extended contract) "
        "would fail this assertion."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 [test-writer/EPIC-DeploymentCompleteness/05_BP-900b-1]: Initial
#   failing test stubs. AC store shows BP-900b-1 work_status: done and the
#   sibling AC BP-900b-1-1 (allowlist) already has extensive coverage, but a
#   direct behavioral spot-check (real build.py run + calling the existing
#   extract_script_path_refs() against the real compiled .claude directory)
#   confirmed no production function targets the COMPILED output with the
#   ticket's delivers_to contract (set[tuple[str, str]] of
#   (template_path, referenced_script_path)) — only the pre-build source-tree
#   scan (extract_script_path_refs against templates/) is wired into build.py
#   today. This is therefore a genuine wiring/contract gap, not a duplicate of
#   already-passing coverage. Expected red state: AttributeError on
#   build_referential_integrity.extract_compiled_script_path_refs (function
#   does not exist yet).
# ====================================================================
