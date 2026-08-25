"""
MODULE: test_bp_900a_3
GOAL: Behavioral regression coverage for AC BP-900a-3 — the ac_store scripts
    build.py deploys to a consumer project must be importable via the exact
    sys.path mechanism the agent templates (build-ac.md, ac-scanner/SKILL.md)
    use at runtime, and the deployed directory must be a valid, side-effect-
    free Python package (__init__.py present and inert).
TICKET: tickets/00_inbox/epics/EPIC-DeploymentCompleteness/04_TICKET-20260611-BP-900a-3.md
AC: BP-900a-3 (docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900a-3.yaml)

ARCHITECTURE: Two real-artifact behavioral tests (per the Real-Artifact
    Behavioral Test Mandate, BP-1100f-2). Both run the REAL ``build.py
    --target-dir`` into a fresh ``tmp_path``, then exercise the deployed
    directory from a FRESH SUBPROCESS using the identical
    ``sys.path.insert(0, '<output_root>/scripts/ac_store')`` pattern that
    ``templates/agents/build-ac.md`` (lines ~159, ~265) and
    ``templates/skills/ac-scanner/SKILL.md`` embed in their inline
    ``python3 -c "..."`` snippets. Neither test mocks the deploy call or
    inspects call_args; both read/execute the real deployed artifact.

    A fresh subprocess (rather than an in-process ``importlib.import_module``
    call from within the pytest process) is used deliberately: the AC's
    ``it_requirements.notes`` field warns that "a unit test that imports from
    scripts/ac_store/ directly will pass while the deployed copy is missing" —
    the masking effect described in CLAUDE.md "New Hook / Gate Dependencies
    Must Be in the Build Deploy-Manifest". Running in a fresh subprocess with
    sys.path seeded ONLY with the deployed directory (no source-tree
    scripts/ac_store/ on the path) closes that masking hole: if the deployed
    copy is incomplete, the subprocess import fails for real.

RED-BASELINE NOTE (2026-08-18): Both of the above tests PASS IMMEDIATELY at
    authoring time — the prerequisite ticket BP-900a-1 already closed the
    deploy_map completeness gap (all 13 ac_store files, including
    __init__.py, are deployed and none of the three named modules have
    internal cross-module imports that would break under this sys.path
    layout). Per the test-writer contract, an all-green new test file is a
    problem to investigate, not a valid sign-off state. Investigating this
    ticket's own ``files_touched`` (all three are documentation/template
    files, doc_links relationship "describes") shows the concrete remaining
    gap: unlike its sibling ACs (BP-900a-2, BP-900b-1, BP-900c-1/2/3),
    ``docs/architecture/components/template-compiler.md`` has ZERO mentions
    of "BP-900a-3" — no section documents this importability contract. A
    third test, ``test_ac_bp900a3_documented_in_template_compiler_doc``, is
    added below to give this ticket a genuine, currently-failing red
    baseline targeting its actual undelivered scope (the missing doc
    section), while the two behavioral import tests above are retained as
    permanent regression coverage for the AC's runtime contract.
"""
# @ac-tag: BP-900a-3

from __future__ import annotations

import subprocess
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

# The three modules the AC names explicitly.
_REQUIRED_IMPORTS = ("ac_prioritizer", "generate_ticket_from_ac", "scan_ac_store")


def _find_output_root(target_dir: Path) -> Path:
    """Return the deployed output root inside *target_dir* — the dir holding scripts/.

    Mirrors the helper in unit_tests/test_bp_900a_1.py: keyed on ``scripts/``
    because that is the prefix consumer templates address, regardless of the
    configured output-root directory name (``.leafcutter`` by default).
    """
    candidates = sorted(
        p for p in target_dir.iterdir() if p.is_dir() and (p / "scripts").is_dir()
    )
    assert len(candidates) == 1, (
        f"Expected exactly one deployed output root under {target_dir} (a directory "
        f"containing a 'scripts/' subdirectory); found {[p.name for p in candidates]}."
    )
    return candidates[0]


def _run_build_into(target_dir: Path) -> Path:
    """Run the REAL build.py --target-dir against *target_dir* and return the
    deployed <output_root>/scripts/ac_store/ directory.
    """
    target_dir.mkdir(parents=True, exist_ok=True)
    exit_code = _build.main(["--target-dir", str(target_dir)])
    assert exit_code == 0, (
        f"build.py --target-dir exited {exit_code!r}; expected 0. The importability "
        "assertions below cannot run against a failed build."
    )
    output_root = _find_output_root(target_dir)
    return output_root / "scripts" / "ac_store"


# ---------------------------------------------------------------------------
# Real-artifact behavioral tests
# ---------------------------------------------------------------------------


def test_deployed_ac_store_modules_import_from_the_deployed_layout(tmp_path: Path) -> None:
    """AC BP-900a-3: Given build.py has deployed the ac_store scripts to a
    consumer project, When a process sets sys.path to include
    "{target}/scripts/ac_store" and imports ac_prioritizer,
    generate_ticket_from_ac, and scan_ac_store, Then all three imports
    succeed without ImportError.

    Runs the real build into tmp_path, then spawns a FRESH subprocess whose
    sys.path contains ONLY the deployed scripts/ac_store directory (plus the
    stdlib) — reproducing the exact `sys.path.insert(0, '.../scripts/ac_store')`
    pattern embedded in templates/agents/build-ac.md and
    templates/skills/ac-scanner/SKILL.md. This is the real-effect round-trip:
    if the deployed copy is missing a file, or if any of the three modules
    were to gain an internal cross-module import that only resolves when
    scripts/ac_store's parent (not itself) is on sys.path, this subprocess
    import fails for real — no mocking involved.
    """
    # covers: BP-900a-3
    deployed_dir = _run_build_into(tmp_path / "consumer")

    import_snippet = (
        "import sys\n"
        f"sys.path.insert(0, {str(deployed_dir)!r})\n"
        + "\n".join(f"import {name}" for name in _REQUIRED_IMPORTS)
        + "\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", import_snippet],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        "Importing ac_prioritizer, generate_ticket_from_ac, and scan_ac_store "
        f"from the deployed layout at {deployed_dir} failed in a fresh subprocess "
        f"(exit code {result.returncode}).\n--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}\n"
        "AC BP-900a-3 requires all three imports to succeed without ImportError "
        "using the same sys.path mechanism templates/agents/build-ac.md and "
        "templates/skills/ac-scanner/SKILL.md embed at runtime."
    )
    assert "ImportError" not in result.stderr, (
        f"Unexpected ImportError in subprocess stderr: {result.stderr}"
    )
    assert "ModuleNotFoundError" not in result.stderr, (
        f"Unexpected ModuleNotFoundError in subprocess stderr: {result.stderr}"
    )


def test_deployed_ac_store_init_is_present_and_side_effect_free(tmp_path: Path) -> None:
    """AC BP-900a-3: And the __init__.py file is present so the directory is
    a valid Python package.

    Verifies (a) __init__.py physically exists in the deployed package
    directory, and (b) importing the deployed package (via the same
    sys.path-insert mechanism, in a fresh subprocess) produces no stdout/
    stderr output and does not raise — i.e. __init__.py introduces no
    import-time side effects, per the AC's it_requirements constraint "Must
    not introduce any import-time side effects in __init__.py".
    """
    # covers: BP-900a-3
    deployed_dir = _run_build_into(tmp_path / "consumer")

    init_path = deployed_dir / "__init__.py"
    assert init_path.is_file(), (
        f"__init__.py not found at {init_path} — the deployed scripts/ac_store/ "
        "directory is not a valid Python package (AC BP-900a-3)."
    )

    # The deployed directory name is "ac_store"; importing it as a package
    # requires its PARENT directory (not itself) on sys.path.
    import_snippet = (
        "import sys\n"
        f"sys.path.insert(0, {str(deployed_dir.parent)!r})\n"
        "import ac_store\n"
    )

    result = subprocess.run(
        [sys.executable, "-c", import_snippet],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert result.returncode == 0, (
        f"Importing the deployed ac_store package from {deployed_dir.parent} failed "
        f"in a fresh subprocess (exit code {result.returncode}).\n"
        f"--- stdout ---\n{result.stdout}\n--- stderr ---\n{result.stderr}"
    )
    assert result.stdout == "", (
        "Importing the deployed ac_store __init__.py produced unexpected stdout "
        f"output (import-time side effect): {result.stdout!r}"
    )
    assert result.stderr == "", (
        "Importing the deployed ac_store __init__.py produced unexpected stderr "
        f"output (import-time side effect): {result.stderr!r}"
    )


def test_ac_bp900a3_documented_in_template_compiler_doc() -> None:
    """AC BP-900a-3: the AC's doc_links declare
    docs/architecture/components/template-compiler.md as a file that
    "describes" this contract (relationship: describes). Its sibling ACs in
    the same epic (BP-900a-2, BP-900b-1, BP-900c-1, BP-900c-2, BP-900c-3) each
    have a dedicated section in that document naming their AC ID and
    explaining the guarantee. This AC currently has none.

    This is a structural/content test (not a grep-for-workflow-behavior
    check governed by the "verify behaviorally, not by grep" convention —
    that convention targets executable workflow/gate ACs; there is no
    executable behavior to run for a prose documentation deliverable, so
    presence/content of the required section is the only feasible signal).
    """
    # covers: BP-900a-3
    doc_path = _REPO_ROOT / "docs" / "architecture" / "components" / "template-compiler.md"
    assert doc_path.is_file(), f"Expected doc file not found: {doc_path}"

    content = doc_path.read_text(encoding="utf-8")

    assert "BP-900a-3" in content, (
        f"{doc_path} has no section documenting AC BP-900a-3. Sibling ACs in "
        "this file (BP-900a-2, BP-900b-1, BP-900c-1/2/3) each get a dedicated "
        "section naming their AC ID and explaining the guarantee it "
        "establishes — add one for BP-900a-3 describing the ac_store "
        "importability contract (sys.path.insert(0, "
        "'<output_root>/scripts/ac_store') + __init__.py present)."
    )
    assert "__init__.py" in content, (
        f"{doc_path} does not mention __init__.py — the BP-900a-3 section "
        "must explain that the deployed ac_store directory is a valid "
        "Python package."
    )
    assert "importable" in content.lower(), (
        f"{doc_path} does not use the word 'importable' anywhere — the "
        "BP-900a-3 section must document that the deployed scripts are "
        "importable via the sys.path mechanism agent templates use."
    )


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-08-18 [test-writer/EPIC-DeploymentCompleteness/BP-900a-3]: Initial
#   failing test stubs, derived directly from the AC's test_spec (the
#   ticket's own "## Test Requirements" section is absent, per the
#   AC-derivation fallback). At authoring time, the two behavioral import
#   tests (test_deployed_ac_store_modules_import_from_the_deployed_layout,
#   test_deployed_ac_store_init_is_present_and_side_effect_free) PASS
#   IMMEDIATELY — prerequisite ticket BP-900a-1 already closed the
#   deploy_map gap that would have made them fail. The third test,
#   test_ac_bp900a3_documented_in_template_compiler_doc, is RED at authoring
#   time: docs/architecture/components/template-compiler.md has zero
#   mentions of "BP-900a-3" (confirmed via grep before writing this test).
#   This targets the concrete undelivered scope of this ticket (its
#   files_touched are all documentation/template files with doc_links
#   relationship "describes"). Expected red state: AssertionError,
#   "has no section documenting AC BP-900a-3".
# ====================================================================
