"""
MODULE: _remedy_registration_parity
GOAL: The GE-132a-1 rule hosted by check-hook-parity: every registered check that
    can refuse a commit has a remedy declaration or is on an excused list that
    only shrinks, and no declaration exists for a check that is not registered.
BUSINESS CONTEXT: A refusal with no declared remedy leaves the author guessing
    what happens next. This leg stops a new check arriving without one, stops the
    excused list (the checks that had none when the rule landed) from growing, and
    stops a declaration outliving the check it describes.
ARCHITECTURE: Population is derived from the canonical manifest at run time:
    hooks_manifest members whose tier is ``judgment`` and whose stages include
    ``pre-commit``. Declarations come from the shared loader
    (``_remedy_declarations``), local table first, package seed per missing hook.
    The excused list is ``hook_parity.undeclared_remedy_baseline`` in the canonical
    manifest; the ratchet compares it with the list in HEAD and in every
    MERGE_HEAD parent. FAIL CLOSED: any unreadable or malformed input raises
    ``RemedyInputError``, which the caller reports as could-not-check (never a
    pass, never "no declaration").
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import _remedy_declaration_validity
import check_outcome
from _remedy_declarations import RemedyInputError, declared_view, load_tables

_GIT_TIMEOUT = 30


def _read_manifest(path: Path) -> dict:
    """Parse the canonical manifest strictly.

    Args:
        path: Canonical commit_guardian.json.

    Returns:
        The parsed manifest dict.

    Raises:
        RemedyInputError: Unreadable, not JSON, or not an object.
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        msg = f"cannot read or parse manifest {path}: {exc}"
        raise RemedyInputError(msg) from exc
    if not isinstance(data, dict):
        msg = f"manifest {path} is not a JSON object"
        raise RemedyInputError(msg)
    return data


def _hooks(manifest: dict, path: Path) -> list[dict]:
    """Return hooks_manifest.hooks, validated.

    Args:
        manifest: Parsed manifest.
        path: Where it came from (for messages).

    Returns:
        The hook dicts.

    Raises:
        RemedyInputError: hooks_manifest.hooks is missing or malformed.
    """
    block = manifest.get("hooks_manifest")
    hooks = block.get("hooks") if isinstance(block, dict) else None
    if not isinstance(hooks, list) or not all(isinstance(h, dict) and isinstance(h.get("id"), str) for h in hooks):
        msg = f"manifest {path} has no valid hooks_manifest.hooks list"
        raise RemedyInputError(msg)
    return hooks


def _excused_of(manifest: dict, where: str, *, required: bool) -> set[str] | None:
    """Return the excused list of one manifest revision.

    Args:
        manifest: Parsed manifest.
        where: Label for messages.
        required: When False an absent key yields None (list never seeded there).

    Returns:
        The excused ids, or None when absent and not required.

    Raises:
        RemedyInputError: The key holds something other than a list of strings.
    """
    section = manifest.get("hook_parity")
    raw = section.get("undeclared_remedy_baseline") if isinstance(section, dict) else None
    if raw is None:
        return set() if required else None
    if not isinstance(raw, list) or not all(isinstance(i, str) for i in raw):
        msg = f"excused list undeclared_remedy_baseline in {where} is not a list of check ids"
        raise RemedyInputError(msg)
    return set(raw)


def _git(args: list[str]) -> subprocess.CompletedProcess:
    """Run git and return the completed process.

    Args:
        args: Arguments after ``git``.

    Returns:
        The completed process (non-zero exit codes are not raised).

    Raises:
        RemedyInputError: git could not be run at all.
    """
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=_GIT_TIMEOUT, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        msg = f"cannot run git {' '.join(args)}: {exc}"
        raise RemedyInputError(msg) from exc


def _parent_revisions() -> list[str]:
    """Return HEAD plus every MERGE_HEAD line (an unborn HEAD yields none).

    Returns:
        Parent revision SHAs for the ratchet comparison.

    Raises:
        RemedyInputError: git or the MERGE_HEAD file cannot be read.
    """
    revisions: list[str] = []
    head = _git(["rev-parse", "--verify", "-q", "HEAD"])
    if head.returncode == 0 and head.stdout.strip():
        revisions.append(head.stdout.strip())
    located = _git(["rev-parse", "--git-path", "MERGE_HEAD"])
    merge_head = Path(located.stdout.strip()) if located.returncode == 0 and located.stdout.strip() else None
    if merge_head is not None and merge_head.is_file():
        try:
            lines = merge_head.read_text(encoding="utf-8").splitlines()
        except (OSError, ValueError) as exc:
            msg = f"cannot read {merge_head}: {exc}"
            raise RemedyInputError(msg) from exc
        revisions.extend(line.strip() for line in lines if line.strip())
    return revisions


def _parent_excused(rel_path: str) -> list[set[str]]:
    """Return the excused list found in each parent revision that carries one.

    Args:
        rel_path: Repo-relative posix path of the canonical manifest.

    Returns:
        One id set per parent whose committed manifest holds the list.

    Raises:
        RemedyInputError: A parent's manifest or list is unreadable.
    """
    found: list[set[str]] = []
    for revision in _parent_revisions():
        shown = _git(["show", f"{revision}:{rel_path}"])
        if shown.returncode != 0:
            continue  # file absent at that revision: it supplies no list
        try:
            manifest = json.loads(shown.stdout)
        except ValueError as exc:
            msg = f"manifest {rel_path} at {revision[:12]} is not valid JSON: {exc}"
            raise RemedyInputError(msg) from exc
        if not isinstance(manifest, dict):
            msg = f"manifest {rel_path} at {revision[:12]} is not a JSON object"
            raise RemedyInputError(msg)
        excused = _excused_of(manifest, f"{rel_path} at {revision[:12]}", required=False)
        if excused is not None:
            found.append(excused)
    return found


def _repo_rel(path: Path, root: Path) -> str:
    """Return ``path`` relative to ``root`` in posix form (or as given if outside).

    Args:
        path: Absolute or relative path.
        root: Project root.

    Returns:
        Posix-style relative path.
    """
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def _ratchet_violations(manifest: dict, excused: set[str], canonical_manifest: Path, root: Path) -> list[str]:
    """Judge the excused-list ratchet against HEAD and every MERGE_HEAD parent.

    The ratchet is skipped only for the seeding commit (no parent has ever carried
    the list). Once any parent carries it, the staged manifest must too: an empty
    list is allowed, a missing key is not (else delete-then-re-add launders entries).

    Args:
        manifest: Parsed staged canonical manifest.
        excused: The staged excused ids (empty when the key is absent).
        canonical_manifest: Canonical commit_guardian.json (for messages).
        root: Project root.

    Returns:
        Refusal strings; empty when the ratchet holds.

    Raises:
        RemedyInputError: A parent's manifest or list is unreadable.
    """
    parents = _parent_excused(_repo_rel(canonical_manifest, root))
    if not parents:
        return []
    if _excused_of(manifest, str(canonical_manifest), required=False) is None:
        return [
            f"  The excused list (hook_parity.undeclared_remedy_baseline) was removed from "
            f"{canonical_manifest}. A parent revision carries it; the list may lose entries "
            f"and never be dropped.\n"
            f"  Fix: restore hook_parity.undeclared_remedy_baseline (an empty list is allowed)."
        ]
    return [
        f"  Check '{hook_id}' was added to the excused list "
        f"(hook_parity.undeclared_remedy_baseline in {canonical_manifest}). The excused "
        f"list may lose entries and never gain one.\n"
        f"  Fix: remove '{hook_id}' from the excused list and give it a remedy declaration."
        for hook_id in sorted(excused - set().union(*parents))
    ]


def check_remedy_declarations(canonical_manifest: Path, root: Path) -> list[str]:
    """Judge the three GE-132a-1 reasons and return one refusal line group per finding.

    Args:
        canonical_manifest: Canonical commit_guardian.json (the file being committed).
        root: Project root (the process cwd).

    Returns:
        Human-readable refusal strings; empty when every rule holds.

    Raises:
        RemedyInputError: Any input is unreadable or malformed (could-not-check).
    """
    if not canonical_manifest.is_file():
        # Consumer layout: no package registry here, so the leg is not applicable.
        print(
            f"check-hook-parity: remedy-declaration check not applicable: canonical manifest "
            f"{canonical_manifest} is absent.",
            file=sys.stderr,
        )
        return []
    manifest = _read_manifest(canonical_manifest)
    if not isinstance(manifest.get("hooks_manifest"), dict):
        msg = f"manifest {canonical_manifest} has no hooks_manifest object"
        raise RemedyInputError(msg)
    hooks = _hooks(manifest, canonical_manifest)
    registered = {h["id"] for h in hooks}
    gating = {h["id"] for h in hooks if h.get("tier") == "judgment" and "pre-commit" in (h.get("stages") or [])}
    tables = load_tables(root)
    declared = declared_view(tables)
    excused = _excused_of(manifest, str(canonical_manifest), required=True) or set()
    violations: list[str] = []

    for hook_id in sorted(gating - set(declared) - excused):
        violations.append(
            f"  Check '{hook_id}' is registered in {canonical_manifest} with no remedy "
            f"declaration. A check needs a remedy declaration before it can be registered.\n"
            f"  Fix: add a rule with a disposition for '{hook_id}' to templates/scripts/precommit-autofix.json."
        )

    violations.extend(_ratchet_violations(manifest, excused, canonical_manifest, root))

    for path, rules in tables:
        for rule in rules:
            if rule.get("disposition") and rule["hook_id"] not in registered:
                violations.append(
                    f"  Remedy declaration for '{rule['hook_id']}' (from {path}) is a declaration "
                    f"for a check that is not registered in {canonical_manifest}.\n"
                    f"  Fix: remove the declaration or register the check."
                )
    # GE-132a-2: every declaration is valid (disposition, instruction, real agent and skills).
    violations.extend(_remedy_declaration_validity.validate(declared, manifest, canonical_manifest, root))
    return violations


def run_leg(canonical_manifest: Path, root: Path) -> tuple[list[str], str | None]:
    """Run the leg, converting unreadable input into a could-not-check reason.

    Args:
        canonical_manifest: Canonical commit_guardian.json.
        root: Project root.

    Returns:
        ``(violations, could_not_check_reason)``; the reason is None when every
        input was readable.
    """
    try:
        return check_remedy_declarations(canonical_manifest, root), None
    except RemedyInputError as exc:
        return [], str(exc)


def report(violations: list[str], could_not_check: str | None) -> int:
    """Print the verdict to stderr/stdout and return the hook exit code.

    Args:
        violations: All parity violations found by every leg.
        could_not_check: Reason the remedy leg could not run, or None.

    Returns:
        1 when any violation was found, 2 when only could-not-check applies
        (GE-120 outcome vocabulary, never a pass), otherwise 0.
    """
    if violations:
        print("\n[check-hook-parity] BLOCKED — hook parity violations detected:\n", file=sys.stderr)
        for violation in violations:
            print(violation, file=sys.stderr)
        print(
            "\nFix: Ensure hook scripts and manifest entries are present in all "
            "required locations before committing.\n",
            file=sys.stderr,
        )
    if could_not_check is not None:
        check_outcome.emit_result(check_outcome.OUTCOME_COULD_NOT_CHECK)
        print(
            f"\n[check-hook-parity] could not check remedy declarations: {could_not_check}\n"
            "A remedy-declaration input is unreadable; this is not a pass.",
            file=sys.stderr,
        )
    if violations:
        return 1
    return 2 if could_not_check is not None else 0
