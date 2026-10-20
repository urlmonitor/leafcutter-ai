"""
MODULE: project_ability_slots
GOAL: Answer, in one place, the questions every part of the build asks about an
    ability a specialist marks ``provided_by: project``: does the project supply
    it, which ids are marked anywhere, and is a project's copy protected from the
    build's own deploy and cleanup.
BUSINESS CONTEXT: AR-400d-1 / -2 / -2-ii. A project can supply an ability the package
    does not ship (``postgres``), or deliberately override one it does ship
    (``signoff``). The project's abilities area is also where the build deploys
    PACKAGED abilities (KI-BP-009), so without one shared rule the skills phase
    would overwrite a project's copy and ``--clean`` would delete it as stale.
    Five readers (gate, compile, delivery verifier, skills phase, ``--clean``) must
    never disagree about whether a project supplies an ability, so none of them
    keeps its own probe.
ARCHITECTURE: ``supplied_by_project(slot_root, skill_id)`` is the one probe: the
    project area holds ``<id>/SKILL.md`` and that file is not merely the packaged
    copy the build itself deployed as a fallback (a fallback deploy leaves a
    ``.packaged-fallback`` marker holding the SHA-256 of the file it wrote; a
    marker whose hash still matches means "not supplied", a changed file means
    the project took the slot over). ``marked_skill_ids(agents_dir)`` reads the
    marked ids from the agents' own frontmatter through
    ``agent_ability_verdict.normalize_entries`` (never a second scan of the text).
    ``configure`` records the project area and the marked set once per build for the
    readers that cannot be handed them (the compiler, the deploy-file enumeration);
    ``is_protected`` is true for a marked id the project supplies, and every marked id
    is kept by ``--clean`` (``marked_skill_ids`` joins the expected-names set). Fallback:
    a marked id the package ships and the project lacks is deployed once into the
    EMPTY project slot (so the Skill tool can load it) with the marker above.
    Build-engine module under ``scripts/``; no deploy-manifest entry needed.

DECISION HISTORY
- 2026-10-16 [python-coder/AR-400d]: Created. (#TICKETLESS reason=ar-400d-project-supplied-abilities)
"""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)
FALLBACK_MARKER = ".packaged-fallback"
_STATE: dict[str, Any] = {"slot_root": None, "marked": frozenset()}


def _digest(path: Path) -> str:
    """Return the SHA-256 hex digest of ``path``'s bytes, logging and re-raising on a read failure."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        _log.warning("cannot read %s: %s", path, exc)
        raise


def _marker_digest(marker: Path) -> str:
    """Return the digest a fallback marker records, logging and re-raising on a read failure."""
    try:
        return marker.read_text(encoding="utf-8").strip()
    except OSError as exc:
        _log.warning("cannot read %s: %s", marker, exc)
        raise


def project_skills_dir(project_root: Path, output_root_name: str = ".leafcutter") -> Path:
    """The project's abilities area: ``<project root>/<output root>/skills``.

    The one definition: the ability gate and verdict call it with the build's target dir, and the
    compile / deploy side's area (``<output root>/skills`` under the same target) is the same path.
    """
    return project_root / output_root_name / "skills"


def supplied_by_project(slot_root: Path | None, skill_id: str) -> bool:
    """True when the project's own abilities area holds a copy of ``skill_id`` the project put there."""
    if slot_root is None:
        return False
    skill_md = slot_root / skill_id / "SKILL.md"
    if not skill_md.is_file():
        return False
    marker = slot_root / skill_id / FALLBACK_MARKER
    if not marker.is_file():
        return True
    return _digest(skill_md) != _marker_digest(marker)


def marked_skill_ids(agents_dir: Path) -> frozenset[str]:
    """Return every ability id any agent template under ``agents_dir`` marks ``provided_by: project``.

    A malformed declaration is skipped here with a logged warning: the ability gate
    refuses it by name before any deploy, so this reader never has to.
    """
    from agent_ability_verdict import normalize_entries  # noqa: PLC0415 - verdict imports this module
    from agent_declaration_shape import MalformedDeclarationError  # noqa: PLC0415
    from template_compiler import parse_frontmatter  # noqa: PLC0415 - template_compiler imports this module

    marked: set[str] = set()
    for template in sorted(agents_dir.glob("*.md")):
        if template.name.startswith("_"):
            continue
        try:
            front = parse_frontmatter(template.read_text(encoding="utf-8"))[0]
        except OSError as exc:
            _log.warning("cannot read agent template %s: %s", template, exc)
            raise
        try:
            entries = normalize_entries(front.get("skills"))
        except MalformedDeclarationError as exc:
            _log.warning("ignoring malformed skills declaration in %s: %s", template.name, exc)
            continue
        marked.update(e["skill_id"] for e in entries if e.get("provided_by"))
    return frozenset(marked)


def configure(slot_root: Path | None, agents_dir: Path | None) -> None:
    """Record, for this build, the project's abilities area and the ids any agent marks."""
    marked = marked_skill_ids(agents_dir) if agents_dir is not None and agents_dir.is_dir() else frozenset()
    _STATE["slot_root"], _STATE["marked"] = slot_root, marked


def project_skills_root() -> Path | None:
    """The project's abilities area recorded by ``configure`` (None before it ran)."""
    return _STATE["slot_root"]


def project_ids() -> frozenset[str]:
    """The ids any agent marks ``provided_by: project`` (recorded by ``configure``)."""
    return _STATE["marked"]


def is_protected(skill_id: str) -> bool:
    """True for a marked id whose project copy exists: the skills phase must not write it."""
    return skill_id in _STATE["marked"] and supplied_by_project(_STATE["slot_root"], skill_id)


def is_not_installed(skill_id: str, marked_here: bool, packaged_ids: set[str]) -> bool:
    """True when ``skill_id`` is project-supplied, shipped by no package and absent from the project."""
    bound = marked_here or skill_id in _STATE["marked"]
    return bound and skill_id not in packaged_ids and not supplied_by_project(_STATE["slot_root"], skill_id)


def is_fallback_candidate(skill_id: str) -> bool:
    """True for a marked id the project does NOT supply: its packaged copy is deployed as a fallback.

    Call this BEFORE the deploy: afterwards the slot holds a SKILL.md either way.
    """
    return skill_id in _STATE["marked"] and not supplied_by_project(_STATE["slot_root"], skill_id)


def write_fallback_marker(skill_id: str, fallback: bool, dry_run: bool) -> None:
    """Record that the slot's SKILL.md is the packaged copy the build just deployed, not the project's own.

    Args:
        skill_id: The ability id.
        fallback: ``is_fallback_candidate(skill_id)`` as asked BEFORE the deploy.
        dry_run: True when nothing was written.

    A no-op unless ``fallback``, on a dry run, or when the deploy wrote no SKILL.md into the slot.
    """
    slot_root = _STATE["slot_root"]
    if not fallback or dry_run or slot_root is None:
        return
    skill_md = slot_root / skill_id / "SKILL.md"
    if not skill_md.is_file():
        return
    try:
        (slot_root / skill_id / FALLBACK_MARKER).write_text(_digest(skill_md) + "\n", encoding="utf-8")
    except OSError as exc:
        _log.warning("cannot record the packaged fallback marker for %s: %s", skill_id, exc)
        raise
