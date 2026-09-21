"""
MODULE: build_phases_product_truth_smoke
GOAL: Run the deployed product-truth checker for real, against a throwaway,
    from-scratch record, as part of every build -- and derive the set of
    files that checker needed in place (and how many) from what it actually
    read while doing so, rather than a hand-restated list (UXP-700a-4).
BUSINESS CONTEXT: build_phases_product_truth.py's pre-UXP-700a-4 guard
    (``_verify_product_truth_required_files``) only checked SIX HAND-NAMED
    files for bare on-disk presence, and never actually ran the checker -- a
    deployed record could crash on its very first real run (as
    UXP-700a-1-i's classifier/eval.jsonl gap once did) and that check would
    still report every file "present" and let the build exit green.

    This module closes that gap. Every build now scaffolds an ephemeral,
    wholly empty product-truth record into its OWN throwaway tempdir (never
    the real consumer target -- see ARCHITECTURE) and runs the REAL,
    just-deployed docs/product-truth/scripts/validate_product_truth.py
    against it, with that checker's own declared I/O boundary
    (``generate_product_truth._load_json`` / ``_load_yaml`` / ``_read_text``,
    re-bound into ``validate_product_truth``'s own namespace by its
    ``from ... import``) instrumented to record every distinct file it
    opens. Because the record it runs against is wholly empty (zero flows,
    zero mock-data, zero mockups, by construction of the scaffold it
    reuses), every file that run actually opens IS, by definition, one of
    the fixed inputs the checker needs before it can begin checking anything
    -- there is nothing else there for it to read. That recorded set both
    IS the derived required-file list (AC-3) and its length IS the count
    the build states (AC-4); a missing entry surfaces as a real
    ``FileNotFoundError`` raised by the checker's own read, caught here and
    translated into the SAME graceful, by-name
    ``build_phases_deploy_failures.record_deploy_failure()`` report every
    other declared-deploy gap already uses (AC-2), rather than a raw
    traceback.
ARCHITECTURE: The scratch copy is built from the SAME ``PACKAGE_ROOT`` the
    real deploy copies from (``docs/product-truth/{scripts,schemas}``), so a
    package-source file missing at deploy time is caught here too -- the
    real consumer deploy globs from the identical source and would silently
    omit the same file (see ``build_product_truth``'s own docstring).
    Isolated, per-call module imports (``_import_scratch_checker``) are
    required, not optional: two derivation runs inside ONE process against
    two DIFFERENT scratch copies (e.g. this ticket's own seam test, a
    baseline vs. a PACKAGE_ROOT-mutated copy) must each see their OWN copy's
    source text, never a stale ``sys.modules['validate_product_truth']``
    entry cached from the other.

    SCOPE NOTE: a runtime trace can only observe what the checker actually
    reached before it stopped -- catching the FIRST missing file and
    reporting it is what this module does; unlike the six-entry hand list it
    replaces, it does not attempt to discover every simultaneously-missing
    file in one pass (that would require re-running past each discovered
    gap, out of this ticket's scope). Removing exactly one required file
    (this repo's own regression fixture, UXP-700a-4-i) is the scenario this
    guarantees.
"""

from __future__ import annotations

import importlib
import shutil
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

#: The deployed product-truth modules a scratch run touches, and therefore
#: must be imported FRESH -- never from a cached ``sys.modules`` entry left
#: by a prior call against a DIFFERENT scratch copy in this same process.
#: Listed once so the isolated-import helper is the single place this set
#: is named.
_TRACED_MODULE_NAMES: tuple[str, ...] = (
    "validate_product_truth",
    "generate_product_truth",
    "product_truth_checks",
    "product_truth_outcome",
    "product_truth_bounds",
    "product_truth_shapes",
    "product_truth_label_checks",
    "product_ownership",
)

#: The checker's own declared I/O boundary functions (validate_product_truth's
#: own docstring: "Imports its derivation logic and its
#: load_flows()/load_mocks() I/O boundary from generate_product_truth so the
#: validator and the single writer agree by construction"). Both modules bind
#: their OWN name to the same underlying function object at import time, so
#: both must be patched for a trace to see every real call site.
_IO_BOUNDARY_FUNCTIONS: tuple[str, ...] = ("_load_json", "_load_yaml", "_read_text")


class RequiredFileMissing(Exception):
    """The checker tried to read a file, before checking began, that does
    not exist.

    Attributes:
        rel: Its path relative to the record root, posix-style -- matching
            the format build_product_truth's other deploy-failure entries
            already use (e.g. ``"schemas/flow.schema.json"``).
    """

    def __init__(self, rel: str) -> None:
        self.rel = rel
        super().__init__(f"required product-truth file not found: {rel}")


def _import_scratch_checker(scripts_dir: Path) -> tuple[Any, Any]:
    """Import validate_product_truth.py (and generate_product_truth.py)
    fresh from *scripts_dir*, bypassing any cached ``sys.modules`` entry a
    prior call (against a different scripts_dir, in this same process) left
    behind.

    Returns:
        (validate_module, generate_module) -- both freshly loaded.
    """
    saved = {name: sys.modules.pop(name) for name in _TRACED_MODULE_NAMES if name in sys.modules}
    scripts_dir_str = str(scripts_dir)
    sys.path.insert(0, scripts_dir_str)
    try:
        validate_module = importlib.import_module("validate_product_truth")
        generate_module = sys.modules["generate_product_truth"]
    finally:
        for name in _TRACED_MODULE_NAMES:
            sys.modules.pop(name, None)
        sys.modules.update(saved)
        try:
            sys.path.remove(scripts_dir_str)
        except ValueError:
            pass
    return validate_module, generate_module


@contextmanager
def _traced_io_boundary(modules: tuple[Any, ...], store: Path) -> Iterator[list[str]]:
    """Patch each module's I/O boundary functions to record every distinct
    file path they are asked to read, relative to *store*, in read order --
    and to raise :class:`RequiredFileMissing` (instead of letting the
    checker's own ``OSError`` propagate raw) the moment one does not exist,
    naming it the same posix-relative way.
    """
    recorded: list[str] = []
    originals: dict[tuple[Any, str], Any] = {}
    for module in modules:
        for fn_name in _IO_BOUNDARY_FUNCTIONS:
            if hasattr(module, fn_name):
                originals[(module, fn_name)] = getattr(module, fn_name)

    def _make_wrapper(original: Any) -> Any:
        def _wrapped(path: Path, *args: Any, **kwargs: Any) -> Any:
            candidate = Path(path)
            try:
                rel = candidate.resolve().relative_to(store.resolve()).as_posix()
            except ValueError:
                rel = None
            if not candidate.exists():
                if rel is not None:
                    raise RequiredFileMissing(rel)
                raise FileNotFoundError(candidate)
            if rel is not None and rel not in recorded:
                recorded.append(rel)
            return original(path, *args, **kwargs)

        return _wrapped

    for key, original in originals.items():
        setattr(key[0], key[1], _make_wrapper(original))
    try:
        yield recorded
    finally:
        for (module, fn_name), original in originals.items():
            setattr(module, fn_name, original)


def _build_scratch_record(product_truth_src: Path) -> Path:
    """Copy the REAL, package-owned sources into a fresh, private tempdir and
    scaffold a wholly empty record into it.

    This is the "throwaway empty project" this ticket's AC installs a record
    into and runs its checker against -- deliberately never the real
    consumer ``target_root``, whose content (on a second build of a project
    that has since authored real journeys) would no longer be from-scratch.

    Returns:
        The tempdir's own ``docs/product-truth`` root. The caller is
        responsible for removing its grandparent (the tempdir itself).
    """
    import build_phases_product_truth as _bppt  # noqa: PLC0415 -- see module ARCHITECTURE note

    scratch_root = Path(tempfile.mkdtemp(prefix="leafcutter-product-truth-smoke-"))
    scratch_pt = scratch_root / "docs" / "product-truth"
    if (product_truth_src / "scripts").is_dir():
        shutil.copytree(product_truth_src / "scripts", scratch_pt / "scripts")
    if (product_truth_src / "schemas").is_dir():
        shutil.copytree(product_truth_src / "schemas", scratch_pt / "schemas")
    _bppt._scaffold_product_truth_record(scratch_pt, dry_run=False)  # noqa: SLF001
    return scratch_pt


def run_product_truth_smoke_test(product_truth_src: Path) -> list[str]:
    """Run the checker for real against a throwaway, from-scratch record.

    Prints the checker's own real outcome-contract stdout line as a side
    effect of running it, exactly as a consumer's own CI would see it.

    Args:
        product_truth_src: The package's own ``docs/product-truth`` root
            (the SAME source the real consumer deploy copies from).

    Returns:
        The derived required-file list, posix-relative to the record root,
        in the order the checker read them, deduplicated.

    Raises:
        RequiredFileMissing: One of the checker's own start-up reads found
            no file at its target path -- named as ``exc.rel``.
    """
    scratch_pt = _build_scratch_record(product_truth_src)
    try:
        validate_module, generate_module = _import_scratch_checker(scratch_pt / "scripts")
        with _traced_io_boundary((validate_module, generate_module), scratch_pt) as recorded:
            saved_argv = sys.argv
            sys.argv = ["validate_product_truth.py", "--quiet"]
            try:
                validate_module.main()
            finally:
                sys.argv = saved_argv
        return recorded
    finally:
        shutil.rmtree(scratch_pt.parent.parent, ignore_errors=True)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-16 16:20 [python-coder]: Created for UXP-700a-4 -- split out of
  build_phases_product_truth.py (which was near its 400-content-line limit)
  rather than grown in place, following the build_phases_knowledge.py /
  build_phases_product_truth.py precedent for the same reason. Replaces the
  hand-restated ``_PRODUCT_TRUTH_REQUIRED_FILES`` tuple and
  ``_verify_product_truth_required_files`` (bare on-disk presence, no real
  checker run) with a runtime-traced derivation: a wholly empty scratch
  record is scaffolded into its own tempdir and the REAL checker is run
  against it, with its own I/O boundary instrumented to record every file
  it actually opens. (#EPIC-TruthfulProjectRecord/08)
====================================================================
"""
