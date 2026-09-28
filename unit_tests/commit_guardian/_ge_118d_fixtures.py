"""
MODULE: unit_tests/commit_guardian/_ge_118d_fixtures.py
GOAL: The shared path constants and fixture helpers used by BOTH GE-118d test
    modules -- test_ge_118d.py (angles: failure, criterion, real_artifact) and
    test_ge_118d_deployed.py (angles: deployed, reachability) -- extracted so
    each of those files stays inside the 400-content-line file-size ratchet
    (check-file-size). Nothing was rewritten in the move: every helper below is
    byte-for-byte the one both suites already called.
BUSINESS CONTEXT: No test logic and no assertions live here -- only constants,
    a real-git-repository builder, a file writer, a real-subprocess hook
    invoker and two document-fixture builders. This module therefore carries no
    coverage of its own and is not itself a test module; the leading underscore
    keeps pytest from collecting it.
ARCHITECTURE: Imported as `from . import _ge_118d_fixtures` / `from
    ._ge_118d_fixtures import ...`, mirroring this same directory's existing
    `_bp_100k_3_iii_harness` convention (and unit_tests/product_truth/
    _uxp_700c_2_fixtures.py, which exists for the identical file-size reason).
    `_REPO_ROOT` is resolved from THIS file's own location -- same directory
    depth as the two test modules -- so the constants below are identical to
    the ones the single pre-split file computed.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

# unit_tests/commit_guardian/_ge_118d_fixtures.py -> unit_tests/ -> repo root
_REPO_ROOT = Path(__file__).resolve().parents[2]

_TEMPLATES_CG_DIR = _REPO_ROOT / "templates" / "scripts" / "commit_guardian"
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_RUN_HOOK = _TEMPLATES_CG_DIR / "run_hook.py"
_CHECK_DOC_FRONTMATTER = _TEMPLATES_CG_DIR / "check_doc_frontmatter.py"
_BUILD_PY = _SCRIPTS_DIR / "build.py"

_KI_CG_008_REL = "docs/known-issues/commit-guardian/resolved/resolved-blocker-ki-cg-008.md"

PYTHON = sys.executable
_SUBPROCESS_TIMEOUT_SECONDS = 30
_BUILD_TIMEOUT_SECONDS = 180


# ---------------------------------------------------------------------------
# Shared fixture helpers
# ---------------------------------------------------------------------------


def _git(args: list[str], cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    """Run a real git command in *cwd*."""
    return subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
        check=check,
    )


def _init_repo(root: Path) -> None:
    """Initialize a real, isolated git repository with a deterministic identity."""
    _git(["init", "-q", "-b", "main"], root)
    _git(["config", "user.email", "ge118d-test@example.com"], root)
    _git(["config", "user.name", "GE-118d test fixture"], root)


def _write(path: Path, content: str) -> None:
    """Write *content* to *path*, creating parent directories as needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _run_hook_against_source(cwd: Path, filenames: list[str]) -> subprocess.CompletedProcess:
    """Invoke the REAL, unmodified SOURCE-tree run_hook.py + check_doc_frontmatter.py.

    Mirrors pre-commit's own invocation convention
    (``python run_hook.py check_doc_frontmatter.py <files...>``) -- a real
    production entry point, not a direct import of any validator function.
    """
    return subprocess.run(
        [PYTHON, str(_RUN_HOOK), str(_CHECK_DOC_FRONTMATTER), *filenames],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def _four_entry_doc_frontmatter(*, title: str, absent_target: str | None = None) -> str:
    """Build hand-typed (non-yaml.safe_dump) frontmatter text for the AC's own
    scenario: related_docs holds one bare + one labelled entry; related_code
    and architecture_diagrams each hold one labelled entry.

    Hand-typed YAML is safe here (unlike the files_touched regex-parser class
    of defect docs/how-to/real-artifact-fixtures.md warns about): every
    consumer of this text is the REAL yaml.safe_load()-based
    extract_frontmatter(), which parses indented and column-0 list forms
    identically -- the defect under test (TypeError on a dict element) is a
    property of the PARSED VALUE's type, not of source indentation. Test 4
    covers the yaml.safe_dump real-artifact requirement separately.

    Args:
        title: Frontmatter ``title`` value (kept unique per test for clarity
            in failure output).
        absent_target: When given, the related_docs labelled entry names this
            path instead of ``docs/explanation/architecture_labelled.md`` --
            used by the negative-arm test to force exactly one broken path.
    """
    labelled_docs_target = absent_target or "docs/explanation/architecture_labelled.md"
    return (
        "---\n"
        f'title: "{title}"\n'
        "type: reference\n"
        "status: active\n"
        'created: "2026-09-28"\n'
        'last_updated: "2026-09-28"\n'
        "components:\n"
        "  - commit_guardian\n"
        "related_docs:\n"
        "  - docs/explanation/architecture.md\n"
        f"  - explanation_labelled: {labelled_docs_target}\n"
        "related_code:\n"
        "  - implementation: scripts/ge118d_temp_helper.py\n"
        "architecture_diagrams:\n"
        "  - c1_context: docs/architecture/diagrams/c1-context.md\n"
        "---\n\n"
        f"Temporary GE-118d fixture: {title}.\n"
    )


def _write_four_entry_targets(root: Path) -> None:
    """Create the four real on-disk files the AC's scenario entries name."""
    _write(root / "docs" / "explanation" / "architecture.md", "# Architecture\n")
    _write(
        root / "docs" / "explanation" / "architecture_labelled.md",
        "# Architecture (labelled target)\n",
    )
    _write(root / "scripts" / "ge118d_temp_helper.py", "# GE-118d temp helper\n")
    _write(
        root / "docs" / "architecture" / "diagrams" / "c1-context.md",
        "# C1 context\n",
    )
