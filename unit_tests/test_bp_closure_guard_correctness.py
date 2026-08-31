"""
MODULE: test_bp_closure_guard_correctness
GOAL: Behavioural tests for three defects in the BP-900g-8 closure guard, each
    of which makes the guard report a script CLEAN that it has not actually
    checked. All three are remediation of BP-900g-8's own criterion rather
    than new behaviour, which is why every test here tags that AC:

      - "Given ANY script the build deploys into a consumer install" is false
        while Set B omits two deploy families            (KI-BP-023).
      - "whether by import statement, by path construction relative to its own
        location, or by dynamic loader" is false while the reference lens sees
        two of the four sys.path idioms and neither dynamic-import builtin
                                                          (KI-BP-021).
      - "or the build exits non-zero naming the deployed script" is false when
        the script cannot be parsed: the closure comes back empty, which is
        indistinguishable from a script with no dependencies, and the build
        reports it clean                                  (KI-BP-022).

BUSINESS CONTEXT: The guard exists so that a module a deployed script needs
    cannot silently fail to ship. Its failure mode is not a crash — it is an
    EMPTY closure, which the containment check reads as "nothing missing". So
    every defect below presents as a passing build. KI-BP-022 is the sharpest
    case: 107 of the 152 scripts the guard parses live under templates/, which
    CI's ruff run excludes (ci.yml:8), so a syntax error in the entire
    commit-guardian hook population is caught by neither ruff nor this guard,
    and the guard actively reports those files clean.

ARCHITECTURE: Fixture-based and behavioural throughout. Each test builds a
    small real package in a tmp dir, runs the REAL analysis functions against
    it, and asserts on the derived closure or the raised error — never on
    source text. A grep-style assertion cannot distinguish a lens that
    recognises an idiom from one that drops it, because both leave the same
    source in the file; only the derived set can.

    Positive controls are included deliberately. A test that only asserts the
    unsupported idioms resolve would still pass if the whole lens broke, so
    each idiom group is paired with the already-supported form.
"""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import build as _build  # noqa: E402 -- after sys.path setup
import build_referential_integrity as _bri  # noqa: E402 -- after sys.path setup


def _make_pkg(tmp_path: Path, main_body: str, extra: dict[str, str] | None = None) -> Path:
    """Write a two-file package under *tmp_path* and return the main script.

    The layout mirrors the real shape the guard analyses: a script inside a
    package directory, with siblings it may or may not resolve.

    Args:
        tmp_path: Root the closure will be expressed relative to.
        main_body: Source for ``pkg/main.py``.
        extra: Additional ``relative path -> source`` files to create.

    Returns:
        Path to the written ``pkg/main.py``.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    main = pkg / "main.py"
    main.write_text(textwrap.dedent(main_body), encoding="utf-8")
    (pkg / "sibling.py").write_text("VALUE = 1\n", encoding="utf-8")
    for rel, src in (extra or {}).items():
        target = tmp_path / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(textwrap.dedent(src), encoding="utf-8")
    return main


# Plain-assignment form, mirroring goal_to_epic.py's real
# ``Path(__file__).parent / "ac_store"``. The annotated variant is the subject
# of its own test below and passes its own assign line.
_DIR_ASSIGN = '_dir = Path(__file__).parent / "other"'


def _make_pushed_pkg(
    tmp_path: Path, push_stmt: str, assign: str = _DIR_ASSIGN
) -> Path:
    """Write a package whose dependency is reachable ONLY via a sys.path push.

    This layout is load-bearing, and the obvious one is worthless. If the
    imported module sits in the script's OWN directory,
    ``_module_name_candidates`` finds it through ``script_dir`` whether or not
    the sys.path lens saw the push at all — so the test passes against a lens
    that drops the idiom entirely. The first draft of these tests made exactly
    that mistake and three of them passed against unfixed code.

    Here ``helper.py`` lives in ``pkg/other/``, which is neither the script's
    own directory nor the root, so the ONLY way ``import helper`` resolves is
    if the push was understood.

    Args:
        tmp_path: Root the closure will be expressed relative to.
        push_stmt: The sys.path mutation statement under test. It may use the
            local ``_dir``, assigned by *assign* to ``pkg/other``.
        assign: The statement binding ``_dir``. Overridden by the annotated-
            assignment test.

    Returns:
        Path to the written ``pkg/main.py``.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True, exist_ok=True)
    other = pkg / "other"
    other.mkdir(parents=True, exist_ok=True)
    (other / "helper.py").write_text("VALUE = 1\n", encoding="utf-8")
    main = pkg / "main.py"
    main.write_text(
        "import sys\n"
        "from pathlib import Path\n"
        f"{assign}\n"
        f"{push_stmt}\n"
        "import helper\n",
        encoding="utf-8",
    )
    return main


# ---------------------------------------------------------------------------
# KI-BP-022 — "could not analyse" must not be reported as "nothing to report"
# ---------------------------------------------------------------------------


def test_ki_bp_022_unparseable_script_is_not_reported_as_having_no_dependencies(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8
    """A script the guard cannot parse must not yield a clean, empty closure.

    This is the whole defect in one assertion. ``_closure_walk`` catches
    SyntaxError, logs a WARNING and returns, leaving the closure empty — and
    an empty closure means "this script has no intra-package dependencies",
    which is exactly what a correctly-analysed leaf module returns. The two
    outcomes are indistinguishable downstream, so the build proceeds.

    The fix must make them distinguishable. Returning an empty set is not an
    acceptable answer to a question that could not be asked.
    """
    main = _make_pkg(
        tmp_path,
        """
        import sibling
        def broken(:      # deliberate SyntaxError
        """,
    )

    with pytest.raises(_bri.ClosureAnalysisError) as excinfo:
        _bri.compute_intra_package_closure(main, tmp_path)

    assert "main.py" in str(excinfo.value), (
        "The error must name the file that could not be analysed — a guard that "
        "fails without saying which of 152 scripts failed is not actionable. "
        f"Got: {excinfo.value}"
    )


def test_ki_bp_022_undecodable_script_raises_the_same_named_error(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8
    """Invalid UTF-8 must fail the same clean, named way as a SyntaxError.

    ``read_text(encoding="utf-8")`` raises UnicodeDecodeError, which subclasses
    ValueError — NOT OSError — so it escapes the read handler entirely and
    propagates as a raw traceback out of build.py. That happens to fail closed,
    which is the right outcome by accident, but it violates the repo's Rule 1
    (catch what the operation can actually raise) and it reaches the operator
    as a stack trace rather than as the guard's own diagnostic.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True)
    main = pkg / "main.py"
    main.write_bytes(b"import sibling\nx = '\xff\xfe not utf-8'\n")
    (pkg / "sibling.py").write_text("VALUE = 1\n", encoding="utf-8")

    with pytest.raises(_bri.ClosureAnalysisError) as excinfo:
        _bri.compute_intra_package_closure(main, tmp_path)

    assert "main.py" in str(excinfo.value), (
        f"The error must name the undecodable file. Got: {excinfo.value}"
    )


def test_ki_bp_022_a_parseable_leaf_still_returns_an_empty_closure(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8
    """Positive control: "no dependencies" must remain a normal, quiet answer.

    Without this, a fix that raised on every script would pass the two tests
    above while destroying the guard. An empty closure is the correct result
    for a genuine leaf module; only an UNDETERMINED closure is the error.
    """
    main = _make_pkg(tmp_path, "VALUE = 2\n")

    assert _bri.compute_intra_package_closure(main, tmp_path) == set()


# ---------------------------------------------------------------------------
# KI-BP-021 — the reference lens must see the idioms the criterion names
# ---------------------------------------------------------------------------


def test_ki_bp_021_syspath_insert_resolves_the_sibling(tmp_path: Path) -> None:
    # covers: BP-900g-8
    """Positive control for the idiom the lens already supports.

    If this one ever fails, the failures below say nothing about the specific
    idioms they name.
    """
    main = _make_pushed_pkg(tmp_path, "sys.path.insert(0, str(_dir))")

    assert "pkg/other/helper.py" in _bri.compute_intra_package_closure(main, tmp_path)


def test_ki_bp_021_syspath_extend_resolves_the_sibling(tmp_path: Path) -> None:
    # covers: BP-900g-8
    """``sys.path.extend([...])`` pushes a directory exactly as insert does.

    ``_is_syspath_mutation_call`` accepts only ``insert``/``append``, so this
    form produces no candidate directory, the following plain import resolves
    against zero candidates, and the dependency is dropped — with no log line,
    because the ``continue`` fires before the disclosure warning.

    Note the argument is a LIST, not a path: widening the predicate alone turns
    a silent drop into a spurious "unresolvable" warning. Both sides need it.
    """
    main = _make_pushed_pkg(tmp_path, "sys.path.extend([str(_dir)])")

    assert "pkg/other/helper.py" in _bri.compute_intra_package_closure(main, tmp_path)


def test_ki_bp_021_syspath_slice_assignment_resolves_the_sibling(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8
    """``sys.path[:0] = [...]`` is an Assign, not a Call, so no predicate runs.

    The ``ast.walk`` loop filters to ``ast.Call`` before testing anything, so a
    slice assignment is skipped before ``_is_syspath_mutation_call`` is ever
    consulted. Widening that predicate cannot reach this form; it needs its own
    branch.
    """
    main = _make_pushed_pkg(tmp_path, "sys.path[:0] = [str(_dir)]")

    assert "pkg/other/helper.py" in _bri.compute_intra_package_closure(main, tmp_path)


def test_ki_bp_021_annotated_assignment_target_resolves(tmp_path: Path) -> None:
    # covers: BP-900g-8
    """``_build_local_assignments`` captures ``ast.Assign`` but not ``AnnAssign``.

    In a codebase that annotates as heavily as this one, the annotated form is
    the one most likely to appear first. This case at least emits the
    "unresolvable" WARNING today, which makes it the least severe of the group
    — but a warning is not a resolution, and the dependency is still absent
    from the closure the containment check consumes.
    """
    main = _make_pushed_pkg(
        tmp_path,
        "sys.path.insert(0, str(_dir))",
        assign='_dir: Path = Path(__file__).parent / "other"',
    )

    assert "pkg/other/helper.py" in _bri.compute_intra_package_closure(main, tmp_path)


def test_ki_bp_021_importlib_import_module_resolves_the_sibling(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8
    """``importlib.import_module("sibling")`` is an import by any reading.

    ``_extract_static_import_candidates`` recognises only ``ast.Import`` and
    ``ast.ImportFrom``, and ``_is_spec_from_file_location_call`` matches only
    that one loader function, so this call is invisible to both lenses and
    produces no log output at all.
    """
    main = _make_pkg(
        tmp_path,
        """
        import importlib
        mod = importlib.import_module("sibling")
        """,
    )

    assert "pkg/sibling.py" in _bri.compute_intra_package_closure(main, tmp_path)


def test_ki_bp_021_relative_import_of_a_subpackage_resolves_its_init(
    tmp_path: Path,
) -> None:
    # covers: BP-900g-8
    """``from . import sub`` must resolve ``sub/__init__.py``, not just ``sub.py``.

    The relative-import branch adds only ``base/"{name}.py"`` as a candidate. A
    plain import resolving to nothing is treated as external BY DESIGN — which
    is correct for a third-party module and wrong for a subpackage that ships
    in this very tree.
    """
    pkg = tmp_path / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    main = pkg / "main.py"
    main.write_text("from . import sub\n", encoding="utf-8")
    sub = pkg / "sub"
    sub.mkdir()
    (sub / "__init__.py").write_text("VALUE = 3\n", encoding="utf-8")

    assert "pkg/sub/__init__.py" in _bri.compute_intra_package_closure(main, tmp_path)


# ---------------------------------------------------------------------------
# KI-BP-023 — Set B must cover every deploy family, not eight of ten
# ---------------------------------------------------------------------------


def test_ki_bp_023_set_b_covers_the_doc_compliance_deploy_family() -> None:
    # covers: BP-900g-8
    """``build_doc_compliance`` ships a whole Python package the guard never sees.

    ``templates/doc-compliance/cli.py`` has five real sibling imports. Because
    the phase deploys its entire source directory, they all ship today and
    nothing is broken — the exposure is nil. That immunity is a property of the
    DEPLOY MECHANISM, not of the guard, and it evaporates the moment the phase
    is refactored toward a curated deploy_map, which is precisely the pattern
    BP-900g-8 just replaced elsewhere.
    """
    set_b = _build._get_source_deployable_scripts(_REPO_ROOT)

    assert any("doc_compliance" in p for p in set_b), (
        "No doc_compliance path is in Set B, so the loop that computes closures "
        "never calls the analyser on any of them — an entire deployed Python "
        "package is outside the guard, with no warning and no error."
    )


def test_ki_bp_023_set_b_covers_nested_template_standalone_scripts() -> None:
    # covers: BP-900g-8
    """``_manifest_template_standalone_scripts`` globs one level, non-recursively.

    ``scripts/sync_platforms/sync_platforms.py`` lives one directory deeper than
    ``.glob("*.py")`` reaches, so ``build_sync_platforms`` deploys a file the
    guard cannot see.
    """
    set_b = _build._get_source_deployable_scripts(_REPO_ROOT)

    assert any("sync_platforms" in p for p in set_b), (
        "sync_platforms is deployed but absent from Set B — the non-recursive "
        "glob at _manifest_template_standalone_scripts cannot reach it."
    )
