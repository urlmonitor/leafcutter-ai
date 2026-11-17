#!/usr/bin/env python3
"""
MODULE: _gtfa_declared_surface
GOAL: Give the ticket generator ONE place that answers "which files does this
    record's work touch, and where did that answer come from" -- the record's
    declared-files list when it has one, the legacy derivation (labelled as
    such) when it does not.
BUSINESS CONTEXT: TKT-600a-3 / TKT-600a-3-i (KI-ACS-002). The checks read the
    declared list while the generated ticket used to read a doc_links /
    prose derivation -- two answers to one question. A record that declares
    its files now gets a ticket whose files_touched is exactly that list, in
    declared order, with the to-be-created marker and the provenance stated
    per path; a record in the "no declared files" state keeps the old
    derivation, visibly marked "derived, not declared", and is never refused
    here (one gate holds: the implementation-readiness gate, ACD-1600c-1).
ARCHITECTURE: The declared list is read ONLY through
    ``declared_files.get_declared_files`` (ACD-1600c-4); the branch is chosen
    from that seam's named state (``NoDeclaredFiles``), never from the
    emptiness of some list, and ``declared_files`` is never parsed here.
    ``_gtfa_files_touched._build_files_touched`` calls ``declared_paths``;
    ``_gtfa_body`` calls ``surface_section``; ``_gtfa_report`` calls
    ``report_lines``. Frontmatter is unchanged (a flat list of path strings --
    ticket_frontmatter_guard reads it as before); the marker and provenance
    live in the ticket BODY and the --verify report. This module imports no
    ``_gtfa_*`` sibling, so it adds no import cycle. Deployed flat beside
    them (AC_STORE_DEPLOY_MAP); ``declared_files`` is a bare sibling import,
    the same convention validate_ac_schema.py uses.

DECISION HISTORY:
  - 2026-10-12 [python-coder/TKT-600a-3]: Created. The body path lines carry
    the marker and "declared by <id>" but never the words "declared files",
    so the --verify report is the one line per path that names the
    declared-files list as the source. Derived-path provenance is a plain
    classification (doc_links entry / reference_file_path / prose bullet),
    the legacy selection rules are unchanged.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from declared_files import NoDeclaredFiles, get_declared_files  # noqa: E402

_STATUS_INFO = "INFO"


def declared_entries(ac: dict[str, Any]) -> list[dict[str, Any]] | None:
    """Return the record's declared entries in order, or None for 'no declared files'."""
    answer = get_declared_files(ac)
    if isinstance(answer, NoDeclaredFiles):
        return None
    return list(answer)


def declared_paths(ac: dict[str, Any]) -> list[str] | None:
    """Return exactly the declared paths in declared order, or None when none are declared.

    No sort, no de-duplication, no addition from doc_links or prose.
    """
    entries = declared_entries(ac)
    if entries is None:
        return None
    return [str(e["path"]) for e in entries]


def derived_provenance(ac: dict[str, Any], path: str) -> str:
    """Name the true source of a DERIVED path: a doc_links entry, the structured
    reference_file_path, or a prose it_requirements bullet."""
    for link in ac.get("doc_links") or []:
        if isinstance(link, dict) and link.get("path") == path:
            return f"doc_links ({link.get('relationship', 'unspecified')})"
        if link == path:
            return "doc_links"
    it_req = ac.get("it_requirements")
    if isinstance(it_req, dict) and it_req.get("reference_file_path") == path:
        return "it_requirements reference_file_path"
    return "it_requirements prose bullet"


def surface_section(ac: dict[str, Any], ac_id: str, files_touched: list[str]) -> str:
    """Build the ticket-body surface section ('' when there are no paths).

    Declared record: one line per path with its to-be-created marker and
    provenance. 'No declared files' record: a statement that the files were
    derived rather than declared, and one line per path with its true source.
    The word 'declared' is never applied to a derived path.
    """
    if not files_touched:
        return ""
    entries = declared_entries(ac)
    lines = ["## Files Touched", ""]
    if entries is not None:
        lines.append(
            f"Source: the declared-files list of {ac_id}, in declared order "
            "(nothing added from documentation links or prose)."
        )
        lines.append("")
        for entry in entries:
            marker = "to be created by this work" if entry.get("state") == "to_be_created" else "existing"
            lines.append(f"- `{entry['path']}` — {marker} (declared by {ac_id})")
    else:
        lines.append(
            f"Files touched were derived from documentation links and technical "
            f"requirements rather than declared (record {ac_id})."
        )
        lines.append("")
        for path in files_touched:
            lines.append(f"- `{path}` — derived from {derived_provenance(ac, path)}")
    lines.append("")
    return "\n".join(lines)


def report_lines(ac: dict[str, Any], ac_id: str, files_touched: list[str]) -> list[tuple[str, str]]:
    """Return the --verify (status, message) lines for the file-scope check.

    Declared record: one INFO line per path naming the declared-files list as
    its source and its marker. Legacy record: an INFO line showing the surface
    as 'derived, not declared' plus one INFO line per path with its true
    source -- never a PASS. An empty derived list is a WARN (no scope signal).
    """
    entries = declared_entries(ac)
    if entries is not None:
        return [
            (
                _STATUS_INFO,
                f"files_touched {entry['path']} — source: declared_files list of {ac_id} "
                f"({'to be created' if entry.get('state') == 'to_be_created' else 'existing'})",
            )
            for entry in entries
        ]
    if not files_touched:
        return [("WARN", "files_touched is empty — coder has no file-scope signal (declare declared_files on the AC)")]
    out = [
        (
            _STATUS_INFO,
            f"files_touched surface for {ac_id} is derived, not declared "
            "(documentation links and technical requirements; declare declared_files to fix)",
        )
    ]
    out.extend((_STATUS_INFO, f"{path} — source: {derived_provenance(ac, path)}") for path in files_touched)
    return out
