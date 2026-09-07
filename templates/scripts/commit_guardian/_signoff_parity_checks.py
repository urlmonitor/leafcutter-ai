"""
MODULE: _signoff_parity_checks.py
GOAL: Parsing helpers and parity-check functions extracted from
    check_ticket_signoff_parity.py to keep each file under the 400-line budget.
BUSINESS CONTEXT: All logic lives here; check_ticket_signoff_parity.py imports
    this module and exposes all names so the existing test shim continues to work.
ARCHITECTURE: Imported by check_ticket_signoff_parity.py via a relative-style
    import. Both files share the same ``scripts/commit_guardian/`` package directory.
    No circular dependencies — this module does not import the main script.
"""

import json
import os
import re
import sys
from pathlib import Path

import yaml

from _resolve_root import find_project_root

_project_root = find_project_root()

from config import (
    AGENT_REGISTRY_PATH,
    DOC_FM_COMPONENTS_REGISTRY,
    TICKET_FM_ALLOWED_STATUSES,
    TICKET_FM_ALLOWED_TYPES,
    TICKET_FM_REQUIRED_FIELDS,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_STATUSES = frozenset({"not_needed", "needed", "signed_off", "failed"})

# Matches:  - [x] agent-name — 2026-05-08 14:30
_SIGNED_OFF_RE = re.compile(
    r"^- \[x\]\s+(?P<agent>[a-zA-Z0-9_-]+)\s+—\s+\d{4}-\d{2}-\d{2} \d{2}:\d{2}\s*$"
)
# Matches:  - [ ] agent-name — failed 2026-05-08 14:30
_FAILED_RE = re.compile(
    r"^- \[ \]\s+(?P<agent>[a-zA-Z0-9_-]+)\s+—\s+failed \d{4}-\d{2}-\d{2} \d{2}:\d{2}\s*$"
)
# Matches:  - [ ] agent-name  (no timestamp, no failed keyword)
_NEEDED_RE = re.compile(
    r"^- \[ \]\s+(?P<agent>[a-zA-Z0-9_-]+)\s*$"
)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def load_components_registry(project_root_path: Path) -> set[str]:
    """Load components from registry.

    Args:
        project_root_path: Path to root

    Returns:
        set of component ids
    """
    registry_path = project_root_path / DOC_FM_COMPONENTS_REGISTRY
    if not registry_path.exists():
        return set()
    try:
        with open(registry_path, encoding="utf-8") as f:
            data = json.load(f)
        return {comp["id"] for comp in data.get("components", []) if isinstance(comp, dict) and "id" in comp}
    except Exception:  # noqa: BLE001  # fail-open: skip components validation, but surface why
        print(
            f"[check-ticket-signoff-parity] WARNING: could not load components registry at "
            f"{registry_path}; skipping components validation",
            file=sys.stderr,
        )
        return set()


def load_agent_registry(project_root_path: Path) -> dict[str, bool]:
    """Load agent registry and return a mapping of agent id to requires_ticket_section flag.

    Fail-open: returns an empty dict when the registry file is absent or unreadable
    so that check #6 is skipped rather than blocking commits. Matches the
    ``DOC_FM_COMPONENTS_REGISTRY`` / ``load_components_registry()`` pattern.

    Args:
        project_root_path: Root path of the project (used to resolve AGENT_REGISTRY_PATH).

    Returns:
        dict mapping agent id strings to their ``requires_ticket_section`` boolean
        (defaults to ``False`` when the field is absent from a registry entry).
    """
    registry_path = project_root_path / AGENT_REGISTRY_PATH
    if not registry_path.exists():
        print(
            f"[check-ticket-signoff-parity] WARNING: agent registry not found at "
            f"{registry_path}; skipping check #6",
            file=sys.stderr,
        )
        return {}
    try:
        with open(registry_path, encoding="utf-8") as f:
            data = json.load(f)
        return {
            agent["id"]: bool(agent.get("requires_ticket_section", False))
            for agent in data.get("agents", [])
            if isinstance(agent, dict) and "id" in agent
        }
    except Exception:  # noqa: BLE001
        print(
            f"[check-ticket-signoff-parity] WARNING: could not load agent registry at "
            f"{registry_path}; skipping check #6",
            file=sys.stderr,
        )
        return {}


def validate_ticket_required_fields(fm: dict) -> list[str]:
    errors = []
    for field in TICKET_FM_REQUIRED_FIELDS:
        if field not in fm or fm[field] is None:
            errors.append(f"Missing required field: '{field}'")
    return errors


def validate_ticket_type_enum(fm: dict) -> list[str]:
    """Validate that the frontmatter ``type`` field is in the allowed set.

    Args:
        fm: Parsed YAML frontmatter dict from a ticket file.

    Returns:
        A list of human-readable error strings (empty when valid or absent).
    """
    doc_type = fm.get("type")
    if doc_type is None:
        return []
    if doc_type not in TICKET_FM_ALLOWED_TYPES:
        return [f"Invalid type '{doc_type}'. Allowed: {', '.join(TICKET_FM_ALLOWED_TYPES)}"]
    return []


def validate_ticket_status_enum(fm: dict) -> list[str]:
    """Validate that the frontmatter ``status`` field is in the allowed set.

    Args:
        fm: Parsed YAML frontmatter dict from a ticket file.

    Returns:
        A list of human-readable error strings (empty when valid or absent).
    """
    status = fm.get("status")
    if status is None:
        return []
    if status not in TICKET_FM_ALLOWED_STATUSES:
        return [f"Invalid status '{status}'. Allowed: {', '.join(TICKET_FM_ALLOWED_STATUSES)}"]
    return []


def validate_ticket_components(fm: dict, valid_components: set[str]) -> list[str]:
    """Validate that all frontmatter ``components`` entries are in the known registry.

    Args:
        fm: Parsed YAML frontmatter dict from a ticket file.
        valid_components: Set of known component identifiers from the config registry.

    Returns:
        A list of human-readable error strings (empty when valid or absent).
    """
    components = fm.get("components")
    if components is None:
        return []
    if not isinstance(components, list):
        return ["'components' must be a list"]
    if not valid_components:
        return []
    errors = []
    for comp in components:
        if comp not in valid_components:
            errors.append(f"Unknown component '{comp}'.")
    return errors


def validate_ticket_files_touched_shape(fm: dict) -> list[str]:
    """Validate that the frontmatter ``files_touched`` field is a list or absent.

    Args:
        fm: Parsed YAML frontmatter dict from a ticket file.

    Returns:
        A list of human-readable error strings (empty when valid or absent).
    """
    files_touched = fm.get("files_touched")
    if files_touched is None or isinstance(files_touched, list):
        return []
    return ["'files_touched' must be a list"]


def _parse_frontmatter(content: str) -> dict | None:
    """Extract and parse the YAML frontmatter block from ticket content.

    Args:
        content: Full text content of a markdown ticket file.

    Returns:
        The parsed frontmatter dict, or None if the block is absent or
        unparseable.
    """
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    raw = content[3:end].strip()
    try:
        parsed = yaml.safe_load(raw)
    except yaml.YAMLError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _parse_signoffs_section(content: str) -> list[str]:
    """Extract lines from the ``## Sign-offs`` section of a ticket.

    Stops at the next ``##`` heading (or end of file). Returns an empty list
    when the section is absent — absence is not an error per the spec.

    Args:
        content: Full text content of a markdown ticket file.

    Returns:
        List of non-blank lines from the ``## Sign-offs`` block.
    """
    lines = content.splitlines()
    in_section = False
    result: list[str] = []
    for line in lines:
        if re.match(r"^## Sign-offs\s*$", line):
            in_section = True
            continue
        if in_section:
            if re.match(r"^##\s+", line):
                break
            stripped = line.strip()
            if stripped:
                result.append(stripped)
    return result


def _parse_impl_tasks_section(content: str) -> dict[str, int]:
    """Parse ``## Implementation Tasks`` and count unchecked ``- [ ]`` items per agent.

    Finds ``### <agent-name>`` subheadings within the Implementation Tasks section
    and counts ``- [ ]`` lines in each agent's block, stopping at the next ``###``
    or ``##`` heading.

    Args:
        content: Full text content of a markdown ticket file.

    Returns:
        dict mapping agent name (from ``### <name>`` heading text) to its unchecked
        item count. Returns an empty dict when the section is absent.
    """
    lines = content.splitlines()
    in_impl_tasks = False
    current_agent: str | None = None
    result: dict[str, int] = {}

    for line in lines:
        if re.match(r"^## Implementation Tasks\s*$", line):
            in_impl_tasks = True
            current_agent = None
            continue
        if in_impl_tasks:
            if re.match(r"^## ", line):
                break  # next ## heading — out of Implementation Tasks
            m = re.match(r"^### (.+?)\s*$", line)
            if m:
                current_agent = m.group(1).strip()
                if current_agent not in result:
                    result[current_agent] = 0
                continue
            if current_agent is not None and re.match(r"^- \[ \]", line):
                result[current_agent] += 1

    return result


def _classify_signoff_line(line: str) -> tuple[str, str] | None:
    """Classify a single ``## Sign-offs`` checklist line and return its agent name and representation type.

    Args:
        line: A single non-blank line from the ``## Sign-offs`` section.

    Returns:
        ``(agent_name, kind)`` where kind is one of ``"signed_off"``,
        ``"failed"``, ``"needed"``, or ``None`` when the line is
        unrecognised (treated as an orphan candidate by the caller).
    """
    m = _SIGNED_OFF_RE.match(line)
    if m:
        return (m.group("agent"), "signed_off")
    m = _FAILED_RE.match(line)
    if m:
        return (m.group("agent"), "failed")
    m = _NEEDED_RE.match(line)
    if m:
        return (m.group("agent"), "needed")
    return None


def _build_signoffs_map(signoff_lines: list[str]) -> tuple[dict[str, str], list[str]]:
    """Convert raw sign-off lines into a mapping from agent name to kind.

    Args:
        signoff_lines: Non-blank lines extracted from the ``## Sign-offs``
            section.

    Returns:
        A tuple of (signoffs_map, unrecognised_lines) where signoffs_map maps
        agent name to its representation kind (``"signed_off"``, ``"failed"``,
        or ``"needed"``), and unrecognised_lines contains any lines that did
        not match any expected pattern.
    """
    signoffs: dict[str, str] = {}
    unrecognised: list[str] = []
    for line in signoff_lines:
        parsed = _classify_signoff_line(line)
        if parsed is None:
            unrecognised.append(line)
        else:
            agent_name, kind = parsed
            signoffs[agent_name] = kind
    return signoffs, unrecognised


# ---------------------------------------------------------------------------
# Parity check helpers
# ---------------------------------------------------------------------------


def _extract_agent_status(raw_value: object) -> str | None:
    """Extract the effective status string from a frontmatter agent entry.

    Accepts both the scalar form (``signed_off``) and the nested-map form
    (``{status: signed_off, grandfathered: true}``) introduced by
    TICKET-20260511 Deliverable 2 (Option A). Returns ``None`` when the value
    cannot be resolved to a string.

    Args:
        raw_value: The raw Python value parsed from the YAML ``agents:`` map
            for a single agent key. Either a ``str`` or a ``dict``.

    Returns:
        The effective status string, or ``None`` when the shape is unrecognised.
    """
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, dict):
        status = raw_value.get("status")
        if isinstance(status, str):
            if raw_value.get("grandfathered"):
                print(
                    f"[check-ticket-signoff-parity] notice: grandfathered entry "
                    f"found (status={status})",
                    file=sys.stderr,
                )
            return status
    return None


def _check_enum_membership(agents: dict) -> list[str]:
    """Report agents whose status values are outside the allowed enum.

    Handles both the scalar form (``signed_off``) and the nested-map form
    (``{status: signed_off, grandfathered: true}``).

    Args:
        agents: The ``agents:`` mapping from ticket frontmatter.

    Returns:
        One violation string per invalid status value.
    """
    violations: list[str] = []
    for name, raw_value in agents.items():
        status = _extract_agent_status(raw_value)
        if status is None:
            violations.append(
                f"agent '{name}' has unrecognised value '{raw_value!r}'; "
                f"expected a status string or {{status: <status>, grandfathered: true}} map"
            )
        elif status not in VALID_STATUSES:
            violations.append(
                f"agent '{name}' has invalid status '{status}'; "
                f"allowed: {', '.join(sorted(VALID_STATUSES))}"
            )
    return violations


def _expected_signoff_repr(status: str) -> str:
    """Return a human-readable description of the expected ``## Sign-offs`` line for a given status.

    Args:
        status: One of the valid status enum values.

    Returns:
        A short description of the expected line format.
    """
    if status == "signed_off":
        return "- [x] <name> — YYYY-MM-DD HH:MM"
    if status == "failed":
        return "- [ ] <name> — failed YYYY-MM-DD HH:MM"
    if status == "needed":
        return "- [ ] <name>"
    return "<not expected in ## Sign-offs>"


def _check_parity(agents: dict, signoffs: dict[str, str]) -> list[str]:
    """Validate that every agent in frontmatter has the correct Sign-offs representation.

    Agents with status ``not_needed`` must NOT appear in ``## Sign-offs``.
    All other agents must appear with the matching representation.

    Accepts both the scalar form (``signed_off``) and the nested-map form
    (``{status: signed_off, grandfathered: true}``) for status values.

    Args:
        agents: The ``agents:`` mapping from ticket frontmatter.
        signoffs: Mapping from agent name to its kind as parsed from
            ``## Sign-offs``.

    Returns:
        One violation string per discrepancy between the two sections.
    """
    violations: list[str] = []
    for name, raw_value in agents.items():
        status = _extract_agent_status(raw_value)
        if status is None or status not in VALID_STATUSES:
            continue  # already reported by enum check
        if status == "not_needed":
            if name in signoffs:
                violations.append(
                    f"agent '{name}' has status 'not_needed' in frontmatter "
                    f"but appears in ## Sign-offs (it must be absent)"
                )
        else:
            if name not in signoffs:
                violations.append(
                    f"agent '{name}' has status '{status}' in frontmatter "
                    f"but is missing from ## Sign-offs "
                    f"(expected: {_expected_signoff_repr(status)})"
                )
            elif signoffs[name] != status:
                violations.append(
                    f"agent '{name}' has status '{status}' in frontmatter "
                    f"but ## Sign-offs shows '{signoffs[name]}' "
                    f"(expected: {_expected_signoff_repr(status)})"
                )
    return violations


def _check_orphans(agents: dict, signoffs: dict[str, str]) -> list[str]:
    """Report Sign-offs entries that have no matching frontmatter agent.

    Args:
        agents: The ``agents:`` mapping from ticket frontmatter.
        signoffs: Mapping from agent name to its kind as parsed from
            ``## Sign-offs``.

    Returns:
        One violation string per orphan Sign-offs entry.
    """
    violations: list[str] = []
    for name in signoffs:
        if name not in agents:
            violations.append(
                f"## Sign-offs has an entry for '{name}' "
                f"but '{name}' is not in the frontmatter agents: map (orphan)"
            )
    return violations


def _check_done_folder(ticket_path: str, agents: dict) -> list[str]:
    """Report agents with ``needed`` or ``failed`` status in a done/ ticket.

    Handles both forward-slash and backslash path separators so Windows paths
    work correctly.

    Args:
        ticket_path: The file path as provided by pre-commit (may use either
            slash style).
        agents: The ``agents:`` mapping from ticket frontmatter.

    Returns:
        One violation string per disallowed status found in a done/ ticket.
    """
    normalised = ticket_path.replace("\\", "/").lower()
    if "/done/" not in normalised:
        return []
    violations: list[str] = []
    for name, raw_value in agents.items():
        status = _extract_agent_status(raw_value)
        if status in ("needed", "failed"):
            violations.append(
                f"ticket is in a done/ folder but agent '{name}' "
                f"still has status '{status}' (must be 'signed_off' or 'not_needed')"
            )
    return violations


def _check_done_folder_prohibition(
    ticket_path: str, *, old_path: str | None = None
) -> list[str]:
    """Report a violation when a ticket is moved into a done/ or 99_done/ subfolder.

    BO-400c-3: Tickets must NOT be moved into done/ subfolders via filesystem
    moves. Use the frontmatter ``status: done`` field instead.

    Detection is move-based when ``old_path`` is provided: the prohibition fires
    only when the ticket was NOT already in a done/ folder before this commit.
    This prevents false positives on in-place edits of files that legitimately
    reside at a done/ path (BO-400c-3-i). When ``old_path`` is absent the check
    falls back to presence-based detection for backward compatibility with
    call sites that do not supply rename information.

    BO-400c-3-ii: moves into ``tickets/99_done/`` are also blocked. The finalize
    archive step is exempted when the ``LEAFCUTTER_FINALIZE_ARCHIVE`` environment
    variable is set to a non-empty value.

    Handles both forward-slash and backslash path separators so Windows paths
    work correctly.

    Args:
        ticket_path: The staged (new) file path as provided by pre-commit (may
            use either slash style).
        old_path: The pre-move (HEAD) path of the file, or ``None`` when the
            caller does not have rename information. When equal to ``ticket_path``
            the commit is an in-place edit of a file already in a done folder and
            no violation is raised (BO-400c-3-i). When the caller omits this
            argument, presence-based detection is used for backward compatibility.

    Returns:
        A list with one violation string when the path change represents a move
        into a done/ or 99_done/ folder; empty list otherwise.
    """
    normalised_new = ticket_path.replace("\\", "/").lower()

    in_plain_done = "/done/" in normalised_new
    in_99_done = "/99_done/" in normalised_new

    if not (in_plain_done or in_99_done):
        return []

    # Move-based check: when old_path is provided, only fire for actual moves.
    if old_path is not None:
        normalised_old = old_path.replace("\\", "/").lower()
        old_in_done = "/done/" in normalised_old or "/99_done/" in normalised_old
        if old_in_done:
            # In-place edit — the file already lived at a done/ path before this
            # commit. No move, no prohibition (BO-400c-3-i).
            return []

    # 99_done move: honour the finalize env-flag carve-out (BO-400c-3-ii).
    if in_99_done:
        if os.environ.get("LEAFCUTTER_FINALIZE_ARCHIVE"):
            return []
        return [
            f"Prohibited: ticket physically moved into a tickets/99_done/ path "
            f"('{ticket_path}'). Use frontmatter 'status: done' instead; "
            f"the finalize archive step sets LEAFCUTTER_FINALIZE_ARCHIVE=1 to "
            f"exempt itself (BO-400c-3-ii)."
        ]

    # Plain done/ move prohibition (BO-400c-3).
    return [
        f"Prohibited: ticket physically located at a done/ path ('{ticket_path}'). "
        f"Use frontmatter 'status: done' instead of moving the file into a done/ "
        f"subfolder (BO-400c-3)."
    ]


def _check_unchecked_tasks(
    agents: dict,
    impl_tasks: dict[str, int],
    agent_requires_section: dict[str, bool],
    ticket_path: str,
) -> list[str]:
    """Check #6: signed_off agents with ``requires_ticket_section: true`` must have no unchecked tasks.

    Algorithm (per ticket spec §Q7):
    - For each agent whose frontmatter status is ``signed_off``:
      - If ``requires_ticket_section`` is absent or ``false`` in the registry: skip (backward-compat).
      - If ``requires_ticket_section`` is ``true`` and the ``### <name>`` section is absent
        in ``## Implementation Tasks``: emit a stderr warning (not a hard error).
      - If the section is present and contains unchecked ``- [ ]`` items: violation (hard error).

    Args:
        agents: The ``agents:`` mapping from ticket frontmatter.
        impl_tasks: Mapping of agent name to unchecked item count from
            ``_parse_impl_tasks_section()``.
        agent_requires_section: Mapping of agent id to ``requires_ticket_section`` flag
            from ``load_agent_registry()``. An empty dict (fail-open) produces no violations.
        ticket_path: Ticket file path used in warning messages.

    Returns:
        List of violation strings (hard errors). Absent-section warnings are emitted to
        stderr directly and do not appear in the returned list.
    """
    violations: list[str] = []

    for name, raw_value in agents.items():
        status = _extract_agent_status(raw_value)
        if status != "signed_off":
            continue
        if not agent_requires_section.get(name, False):
            continue
        if name not in impl_tasks:
            print(
                f"WARNING: {ticket_path}: agent '{name}' is signed_off and "
                f"requires_ticket_section=true but '### {name}' is absent from "
                f"## Implementation Tasks (section may be legitimately absent)",
                file=sys.stderr,
            )
            continue
        unchecked_count = impl_tasks[name]
        if unchecked_count > 0:
            violations.append(
                f"agent '{name}' is signed_off but has {unchecked_count} unchecked "
                f"task(s) in '### {name}' under ## Implementation Tasks"
            )

    return violations


# ---------------------------------------------------------------------------
# Cross-layer seam answer checks (BP-1100g-5-i) — re-exported from the
# dedicated _cross_layer_seam_checks module so this file stays under its
# 400-line budget. `from _signoff_parity_checks import
# check_cross_layer_seam_answer` (the import surface test-writer built
# against) keeps working via this re-export.
# ---------------------------------------------------------------------------

from _cross_layer_seam_checks import (  # noqa: E402, F401
    check_cross_layer_seam_answer,
    extract_cross_layer_seam_answers,
)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-08-31 [python-coder/BP-1100g-5-i]: Re-exported check_cross_layer_seam_answer
  and extract_cross_layer_seam_answers from the new _cross_layer_seam_checks.py
  module (kept out of this file to preserve its 400-line budget — it was
  already at 414 stripped lines before this ticket). Wired into
  check_ticket_signoff_parity.py's _validate_ticket_content().
- 2026-07-14 [python-coder/BO-400c-3]: Extended _check_done_folder_prohibition
  with an ``old_path`` keyword-only argument for move-based detection (BO-400c-3-i),
  added ``/99_done/`` detection (BO-400c-3-ii), and added the
  LEAFCUTTER_FINALIZE_ARCHIVE env-flag carve-out. When old_path is absent, the
  check falls back to the original presence-based logic for backward compat with
  callers that do not supply rename info. Added ``import os`` at module level.
- 2026-05-15 15:10 [python-coder/file-size-fix]: Extracted from check_ticket_signoff_parity.py
  to keep each file under the 400-line budget. Contains all parsing helpers
  (load_components_registry, load_agent_registry, _parse_frontmatter,
  _parse_signoffs_section, _parse_impl_tasks_section, _build_signoffs_map,
  _classify_signoff_line) and all parity-check helpers (_check_enum_membership,
  _check_parity, _check_orphans, _check_done_folder, _check_unchecked_tasks).
  Ticket 06 added load_agent_registry, _parse_impl_tasks_section, and
  _check_unchecked_tasks for check #6 (unchecked-tasks guard).
====================================================================
"""
