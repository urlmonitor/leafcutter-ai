"""
MODULE: test_bp_900g_6
GOAL: Regression guard for the workflow-source blind spot in
    ``extract_script_path_refs`` / ``extract_script_path_refs_with_sources`` —
    before this fix, only ``templates/agents/`` and ``templates/skills/`` (``.md``)
    were scanned, so a workflow that shells out to a script the build never
    deploys (``templates/workflows-js/*.js``, ``templates/workflows/*.md``) was
    completely invisible to ``_check_script_reference_guard`` in ``build.py``.
BUSINESS CONTEXT: This is the same defect class BP-900g-4 and BP-900g-5 closed
    for agent and skill templates, extended to the workflow-orchestration layer.
    AC BP-900g-6.
ARCHITECTURE: Synthetic-fixture unit tests built under ``tmp_path``, following
    the style of ``test_bp_900g_4.py``. Each test writes a minimal template tree
    and asserts on the return value of ``extract_script_path_refs`` (or the
    ``_with_sources`` variant where provenance matters), never on the real
    package templates — the real-package behavioral check lives in
    ``test_build_guard_real_package.py`` and is exercised separately.
"""

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

import build_referential_integrity as _bri  # noqa: E402 — after sys.path setup


def _write(templates_dir: Path, rel_path: str, body: str) -> None:
    """Create ``templates_dir/<rel_path>`` (creating parent dirs) containing ``body``."""
    target = templates_dir / rel_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")


# ---------------------------------------------------------------------------
# workflows-js/*.js scanning
# ---------------------------------------------------------------------------


def test_extractor_scans_workflows_js_output_root_form(tmp_path: Path) -> None:
    """A ``{{config.output_root}}/scripts/...`` reference inside a .js workflow

    must be extracted. Before BP-900g-6, ``templates/workflows-js/`` was not in
    the scanned directory list at all, so this reference — regardless of which
    prefix form it used — produced zero matches.
    """
    # covers: BP-900g-6
    templates = tmp_path / "templates"
    _write(
        templates,
        "workflows-js/x.js",
        "const gateScript =\n"
        '  `python3 {{config.output_root}}/scripts/build_orchestration/fast_lane.py ` +\n'
        '  `select_batch --ac-root <root>`;\n',
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/build_orchestration/fast_lane.py" in refs, (
        "extract_script_path_refs() did not extract "
        "'scripts/build_orchestration/fast_lane.py' from a "
        "{{config.output_root}}/-prefixed reference inside templates/workflows-js/x.js. "
        f"Extracted: {sorted(refs)!r}. templates/workflows-js/ must be scanned "
        "(AC BP-900g-6)."
    )


def test_extractor_scans_workflows_js_bare_form(tmp_path: Path) -> None:
    """A bare ``scripts/foo.py`` reference inside a .js workflow must be extracted.

    This is the literal pattern that already existed in the real
    ``templates/workflows-js/finalize-feature.js`` and ``plan-feature.js``
    (``python scripts/pause_store.py ...``) and was silently unscanned.
    """
    # covers: BP-900g-6
    templates = tmp_path / "templates"
    _write(
        templates,
        "workflows-js/y.js",
        'const helpText =\n  "  python scripts/foo.py --run-id " + runId + "\\n";\n',
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/foo.py" in refs, (
        "extract_script_path_refs() did not extract 'scripts/foo.py' from a bare "
        "'python scripts/foo.py' reference inside templates/workflows-js/y.js. "
        f"Extracted: {sorted(refs)!r} (AC BP-900g-6)."
    )


def test_extractor_scans_workflows_md_dot_prefixed_form(tmp_path: Path) -> None:
    """A rendered-output-root reference inside a ``templates/workflows/*.md`` file

    must be extracted. ``templates/workflows/`` holds slash-command bodies and
    was, like ``workflows-js/``, absent from the pre-fix scan list.
    """
    # covers: BP-900g-6
    templates = tmp_path / "templates"
    _write(
        templates,
        "workflows/do-thing.md",
        "Run:\n\npython3 .leafcutter/scripts/thing/do_thing.py --flag\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/thing/do_thing.py" in refs, (
        "extract_script_path_refs() did not extract 'scripts/thing/do_thing.py' from "
        "a '.leafcutter/'-prefixed reference inside templates/workflows/do-thing.md. "
        f"Extracted: {sorted(refs)!r} (AC BP-900g-6)."
    )


# ---------------------------------------------------------------------------
# Backward compatibility — agents/ and skills/ .md scanning must be unaffected
# ---------------------------------------------------------------------------


def test_extractor_still_scans_agents_and_skills(tmp_path: Path) -> None:
    """Pre-existing agents/ and skills/ .md scanning must keep working unchanged.

    Widening the scan target list to include workflows/workflows-js must not
    drop or alter matching for the two directories the guard already relied on.
    """
    # covers: BP-900g-6
    # covers: BP-900b-1
    # BP-900b-1 requires the guard to extract script path references from every
    # compiled agent template and skill file. The two assertions below are what
    # hold that behaviour in place: remove the agents/ or skills/ scan target
    # from _SCAN_TARGETS and this test goes red.
    templates = tmp_path / "templates"
    _write(
        templates,
        "agents/some-agent.md",
        "python3 scripts/agent_thing.py --flag\n",
    )
    _write(
        templates,
        "skills/some-skill/SKILL.md",
        "python scripts/skill_thing.py --flag\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/agent_thing.py" in refs, (
        "extract_script_path_refs() stopped extracting references from "
        f"templates/agents/. Extracted: {sorted(refs)!r} (AC BP-900g-6)."
    )
    assert "scripts/skill_thing.py" in refs, (
        "extract_script_path_refs() stopped extracting references from "
        f"templates/skills/. Extracted: {sorted(refs)!r} (AC BP-900g-6)."
    )


def test_with_sources_reports_workflow_provenance(tmp_path: Path) -> None:
    """``extract_script_path_refs_with_sources`` must name the workflow source file.

    The broken-reference JSONL report (AC BP-900c-2) names the referencing
    template so a human can go fix it; a workflow-sourced reference must
    resolve to a ``workflows-js/...`` or ``workflows/...`` relative path, not
    be silently dropped or misattributed.
    """
    # covers: BP-900g-6
    templates = tmp_path / "templates"
    _write(
        templates,
        "workflows-js/finalize-thing.js",
        'const cmd = "python scripts/pause_store.py read --run-id " + runId;\n',
    )

    refs_to_sources = _bri.extract_script_path_refs_with_sources(templates)

    assert "scripts/pause_store.py" in refs_to_sources, (
        "extract_script_path_refs_with_sources() did not extract "
        f"'scripts/pause_store.py'. Extracted keys: {sorted(refs_to_sources)!r} "
        "(AC BP-900g-6)."
    )
    assert refs_to_sources["scripts/pause_store.py"] == {
        "workflows-js/finalize-thing.js"
    }, (
        "extract_script_path_refs_with_sources() did not attribute "
        "'scripts/pause_store.py' to 'workflows-js/finalize-thing.js'. Got: "
        f"{refs_to_sources['scripts/pause_store.py']!r} (AC BP-900g-6)."
    )


# ---------------------------------------------------------------------------
# Negative control — host-project paths must still not be captured
# ---------------------------------------------------------------------------


def test_extractor_does_not_capture_host_project_path_in_workflow(tmp_path: Path) -> None:
    """A host-project path referenced from a workflow file must NOT be captured.

    Mirrors the existing agents/skills negative control in test_bp_900g_4.py:
    ``debugging/scripts/check/x.py`` belongs to the consumer's own project, not
    to leafcutter, and must not be normalised into a ``scripts/...`` deploy key
    merely because it is now reachable via the widened workflow scan.
    """
    # covers: BP-900g-6
    templates = tmp_path / "templates"
    _write(
        templates,
        "workflows-js/z.js",
        'const cmd = "python debugging/scripts/check/x.py --action all";\n',
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/check/x.py" not in refs, (
        "extract_script_path_refs() captured 'scripts/check/x.py' from the "
        "host-project path 'debugging/scripts/check/x.py' inside a workflow .js "
        f"file. Extracted: {sorted(refs)!r}. Only an output root (the "
        "'{{config.output_root}}/' token or a dot-prefixed root like '.leafcutter/') "
        "may precede 'scripts/', regardless of which directory is scanned "
        "(AC BP-900g-6)."
    )


def test_extractor_does_not_capture_js_template_literal_prefix(tmp_path: Path) -> None:
    """A JS ``${variable}/scripts/...`` interpolation must NOT be captured.

    Documented design decision (see DECISION HISTORY in
    build_referential_integrity.py): a ``${...}`` prefix is a JS variable
    holding an arbitrary runtime path (e.g. a worktree checkout or a temp
    baseline clone), not an output-root token, so treating it as one would
    reopen the over-wide-prefix false-positive failure mode
    (EPIC-BuildGuardFalsePositive) in a new shape.
    """
    # covers: BP-900g-6
    templates = tmp_path / "templates"
    _write(
        templates,
        "workflows-js/w.js",
        "const gateScript =\n"
        "  `python3 ${worktreePath}/scripts/injection_builders.py assemble`;\n",
    )

    refs = _bri.extract_script_path_refs(templates)

    assert "scripts/injection_builders.py" not in refs, (
        "extract_script_path_refs() captured 'scripts/injection_builders.py' from "
        "a JS template-literal-interpolated prefix ('${worktreePath}/'). This "
        "prefix is deliberately excluded — see the DECISION HISTORY in "
        f"build_referential_integrity.py. Extracted: {sorted(refs)!r} "
        "(AC BP-900g-6)."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-14 [BrainCandy/BP-900g-6]: Initial implementation. Pins the
#   extension of extract_script_path_refs()/extract_script_path_refs_with_sources()
#   to templates/workflows-js/*.js and templates/workflows/*.md, the
#   backward-compatibility invariant for agents/skills scanning, and the
#   negative controls for host-project paths and JS template-literal
#   interpolation prefixes (the latter is a deliberately-excluded form, not a
#   bug — see build_referential_integrity.py's DECISION HISTORY for the
#   reasoning). (#BP-900g-6)
# ====================================================================
