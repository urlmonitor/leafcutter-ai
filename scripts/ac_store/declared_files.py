"""
MODULE: scripts/ac_store/declared_files.py
GOAL: The single read seam for an AC record's `declared_files` field --
    "the files this piece of work changes" -- so every consumer (the
    commit-time schema hook, the agent-side validator, the implementation-
    readiness gate, the ticket generator, the requirement rule check, the
    file-aware pre-pass) reads the same answer from the same place, never
    re-deriving it from doc_links, it_requirements prose, or reference_file_path.
BUSINESS CONTEXT: ACD-1600c-4 (+ -4-i/-ii/-iii/-iv). Before this module, "which
    files does this work change" had no single answer -- doc_links entries
    tagged 'describes' were sometimes counted as files-to-change and files
    actually touched by the work could be missing entirely when their link
    was tagged 'describes' instead of 'modifies' (KI-ACS-002). `declared_files`
    is a new, OPTIONAL top-level AC field: a list of {path, state} objects,
    state in {"existing", "to_be_created"}, in declared order. Absence of the
    field is the named state "no declared files" -- never a violation
    (ADR-026 safety rule 4: absence is never a violation; migration is purely
    additive).
ARCHITECTURE: Four families of pure, side-effect-free functions:
      (1) get_declared_files / NoDeclaredFiles / NOT_EVALUATED_LABEL --
          the read accessor and its named "not present" state.
      (2) declared_files_shape_errors, plus path_form_errors /
          load_build_definition (imported from sibling
          _declared_files_path_form.py -- structural and lexical refusals
          the JSON Schema cannot express: empty list here; non-repo-relative
          paths, regenerated-copy roots, and non-canonical spellings there;
          see that module's own docstring).
      (3) existence_messages -- the existence-vs-marker rule (ACD-1600c-4-i),
          extended by the finished-work exemption (ACD-1600c-4-iv): an
          'existing' entry absent from the tree is a refusal UNLESS the
          record is finished (work_status == 'done'); a 'to_be_created' entry
          already present is a non-blocking report, also exempted once
          finished.
      (4) store_wide_report / main -- the read-only, deterministic,
          command-line-exposed store-wide report: which records carry no
          declared files, and which finished records declare an 'existing'
          file that has since been deleted (never a refusal, always
          informational -- ACD-1600c-4-iv).
    `declared_files_commit_messages` composes (2) and (3) into the single
    (refusals, reports) pair the commit-time hook and the agent-side
    validator both call, so the two enforcement points cannot diverge
    (ACD-1600c-4 it_requirements: "implemented once, in the seam, and
    invoked by both -- neither re-implements them").

    Canonical source is directly at scripts/ac_store/ (tracked in git; no
    templates/ counterpart) -- this tooling operates on THIS repository's own
    AC store, mirroring scan_ac_store.py and validate_ac_schema.py. It is
    listed in build_phases_ac_store.AC_STORE_DEPLOY_MAP so the build's own
    dependency-closure guard can see the commit hook's import of it
    (ADR-026 safety rule 2: deploy-manifest-first).

DECISION HISTORY:
  - 2026-09-28 [python-coder/ACD-1600c-4]: Created. One seam for
    declared_files reads, structural/lexical refusals, the existence-vs-
    marker rule and its finished-work exemption, and the store-wide report.
  - 2026-09-28 [python-coder/ACD-1600c-4]: load_build_definition() now
    reads build_helpers.shim_map first (the build's real in-code
    regenerated-root table), falling back to the .gitignore-derived list
    only when scripts/build_helpers.py cannot be imported (a deployed
    consumer install never ships that build-engine file).
  - 2026-09-28 [python-coder/ACD-1600c-4]: H-1 review-finding fix (raw
    `startswith` let a leading './' or case-varied spelling of a regenerated
    root escape the refusal) landed alongside moving path_form_errors,
    load_build_definition, and their helpers out to sibling
    _declared_files_path_form.py, to stay under the check-file-size ratchet.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

from yaml_safe_loader import get_safe_yaml_loader

from _declared_files_path_form import load_build_definition, path_form_errors  # noqa: E402,F401

# scripts/ac_store/declared_files.py -> repo root is two parents up.
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent

_VALID_STATES = {"existing", "to_be_created"}

NOT_EVALUATED_LABEL = "not evaluated: no declared files"


class NoDeclaredFiles:
    """Sentinel: the record carries no `declared_files` list at all.

    The ONE named state a reader gets back instead of a list -- never an
    empty list, never a fallback derived from doc_links.
    """

    def __str__(self) -> str:
        """The exact phrase readers and messages use: "no declared files"."""
        return "no declared files"

    def __repr__(self) -> str:
        """Debug repr -- carries no record data, so it never leaks a path."""
        return "NoDeclaredFiles()"


NO_DECLARED_FILES = NoDeclaredFiles()


# ---------------------------------------------------------------------------
# (1) Read accessor
# ---------------------------------------------------------------------------


def get_declared_files(record: dict[str, Any]) -> list[dict[str, Any]] | NoDeclaredFiles:
    """Return the record's declared files, verbatim and in declared order.

    Args:
        record: Parsed AC YAML content.

    Returns:
        NO_DECLARED_FILES when the `declared_files` key is absent or the
        value is not a non-empty list; otherwise the raw declared entries,
        unmodified, in declared order.
    """
    if "declared_files" not in record:
        return NO_DECLARED_FILES
    value = record["declared_files"]
    if not isinstance(value, list) or len(value) == 0:
        return NO_DECLARED_FILES
    return value


# ---------------------------------------------------------------------------
# (2) Structural / lexical refusals the JSON Schema cannot express
# ---------------------------------------------------------------------------


def declared_files_shape_errors(
    record_id: str, declared_files_value: Any
) -> list[str]:
    """Structural/semantic errors on the RAW declared_files value.

    Independent of the filesystem. An empty list is refused (a requirement
    with no files to declare leaves the list out, per ACD-1600c-4-ii); an
    entry missing 'path' or carrying an unrecognised 'state' is refused,
    one message per offending entry.

    Args:
        record_id: The AC id, for message attribution.
        declared_files_value: The raw `declared_files` field value.

    Returns:
        One message per violation; empty when the value is well-formed.
    """
    if not isinstance(declared_files_value, list):
        return [f"{record_id}: declared_files must be a list of {{path, state}} entries."]

    if len(declared_files_value) == 0:
        return [
            f"{record_id}: declared_files is an empty list -- a requirement "
            "with no files to declare leaves the list out rather than "
            "declaring it empty."
        ]

    errors: list[str] = []
    for entry in declared_files_value:
        if not isinstance(entry, dict) or not entry.get("path"):
            errors.append(
                f"{record_id}: declared_files entry {entry!r} is missing 'path'."
            )
            continue
        state = entry.get("state")
        if state not in _VALID_STATES:
            errors.append(
                f"{record_id}: declared_files entry for '{entry['path']}' has "
                f"unknown state {state!r}; must be 'existing' or 'to_be_created'."
            )
    return errors


# ---------------------------------------------------------------------------
# (3) Existence-vs-marker rule, with the finished-work exemption
# ---------------------------------------------------------------------------


def existence_messages(
    record: dict[str, Any], repo_root: Path
) -> tuple[list[str], list[str]]:
    """(refusals, reports) for the existence-vs-marker rule.

    An 'existing' entry absent from repo_root's tree is a refusal UNLESS the
    record's work_status == 'done' (then neither refused nor reported --
    ACD-1600c-4-iv). A 'to_be_created' entry already present is a
    non-blocking report, also exempted once finished (ACD-1600c-4-i).

    Args:
        record: Parsed AC YAML content (reads `id`, `work_status`,
            `declared_files`).
        repo_root: Repository root the declared paths are checked against.

    Returns:
        `(refusals, reports)`; reports never block a commit.
    """
    record_id = record.get("id", "?")
    finished = record.get("work_status") == "done"
    declared = record.get("declared_files")
    refusals: list[str] = []
    reports: list[str] = []
    if not isinstance(declared, list):
        return refusals, reports

    for entry in declared:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        state = entry.get("state")
        if not path or state not in _VALID_STATES:
            continue  # Reported by declared_files_shape_errors already.
        exists = (Path(repo_root) / path).exists()
        if state == "existing" and not exists:
            if finished:
                continue
            refusals.append(
                f"{record_id}: declared path '{path}' is neither present "
                "nor marked to be created."
            )
        elif state == "to_be_created" and exists:
            if finished:
                continue
            reports.append(
                f"{record_id}: declared path '{path}' is marked to be "
                "created but already exists."
            )
    return refusals, reports


def _finished_absent_existing_paths(record: dict[str, Any], repo_root: Path) -> list[str]:
    """Declared 'existing' paths of a FINISHED record now absent from the tree.

    The ACD-1600c-4-iv store-wide report entries: never a refusal, never a
    warning at commit time -- informational only.
    """
    if record.get("work_status") != "done":
        return []
    declared = record.get("declared_files")
    if not isinstance(declared, list):
        return []
    paths: list[str] = []
    for entry in declared:
        if not isinstance(entry, dict):
            continue
        path = entry.get("path")
        state = entry.get("state")
        if path and state == "existing" and not (Path(repo_root) / path).exists():
            paths.append(path)
    return paths


def declared_files_commit_messages(
    record: dict[str, Any], repo_root: Path
) -> tuple[list[str], list[str]]:
    """(refusals, reports) combining shape, path-form and existence checks.

    The ONE call the commit-time hook (check_ac_schema.py, both its
    jsonschema and manual-fallback branches) and the agent-side validator
    (validate_ac_schema.py) each make, so the declared_files rule set is
    enforced identically at both points and neither re-implements it
    (ACD-1600c-4 it_requirements).

    Args:
        record: Parsed AC YAML content.
        repo_root: Repository root the declared paths are checked against.

    Returns:
        `(refusals, reports)`; reports never block a commit. Absence of
        `declared_files` is never a violation -- returns `([], [])`.
    """
    if "declared_files" not in record:
        return [], []
    record_id = record.get("id", "?")
    declared = record["declared_files"]

    refusals = list(declared_files_shape_errors(record_id, declared))
    if not isinstance(declared, list) or not declared:
        return refusals, []

    refusals.extend(path_form_errors(record_id, declared))
    existence_refusals, reports = existence_messages(record, repo_root)
    refusals.extend(existence_refusals)
    return refusals, reports


# ---------------------------------------------------------------------------
# (4) Store-wide report
# ---------------------------------------------------------------------------


def _load_store_records(store_root: Path) -> list[tuple[str, dict[str, Any]]]:
    """Every (id, parsed record) pair under store_root, sorted by id."""
    files = sorted(
        p
        for p in (*store_root.rglob("*.yaml"), *store_root.rglob("*.yml"))
        if p.is_file() and p.name != "index.yaml"
    )
    records: list[tuple[str, dict[str, Any]]] = []
    for path in files:
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            print(f"declared_files: WARNING: cannot read {path}: {exc}", file=sys.stderr)
            continue
        try:
            data = yaml.load(content, Loader=get_safe_yaml_loader())
        except yaml.YAMLError as exc:
            print(f"declared_files: WARNING: cannot parse {path}: {exc}", file=sys.stderr)
            continue
        if isinstance(data, dict) and data.get("id"):
            records.append((str(data["id"]), data))
    records.sort(key=lambda pair: pair[0])
    return records


def store_wide_report(store_root: Path, repo_root: Path) -> str:
    """Deterministic, read-only text report over the whole AC store.

    Two sections: records in the "no declared files" state (sorted by id,
    with a total), and finished records whose declared 'existing' file is
    now absent from the tree (sorted by record id then declared order, with
    a total, ACD-1600c-4-iv) -- followed by the count of records scanned.
    Never writes to any record; byte-identical across repeated calls on the
    same store and tree.

    Args:
        store_root: Directory to scan recursively for AC YAML files.
        repo_root: Repository root declared paths are checked against.

    Returns:
        The report text.
    """
    store_root = Path(store_root)
    repo_root = Path(repo_root)
    records = _load_store_records(store_root)

    no_declared_ids = [
        record_id
        for record_id, data in records
        if isinstance(get_declared_files(data), NoDeclaredFiles)
    ]

    finished_absent: list[tuple[str, str]] = [
        (record_id, path)
        for record_id, data in records
        for path in _finished_absent_existing_paths(data, repo_root)
    ]

    lines: list[str] = ["Declared-files store-wide report", ""]
    lines.append("no declared files:")
    for record_id in no_declared_ids:
        lines.append(f"  {record_id}: {NOT_EVALUATED_LABEL}")
    lines.append(f"  total: {len(no_declared_ids)}")
    lines.append("")
    lines.append("declared existing, now absent (work finished):")
    for record_id, path in finished_absent:
        lines.append(f"  {record_id}: {path} -- declared existing, now absent (work finished)")
    lines.append(f"  total: {len(finished_absent)}")
    lines.append("")
    lines.append(f"records scanned: {len(records)}")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    """CLI entry point exposing `store_wide_report`.

    Usage: `declared_files.py --report <store_root> [--repo-root <root>]`.
    Always exits 0 -- the report is informational and never blocks.

    Args:
        argv: Argument list; defaults to `sys.argv[1:]`.

    Returns:
        0, always.
    """
    args = list(argv) if argv is not None else sys.argv[1:]
    store_arg: str | None = None
    repo_root_arg: str | None = None
    i = 0
    while i < len(args):
        if args[i] == "--report" and i + 1 < len(args):
            store_arg = args[i + 1]
            i += 2
        elif args[i] == "--repo-root" and i + 1 < len(args):
            repo_root_arg = args[i + 1]
            i += 2
        else:
            i += 1

    if store_arg:
        repo_root = Path(repo_root_arg) if repo_root_arg else Path.cwd()
        try:
            print(store_wide_report(Path(store_arg), repo_root))
        except OSError as exc:
            print(f"declared_files: report failed: {exc}", file=sys.stderr)
    else:
        print(
            "Usage: declared_files.py --report <store_root> [--repo-root <root>]",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
