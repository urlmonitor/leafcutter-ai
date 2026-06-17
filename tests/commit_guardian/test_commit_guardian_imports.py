"""
MODULE: tests/commit_guardian/test_commit_guardian_imports.py
GOAL: Smoke-import every commit_guardian hook and validator module so a
      missing-sibling-module regression (e.g. a half-landed refactor that
      removes a module another module imports) fails the test suite instead
      of silently disabling a pre-commit hook in every consumer repo.
BUSINESS CONTEXT: GE-103. check_doc_frontmatter.py crashed on import because
      frontmatter_validators.py imported the diagram_type_validators module,
      which had never been deployed. The crash disabled ALL doc-frontmatter
      enforcement at commit time without any visible signal. This test makes
      the import contract for the package explicit and enforced.
ARCHITECTURE: The commit_guardian modules use flat, same-directory imports
      (e.g. ``from config import ...``), so the package directory must be on
      sys.path before importing a module by its file stem. covers: GE-103
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

WORKTREE_ROOT = Path(__file__).resolve().parent.parent.parent
CG_DIR = WORKTREE_ROOT / "scripts" / "commit_guardian"

# Optional third-party packages the hooks import. These are provided by the
# project's poetry venv (run_hook.py resolves to it at commit time) but may be
# absent in a minimal test environment. A missing one of these is an
# environment-setup concern, NOT the missing-sibling-module regression this
# test guards against, so we skip rather than fail. Anything missing that is
# NOT in this set is treated as a packaging regression (see GE-103).
OPTIONAL_THIRD_PARTY = {"docstring_parser", "psycopg2", "psycopg2-binary"}


def _module_stems() -> list[str]:
    """Collect the file stems of all check_*.py and *_validators.py modules.

    Returns:
        list[str]: Sorted, de-duplicated module stems found directly inside
            ``scripts/commit_guardian/`` (top level only; subpackages such as
            ``hooks/`` are imported via their own __init__ contract elsewhere).
    """
    stems = {
        p.stem
        for p in CG_DIR.glob("check_*.py")
    } | {
        p.stem
        for p in CG_DIR.glob("*_validators.py")
    }
    return sorted(stems)


@pytest.fixture(autouse=True)
def _cg_on_syspath():
    """Put the commit_guardian directory on sys.path for the duration of a test.

    The hook modules import their siblings by bare name (``from config import``),
    which only resolves when their containing directory is the first sys.path
    entry — exactly how pre-commit invokes them as top-level scripts.
    """
    inserted = str(CG_DIR)
    sys.path.insert(0, inserted)
    try:
        yield
    finally:
        if inserted in sys.path:
            sys.path.remove(inserted)


def test_commit_guardian_dir_exists():
    """The deployed commit_guardian source directory must exist."""
    assert CG_DIR.is_dir(), f"commit_guardian dir missing: {CG_DIR}"


def test_module_set_is_non_empty():
    """Guard against the glob silently matching nothing (false-green)."""
    stems = _module_stems()
    assert stems, "no check_*.py / *_validators.py modules found to smoke-import"


@pytest.mark.parametrize("stem", _module_stems())
def test_module_imports_cleanly(stem: str):
    """Every hook/validator module must import without ModuleNotFoundError.

    A missing sibling module (the GE-103 regression) surfaces here as an
    ImportError, turning a silently-disabled hook into a hard test failure.
    A missing *optional third-party* package is an environment concern, not a
    packaging regression, so it is skipped rather than failed.
    """
    try:
        importlib.import_module(stem)
    except ModuleNotFoundError as exc:
        missing = exc.name
        if missing in OPTIONAL_THIRD_PARTY:
            pytest.skip(
                f"optional third-party dependency '{missing}' not installed "
                f"in this environment (required by '{stem}')"
            )
        pytest.fail(
            f"commit_guardian module '{stem}' failed to import: {exc}. "
            f"Local sibling module '{missing}' is missing or undeployed "
            "(see GE-103)."
        )
    finally:
        sys.modules.pop(stem, None)


def test_diagram_type_validators_present_and_callable():
    """The specific module that caused GE-103 must exist and expose its API.

    covers: GE-103
    """
    mod = importlib.import_module("diagram_type_validators")
    try:
        assert hasattr(mod, "validate_diagram_type"), (
            "diagram_type_validators must expose validate_diagram_type()"
        )
        # A doc with no diagram_type declared is valid (field is optional).
        assert mod.validate_diagram_type({}) == []
        # A bogus value must be rejected.
        assert mod.validate_diagram_type({"diagram_type": "not_a_real_type"})
        # Any value from the module's *active* enum source (diagram_types.json
        # when resolvable, else the config-constant fallback) must pass. We read
        # the active enum from the module rather than hardcoding a value, so this
        # test stays scoped to the GE-103 import/validation contract and does not
        # couple to the separate SSOT-path-resolution concern.
        known = mod._load_diagram_types()
        assert known, "diagram_type enum must be non-empty"
        sample = sorted(known.keys())[0]
        assert mod.validate_diagram_type({"diagram_type": sample}) == []
    finally:
        sys.modules.pop("diagram_type_validators", None)
