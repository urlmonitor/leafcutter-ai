"""
MODULE: test_bp_900b_2
GOAL: RED test stubs for AC BP-900b-2 — a guard that cross-checks extracted
    script-path references (BP-900b-1's contract) against the deployable
    script manifest derived from build_phases.py, producing a list of broken
    references.
TICKET: tickets/00_inbox/epics/EPIC-DeploymentCompleteness/07_TICKET-20260611-BP-900b-2.md
AC: BP-900b-2 (source_ac)

SOURCE-OF-TRUTH NOTE (Rule 1 classification: production_drift / genuine gap):
    ``build._get_source_deployable_scripts()`` (in ``scripts/build.py``) already
    derives a deployable-script manifest, but it (a) lives in ``build.py``, not
    ``scripts/build_phases.py`` — the file this AC's ``it_requirements`` names
    as ``reference_file_path`` with ``n_location_rule: "1 — the manifest
    derivation..."`` — and (b) is source-tree-only (never reads a built target
    directory), whereas this AC's Gherkin frames the manifest explicitly in
    terms of ``{target}/.leafcutter/scripts/`` and the ``{target}/scripts/``
    shim. No production function in ``build_phases.py`` currently derives this
    manifest, and no function anywhere implements the per-reference-tuple
    cross-check contract this AC's ``delivers_to`` specifies (``list[dict]``,
    one entry per broken *reference*, not one entry per broken *script* the
    way ``build_propagation_audit.build_broken_ref_report`` groups
    ``referencing_templates`` (plural) per missing script). This is therefore
    a genuine implementation gap, not a duplicate of already-green coverage.

    Also relevant: ``build_ac_store()``'s ``deploy_map`` in ``build_phases.py``
    is a hand-maintained Python literal list — precisely the drift-prone shape
    the AC's ``it_requirements.notes`` warns against (the BP-900g-4/-5/-6
    hotfixes were all cases where such a literal list silently drifted from
    what the build actually deploys). The manifest derivation this AC requires
    must NOT be a second hardcoded list mirroring the first; it must observe
    what the build phase functions actually write.

CONTRACT (from ticket ``delivers_to`` / ``expects_from`` / Gherkin):
    Two new functions, pinned to ``scripts/build_phases.py`` per this AC's
    ``it_requirements.reference_file_path`` and ``n_location_rule``:

    1. ``get_deployable_script_manifest(target_root: Path) -> set[str]``
       Given a project root that has already been built (a real
       ``build.py --target-dir <target_root>`` run has completed), returns the
       set of ``"scripts/<relpath>"`` strings for every script that is
       deployed either under ``<target_root>/.leafcutter/scripts/`` or shimmed
       at ``<target_root>/scripts/`` — i.e. every path a compiled-template
       reference of the form ``scripts/<relpath>`` could legitimately resolve
       against. This is the manifest the Gherkin's "When" clause names.

    2. ``cross_check_refs_against_manifest(refs, manifest) -> list[dict]``
       Consumes BP-900b-1's ``expects_from`` contract directly:
       ``refs: set[tuple[str, str]]`` of ``(referencing_template, "scripts/<path>")``
       tuples (the same shape ``extract_compiled_script_path_refs`` returns),
       and ``manifest: set[str]`` (the return of function 1, or any
       equivalent set of ``"scripts/<path>"`` strings). Returns this AC's
       ``delivers_to`` contract exactly: ``list[dict]``, one dict per
       reference tuple whose script path is NOT in ``manifest``, each shaped
       ``{"missing_path": str, "referencing_template": str}``. A reference
       whose script path IS in ``manifest`` is marked resolved simply by its
       ABSENCE from the returned list (Gherkin: "every reference that matches
       a deployed script path is marked as resolved"). Zero broken references
       returns ``[]`` (Gherkin: "zero or more broken references").

    python-coder chooses the exact function names/locations; this test pins
    the names above because they are the natural, literal reading of the
    ticket title ("Guard cross-checks extracted references against the
    deployable script manifest") and the two nouns in that title map cleanly
    onto one function per noun. If python-coder implements the contract under
    different names, update the imports below to match — the BEHAVIORAL
    assertions (per-reference [not per-script] list shape, exact dict keys,
    resolved-by-absence semantics, real-build integration) are the
    load-bearing part of this test, not the names.
"""
# @ac-tag: BP-900b-2

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
import build_phases as _bp  # noqa: E402 — after sys.path setup
import build_referential_integrity as _bri  # noqa: E402 — after sys.path setup


# ---------------------------------------------------------------------------
# Existence checks — both new functions must exist on build_phases.
# ---------------------------------------------------------------------------


def test_ac1_get_deployable_script_manifest_exists() -> None:
    """AC BP-900b-2: a manifest-derivation function must exist on build_phases.

    RED at authoring time: ``get_deployable_script_manifest`` does not yet
    exist — this raises AttributeError until python-coder implements it.
    """
    # covers: BP-900b-2
    fn = getattr(_bp, "get_deployable_script_manifest", None)
    assert fn is not None, (
        "build_phases.get_deployable_script_manifest does not exist. AC "
        "BP-900b-2 requires a function that derives the set of scripts build "
        "phases deploy to {target}/.leafcutter/scripts/ and shim to "
        "{target}/scripts/ — derived from the actual build phase functions, "
        "not a hardcoded list (see it_requirements.notes re: BP-900g-4/-5/-6)."
    )


def test_ac1_cross_check_refs_against_manifest_exists() -> None:
    """AC BP-900b-2: a per-reference cross-check guard function must exist.

    RED at authoring time: ``cross_check_refs_against_manifest`` does not yet
    exist — this raises AttributeError until python-coder implements it.
    """
    # covers: BP-900b-2
    fn = getattr(_bp, "cross_check_refs_against_manifest", None)
    assert fn is not None, (
        "build_phases.cross_check_refs_against_manifest does not exist. AC "
        "BP-900b-2 requires a function that consumes BP-900b-1's "
        "set[tuple[str, str]] extraction contract and a deployable-script "
        "manifest, returning list[dict] of broken references "
        "({'missing_path': str, 'referencing_template': str})."
    )


# ---------------------------------------------------------------------------
# Synthetic unit-level: cross_check_refs_against_manifest's own logic.
# ---------------------------------------------------------------------------


def _cross_check(refs, manifest):
    fn = getattr(_bp, "cross_check_refs_against_manifest", None)
    assert fn is not None, (
        "cross_check_refs_against_manifest must exist before its behavior "
        "can be checked."
    )
    return fn(refs, manifest)


def test_ac1_resolved_reference_not_marked_broken() -> None:
    """A reference whose script path IS in the manifest produces zero broken entries."""
    # covers: BP-900b-2
    refs = {("agents/foo.md", "scripts/ac_store/ac_prioritizer.py")}
    manifest = {"scripts/ac_store/ac_prioritizer.py"}

    result = _cross_check(refs, manifest)

    assert result == [], (
        f"Expected an empty broken-reference list when the referenced script "
        f"is present in the manifest (Gherkin: 'every reference that matches "
        f"a deployed script path is marked as resolved'). Got: {result!r}."
    )


def test_ac1_broken_reference_included_with_correct_keys() -> None:
    """A reference whose script path is NOT in the manifest is reported with exact keys."""
    # covers: BP-900b-2
    refs = {("agents/foo.md", "scripts/does_not_exist.py")}
    manifest = {"scripts/ac_store/ac_prioritizer.py"}

    result = _cross_check(refs, manifest)

    assert len(result) == 1, (
        f"Expected exactly one broken-reference entry for one unresolved "
        f"reference. Got {len(result)}: {result!r}."
    )
    entry = result[0]
    assert isinstance(entry, dict), f"Expected a dict entry, got {type(entry)!r}."
    assert set(entry.keys()) == {"missing_path", "referencing_template"}, (
        f"AC BP-900b-2's delivers_to contract requires each broken-reference "
        f"dict to have exactly the keys 'missing_path' and "
        f"'referencing_template'. Got keys: {sorted(entry.keys())!r}."
    )
    assert entry["missing_path"] == "scripts/does_not_exist.py", (
        f"Expected missing_path == 'scripts/does_not_exist.py'. Got: "
        f"{entry['missing_path']!r}."
    )
    assert entry["referencing_template"] == "agents/foo.md", (
        f"Expected referencing_template == 'agents/foo.md'. Got: "
        f"{entry['referencing_template']!r}."
    )


def test_ac1_mixed_resolved_and_broken_refs() -> None:
    """Only the unresolved reference appears; the resolved one is silently dropped."""
    # covers: BP-900b-2
    refs = {
        ("agents/foo.md", "scripts/ac_store/ac_prioritizer.py"),  # resolved
        ("agents/bar.md", "scripts/does_not_exist.py"),  # broken
    }
    manifest = {"scripts/ac_store/ac_prioritizer.py"}

    result = _cross_check(refs, manifest)

    assert len(result) == 1, (
        f"Expected exactly one broken entry out of two references (one "
        f"resolved, one broken). Got {len(result)}: {result!r}."
    )
    assert result[0]["missing_path"] == "scripts/does_not_exist.py", (
        f"The resolved reference must not appear in the broken list. Got: "
        f"{result!r}."
    )


def test_ac1_multiple_templates_referencing_same_missing_script_each_reported() -> None:
    """Each broken (template, script) TUPLE is reported — the guard does not group by script.

    This pins the AC's Gherkin/delivers_to shape (list[dict] per *reference*)
    against the different, ALREADY-EXISTING grouped shape produced by
    ``build_propagation_audit.build_broken_ref_report`` (one entry per missing
    *script*, with a tuple of ``referencing_templates`` (plural)). A guard
    that reused that grouped shape unmodified would fail this assertion.
    """
    # covers: BP-900b-2
    refs = {
        ("agents/foo.md", "scripts/does_not_exist.py"),
        ("agents/bar.md", "scripts/does_not_exist.py"),
    }
    manifest: set[str] = set()

    result = _cross_check(refs, manifest)

    assert len(result) == 2, (
        f"Expected two broken-reference entries (one per referencing "
        f"template), not one grouped entry. Got {len(result)}: {result!r}."
    )
    referencing_templates = {entry["referencing_template"] for entry in result}
    assert referencing_templates == {"agents/foo.md", "agents/bar.md"}, (
        f"Expected both referencing templates to be individually represented. "
        f"Got: {sorted(referencing_templates)!r}."
    )


def test_ac1_empty_refs_returns_empty_list() -> None:
    """An empty reference set produces an empty broken list (Gherkin: 'zero or more')."""
    # covers: BP-900b-2
    result = _cross_check(set(), {"scripts/ac_store/ac_prioritizer.py"})
    assert result == [], f"Expected [] for an empty refs input. Got: {result!r}."


def test_ac1_return_type_is_list_not_set_or_dict() -> None:
    """The delivers_to contract requires list[dict], not a set or dict keyed by path."""
    # covers: BP-900b-2
    refs = {("agents/foo.md", "scripts/does_not_exist.py")}
    result = _cross_check(refs, set())
    assert isinstance(result, list), (
        f"AC BP-900b-2's delivers_to contract is 'list[dict]'. Got type "
        f"{type(result)!r}: {result!r}."
    )


# ---------------------------------------------------------------------------
# Real-artifact behavioral test: run the REAL build.py, derive the REAL
# manifest, extract REAL compiled references, and cross-check end-to-end.
# ---------------------------------------------------------------------------


def _find_compiled_root(target_dir: Path) -> Path:
    candidate = target_dir / ".claude"
    assert candidate.is_dir(), (
        f"Expected a compiled '.claude' directory under {target_dir} after a "
        "real build.py run."
    )
    return candidate


def test_ac1_real_build_manifest_resolves_real_deployed_references() -> None:
    """AC BP-900b-2: end-to-end against a REAL build — no mocking of build.py,
    the manifest derivation, the compiled-output extractor, or the cross-check.

    Runs a real ``build.py --target-dir`` into a fresh temp directory (a real,
    durable, on-disk artifact), extracts real compiled-template references via
    BP-900b-1's ``extract_compiled_script_path_refs``, derives the real
    deployable-script manifest via ``get_deployable_script_manifest``, and
    cross-checks them. A known-real, always-deployed script
    ('scripts/ac_store/ac_prioritizer.py') must NOT be reported broken, and a
    deliberately injected bogus reference (never deployed by any build phase)
    MUST be reported broken — proving the guard actually discriminates rather
    than marking everything resolved or everything broken.
    """
    # covers: BP-900b-2
    import shutil
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        target_dir = Path(tmp) / "consumer"
        target_dir.mkdir()

        exit_code = _build.main(["--target-dir", str(target_dir)])
        assert exit_code == 0, (
            f"build.py --target-dir exited {exit_code!r}; expected 0. The "
            "manifest/cross-check below cannot run against a failed build."
        )

        manifest_fn = getattr(_bp, "get_deployable_script_manifest", None)
        assert manifest_fn is not None, (
            "get_deployable_script_manifest must exist before the real-build "
            "integration can run."
        )
        manifest = manifest_fn(target_dir)
        assert isinstance(manifest, set) and manifest, (
            f"get_deployable_script_manifest({target_dir}) returned "
            f"{manifest!r} — expected a non-empty set[str] of "
            "'scripts/<path>' entries derived from the real build output."
        )

        compiled_root = _find_compiled_root(target_dir)
        compiled_refs = _bri.extract_compiled_script_path_refs(compiled_root)

        # Inject one deliberately-bogus reference so the test does not rely on
        # every real template happening to contain a currently-broken
        # reference (there should be none in a healthy build) to exercise the
        # broken-detection path.
        refs = set(compiled_refs) | {
            ("agents/synthetic-nonexistent.md", "scripts/does_not_exist_anywhere.py"),
        }

        result = _cross_check_pipeline(refs, manifest)

        missing_paths = {entry["missing_path"] for entry in result}
        assert "scripts/does_not_exist_anywhere.py" in missing_paths, (
            f"The deliberately-injected bogus reference was not reported as "
            f"broken. Broken entries: {result!r}. Manifest size: "
            f"{len(manifest)}."
        )

        # A known-real, always-deployed script must resolve (not appear broken)
        # against the manifest derived from this same real build.
        known_deployed_refs = {
            script for _tmpl, script in compiled_refs
            if script == "scripts/ac_store/ac_prioritizer.py"
        }
        if known_deployed_refs:
            assert "scripts/ac_store/ac_prioritizer.py" not in missing_paths, (
                f"'scripts/ac_store/ac_prioritizer.py' is referenced by a real "
                f"compiled template and IS deployed by build_ac_store, but was "
                f"reported broken. Manifest: {sorted(manifest)[:20]!r}... "
                f"Broken entries: {result!r}."
            )

        shutil.rmtree(target_dir, ignore_errors=True)


def _cross_check_pipeline(refs, manifest):
    fn = getattr(_bp, "cross_check_refs_against_manifest", None)
    assert fn is not None, (
        "cross_check_refs_against_manifest must exist before the real-build "
        "integration test can run."
    )
    return fn(refs, manifest)


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 [test-writer/EPIC-DeploymentCompleteness/07_BP-900b-2]: Initial
#   failing test stubs. No production function in build_phases.py currently
#   derives a deployable-script manifest from build.py's target output, nor
#   does any function implement the per-reference-tuple cross-check the
#   ticket's delivers_to contract specifies (list[dict], one entry per broken
#   reference — distinct from build_propagation_audit.build_broken_ref_report's
#   already-existing per-SCRIPT grouped shape). Confirmed via research read of
#   scripts/build_phases.py, scripts/build.py, and scripts/build_propagation_audit.py:
#   no matching function name exists anywhere in the package. Expected red
#   state: AttributeError on build_phases.get_deployable_script_manifest and
#   build_phases.cross_check_refs_against_manifest (neither exists yet).
# ====================================================================
