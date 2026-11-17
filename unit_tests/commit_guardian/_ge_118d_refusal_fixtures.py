"""
MODULE: unit_tests/commit_guardian/_ge_118d_refusal_fixtures.py
GOAL: Shared helpers for the GE-118d-1 and GE-118d-2 suites (refusal of an
    unaccepted path-entry shape; refusal of a multi-key labelled entry).
BUSINESS CONTEXT: No assertions live here. Document fixtures are produced with
    the REAL serializer (yaml.safe_dump), never a hand-indented literal, per
    the Fixture Authenticity Rule -- an integer 7, a nested list and a
    mapping-of-mapping cannot be mistaken for a string by a typed literal's
    author, and PyYAML's column-0 block lists are the real on-disk shape.
ARCHITECTURE: Builds on the sibling `_ge_118d_fixtures` module (real git repo
    builder, file writer, source-tree hook invoker). Leading underscore keeps
    pytest from collecting it.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

from ._ge_118d_fixtures import (
    _REPO_ROOT,
    _SCRIPTS_DIR,
    _SUBPROCESS_TIMEOUT_SECONDS,
    PYTHON,
    _write,
)

_BASE_FM: dict[str, Any] = {
    "title": "GE-118d refusal fixture",
    "type": "reference",
    "status": "active",
    "created": "2026-09-28",
    "last_updated": "2026-09-28",
    "components": ["commit_guardian"],
}


def doc_text(path_fields: dict[str, Any]) -> str:
    """Return a markdown document whose frontmatter is yaml.safe_dump output."""
    fm = {**_BASE_FM, **path_fields}
    return f"---\n{yaml.safe_dump(fm, sort_keys=False)}---\n\nGE-118d refusal fixture body.\n"


def write_existing_targets(root: Path) -> None:
    """Create every on-disk path the refusal fixtures name, so a refusal can
    never be explained by a missing file."""
    for rel in (
        "docs/explanation/architecture.md",
        "docs/reference/configuration.md",
        "scripts/ge118d_temp_helper.py",
        "docs/architecture/diagrams/c1-context.md",
        "docs/architecture/diagrams/c2-container.md",
    ):
        _write(root / rel, "# existing target\n")


def run_deployed_hook(layout: Path, cwd: Path, doc_rel: str) -> subprocess.CompletedProcess:
    """Invoke the DEPLOYED run_hook.py + check_doc_frontmatter.py from *layout*
    (read-only: the layout is never mutated) against *doc_rel* under *cwd*."""
    hook_dir = layout / "scripts" / "commit_guardian"
    return subprocess.run(
        [
            PYTHON,
            str(hook_dir / "run_hook.py"),
            str(hook_dir / "check_doc_frontmatter.py"),
            doc_rel,
        ],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=_SUBPROCESS_TIMEOUT_SECONDS,
    )


def import_resolver():
    """Import the source-tree resolver module (scripts/frontmatter_path_resolver.py)."""
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    import frontmatter_path_resolver as resolver

    return resolver


__all__ = [
    "_REPO_ROOT",
    "doc_text",
    "import_resolver",
    "run_deployed_hook",
    "write_existing_targets",
]
