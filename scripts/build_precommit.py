"""
MODULE: build_precommit
GOAL: Generate and merge .pre-commit-config.yaml at the consumer project root
    from the hooks_manifest defined in commit_guardian.json.
BUSINESS CONTEXT: A fresh consumer project that runs build.py must receive both
    the hook scripts AND the YAML that registers them so all hooks actually fire.
    This module owns the YAML generation and idempotent merge logic so that
    build_phases.py stays within the 400-line complexity budget.
ARCHITECTURE: Three public functions exported to build_phases.py:
    ``build_precommit_config`` — the phase entry point (matches the standard
    phase signature); ``_render_hook_yaml`` and ``_strip_package_managed_blocks``
    are private helpers exposed for unit-testing. A ``@package-managed`` sentinel
    on the ``name:`` line identifies package-owned blocks so they can be replaced
    on re-run while project-specific hooks are preserved.

"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_log = logging.getLogger(__name__)

_HOOK_FIELD_PREFIXES = frozenset([
    "- id:", "name:", "entry:", "language:", "types", "files:",
    "stages:", "pass_filenames:", "always_run:",
])


def _is_hook_field_line(stripped: str) -> bool:
    """Return True if ``stripped`` is a blank line or a recognised hook field prefix.

    Used by ``_strip_package_managed_blocks`` to decide whether a line belongs
    to a hook block (and should be skipped) or to the surrounding YAML structure
    (and should terminate skip mode).

    Lines starting with ``# ===`` are the DECISION HISTORY sentinel and must
    NOT be treated as hook fields — they should terminate skip mode so that
    the DECISION HISTORY block is preserved verbatim.

    Args:
        stripped: The line with leading/trailing whitespace removed.

    Returns:
        True if the line is blank, a non-sentinel comment, or a known hook
        field keyword.
    """
    if not stripped:
        return True
    if stripped.startswith("#"):
        # DECISION HISTORY sentinel — exit skip mode
        if stripped.startswith("# ==="):
            return False
        return True
    return any(stripped.startswith(prefix) for prefix in _HOOK_FIELD_PREFIXES)


def _next_line_is_package_managed(lines: list[str], id_index: int) -> bool:
    """Return True when the line after a ``- id:`` line has the sentinel marker.

    Looks ahead past the ``- id:`` line to the next non-blank line and checks
    whether it contains ``@package-managed``.

    Args:
        lines: All lines of the YAML file.
        id_index: Index of the ``- id:`` line in ``lines``.

    Returns:
        True if the following non-blank line contains ``@package-managed``.
    """
    j = id_index + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    return j < len(lines) and "@package-managed" in lines[j]


def _advance_skip_mode(
    lines: list[str], i: int, result: list[str]
) -> tuple[bool, int]:
    """Process one line while in skip mode and return updated (skip, i).

    Called by ``_strip_package_managed_blocks`` when ``skip`` is True. Decides
    whether the current line ends skip mode or should be consumed.

    Args:
        lines: All lines of the YAML file.
        i: Current line index.
        result: Accumulator list (mutated when skip mode ends).

    Returns:
        Tuple of (new skip flag, new index).
    """
    line = lines[i]
    stripped = line.strip()
    if stripped.startswith("- id:"):
        if i + 1 < len(lines) and "@package-managed" in lines[i + 1]:
            return True, i + 1  # still a package-managed hook — keep skipping
        result.append(line)
        return False, i + 1  # non-package hook — exit skip mode
    if _is_hook_field_line(stripped):
        return True, i + 1  # still inside a block or blank line
    # Non-hook YAML structure — exit skip mode
    result.append(line)
    return False, i + 1


def _strip_package_managed_blocks(lines: list[str]) -> list[str]:
    """Remove all @package-managed hook blocks from a list of YAML lines.

    A ``@package-managed`` block starts at the ``- id:`` line immediately
    before a line whose ``name:`` field ends with ``@package-managed``.
    The block ends at the last non-blank line before the next ``- id:`` sibling
    or the end of the hook list. The ``# --- package-managed hooks`` sentinel
    comment is also stripped.

    Args:
        lines: Raw lines of the existing ``.pre-commit-config.yaml``.

    Returns:
        Filtered lines with all package-managed blocks removed.
    """
    result: list[str] = []
    skip = False
    i = 0
    while i < len(lines):
        line = lines[i]
        if "# --- package-managed hooks" in line:
            skip = True
            i += 1
            continue
        if skip:
            skip, i = _advance_skip_mode(lines, i, result)
            continue
        # Normal mode: check whether this id: starts a package-managed block
        if line.strip().startswith("- id:") and _next_line_is_package_managed(lines, i):
            skip = True
            i += 1
            continue
        result.append(line)
        i += 1
    return result


def _render_hook_yaml(hook: dict[str, Any]) -> str:
    """Render a single hook dict from the manifest as a YAML hook block.

    The sentinel comment ``@package-managed`` is appended to the ``name:``
    line so ``build_precommit_config`` can identify and replace package-owned
    entries on subsequent runs.

    Args:
        hook: A single hook entry dict from ``hooks_manifest.hooks``.

    Returns:
        Indented YAML string for one ``- id: ...`` block (no leading newline).
    """
    lines: list[str] = []
    lines.append(f"      - id: {hook['id']}")
    lines.append(f"        name: {hook['name']}  # @package-managed")
    lines.append(f"        entry: {hook['entry']}")
    lines.append(f"        language: {hook.get('language', 'system')}")
    if "types_or" in hook:
        lines.append(f"        types_or: [{', '.join(hook['types_or'])}]")
    elif "types" in hook:
        lines.append(f"        types: [{', '.join(hook['types'])}]")
    if "files" in hook:
        lines.append(f"        files: {hook['files']}")
    stages_str = ", ".join(hook.get("stages", ["pre-commit"]))
    lines.append(f"        stages: [{stages_str}]")
    pf = hook.get("pass_filenames", False)
    lines.append(f"        pass_filenames: {str(pf).lower()}")
    if hook.get("always_run"):
        lines.append("        always_run: true")
    return "\n".join(lines)


def _find_decision_history_index(lines: list[str]) -> int:
    """Return the index of the first DECISION HISTORY marker line, or -1.

    Searches for the ``# ====`` block that precedes the DECISION HISTORY
    section so that package-managed hooks can be inserted before it.

    Args:
        lines: Lines to search.

    Returns:
        Index of the DECISION HISTORY block start, or -1 if not found.
    """
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("# ===") and "DECISION HISTORY" in "".join(
            lines[i : i + 3]
        ):
            return i
    return -1


def _build_output_lines(clean_lines: list[str], hook_yaml_blocks: list[str]) -> str:
    """Assemble the final YAML content from clean lines and hook blocks.

    Inserts the package-managed hooks block immediately before the DECISION
    HISTORY section when one exists, so that DECISION HISTORY remains the
    last section of the file (as required by check-documentation).

    Args:
        clean_lines: Lines from the existing config with package-managed blocks
            stripped (or the bootstrap header for a fresh project).
        hook_yaml_blocks: Rendered YAML blocks for each manifest hook.

    Returns:
        Full file content as a string (newline-terminated).
    """
    dh_index = _find_decision_history_index(clean_lines)

    pkg_section: list[str] = ["", "      # --- package-managed hooks (do not edit below) ---"]
    for block in hook_yaml_blocks:
        pkg_section.append("")
        pkg_section.extend(block.splitlines())
    pkg_section.append("")

    if dh_index >= 0:
        # Insert before the DECISION HISTORY section
        prefix = clean_lines[:dh_index]
        while prefix and prefix[-1].strip() == "":
            prefix.pop()
        suffix = clean_lines[dh_index:]
        output_lines = prefix + pkg_section + suffix
    else:
        output_lines = clean_lines[:]
        while output_lines and output_lines[-1].strip() == "":
            output_lines.pop()
        output_lines.extend(pkg_section)

    return "\n".join(output_lines) + "\n"


def _resolve_template_vars(
    hooks: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    """Replace ``{{config.KEY}}`` placeholders in hook string fields."""
    from template_compiler import inject_config

    resolved = []
    for hook in hooks:
        h = {}
        for k, v in hook.items():
            if isinstance(v, str):
                h[k] = inject_config(v, config)
            else:
                h[k] = v
        resolved.append(h)
    return resolved


def build_precommit_config(target_root: Path, config: dict[str, Any],
                           dry_run: bool, force: bool) -> int:
    """Generate or update ``.pre-commit-config.yaml`` at the target project root.

    Reads ``hooks_manifest.hooks`` from the commit-guardian template
    ``commit_guardian.json``. Each hook entry is rendered as a YAML block
    and tagged with the ``@package-managed`` sentinel on its ``name:`` line.

    Merge logic (idempotent): parse the existing YAML, strip package-managed
    blocks, append rendered blocks for all manifest hooks. Project-specific
    hooks (no sentinel) are preserved.

    Args:
        target_root: Absolute path to the target project root directory.
        config: Merged config dictionary (unused; reserved for future use).
        dry_run: When True, prints intent but writes nothing.
        force: When True, overwrites the existing file.

    Returns:
        1 if the file was written (or would be in dry-run); 0 if skipped.
    """
    from build_phases import TEMPLATES_DIR  # late import to avoid circular

    cg_dir = TEMPLATES_DIR / "scripts" / "commit_guardian"
    manifest_path = cg_dir / "commit_guardian.json"
    if not manifest_path.exists():
        # Fall back to legacy path for backward compatibility
        cg_dir = TEMPLATES_DIR / "commit-guardian"
        manifest_path = cg_dir / "commit_guardian.json"
    if not manifest_path.exists():
        _log.warning(
            "commit_guardian.json not found at %s; skipping pre-commit config generation.",
            manifest_path,
        )
        return 0

    raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    hooks = raw.get("hooks_manifest", {}).get("hooks", [])
    if not hooks:
        return 0

    hooks = _resolve_template_vars(hooks, config)

    output_path = target_root / "pre-commit-config.yaml"

    if output_path.exists():
        clean_lines = _strip_package_managed_blocks(
            output_path.read_text(encoding="utf-8").splitlines()
        )
    else:
        clean_lines = [
            "fail_fast: true",
            "repos:",
            "  - repo: local",
            "    hooks:",
            "",
        ]

    hook_yaml_blocks = [_render_hook_yaml(h) for h in hooks]
    content = _build_output_lines(clean_lines, hook_yaml_blocks)

    if not (not output_path.exists() or force):
        return 0

    if dry_run:
        print(f"  [DRY-RUN] would write .pre-commit-config.yaml ({len(hooks)} package hooks)")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"  .pre-commit-config.yaml ({len(hooks)} package hooks merged)")
    return 1


# ===========================================================================
# DECISION HISTORY
# ===========================================================================
# - 2026-05-13 16:30 [epic-supervisor]: Extracted from build_phases.py to keep module within 400-line limit. (#TICKETLESS reason=split-build-phases)
# - 2026-05-14 02:30 [epic-supervisor]: Added test fixtures for _strip_package_managed_blocks / _build_output_lines; four YAML scenarios covered. (#TICKETLESS reason=build-precommit-test)
# - 2026-05-14 00:40 [epic-supervisor]: Fixed _build_output_lines to insert package-managed hooks BEFORE DECISION HISTORY sentinel. (#TICKETLESS reason=build-precommit-fix)
# - 2026-05-18 11:15 [EPIC-PortableInstallHardening/T03]: Updated cg_dir to canonical templates/scripts/commit_guardian/ with backward-compat fallback. (#EPIC-PortableInstallHardening/T03)
# ===========================================================================
