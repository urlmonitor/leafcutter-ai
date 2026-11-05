"""
MODULE: worktree_identity
GOAL: Decide "which workspace and which line of work is this request for" for
    the workspace maker: the one naming table (with its declared legacy
    spellings), the hub-line resolution, the occupied-location and
    legacy-worktree refusals, and the ticket-location checks (BO-4300a-2,
    BO-4300a-1-ii, BO-4300d-3, BO-4300d-3-i, BO-4300d-4).
BUSINESS CONTEXT: The same piece of work must always map to the same
    workspace, whichever route or spelling asked for it, and a request must
    never abandon, overwrite or silently adopt work that already exists --
    on the hub, at the location, or in an old-style linked worktree.
ARCHITECTURE: Stdlib-only; imports ``worktree_git`` (git boundary),
    ``worktree_answer`` (code table), ``worktree_layout`` (other-project
    occupant), ``worktree_paths`` (path spelling) and ``worktree_remove``
    (the shared whole-folder delete). ``worktree.py`` calls
    ``resolve`` once per request and passes the :class:`Identity` to the
    other functions here. Nothing here writes to the hub or to git's
    worktree administration: legacy registrations are read as plain files.
"""

from __future__ import annotations

import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import worktree_answer as wa
import worktree_git as wg
import worktree_layout as wl
import worktree_paths as wp
import worktree_remove as wrm

_log = logging.getLogger(__name__)

# One scheme for every kind: the line of work is ``<kind>/<slug>``. Each kind
# declares its legacy spellings here (prefix, reason) -- there is no second
# table and no per-caller mapping (Q4, decided 2026-09-28).
LEGACY_ALIASES: dict[str, tuple[tuple[str, str], ...]] = {
    "epic": (("EPIC-", "the feature skill names epic lines EPIC-<Name>"),),
    "ac": (("ac-authoring/", "create-ac-worktree named AC lines ac-authoring/<slug>"),),
    "fastlane": (("fast-lane/", "create-fastlane-worktree named lines fast-lane/<slug>"),),
}


def _check_alias_table() -> None:
    """Refuse a naming table that declares a kind's canonical ``<kind>/`` prefix as any alias (A4)."""
    canonical = {f"{k}/": k for k in wg.VALID_KINDS}
    for kind, aliases in LEGACY_ALIASES.items():
        for prefix, _reason in aliases:
            if prefix in canonical:
                raise ValueError(f"LEGACY_ALIASES[{kind!r}] declares {prefix!r}, which is canonical for "
                                 f"kind {canonical[prefix]!r}")


_check_alias_table()

_CAMEL_BOUNDARY = re.compile(r"(?<=[a-z])(?=[A-Z])")
_SLUG_DISALLOWED = re.compile(r"[^a-z0-9.-]+")
_SLUG_DOTS = re.compile(r"\.{2,}")
_SLUG_EDGE = "-."
SLUG_MAX_LENGTH = 64
_WINDOWS_DEVICES = frozenset({"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)),
                              *(f"lpt{i}" for i in range(1, 10))})


def slugify(text: str) -> str:
    """Return the safe kebab form of *text*: one valid ref segment, or ``""`` when nothing is left (A5).

    Lower-case letters, digits, ``-`` and single ``.``; no leading or trailing
    ``-``/``.``; no ``.lock`` suffix. ``_`` and every other separator become
    ``-``. Non-ASCII letters are dropped (``café`` becomes ``caf``). There is
    no default slug.
    """
    spaced = _CAMEL_BOUNDARY.sub("-", text.strip())
    slug = _SLUG_DOTS.sub(".", _SLUG_DISALLOWED.sub("-", spaced.lower())).rstrip(_SLUG_EDGE)
    while slug.endswith(".lock"):
        slug = slug[: -len(".lock")].rstrip(_SLUG_EDGE)
    return slug.lstrip(_SLUG_EDGE)


def slug_problem(slug: str) -> str | None:
    """Return why a normalised *slug* cannot name a workspace on every OS, else ``None`` (pure).

    Refuses an empty slug, a slug over :data:`SLUG_MAX_LENGTH` characters
    (never truncated: that could merge two identities) and a slug whose name
    part before the first ``.`` is a Windows reserved device name.
    """
    if not slug:
        return "nothing is left of it after normalising (letters, digits, '-' and single '.' only)"
    if len(slug) > SLUG_MAX_LENGTH:
        return f"it is {len(slug)} characters long; the limit is {SLUG_MAX_LENGTH} (it is never truncated)"
    if slug.split(".", 1)[0] in _WINDOWS_DEVICES:
        return f"{slug.split('.', 1)[0]!r} is a reserved device name on Windows and cannot be a folder"
    return None


def _prefixes(kind: str) -> tuple[str, ...]:
    """The canonical prefix first, then the kind's declared legacy prefixes."""
    return (f"{kind}/", *(p for p, _reason in LEGACY_ALIASES.get(kind, ())))


def normalize_slug(raw: str, kind: str | None = None) -> str:
    """Normalise *raw* (a slug, a legacy spelling or a display title) to a slug for *kind*."""
    text = raw.strip()
    for prefix in _prefixes(kind) if kind else ():
        if text.startswith(prefix) and len(text) > len(prefix):
            text = text[len(prefix):]
            break
    return slugify(text)


@dataclass(frozen=True)
class Identity:
    """The canonical identity of one piece of work: ``kind`` and ``slug``."""

    kind: str
    slug: str

    @property
    def branch(self) -> str:
        """The canonical line-of-work name for this identity."""
        return f"{self.kind}/{self.slug}"

    def matches_branch(self, branch: str) -> bool:
        """True when *branch* is the canonical or a declared legacy spelling of this identity (exact)."""
        return any(branch.startswith(p) and len(branch) > len(p) and slugify(branch[len(p):]) == self.slug
                   for p in _prefixes(self.kind))


def resolve(kind: str, raw_slug: str) -> Identity:
    """Return the canonical :class:`Identity` for a request's ``--kind`` and ``--slug``."""
    slug = normalize_slug(raw_slug, kind)
    problem = slug_problem(slug)
    if problem is not None:
        raise wa.UsageError(f"--slug {raw_slug!r} for kind {kind!r} cannot name work: {problem}. "
                            "Nothing was created.")
    return Identity(kind, slug)


# ---------------------------------------------------------------- hub lines

def hub_lines(workspace: Path, ident: Identity) -> list[str]:
    """Return the hub branches of *ident* (any spelling) that hold commits not on origin/main.

    Reads only the clone's ``origin/*`` refs (the hub's), never the main
    checkout's local branches.
    """
    proc = wg.run_git(["for-each-ref", "--format=%(refname)", "refs/remotes/origin"], workspace)
    prefix = "refs/remotes/origin/"
    found = []
    for ref in proc.stdout.split():
        branch = ref[len(prefix):]
        if branch == "HEAD" or not ident.matches_branch(branch):
            continue
        ahead = wg.run_git(["rev-list", "--count", f"origin/main..{ref[len('refs/remotes/'):]}"], workspace)
        if ahead.returncode == 0 and ahead.stdout.strip() not in ("", "0"):
            found.append(branch)
    return sorted(found)


def line_refusal(lines: list[str], ident: Identity) -> dict[str, Any] | None:
    """Return the AMBIGUOUS_LINE refusal when more than one spelling holds a hub line, else ``None``."""
    if len(lines) < 2:
        return None
    return wa.error_answer("AMBIGUOUS_LINE", f"More than one line of work exists on the hub for "
                           f"{ident.branch}: {', '.join(lines)}. Nothing was created or changed; "
                           "merge or delete all but one, then ask again.", lines=lines)


# ----------------------------------------------------- occupied / legacy

def _read_text(path: Path) -> str:
    """Return *path*'s text, or an empty string when unreadable."""
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        _log.warning("_read_text: cannot read %s: %s", path, exc)
        return ""


def _admin_dir(repo_root: Path) -> Path:
    """The main checkout's ``worktrees`` administrative folder (may not exist)."""
    proc = wg.run_git(["rev-parse", "--git-common-dir"], repo_root)
    common = Path(proc.stdout.strip() or ".git")
    return (common if common.is_absolute() else repo_root / common) / "worktrees"


def legacy_registrations(repo_root: Path) -> list[tuple[Path, str]]:
    """Return ``(folder, branch)`` for each linked worktree registered in the main checkout (read-only)."""
    admin = _admin_dir(repo_root)
    if not admin.is_dir():
        return []
    found = []
    for entry in sorted(admin.iterdir()):
        head, gitdir = _read_text(entry / "HEAD"), _read_text(entry / "gitdir")
        if head.startswith("ref: refs/heads/") and gitdir:
            found.append((Path(gitdir).parent, head[len("ref: refs/heads/"):]))
    return found


def _legacy_refusal(folder: Path, branch: str) -> dict[str, Any]:
    """The OCCUPIED_LEGACY_WORKTREE refusal naming the old-style workspace at *folder*."""
    return wa.error_answer(
        "OCCUPIED_LEGACY_WORKTREE",
        f"An old-style workspace for this work exists at {folder} (line of work {branch}); it must be "
        "brought over first. Nothing was created or changed.",
        occupant={"path": str(folder), "kind": "legacy-worktree", "branch": branch})


def _classify_unmarked(location: Path, hub: str) -> dict[str, Any]:
    """Describe the occupant of *location*, which carries no leafcutter marker."""
    occupant: dict[str, Any] = {"path": str(location), "kind": "plain-folder", "branch": None}
    if not (location / ".git").exists():
        return occupant
    origin = wg.origin_url(location)
    branch = wg.run_git(["rev-parse", "--abbrev-ref", "HEAD"], location).stdout.strip() or None
    occupant.update(kind="other-line" if origin and wg.same_location(origin, hub) else "other-project", branch=branch)
    return occupant


def occupied_refusal(repo_root: Path, ident: Identity, location: Path, hub: str) -> dict[str, Any] | None:
    """Return the refusal when *location* or a legacy registration already holds other work, else ``None``.

    A ready workspace of this project at *location* is not an occupant (the
    caller short-circuits on it). The occupant is described, never touched.
    """
    for folder, branch in legacy_registrations(repo_root):
        if ident.matches_branch(branch):
            return _legacy_refusal(folder, branch)
    if not location.exists():
        return None
    marker = wg.read_marker(location)
    if marker is not None:
        other = wl.other_project_occupant(location, marker, repo_root)
        return None if other is None else wa.error_answer(
            "OCCUPIED", f"{location} holds another project's workspace.", occupant=other)
    occ = _classify_unmarked(location, hub)
    return wa.error_answer("OCCUPIED", f"{location} is already occupied ({occ['kind']}) and carries no "
                           "leafcutter workspace marker; it was left untouched.", occupant=occ)


def discard_new_clone(workspace: Path, place: Path) -> None:
    """Remove a clone this request just made (it holds no work) and its emptied kind folder."""
    try:
        reason = wrm.delete_whole_folder(workspace)
        if reason is not None:
            _log.warning("discard_new_clone: %s", reason)
            return
        parent = workspace.parent
        if parent != place and not any(parent.iterdir()):
            parent.rmdir()
    except OSError as exc:
        _log.warning("discard_new_clone: could not clear %s: %s", workspace, exc)


# ------------------------------------------------------------------- tickets

@dataclass(frozen=True)
class TicketRequest:
    """A ``--ticket`` request: the path as given and its project-relative form."""

    arg: str
    rel: Path
    main_copy: Path


def resolve_ticket(arg: str | None, repo_root: Path) -> tuple[TicketRequest | None, dict[str, Any] | None]:
    """Return ``(request, None)``, ``(None, None)`` when no ticket was named, or ``(None, USAGE answer)``."""
    if not arg:
        return None, None
    path = wp.to_native(arg)
    path = path if path.is_absolute() else repo_root / path
    try:
        rel = path.resolve().relative_to(repo_root.resolve())
    except ValueError:
        return None, wa.error_answer("USAGE", f"--ticket {arg!r} lies outside the project {repo_root}; "
                                              "name a ticket inside the project.")
    return TicketRequest(arg, rel, path.resolve()), None


def _lf(data: bytes) -> bytes:
    """Line-ending-neutral form for comparing a ticket's bytes."""
    return data.replace(b"\r\n", b"\n")


def _show_bytes(workspace: Path, ref: str, rel: Path) -> bytes | None:
    """Return the bytes of *rel* at *ref* in *workspace*, or ``None`` when absent there."""
    try:
        proc = subprocess.run(["git", "show", f"{ref}:{rel.as_posix()}"], cwd=str(workspace),
                              capture_output=True, check=False, timeout=60,
                              stdin=subprocess.DEVNULL, env=wg.git_env())
    except (OSError, subprocess.SubprocessError) as exc:
        _log.warning("_show_bytes: git show failed in %s: %s", workspace, exc)
        return None
    return proc.stdout if proc.returncode == 0 else None


def _not_on_base(ticket: TicketRequest, reason: str) -> dict[str, Any]:
    """The TICKET_NOT_ON_BASE refusal for *reason* ('absent' or 'differs')."""
    return wa.error_answer(
        "TICKET_NOT_ON_BASE",
        f"Ticket {ticket.rel.as_posix()} is {'not on' if reason == 'absent' else 'different from the copy on'} "
        "the workspace's base; push it and ask again. Nothing was copied.",
        ticket_path=ticket.arg, reason=reason)


def base_ticket_refusal(workspace: Path, base_ref: str, ticket: TicketRequest) -> dict[str, Any] | None:
    """Refuse when the ticket is absent from *base_ref* or differs from the main copy, else ``None``."""
    on_base = _show_bytes(workspace, base_ref, ticket.rel)
    if on_base is None:
        return _not_on_base(ticket, "absent")
    try:
        main = ticket.main_copy.read_bytes() if ticket.main_copy.is_file() else None
    except OSError as exc:
        _log.warning("base_ticket_refusal: cannot read %s: %s", ticket.main_copy, exc)
        main = None
    return _not_on_base(ticket, "differs") if main is not None and _lf(main) != _lf(on_base) else None


def attach_ticket(answer: dict[str, Any], ticket: TicketRequest | None, workspace: Path) -> dict[str, Any] | None:
    """Add the in-workspace ticket fields to an ok *answer*, or return a refusal when no file is there."""
    if ticket is None:
        return None
    found = workspace / ticket.rel
    if not found.is_file() or found.is_symlink():
        return _not_on_base(ticket, "absent")
    answer["ticket_path_in_worktree"] = str(found)
    answer["ticket_path_in_worktree_posix"] = wp.to_posix(found)
    return None


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-10-22 [python-coder/EPIC-WorkspaceMakerHardening/06]:
#   A5 safe slugs (empty -> UsageError, no default), A4 dropped ticket<-feature/
#   alias plus a load-time alias/canonical overlap check, M17 shared delete helper.
# - 2026-10-10 09:00 [python-coder/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06]:
#   (#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/06)
#   Created for BO-4300a-2, a-1-ii, d-3, d-3-i, d-4: the one naming table
#   (<kind>/<slug>, legacy aliases declared per kind with reasons), hub-line
#   resolution (resume one, refuse AMBIGUOUS_LINE for two), the occupied
#   location and legacy-worktree refusals (read-only on .git/worktrees),
#   and the ticket-location checks. All additions live here because
#   worktree.py is at the file-size ratchet. (ADR-018)
# ===========================================================================
