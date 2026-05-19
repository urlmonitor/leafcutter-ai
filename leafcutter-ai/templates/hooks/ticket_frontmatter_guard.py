"""
MODULE: ticket_frontmatter_guard.py
GOAL: PostToolUse hook that gives Claude blocking feedback when a tickets/**/*.md
    file is created or edited without valid YAML frontmatter.
BUSINESS CONTEXT: Ticket frontmatter (per EPIC-DocTraceability ticket 15) is the
    machine-readable layer that lets agents and tooling resolve dependencies,
    components, and status across the ticket tree. Catching violations the moment
    a ticket is written keeps the agent in a tight self-correction loop instead
    of producing structurally invalid tickets that only fail at commit time.
ARCHITECTURE: Schema mirrors scripts/commit_guardian/commit_guardian.json
    (ticket_frontmatter section) and validate_ticket_file from
    scripts/commit_guardian/frontmatter_validators.py (currently unmerged on
    EPIC-DocTraceability). The hook is intentionally self-contained so it works
    on main today; once the EPIC merges, its implementation can be replaced by a
    thin call into validate_ticket_file.

PostToolUse hook contract:
- Exit 0 with no JSON              = silently allow
- Exit 0 with {decision: "block"}  = inject the reason back to Claude (agent self-corrects)
"""
import json
import sys
from datetime import date
from pathlib import Path

REQUIRED_FIELDS = ("title", "status", "components", "created", "depends_on")
ALLOWED_STATUSES = ("todo", "in_progress", "blocked", "done", "deferred")
ALLOWED_TYPES = ("epic",)
ALLOWED_AGENT_STATUSES = ("not_needed", "needed", "signed_off", "failed")

import json as _json
from pathlib import Path as _Path

_DOC_TYPES_JSON = (
    _Path(__file__).resolve().parents[2]
    / "leafcutter" / "config" / "doc_types.json"
)
_DOC_TYPES_CACHE: dict | None = None


def _load_doc_types() -> dict:
    global _DOC_TYPES_CACHE
    if _DOC_TYPES_CACHE is not None:
        return _DOC_TYPES_CACHE
    if _DOC_TYPES_JSON.exists():
        try:
            with open(_DOC_TYPES_JSON, encoding="utf-8") as f:
                data = _json.load(f)
            _DOC_TYPES_CACHE = data.get("doc_types", {})
            return _DOC_TYPES_CACHE
        except (ValueError, OSError):
            pass
    # fallback: accept any string (no blocking on missing file)
    _DOC_TYPES_CACHE = {}
    return _DOC_TYPES_CACHE


def find_project_root(start: Path) -> Path | None:
    """Walk up from *start* to the first ancestor that contains pyproject.toml.

    Args:
        start: Path to begin the search from.

    Returns:
        The project root, or None when no pyproject.toml is found within 15 levels.
    """
    cur = start
    for _ in range(15):
        if (cur / "pyproject.toml").exists():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent
    return None


def parse_frontmatter(content: str) -> dict | None:
    """Return the YAML mapping at the top of *content*, or None.

    Args:
        content: Full text content of a markdown file.

    Returns:
        The parsed mapping when present and well-formed; None otherwise.
    """
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    raw = content[3:end].strip()
    try:
        import yaml
    except ImportError:
        return None
    try:
        parsed = yaml.safe_load(raw)
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _check_required(fm: dict) -> list[str]:
    """Report missing required ticket frontmatter fields.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        One error string per missing or null required field.
    """
    return [
        f"Missing required field: '{field}'"
        for field in REQUIRED_FIELDS
        if field not in fm or fm[field] is None
    ]


def _check_status(fm: dict) -> list[str]:
    """Report a ``status`` value that is not in the allowed enum.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        Error list with at most one entry.
    """
    status = fm.get("status")
    if status is None or status in ALLOWED_STATUSES:
        return []
    return [f"Invalid status '{status}'. Allowed: {', '.join(ALLOWED_STATUSES)}"]


def _check_type(fm: dict) -> list[str]:
    """Report a ``type`` value that is not in the allowed enum.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        Error list with at most one entry. ``type`` is optional.
    """
    ticket_type = fm.get("type")
    if ticket_type is None or ticket_type in ALLOWED_TYPES:
        return []
    return [f"Invalid type '{ticket_type}'. Allowed (optional): {', '.join(ALLOWED_TYPES)}"]


def _check_components_shape(fm: dict) -> list[str]:
    """Report a non-list ``components`` value.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        Error list with at most one entry.
    """
    components = fm.get("components")
    if components is None or isinstance(components, list):
        return []
    return ["'components' must be a list"]


def _check_files_touched(fm: dict) -> list[str]:
    """Report a non-list ``files_touched`` value.

    ``files_touched`` is optional; when present it must be a list of strings.
    Each entry is a relative path hint used by the supervisor for parallelism
    gating. Individual paths are not verified on disk (files may not exist yet
    at ticket-authoring time).

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        Error list with at most one entry. Empty when field is absent.
    """
    files_touched = fm.get("files_touched")
    if files_touched is None:
        return []
    if not isinstance(files_touched, list):
        return ["'files_touched' must be a list of relative path strings (or omit it)"]
    non_strings = [e for e in files_touched if not isinstance(e, str)]
    if non_strings:
        return [
            f"'files_touched' entries must be strings; got non-string value(s): "
            f"{non_strings!r}"
        ]
    return []


def _extract_agent_status(raw_value: object) -> str | None:
    """Extract the effective status string from an agents map entry.

    Accepts both the scalar form (``signed_off``) and the nested-map form
    (``{status: signed_off, grandfathered: true}``) introduced by
    TICKET-20260511 Deliverable 2 (Option A — backward-compatible).

    Args:
        raw_value: The raw Python value for a single agent key. Either a
            ``str`` (scalar) or a ``dict`` (nested-map).

    Returns:
        The effective status string, or ``None`` when the shape is unrecognised.
    """
    if isinstance(raw_value, str):
        return raw_value
    if isinstance(raw_value, dict):
        status = raw_value.get("status")
        if isinstance(status, str):
            return status
    return None


def _check_bool_field(fm, f):
    v = fm.get(f)
    if v is None or isinstance(v, bool): return []
    return [f"'{f}' must be bool (true/false); got {type(v).__name__} {v!r}"]


def _check_required_tristate(fm: dict, field: str) -> list[str]:
    """Validate a required tri-state field (true | false | null; absent = error).

    This is distinct from _check_bool_field: that function accepts absence
    silently (the field is optional). This function REQUIRES the field to be
    present; only the key being missing triggers an error. Values of True,
    False, and None (YAML null) are all valid.

    Args:
        fm: Parsed frontmatter mapping.
        field: The field name to check (e.g. 'requires_diagram').

    Returns:
        Error list with at most one entry (the absence error).
    """
    if field not in fm:
        return [
            f"'{field}': field missing — agent must set true, false, or null "
            f"(true=needed, false=considered/not-needed, null=not-applicable)"
        ]
    v = fm[field]
    if v is None or isinstance(v, bool):
        return []
    return [
        f"'{field}': invalid value {v!r} — must be true, false, or null"
    ]


def _check_agents(fm: dict) -> list[str]:
    """Report an ``agents`` map whose values fall outside the allowed enum.

    ``agents`` is optional; when present it must be a mapping of agent-name
    strings to status strings or nested maps of the form
    ``{status: <status>, grandfathered: true}``. Each resolved status must be
    in ``{not_needed, needed, signed_off, failed}``.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        One error per invalid agent-status pair. Empty when field is absent
        or all values are valid.
    """
    agents = fm.get("agents")
    if agents is None:
        return []
    if not isinstance(agents, dict):
        return [
            "'agents' must be a map of agent-name → status "
            "(e.g. agents:\\n  python-coder: needed)"
        ]
    errors: list[str] = []
    for agent_name, raw_value in agents.items():
        status = _extract_agent_status(raw_value)
        if status is None:
            errors.append(
                f"'agents.{agent_name}' has unrecognised value '{raw_value!r}'. "
                f"Expected a status string or {{status: <status>, grandfathered: true}} map."
            )
        elif status not in ALLOWED_AGENT_STATUSES:
            allowed = " | ".join(ALLOWED_AGENT_STATUSES)
            errors.append(
                f"'agents.{agent_name}' has invalid status '{status}'. "
                f"Allowed: {allowed}"
            )
    return errors


def _depends_candidates(entry: str, ticket_path: Path) -> list[Path]:
    """Build the list of paths a ``depends_on`` filename may resolve to.

    Args:
        entry: Filename listed in ``depends_on``.
        ticket_path: Absolute path to the ticket being validated.

    Returns:
        Candidate paths in resolution order: sibling, sibling/done/, then
        epic-root if the ticket itself sits in a ``done/`` subfolder.
    """
    parent = ticket_path.parent
    candidates = [parent / entry, parent / "done" / entry]
    if parent.name == "done":
        candidates.append(parent.parent / entry)
    return candidates


def _check_depends_on(fm: dict, ticket_path: Path) -> list[str]:
    """Report malformed entries or unresolved sibling references.

    Args:
        fm: Parsed frontmatter mapping.
        ticket_path: Absolute path to the ticket being validated.

    Returns:
        One error per malformed or missing dependency.
    """
    depends_on = fm.get("depends_on")
    if depends_on is None:
        return []
    if not isinstance(depends_on, list):
        return ["'depends_on' must be a list (use [] when there are no dependencies)"]

    errors: list[str] = []
    for entry in depends_on:
        if not isinstance(entry, str):
            errors.append(f"'depends_on' entry must be a string filename, got: {entry!r}")
            continue
        if not any(c.exists() for c in _depends_candidates(entry, ticket_path)):
            errors.append(f"'depends_on' references missing file: '{entry}'")
    return errors


def _check_status_folder(fm: dict, ticket_path: Path) -> list[str]:
    """Report a status that contradicts the file's location under ``done/``.

    Args:
        fm: Parsed frontmatter mapping.
        ticket_path: Absolute path to the ticket being validated.

    Returns:
        Error list with at most one entry.
    """
    status = fm.get("status")
    if not status or status == "done":
        return []
    if "done" not in ticket_path.parts:
        return []
    return [f"File is in a done/ folder but status='{status}' (expected 'done')"]


def _check_requires_documentation(fm: dict) -> list[str]:
    """Report invalid entries in the optional requires_documentation list.

    Args:
        fm: Parsed frontmatter mapping.

    Returns:
        One error per invalid entry; empty when field is absent or all valid.
    """
    value = fm.get("requires_documentation")
    if value is None:
        return []  # Optional field
    if not isinstance(value, list):
        return ["'requires_documentation' must be a list (e.g. [how_to, reference])"]
    known = _load_doc_types()
    if not known:
        return []  # doc_types.json absent — permissive fallback
    errors: list[str] = []
    for entry in value:
        if not isinstance(entry, str):
            errors.append(f"'requires_documentation' entries must be strings; got {entry!r}")
        elif entry not in known:
            errors.append(
                f"unknown doc_type in requires_documentation: {entry}; "
                f"valid values: {', '.join(sorted(known.keys()))}"
            )
    return errors


def validate(fm: dict, ticket_path: Path) -> list[str]:
    """Aggregate all blocking errors for a parsed ticket frontmatter.

    Args:
        fm: Parsed frontmatter mapping.
        ticket_path: Absolute path to the ticket file being validated.

    Returns:
        Concatenated error list across every individual check.
    """
    errors: list[str] = []
    errors.extend(_check_required(fm))
    errors.extend(_check_status(fm))
    errors.extend(_check_type(fm))
    errors.extend(_check_components_shape(fm))
    errors.extend(_check_depends_on(fm, ticket_path))
    errors.extend(_check_status_folder(fm, ticket_path))
    errors.extend(_check_files_touched(fm))
    errors.extend(_check_required_tristate(fm, "requires_diagram"))
    errors.extend(_check_required_tristate(fm, "requires_adr"))
    errors.extend(_check_requires_documentation(fm))
    errors.extend(_check_agents(fm))
    return errors


def template(ticket_path: Path) -> str:
    """Build a minimal valid frontmatter block tailored to *ticket_path*.

    Args:
        ticket_path: Absolute path to the ticket file the agent is creating.

    Returns:
        Multi-line frontmatter the agent can paste at the top of the file.
    """
    today = date.today().isoformat()
    title = ticket_path.stem.replace("_", " ").strip()
    if ticket_path.name.lower().startswith("master_plan"):
        return (
            "---\n"
            f"title: \"{title or 'EPIC Master Plan'}\"\n"
            "type: epic\n"
            "status: in_progress\n"
            "components:\n"
            "  - <component_id>\n"
            f"created: {today}\n"
            "depends_on: []\n"
            "---\n"
        )
    return (
        "---\n"
        f"title: \"{title or 'Ticket Title'}\"\n"
        "status: todo\n"
        "components:\n"
        "  - <component_id>\n"
        f"created: {today}\n"
        "depends_on: []\n"
        "priority: medium\n"
        "---\n"
    )


def _resolve_ticket_path(payload: dict) -> tuple[Path, str] | None:
    """Extract the target ticket path from a PostToolUse payload.

    Returns None for any payload that should be silently ignored: missing
    file path, non-markdown, README.md, project root not found, or path
    outside ``tickets/``. The caller exits 0 in those cases.

    Args:
        payload: Parsed PostToolUse JSON payload.

    Returns:
        ``(absolute_path, posix_relative_path)`` for in-scope ticket files,
        or None when the hook should no-op.
    """
    tool_input = payload.get("tool_input") or {}
    raw = tool_input.get("file_path") or tool_input.get("path") or ""
    if not raw:
        return None
    try:
        file_path = Path(raw).resolve()
    except Exception:
        return None
    if file_path.suffix.lower() != ".md" or file_path.name.lower() == "readme.md":
        return None
    project_root = find_project_root(file_path)
    if project_root is None:
        return None
    try:
        rel = file_path.relative_to(project_root).as_posix()
    except ValueError:
        return None
    if not rel.startswith("tickets/"):
        return None
    if not file_path.exists():
        return None
    return file_path, rel


def _missing_message(file_path: Path, rel: str) -> str:
    """Build the block reason when frontmatter is entirely absent.

    Args:
        file_path: Absolute path to the ticket file.
        rel: Project-relative POSIX path used in the message header.

    Returns:
        Multi-line reason string ready to send back to Claude.
    """
    return (
        "TICKET FRONTMATTER MISSING\n"
        "==========================\n"
        f"File: {rel}\n"
        "\n"
        "Every ticket needs YAML frontmatter at the top. Add this block:\n"
        "\n"
        f"{template(file_path)}"
        "\n"
        "Required fields: title, status, components, created, depends_on.\n"
        "Allowed status: todo | in_progress | blocked | done | deferred.\n"
        "`depends_on` is a list of sibling filenames (use [] when none).\n"
        "Run the 'create-ticket' skill for the full schema, structure, and granularity rules."
    )


def _violation_message(rel: str, errors: list[str]) -> str:
    """Build the block reason when frontmatter is present but invalid.

    Args:
        rel: Project-relative POSIX path used in the message header.
        errors: One-line strings produced by the per-concern validators.

    Returns:
        Multi-line reason string ready to send back to Claude.
    """
    bullets = "\n".join(f"  - {e}" for e in errors)
    return (
        "TICKET FRONTMATTER VIOLATION\n"
        "============================\n"
        f"File: {rel}\n"
        "\n"
        f"Issues:\n{bullets}\n"
        "\n"
        "Allowed status: todo | in_progress | blocked | done | deferred.\n"
        "Allowed type (optional): epic.\n"
        "`depends_on` references must exist in the same epic folder (or its done/ subfolder).\n"
        "Run the 'create-ticket' skill for the full schema."
    )


def _emit_block(reason: str) -> None:
    """Print the PostToolUse block decision JSON and exit 0.

    Args:
        reason: Human-readable explanation injected back to Claude.
    """
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main() -> None:
    """Entry point. Reads the PostToolUse payload from stdin and emits a decision."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)

    resolved = _resolve_ticket_path(payload)
    if resolved is None:
        sys.exit(0)
    file_path, rel = resolved

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        sys.exit(0)

    fm = parse_frontmatter(content)
    if fm is None:
        _emit_block(_missing_message(file_path, rel))

    errors = validate(fm, file_path)
    if errors:
        _emit_block(_violation_message(rel, errors))

    sys.exit(0)


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-06 11:30 [Hendrik/Claude]: Initial implementation. PostToolUse hook on
  Edit|Write that validates ticket frontmatter immediately after the file is
  written, blocking with feedback so the agent self-corrects. Schema mirrors
  EPIC-DocTraceability ticket 15 to stay forward-compatible with the upcoming
  validate_ticket_file in frontmatter_validators.py.
- 2026-05-06 12:00 [Hendrik/Claude]: Split validate() and main() into per-concern
  helpers (_check_*, _resolve_ticket_path, _emit_block, _missing_message,
  _violation_message) to clear the cyclomatic-complexity guardrail (max 15).
- 2026-05-12 00:00 [Hendrik/Claude]: Extended _check_agents for TICKET-20260511
  Deliverable 2 (Option A). Added _extract_agent_status() helper that accepts both
  the scalar form (``signed_off``) and the nested-map form
  (``{status: signed_off, grandfathered: true}``). Backward-compatible: existing
  scalar-format tickets continue to pass without modification.
- 2026-05-08 17:00 [Hendrik/Claude]: Added ALLOWED_AGENT_STATUSES constant and two
  new optional-field validators: _check_files_touched (list-of-strings) and
  _check_agents (map-of-name→enum). Both wired into validate(). Backward-compatible:
  absent fields pass without error. Part of EPIC-AgentSupervisor ticket 03.
- 2026-05-14 20:00 [EPIC-ArchitectureDocsEnforcement/ticket 01]: Added _check_bool_field; wired requires_diagram+requires_adr.
- 2026-05-14 00:00 [EPIC-ArchitectureDocsEnforcement/ticket 08]: Added _load_doc_types() loader,
  _check_requires_documentation() validator, wired into validate(). Field is optional; absence
  passes without error. Invalid entries (non-string, unknown type) block with a clear message.
  Permissive fallback when doc_types.json is absent (no blocking).
- 2026-05-15 00:00 [EPIC-EmbeddedArchDiagramsHardening/ticket 04]: Replaced _check_bool_field
  calls for requires_diagram + requires_adr with _check_required_tristate. New helper treats
  absent key as a hard block ("agent must set true, false, or null") while accepting True, False,
  and None (YAML null) as valid. _check_bool_field itself is unchanged (used by other optional
  bool fields). Backfill script (scripts/backfill_requires_diagram_adr.py) must run before this
  change is committed. See ADR-026-requires-diagram-adr-tri-state.md.
- 2026-05-18 00:00 [EPIC-DocTraceability/05]: Verification pass — _check_required_tristate at
  line 221 already handles requires_adr as a tri-state field (true/false/null), enforced by the
  wiring at lines 398-399 in validate(). No code changes required; this entry records the
  explicit confirmation that the guard is forward-compatible with the adr-author dispatch logic
  introduced in building-epics §2.1 and ticket-wiring skill.
  (#EPIC-DocTraceability/05) (ADR-033)
====================================================================
"""
