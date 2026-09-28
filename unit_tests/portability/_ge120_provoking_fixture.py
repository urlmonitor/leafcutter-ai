"""
MODULE: _ge120_provoking_fixture
GOAL: Stage a fixed set of files into a working copy that provokes a genuine
    violation for as many checks in hooks_manifest.hooks[] as a single shared
    git-index snapshot can produce simultaneously.
BUSINESS CONTEXT: SHARED between GE-120b-2-i (this ticket) and GE-120b-4 — both
    ACs' own it_requirements say "build it once and own it in one place". A
    fixture that leaves a check clean makes that check's later agreement
    uninformative: it could have silently stopped running altogether. This
    module is the single source of provocation content for the whole GE-120
    tree; do not fork a second copy for a sibling AC.
ARCHITECTURE: Exposes exactly one public symbol, `stage(working_copy_dir)`,
    which writes a fixed file set (built by the sibling `_ge120_provoking_
    fixture_content` module, split out purely to respect the 400-line
    new-file limit) into an already-`git init`-ed, already-built
    (`scripts/build.py --target-dir`) working copy and `git add`s every file
    it writes. Callers (the GE-120b-2-i CLI, and any future GE-120b-4 caller)
    run the manifest's checks against the DEPLOYED copy inside
    working_copy_dir AFTER calling this function — this module never invokes
    a check itself.

    Two classes of check cannot be jointly provoked from one git index and are
    NOT attempted here (see ge120b2i_verify_unchanged.py's sign-off comment
    for the full residual list, since that is where "still clean" is reported
    honestly rather than silently accepted):
      - check-structural-change vs check-components-integrity: the former
        requires docs/components.json NOT staged; the latter requires it
        staged with a bad new entry. This fixture stages components.json, so
        check-structural-change is a deliberate, documented miss.
      - Any check whose provocation logic lives entirely in a nested
        `leafcutter/` package subdirectory (check-agent-registry,
        check-architecture-scaffolds, check-doc-types-agents,
        check-roadmap-schema's `leafcutter/config/roadmap.schema.json` path) —
        out of scope for a staged-files-only fixture.

DECISION HISTORY
====================================================================
- 2026-09-08 [python-coder/GE-120b-2-i]: Initial version, built empirically
  against a real `capture` run per this AC's own it_requirements ("build it
  empirically, not by reasoning" — see ticket body). Provokes the checks whose
  violation condition is reachable from staged file content alone. File
  content builders live in _ge120_provoking_fixture_content.py to keep this
  module under the 400-line new-file limit.
====================================================================
"""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from _ge120_provoking_fixture_content import build_files

logger = logging.getLogger(__name__)

# check-build-drift and check-output-drift both scan the WHOLE tree by hash
# against .build_manifest.json's output_mappings (always_run: true; neither
# consults the staged file list). Appending a marker to an already-deployed
# output file — one build.py itself just wrote from a real template, so a
# real expected_output_hash entry exists for it — provokes both without
# touching any file another provocation in this fixture depends on. Targets
# the `.leafcutter/...` path directly, never the `scripts/commit_guardian`
# symlink to it — `git add` refuses any pathspec that crosses a symlink
# ("fatal: pathspec ... is beyond a symbolic link").
_DRIFT_TARGET_REL = ".leafcutter/scripts/commit_guardian/check_agent_diagrams.py"


def _provoke_output_drift(working_copy_dir: Path) -> str:
    """Append a marker line to an already-deployed output file on disk.

    Args:
        working_copy_dir: Root of the working copy to modify.

    Returns:
        The repo-relative path that was modified, for staging.
    """
    target = working_copy_dir / _DRIFT_TARGET_REL
    try:
        existing = target.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not read %s to provoke drift: %s", target, exc)
        raise
    try:
        target.write_text(existing + "\n# ge120fixture drift marker\n", encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write %s to provoke drift: %s", target, exc)
        raise
    return _DRIFT_TARGET_REL


def _merge_components_json(working_copy_dir: Path) -> None:
    """Add a schema-incomplete component entry to docs/components.json.

    Reads the existing file when present (the deployed default is an empty
    registry) and adds one new top-level key with no `detail_ref` — this is
    what provokes check-components-integrity. Never removes existing entries.

    Args:
        working_copy_dir: Root of the working copy to modify.
    """
    path = working_copy_dir / "docs" / "components.json"
    try:
        existing = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except (OSError, ValueError) as exc:
        logger.warning("Could not read %s, starting fresh: %s", path, exc)
        existing = {}
    components = existing.setdefault("components", {})
    components["ge120fixture_bad_component"] = {
        "id": "ge120fixture_bad_component",
        "name": "GE-120b-2-i fixture component",
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(existing, indent=2) + "\n", encoding="utf-8")


def _git_add(working_copy_dir: Path, relpaths: list[str]) -> None:
    """Stage every fixture path with a real `git add`.

    Args:
        working_copy_dir: Root of the working copy to stage into.
        relpaths: Repo-relative paths to add to the git index.

    Raises:
        subprocess.CalledProcessError: If `git add` exits non-zero.
        OSError: If the git executable cannot be launched.
    """
    try:
        subprocess.run(
            ["git", "-C", str(working_copy_dir), "add", *relpaths],
            check=True,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.CalledProcessError, OSError) as exc:
        logger.warning("git add failed while staging the GE-120 fixture: %s", exc)
        raise


def stage(working_copy_dir: Path) -> None:
    """Stage the shared GE-120 provoking fixture into `working_copy_dir`.

    Writes every fixture file from `_ge120_provoking_fixture_content.
    build_files()`, merges one schema-incomplete entry into the existing
    docs/components.json, and `git add`s the full set so the resulting index
    is what every hooks_manifest check runs against.

    Args:
        working_copy_dir: Root of an already-`git init`-ed, already-built
            (`scripts/build.py --target-dir`) working copy.
    """
    working_copy_dir = Path(working_copy_dir)
    files = build_files()

    for rel_path, content in files.items():
        dest = working_copy_dir / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(content, encoding="utf-8")

    _merge_components_json(working_copy_dir)
    drift_target = _provoke_output_drift(working_copy_dir)

    all_paths = sorted([*files.keys(), "docs/components.json", drift_target])
    _git_add(working_copy_dir, all_paths)
