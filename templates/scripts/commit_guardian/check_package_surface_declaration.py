"""
MODULE: check_package_surface_declaration
GOAL: Commit-time gate (ACS-100i-8 / ACS-100i-8-i) refusing a change that adds a
    NEW entry to a package registry unless at least one acceptance criterion the
    change cites carries `package_surface: true`.
BUSINESS CONTEXT: ACS-100i-6 keyed the structured-implementation-spec obligation
    off an explicit declaration instead of the `assigned_agent` + `component`
    proxy that KI-ACS-005 measured as both over- and under-matching. That
    narrowing has one hole: an author who registers a package surface and simply
    omits `package_surface: true` escapes the obligation, and nothing in the
    record contradicts them — the record is a statement of intent, and intent is
    what the author controls. The signal NOT under their control is the
    registration itself. A package surface exists because an entry appears in a
    registry the build reads; that entry is in the diff, it is enumerable, and it
    cannot be omitted without failing to ship the feature. So this check runs
    against the registration and reconciles it against the declaration.

    CONCESSION 1 (recorded on ACS-100i-8): detection moves from authoring time to
    landing time. What survives is the guarantee that a surface cannot reach a
    consumer undeclared.

ARCHITECTURE: Invoked as `python check_package_surface_declaration.py
    <commit_msg_file>` with the working directory inside the committing repo, so
    it is a `commit-msg`-stage hook. Staged files come from a real
    `git diff --cached --name-only --diff-filter=AM`; the staged and HEAD
    revisions of each watched registry are read with `git show`, and a NEW entry
    is a key present in the staged document and absent from HEAD. Citations are
    parsed from the commit-message file and from any staged ticket body in the
    same commit. The watched-registry enumeration and every pure helper live in
    _package_surface_registry.py, deployed alongside this file.

    Exit 0 = allowed; exit 1 = refused. A change touching no watched registry, or
    touching one without adding an entry, exits 0 and says it had NOTHING TO
    EVALUATE — reporting a pass for an examination that never happened is the
    KI-ACS-001 failure mode and would make this gate unfalsifiable.

    Fail-open: an unexpected error prints a diagnostic and exits 0, so a defect
    in the gate can never block every commit.

DOC_LINKS:
  - docs/reference/ac-schema.md

DECISION HISTORY:
  - 2026-08-19 [python-coder/ACS-100i-8]: Created alongside the ACS-100i-6
    trigger narrowing. Registration-versus-declaration reconciliation, with
    omission and denial reported as the different acts they are (ACS-100i-8-i).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from _package_surface_registry import (
    WATCHED_REGISTRIES,
    extract_ac_citations,
    find_ac_record,
    parse_registry_document,
    read_declaration,
    registry_entry_keys,
)

_HOOK_PREFIX = "[check-package-surface-declaration]"
_AC_STORE_DIR = "docs/acceptance-criteria"
_TICKET_SUFFIX = ".md"
_TICKET_DIR = "tickets/"


def _git(repo: Path, *args: str) -> tuple[int, str]:
    """Run a git command inside ``repo``.

    Args:
        repo: Repository root to run in.
        *args: Git arguments after ``git -C <repo>``.

    Returns:
        ``(returncode, stdout)``. A git failure yields ``(1, "")`` rather than
        raising, so the caller can treat it as "no content at that revision".
    """
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo), *args],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (subprocess.SubprocessError, OSError) as exc:
        print(f"{_HOOK_PREFIX} WARNING: git {args[0]} failed: {exc}", file=sys.stderr)
        return 1, ""
    return proc.returncode, proc.stdout


def _repo_root() -> Path:
    """Return the committing repository's root directory.

    Returns:
        The path reported by ``git rev-parse --show-toplevel``, falling back to
        the current working directory when git cannot answer.
    """
    code, out = _git(Path.cwd(), "rev-parse", "--show-toplevel")
    if code == 0 and out.strip():
        return Path(out.strip())
    return Path.cwd()


def _staged_paths(repo: Path) -> list[str]:
    """Return the repo-relative paths added or modified in the index.

    Args:
        repo: Repository root.

    Returns:
        Repo-relative path strings; empty when git cannot be read.
    """
    code, out = _git(repo, "diff", "--cached", "--name-only", "--diff-filter=AM")
    if code != 0:
        return []
    return [line.strip() for line in out.splitlines() if line.strip()]


def _blob(repo: Path, revision_spec: str) -> str | None:
    """Return the content of a git blob, or None when it does not exist.

    Args:
        repo: Repository root.
        revision_spec: A ``git show`` spec such as ``:path`` (index) or
            ``HEAD:path``.

    Returns:
        The blob text, or None.
    """
    code, out = _git(repo, "show", revision_spec)
    return out if code == 0 else None


def _new_entries(repo: Path, rel_path: str) -> list[str]:
    """Return the entry keys ``rel_path`` gains between HEAD and the index.

    Args:
        repo: Repository root.
        rel_path: Repo-relative path of a watched registry.

    Returns:
        Sorted keys present in the staged document and absent from HEAD. An
        edited or removed entry produces none — the obligation attaches to
        bringing a surface into existence, not to maintaining one.
    """
    containers = WATCHED_REGISTRIES[rel_path]
    staged = registry_entry_keys(
        parse_registry_document(_blob(repo, f":{rel_path}")), containers
    )
    head = registry_entry_keys(
        parse_registry_document(_blob(repo, f"HEAD:{rel_path}")), containers
    )
    return sorted(staged - head)


def _citations(repo: Path, commit_msg_file: Path, staged: list[str]) -> list[str]:
    """Return the acceptance-criterion ids this change cites.

    Args:
        repo: Repository root.
        commit_msg_file: The file holding the commit message being written.
        staged: Repo-relative staged paths, scanned for ticket bodies.

    Returns:
        De-duplicated ids in first-seen order.
    """
    texts: list[str] = []
    try:
        texts.append(commit_msg_file.read_text(encoding="utf-8"))
    except OSError as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read commit message "
            f"{commit_msg_file}: {exc}",
            file=sys.stderr,
        )

    for rel_path in staged:
        if rel_path.endswith(_TICKET_SUFFIX) and _TICKET_DIR in rel_path:
            body = _blob(repo, f":{rel_path}")
            if body:
                texts.append(body)

    return extract_ac_citations(*texts)


def _classify(repo: Path, cited: list[str]) -> tuple[list[str], list[str]]:
    """Split cited ids into those declaring a surface and those denying one.

    Args:
        repo: Repository root.
        cited: Acceptance-criterion ids the change cites.

    Returns:
        ``(declaring, denying)`` — ids whose record carries
        ``package_surface: true`` and ids whose record carries
        ``package_surface: false``. Ids that made no declaration, and ids that
        resolve to no record at all, appear in neither list.
    """
    store_dir = repo / _AC_STORE_DIR
    declaring: list[str] = []
    denying: list[str] = []
    for ac_id in cited:
        record = find_ac_record(store_dir, ac_id)
        if record is None:
            continue
        declaration = read_declaration(record)
        if declaration is True:
            declaring.append(ac_id)
        elif declaration is False:
            denying.append(ac_id)
    return declaring, denying


def _entry_lines(additions: dict[str, list[str]]) -> list[str]:
    """Render one report line per registry naming the entries it gains.

    Args:
        additions: Registry rel-path to the entry keys it adds.

    Returns:
        Report lines.
    """
    return [
        f"  {rel_path}: new entry {', '.join(repr(k) for k in keys)}"
        for rel_path, keys in sorted(additions.items())
    ]


def _refuse(additions: dict[str, list[str]], cited: list[str], denying: list[str]) -> int:
    """Print the refusal that fits what was actually seen, and return 1.

    Three refusals, deliberately distinct. Citing nothing is the free path an
    undeclared surface would take; citing a record that DENIES the surface is a
    contradiction between the record and the change, and a reviewer needs to
    read it as one rather than as an oversight; citing records that simply made
    no declaration is the ordinary omission.

    Args:
        additions: Registry rel-path to the entry keys it adds.
        cited: Every acceptance-criterion id the change cited.
        denying: The subset whose record carries ``package_surface: false``.

    Returns:
        1, always — this function is only reached on a refusal.
    """
    lines: list[str]
    if not cited:
        lines = [
            f"{_HOOK_PREFIX} REFUSED: a change that adds a package-registry entry "
            "must cite the acceptance criterion that declares it.",
            *_entry_lines(additions),
            "  This commit cited no acceptance criterion, in its message or in any "
            "staged ticket.",
            "  Author the criterion with `package_surface: true` and cite its id in "
            "the commit message.",
        ]
    elif denying:
        lines = [
            f"{_HOOK_PREFIX} REFUSED: a cited acceptance criterion denies registering "
            "a package surface while this change adds one — a contradiction between "
            "the record and the change.",
            *_entry_lines(additions),
            *(f"  {ac_id} declares package_surface: false" for ac_id in denying),
            *(
                f"  {ac_id} made no declaration"
                for ac_id in cited
                if ac_id not in denying
            ),
            "  Either correct the record to `package_surface: true`, or drop the "
            "registry entry.",
        ]
    else:
        lines = [
            f"{_HOOK_PREFIX} REFUSED: this change adds a package-registry entry, but "
            "none of the acceptance criteria it cites declares a package surface.",
            *_entry_lines(additions),
            f"  cited: {', '.join(cited)}",
            "  Set `package_surface: true` on the criterion that registers this "
            "surface, then re-commit.",
        ]

    for line in lines:
        print(line, file=sys.stderr)
    return 1


def _is_enabled() -> bool:
    """Return whether the gate is switched on in commit_guardian.json.

    Returns:
        The ``package_surface_declaration.enabled`` flag, defaulting to True.
        A config that cannot be read leaves the gate ON: a check that silently
        disables itself when its own configuration is unreadable is the failure
        mode this whole tree exists to prevent.
    """
    try:
        from config import load_config  # noqa: PLC0415

        section = load_config().get("package_surface_declaration", {})
    except (ImportError, OSError, ValueError) as exc:
        print(
            f"{_HOOK_PREFIX} WARNING: cannot read hook configuration ({exc}); "
            "the gate stays enabled.",
            file=sys.stderr,
        )
        return True
    return bool(section.get("enabled", True)) if isinstance(section, dict) else True


def _nothing_to_evaluate(touched: list[str]) -> int:
    """Report that the check examined no registration, and return 0.

    A check that reports a pass when it examined nothing is the KI-ACS-001
    failure mode, and it would make ACS-100i-8 unfalsifiable. The wording, not
    the exit code, is what carries the distinction here.

    Args:
        touched: Watched registries the change touched without adding an entry.

    Returns:
        0.
    """
    if touched:
        detail = (
            f"{', '.join(touched)} changed, but no new entry was added — the "
            "obligation attaches to bringing a surface into existence, not to "
            "maintaining one."
        )
    else:
        detail = "this change touches no watched package registry."
    print(f"{_HOOK_PREFIX} nothing to evaluate: {detail}")
    return 0


def main(argv: list[str] | None = None) -> int:
    """Reconcile the package-registry entries a change adds against its citations.

    Args:
        argv: Arguments after the script name; defaults to ``sys.argv[1:]``. The
            first entry is the commit-message file, as a ``commit-msg``-stage
            hook receives it.

    Returns:
        0 when allowed or when there was nothing to evaluate; 1 when refused.
    """
    args = argv if argv is not None else sys.argv[1:]
    if not args:
        print(
            f"{_HOOK_PREFIX} usage: check_package_surface_declaration.py "
            "<commit_msg_file>",
            file=sys.stderr,
        )
        return 1

    if os.environ.get("HOOK_NO_GIT"):
        return _nothing_to_evaluate([])

    repo = _repo_root()
    staged = _staged_paths(repo)
    touched = [p for p in staged if p in WATCHED_REGISTRIES]

    additions = {p: keys for p in touched if (keys := _new_entries(repo, p))}
    if not additions:
        return _nothing_to_evaluate(touched)

    cited = _citations(repo, Path(args[0]), staged)
    declaring, denying = _classify(repo, cited)

    if declaring:
        entries = ", ".join(k for keys in additions.values() for k in keys)
        registries = ", ".join(sorted(additions))
        print(
            f"{_HOOK_PREFIX} allowed: {registries} adds {entries}; declared by "
            f"{', '.join(declaring)}."
        )
        return 0

    return _refuse(additions, cited, denying)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(
            f"{_HOOK_PREFIX} unexpected error, skipping: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        sys.exit(0)
