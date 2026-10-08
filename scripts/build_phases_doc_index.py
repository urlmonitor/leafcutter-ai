"""
MODULE: build_phases_doc_index
GOAL: Generate the documentation map (<docs_root>/INDEX.md) during a build,
    from the same docs folder the map is written into, and never replace a
    populated map with an empty one (BP-1500a-1).
BUSINESS CONTEXT: In the self-hosting layout (target = the workspace parent,
    docs_root = "leafcutter-ai/docs/") the phase used to scan the workspace
    parent, which has no docs/, and overwrote the tracked index with a stub
    whose every section read "No docs found." (KI-BP-016 / KI-BP-001 /
    KI-BP-20260907-1620).
ARCHITECTURE: One public function, ``build_doc_index``, with the phase
    signature every build phase shares (target_root, config, dry_run, force).
    build.py re-exports it and lists it in its phase table, so build:main is
    the only runtime way in; this module deliberately defines no ``main``
    of its own. Carried out of
    build.py, which is over the file-size ratchet, exactly as the other
    build_phases_* modules were. Log helpers come from build_colors, the same
    ones build.py uses.
DECISION HISTORY:
- 2026-09-28 12:00 [python-coder/quick-fix]: Extracted from build.py so the
  covers-tagged proof can import the phase without importing build.py's
  ``main`` (the BO-2900a-1 entry-point gate refuses a direct-import proof of
  a unit that defines main, and build.main has no single-phase mode; a full
  build per test is forbidden by CLAUDE.md). Body moved verbatim. The
  done-proof oracle accepts the in-process proof without any
  reachability-exemption entry.
  (#TICKETLESS reason=quick-fix-BP-1500a-1)
"""

from __future__ import annotations

from pathlib import Path

from build_colors import (
    dry_run as _dry_run_msg,
    success as _success,
    warn as _warn,
)


def build_doc_index(target_root: Path, config: dict, dry_run: bool, force: bool) -> int:  # noqa: ARG001
    """Generate <docs_root>/INDEX.md by walking that docs tree.

    The index is regenerated on every build run (not write-if-absent) because
    it is fully derived from the existing docs tree and must stay current.
    Idempotent: if the content is byte-identical to what is already on disk,
    no write is performed and 0 is returned.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary; only ``docs_root`` (default
            "docs/") is read -- it names the folder the map is written into.
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — index is always regenerated (content-addressed write).

    Scan root (BP-1500a-1): the map is built from the repository that
    CONTAINS the docs_root folder (``docs_path.parent``), because
    generate_doc_index's categories are "docs/..." paths relative to that
    root. For the default docs_root "docs/" this is target_root, so consumer
    installs are unchanged; in the self-hosting layout (docs_root
    "leafcutter-ai/docs/") it is the package repo, not the workspace parent
    that has no docs/. When docs_root does not end in a "docs" folder the old
    scan root (target_root) is kept and a warning is emitted.

    Fail-safe (BP-1500a-1): if every generated category reads "No docs
    found." while the existing map lists at least one entry, the scan almost
    certainly resolved the wrong folder -- nothing is written, a warning
    names the scanned folder, and 0 is returned. generate_doc_index renders
    every entry as a Markdown link and an empty category as "No docs found."
    with no link, and its header and footer carry no link, so "the text has
    no ``](``" is exactly "every category is empty".

    Error handling: a failure to read the existing map or to write the new
    one is reported with ``_warn`` and returns 0; it never aborts the build.

    Returns:
        1 if the file was written; 0 if the content was already up-to-date,
        the fail-safe refused the write, or reading/writing failed.
    """
    from generate_doc_index import generate_index
    docs_path = target_root / config.get("docs_root", "docs/").rstrip("/")
    output_path = docs_path / "INDEX.md"
    if docs_path.name != "docs":
        _warn(f"docs_root {docs_path} does not end in a 'docs' folder; doc index scans {target_root}.")
    content = generate_index(docs_path.parent if docs_path.name == "docs" else target_root, docs_path)
    if dry_run:
        _dry_run_msg(f"would write {output_path}")
        return 1
    try:
        existing = output_path.read_text(encoding="utf-8", errors="replace") if output_path.is_file() else None
        if existing == content:
            return 0
        if existing and "](" in existing and "](" not in content:
            _warn(f"Doc index: found no docs under {docs_path}; kept the populated {output_path} unchanged.")
            return 0
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        _warn(f"Failed to read or write {output_path}: {exc}")
        return 0
    _success(f"wrote {output_path.relative_to(target_root)}")
    return 1
