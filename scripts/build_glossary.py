"""
MODULE: build_glossary
GOAL: build.py phase for the GlossaryAutomation system — seeds docs/glossary.md
    and docs/glossary_blacklist.md into the target project, registers the
    check_glossary_coverage pre-commit hook, and wires a glossary reference into
    CLAUDE.md.
BUSINESS CONTEXT: Extracted from build.py (which is at the 400-line limit) to
    keep that module clean. Called by _run_phases() in build.py after the other
    build phases complete.
ARCHITECTURE: Three public functions:
    - build_glossary_seed_files(): copy-if-not-exists for glossary.md + blacklist.md
    - build_glossary_hook_registration(): idempotent hook entry in commit_guardian.json
    - wire_glossary_claude_md(): idempotent CLAUDE.md glossary-section injection

    All three are idempotent (safe to re-run). Seed files are NEVER overwritten
    once they exist — they are human-curated after the initial bootstrap.

    The CLAUDE.md marker comment ``<!-- glossary-section: leafcutter -->``
    is the idempotency sentinel: if present, the section is skipped. This pattern
    is the same as build_vision.py's ``<!-- QUESTION -->`` sentinel.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_GLOSSARY_SECTION_MARKER = "<!-- glossary-section: leafcutter -->"

_GLOSSARY_HOOK_ID = "check-glossary-coverage"

_GLOSSARY_SECTION_TEMPLATE = """\
{marker}
## Glossary

Project jargon and terminology is tracked at [docs/glossary.md](docs/glossary.md).

Consult it for project-specific terms when reading code or docs.

- **To populate from scratch**: run `/glossary-bootstrap` (once after initial install
  or after a major codebase merge).
- **Ongoing additions**: the `check-glossary-coverage` pre-commit hook detects novel
  terms in staged files and dispatches the `glossary-triage` agent automatically.
- **Do NOT hand-edit to add entries** — always use the triage flow so the blacklist
  stays consistent. Manual edits are only for correcting existing entries.
""".format(marker=_GLOSSARY_SECTION_MARKER)

# ---------------------------------------------------------------------------
# Seed file materialization (copy-if-not-exists)
# ---------------------------------------------------------------------------


def build_glossary_seed_files(
    target_root: Path,
    package_root: Path,
    dry_run: bool,
) -> int:
    """Materialise seed docs/glossary.md and docs/glossary_blacklist.md — write-if-absent.

    Copies the templates from
    ``leafcutter/templates/docs/glossary.md`` and
    ``leafcutter/templates/docs/glossary_blacklist.md`` into the
    target project's ``docs/`` directory. Existing files are NEVER overwritten —
    once a project has its own glossary content, build.py must not clobber it.

    Args:
        target_root: Absolute path to the target project root directory.
        package_root: Absolute path to the leafcutter package root.
        dry_run: When True, logs intent but writes nothing.

    Returns:
        Number of files written (0, 1, or 2).
    """
    templates_docs = package_root / "templates" / "docs"
    written = 0

    for filename in ("glossary.md", "glossary_blacklist.md"):
        src = templates_docs / filename
        dst = target_root / "docs" / filename

        if not src.exists():
            print(f"  glossary: template {src.name} not found — skipping.", file=sys.stderr)
            continue

        if dst.exists():
            print(f"  glossary: docs/{filename} exists (skipped)")
            continue

        if dry_run:
            print(f"  [DRY-RUN] would write docs/{filename}")
            written += 1
            continue

        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"  glossary: created docs/{filename}")
        written += 1

    return written


# ---------------------------------------------------------------------------
# Pre-commit hook registration (idempotent)
# ---------------------------------------------------------------------------


def build_glossary_hook_registration(
    target_root: Path,
    package_root: Path,
    dry_run: bool,
) -> int:
    """Register check_glossary_coverage in the target project's commit_guardian.json.

    Reads the target project's ``scripts/commit_guardian/commit_guardian.json``
    (or the package template if the project does not have one yet) and adds the
    ``check-glossary-coverage`` hook entry if it is not already present.

    The hook entry is sourced from the package template's
    ``templates/commit-guardian/commit_guardian.json`` hooks_manifest section.

    Args:
        target_root: Absolute path to the target project root directory.
        package_root: Absolute path to the leafcutter package root.
        dry_run: When True, logs intent but writes nothing.

    Returns:
        1 if the file was modified, 0 if the entry already existed or file not found.
    """
    target_cg = target_root / "scripts" / "commit_guardian" / "commit_guardian.json"
    if not target_cg.exists():
        print("  glossary: commit_guardian.json not found — hook registration skipped.")
        return 0

    try:
        cg_data = json.loads(target_cg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"  glossary: WARNING — cannot read commit_guardian.json: {exc}", file=sys.stderr)
        return 0

    hooks_manifest = cg_data.get("hooks_manifest", {})
    hooks = hooks_manifest.get("hooks", [])

    # Idempotency: check if already registered
    if any(h.get("id") == _GLOSSARY_HOOK_ID for h in hooks):
        print(f"  glossary: {_GLOSSARY_HOOK_ID} hook already registered (skipped)")
        return 0

    # Load hook spec from template
    hook_entry = _load_hook_entry_from_template(package_root)
    if hook_entry is None:
        return 0

    if dry_run:
        print(f"  [DRY-RUN] would add {_GLOSSARY_HOOK_ID} to commit_guardian.json")
        return 1

    hooks.append(hook_entry)
    hooks_manifest["hooks"] = hooks
    cg_data["hooks_manifest"] = hooks_manifest

    target_cg.write_text(
        json.dumps(cg_data, indent=4, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"  glossary: added {_GLOSSARY_HOOK_ID} hook to commit_guardian.json")
    return 1


def _load_hook_entry_from_template(package_root: Path) -> dict | None:
    """Load the check_glossary_coverage hook spec from the package template.

    Args:
        package_root: Absolute path to the leafcutter package root.

    Returns:
        Hook entry dict, or None if the template cannot be loaded.
    """
    template_cg = package_root / "templates" / "scripts" / "commit_guardian" / "commit_guardian.json"
    if not template_cg.exists():
        # Fall back to legacy path for backward compatibility
        template_cg = package_root / "templates" / "commit-guardian" / "commit_guardian.json"
    if not template_cg.exists():
        print(
            "  glossary: WARNING — package commit_guardian.json template not found.",
            file=sys.stderr,
        )
        return None
    try:
        tpl = json.loads(template_cg.read_text(encoding="utf-8"))
        hooks = tpl.get("hooks_manifest", {}).get("hooks", [])
        for h in hooks:
            if h.get("id") == _GLOSSARY_HOOK_ID:
                return h
    except (json.JSONDecodeError, OSError) as exc:
        print(
            f"  glossary: WARNING — cannot read template commit_guardian.json: {exc}",
            file=sys.stderr,
        )
    return None


# ---------------------------------------------------------------------------
# CLAUDE.md wiring (idempotent)
# ---------------------------------------------------------------------------


def _resolve_todo_placeholders(text: str) -> str:
    """Convert unresolved {{config.key}} tokens to HTML comment TODOs.

    Called after ``inject_config()`` so that any placeholder not present in
    ``skills_config.json`` degrades to a visible reminder rather than leaking
    raw template syntax into the generated CLAUDE.md.

    Args:
        text: Template text after ``inject_config()`` substitution.

    Returns:
        Text with all remaining ``{{config.key}}`` tokens replaced by
        ``<!-- TODO: fill in key -->``.
    """
    return re.sub(
        r"\{\{config\.([a-zA-Z0-9_]+)\}\}",
        lambda m: f"<!-- TODO: fill in {m.group(1)} -->",
        text,
    )


def wire_glossary_claude_md(target_root: Path, dry_run: bool, config: dict | None = None) -> int:
    """Inject a glossary reference section into the target project's CLAUDE.md.

    When ``leafcutter/templates/CLAUDE.md.template`` exists, uses it
    as the base content (interpolating ``{{config.key}}`` placeholders from
    ``config`` and converting any remaining tokens to ``<!-- TODO: fill in key
    -->``). Otherwise falls back to a minimal 4-line stub.

    Detects presence via ``<!-- glossary-section: leafcutter -->``
    marker. If the marker is already in CLAUDE.md, the function is a no-op
    (idempotent). If CLAUDE.md does not exist, creates one from the template.

    Args:
        target_root: Absolute path to the target project root directory.
        dry_run: When True, logs intent but writes nothing.
        config: Build config dict for placeholder injection. Defaults to ``{}``
            when not supplied (all placeholders become TODOs).

    Returns:
        1 if CLAUDE.md was written or created; 0 if marker already present.
    """
    cfg = config or {}
    claude_md = target_root / "CLAUDE.md"

    if claude_md.exists():
        existing = claude_md.read_text(encoding="utf-8")
        if _GLOSSARY_SECTION_MARKER in existing:
            print("  glossary: CLAUDE.md glossary section already present (skipped)")
            return 0
        # Append section to existing CLAUDE.md
        if dry_run:
            print("  [DRY-RUN] would append glossary section to CLAUDE.md")
            return 1
        new_content = existing.rstrip() + "\n\n" + _GLOSSARY_SECTION_TEMPLATE
        claude_md.write_text(new_content, encoding="utf-8")
        print("  glossary: appended glossary section to CLAUDE.md")
        return 1

    # CLAUDE.md does not exist — create from template or minimal stub
    package_root = Path(__file__).resolve().parent.parent
    template_path = package_root / "templates" / "CLAUDE.md.template"

    if template_path.exists():
        raw = template_path.read_text(encoding="utf-8")
        # Import here to avoid circular dependency at module load time
        try:
            from template_compiler import inject_config  # noqa: PLC0415
            interpolated = inject_config(raw, cfg)
        except ImportError:
            interpolated = raw
        base_content = _resolve_todo_placeholders(interpolated)
    else:
        base_content = (
            "# CLAUDE.md\n\n"
            "This file provides guidance to Claude Code when working in this repository.\n\n"
        )

    full_content = base_content.rstrip() + "\n\n" + _GLOSSARY_SECTION_TEMPLATE
    if dry_run:
        print("  [DRY-RUN] would create CLAUDE.md from template with glossary section")
        return 1
    claude_md.write_text(full_content, encoding="utf-8")
    src = "template" if template_path.exists() else "stub"
    print(f"  glossary: created CLAUDE.md from {src}")
    return 1


# ---------------------------------------------------------------------------
# Phase entry point (called by build.py _run_phases)
# ---------------------------------------------------------------------------


def build_glossary(
    target_root: Path,
    config: dict[str, Any],
    dry_run: bool,
    force: bool,
) -> int:
    """Run all three glossary build sub-phases.

    The ``force`` parameter is intentionally unused — all glossary operations
    use write-if-absent / idempotent semantics regardless of the caller's flag.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Build configuration dict (unused but required by phase protocol).
        dry_run: When True, logs intent but writes nothing.
        force: Ignored — glossary operations always use write-if-absent semantics.

    Returns:
        Total files written across all three sub-phases.
    """
    package_root = Path(__file__).resolve().parent.parent
    total = 0
    total += build_glossary_seed_files(target_root, package_root, dry_run)
    total += build_glossary_hook_registration(target_root, package_root, dry_run)
    total += wire_glossary_claude_md(target_root, dry_run, config)
    return total


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 20:00 [python-coder/EPIC-GlossaryAutomation/ticket-05]: Created module. Three sub-phases: seed-files (copy-if-not-exists), hook-registration (idempotent via ID check), CLAUDE.md wiring (idempotent via marker comment). Extracted from build.py (at 400-line limit) as a sibling module. Marker: <!-- glossary-section: leafcutter -->. (#TICKETLESS reason=build-glossary-module)
# - 2026-05-18 11:15 [EPIC-PortableInstallHardening/T03]: Updated _load_hook_entry_from_template() to check canonical templates/scripts/commit_guardian/ path first, with backward-compat fallback to templates/commit-guardian/. (#EPIC-PortableInstallHardening/T03)
# - 2026-05-18 12:00 [EPIC-PortableInstallHardening/T05]: Extended wire_glossary_claude_md() to load templates/CLAUDE.md.template when present, run inject_config(), and convert remaining {{config.key}} tokens to <!-- TODO: fill in key --> via _resolve_todo_placeholders(). Added config param to wire_glossary_claude_md and build_glossary. Added import re. (#EPIC-PortableInstallHardening/T05)
# ====================================================================
