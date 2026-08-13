"""
MODULE: emit_entry
GOAL: CLI helper that writes a single per-file changelog entry with required
    YAML frontmatter, enforcing required fields and a canonical filename
    convention before any bytes reach disk.
BUSINESS CONTEXT: Replaces the legacy monolithic CHANGELOG.md append path.
    Three call sites funnel through this helper so the write logic lives in
    one testable place: the changelog-agent (Call site 1: standalone
    /changelog), the epic-supervisor post-completion chain (Call site 2:
    type=epic_completion), and the build-single-ticket Step 5 success path
    (Call site 3: type=ticket_completion, mirrors Call site 2 for standalone
    tickets driven by /build-feature). The existing CHANGELOG.md is
    intentionally untouched; this helper only creates new files.
ARCHITECTURE: Single-module CLI (no external dependencies beyond stdlib).
    Accepts frontmatter fields as a JSON payload via --payload flag or stdin
    (-). Validates required fields and conditional requirements, generates the
    canonical slug + filename, handles collision avoidance, then writes the
    YAML frontmatter block plus an empty ## Entry body. Prints the written
    filepath to stdout on success. Raises SystemExit(1) on validation error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Allowed values for the ``type`` frontmatter field.
VALID_TYPES: frozenset[str] = frozenset(
    {"epic_completion", "ticket_completion", "deploy_tag", "feature", "manual", "rollback"}
)

#: Path to the commit-guardian config JSON, relative to the repo root.
_CONFIG_REL_PATH: str = (
    "leafcutter/templates/scripts/commit_guardian/commit_guardian.json"
)

#: Fields that must always be present in the payload.
REQUIRED_FIELDS: tuple[str, ...] = (
    "title",
    "date",
    "time",
    "type",
    "components",
    "summary",
    "description",
)


# ---------------------------------------------------------------------------
# Self-location helpers (repo root + changelogs_dir)
# ---------------------------------------------------------------------------


def _resolve_repo_root() -> Path:
    """Compute the repository root from this script's own location.

    Supports both:
    1. Standalone package development workspace:
       __file__ = <repo_root>/scripts/changelog/emit_entry.py
       parents[2] = <repo_root> (contains .git/ as a directory or .git as a file)
    2. Consumer project environment:
       __file__ = <repo_root>/leafcutter/scripts/changelog/emit_entry.py
       parents[3] = <repo_root>

    In a standard git checkout, ``parents[2]/.git`` is a directory.
    In a git worktree, ``parents[2]/.git`` is a **file** (containing
    ``gitdir: <path>``). ``.exists()`` returns ``True`` for both cases, so
    this function correctly identifies the worktree root in both environments.
    Using ``.is_dir()`` would fail in worktrees because ``.git`` is a file
    there, causing the function to fall through to the wrong ``parents[3]``
    path.

    Returns:
        Absolute Path of the repository root.
    """
    resolved_self = Path(__file__).resolve()
    p2 = resolved_self.parents[2]
    if (p2 / ".git").exists():
        return p2
    return resolved_self.parents[3]


def _load_changelogs_dir(repo_root: Path) -> str:
    """Read ``changelogs_dir`` from the commit-guardian config JSON.

    Looks for ``<repo_root>/leafcutter/templates/scripts/commit_guardian/
    commit_guardian.json`` and returns the value of the ``changelogs_dir``
    key.  Falls back to ``"changelogs"`` when the file or key is absent so
    that unusual setups (missing template, partial package checkout) degrade
    gracefully rather than crashing.

    Args:
        repo_root: Absolute path of the repository root, as returned by
            :func:`_resolve_repo_root`.

    Returns:
        The changelogs directory name (relative to *repo_root*), defaulting
        to ``"changelogs"`` when the config cannot be read.
    """
    config_path = repo_root / _CONFIG_REL_PATH
    try:
        with config_path.open(encoding="utf-8") as fh:
            config = json.load(fh)
        return str(config.get("changelogs_dir", "changelogs"))
    except (OSError, json.JSONDecodeError, KeyError):
        return "changelogs"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_payload(payload: dict[str, Any]) -> None:
    """Validate that required fields are present and enum values are legal.

    Performs four checks in order:
    1. All ``REQUIRED_FIELDS`` keys exist in ``payload``.
    2. ``payload["type"]`` is a member of ``VALID_TYPES``.
    3. When ``payload["type"] == "epic_completion"``, ``payload["epic"]``
       must also be present.
    4. When ``payload["type"] == "ticket_completion"``, ``payload["ticket"]``
       must also be present (the ticket basename or title — mirrors the
       ``epic`` requirement for epic_completion entries).

    Args:
        payload: Dictionary of frontmatter fields passed by the caller.

    Raises:
        ValueError: If any required field is missing, the type is unknown,
            or either of the conditional ``epic`` / ``ticket`` requirements
            is not satisfied.
    """
    for field in REQUIRED_FIELDS:
        if field not in payload:
            raise ValueError(  # noqa: TRY003
                f"Missing required field: '{field}'. "
                f"Required fields are: {', '.join(REQUIRED_FIELDS)}"
            )

    entry_type = payload["type"]
    if entry_type not in VALID_TYPES:
        raise ValueError(  # noqa: TRY003
            f"Unknown type value: '{entry_type}'. "
            f"Allowed values are: {', '.join(sorted(VALID_TYPES))}"
        )

    if entry_type == "epic_completion" and "epic" not in payload:
        raise ValueError(  # noqa: TRY003
            "Field 'epic' is required when type='epic_completion' but was not provided."
        )

    if entry_type == "ticket_completion" and "ticket" not in payload:
        raise ValueError(  # noqa: TRY003
            "Field 'ticket' is required when type='ticket_completion' but was not provided."
        )

    breaking = payload.get("breaking", False)
    if breaking:
        migration_steps = payload.get("migration_steps")
        if not migration_steps or not isinstance(migration_steps, list) or len(migration_steps) == 0:
            raise ValueError(  # noqa: TRY003
                "Field 'migration_steps' must be a non-empty list when breaking=True"
            )


# ---------------------------------------------------------------------------
# Slug generation
# ---------------------------------------------------------------------------


def slugify(title: str) -> str:
    """Convert a title string into a URL-safe, lowercase hyphenated slug.

    Transformation steps:
    1. Lowercase the input.
    2. Replace every run of non-alphanumeric characters with a single hyphen.
    3. Strip leading and trailing hyphens.

    Args:
        title: Human-readable title string (e.g. ``"My Epic: Deploy v2 (hotfix)"``).

    Returns:
        Canonical slug string (e.g. ``"my-epic-deploy-v2-hotfix"``).
    """
    lowered = title.lower()
    hyphenated = re.sub(r"[^a-z0-9]+", "-", lowered)
    return hyphenated.strip("-")


# ---------------------------------------------------------------------------
# Filename generation with collision avoidance
# ---------------------------------------------------------------------------


def generate_filename(date: str, time_str: str, slug: str, output_dir: Path) -> Path:
    """Generate a canonical changelog entry filename, avoiding collisions.

    The base filename follows the pattern ``YYYY-MM-DD-HHMM-<slug>.md``
    where ``HHMM`` is the ``time_str`` with the colon stripped.

    If the target file already exists, appends ``-2``, ``-3``, etc. before
    the ``.md`` extension until a free path is found.

    Args:
        date: ISO-8601 date string in ``YYYY-MM-DD`` format.
        time_str: Time string in ``HH:MM`` format.
        slug: Pre-computed slug from :func:`slugify`.
        output_dir: Directory where the file will be written.

    Returns:
        Absolute :class:`~pathlib.Path` for the new changelog entry file.
    """
    time_compact = time_str.replace(":", "")
    base_stem = f"{date}-{time_compact}-{slug}"
    candidate = output_dir / f"{base_stem}.md"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = output_dir / f"{base_stem}-{counter}.md"
        if not candidate.exists():
            return candidate
        counter += 1


# ---------------------------------------------------------------------------
# YAML serialisation (stdlib only)
# ---------------------------------------------------------------------------


def _yaml_value(value: Any) -> str:
    """Serialise a single frontmatter value to a YAML-compatible string.

    Handles strings, integers, and lists of strings. Other types are
    converted via ``str()``.

    Args:
        value: The Python value to serialise.

    Returns:
        A YAML-safe inline representation of the value.
    """
    if isinstance(value, list):
        if not value:
            return "[]"
        items = "\n".join(f"  - {item}" for item in value)
        return f"\n{items}"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    # String: quote if contains special chars or is empty
    text = str(value)
    if not text or any(c in text for c in (':', '#', '{', '}', '[', ']', ',', '&', '*', '?', '|', '-', '<', '>', '=', '!', '%', '@', '`', '"', "'")):
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text


def build_frontmatter(payload: dict[str, Any]) -> str:
    """Render the YAML frontmatter block for a changelog entry.

    Emits required fields first (in the order defined by REQUIRED_FIELDS),
    followed by any optional fields that are present in payload.

    Args:
        payload: Validated dictionary of frontmatter fields. Must have already
            passed validate_payload(); no additional validation is performed here.

    Returns:
        Complete YAML frontmatter string, delimited by triple-dash markers and
        terminated with a newline. Ready to be written directly to a file.
    """
    optional_order = ["epic", "pr", "adrs", "diagrams", "tickets", "commits", "breaking", "migration_steps"]
    lines = ["---"]
    for field in REQUIRED_FIELDS:
        val = _yaml_value(payload[field])
        lines.append(f"{field}: {val}")
    for field in optional_order:
        if field in payload:
            val = _yaml_value(payload[field])
            lines.append(f"{field}: {val}")
    # Any remaining keys not in required or optional_order
    known = set(REQUIRED_FIELDS) | set(optional_order)
    for key, value in payload.items():
        if key not in known:
            val = _yaml_value(value)
            lines.append(f"{key}: {val}")
    lines.append("---")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Main write function
# ---------------------------------------------------------------------------


def emit_entry(
    payload: dict[str, Any],
    changelog_dir: Optional[str | Path] = None,
) -> Path:
    """Validate the payload, generate the filename, and write the entry file.

    The written file contains:
    - A YAML frontmatter block (``---`` delimited) with all provided fields.
    - A bare ``## Entry`` section heading as the body placeholder.

    The ``changelog_dir`` is created with ``mkdir -p`` semantics if it does
    not exist; a missing directory is not a fatal error.

    When ``changelog_dir`` is ``None`` (the default), the output directory is
    derived from this script's own ``__file__`` location via
    :func:`_resolve_repo_root` and :func:`_load_changelogs_dir`.  This ensures
    that the entry always lands in the correct worktree's ``changelogs/``
    directory regardless of the calling process's CWD.

    When ``changelog_dir`` is an absolute path it is used directly.  When it
    is a relative path it is resolved against the *repo root* (computed from
    ``__file__``), **not** the CWD, so callers remain CWD-agnostic.

    Args:
        payload: Dictionary of frontmatter fields. Must pass :func:`validate_payload`.
        changelog_dir: Filesystem path to the directory where the entry file
            will be written.  Accepts ``str``, :class:`~pathlib.Path`, or
            ``None``.  ``None`` uses the config-derived default.

    Returns:
        The :class:`~pathlib.Path` of the written file.

    Raises:
        ValueError: If payload validation fails (see :func:`validate_payload`).
        OSError: If the file cannot be written due to a filesystem error.
    """
    validate_payload(payload)

    repo_root = _resolve_repo_root()

    if changelog_dir is None:
        changelogs_rel = _load_changelogs_dir(repo_root)
        output_dir = repo_root / changelogs_rel
    else:
        p = Path(changelog_dir)
        output_dir = p if p.is_absolute() else repo_root / p

    output_dir.mkdir(parents=True, exist_ok=True)

    slug = slugify(payload["title"])
    filepath = generate_filename(payload["date"], payload["time"], slug, output_dir)

    frontmatter = build_frontmatter(payload)
    content = frontmatter + "\n## Entry\n"

    filepath.write_text(content, encoding="utf-8")
    return filepath


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Construct the argument parser for the emit_entry CLI.

    Returns:
        Configured :class:`~argparse.ArgumentParser` instance.
    """
    parser = argparse.ArgumentParser(
        prog="emit_entry",
        description=(
            "Write a per-file changelog entry with YAML frontmatter. "
            "Pass frontmatter fields as a JSON object via --payload or on stdin (-)."
        ),
    )
    parser.add_argument(
        "--changelog-dir",
        required=False,
        default=None,
        metavar="DIR",
        help=(
            "Directory where the changelog entry file will be written. "
            "When omitted, derived from the script's own location and the "
            "changelogs_dir key in commit_guardian.json."
        ),
    )
    parser.add_argument(
        "--payload",
        metavar="JSON",
        help=(
            "JSON object containing frontmatter fields. "
            "Use '-' to read from stdin instead."
        ),
    )
    return parser


def main(argv: list[str] | None = None) -> None:
    """CLI entry point for emit_entry.

    Parses arguments, loads the JSON payload (from --payload or stdin),
    calls :func:`emit_entry`, and prints the written filepath to stdout.

    When ``--changelog-dir`` is omitted the output directory is derived from
    the script's own ``__file__`` location (see :func:`emit_entry` for
    details).

    Args:
        argv: Argument list (defaults to ``sys.argv[1:]`` when ``None``).

    Raises:
        SystemExit: With code 1 on validation error or missing arguments;
            code 0 on success.
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Load JSON payload
    if args.payload is None or args.payload == "-":
        try:
            raw = sys.stdin.read()
        except KeyboardInterrupt:
            sys.exit(1)
    else:
        raw = args.payload

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"ERROR: Invalid JSON payload: {exc}", file=sys.stderr)
        sys.exit(1)

    try:
        written_path = emit_entry(payload, args.changelog_dir)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    print(str(written_path))


if __name__ == "__main__":
    main()


# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-13 10:15 [python-coder/TICKET-20260513]: Created module. (#EPIC-LeafcutterMVP/01)
#   Implements the per-file changelog write path described in ADR-019.
#   Stdlib-only (no external dependencies) to keep the leafcutter
#   package self-contained. CLI accepts JSON payload via --payload flag or
#   stdin (-) to handle large or complex payloads without shell quoting issues.
#   _yaml_value handles list/int/bool/string serialisation; strings containing
#   YAML special characters are double-quoted. Collision avoidance uses a
#   simple counter suffix (-2, -3, ...) before the .md extension.
# - 2026-05-14 13:30 [Claude/TICKET-20260514-Agent_Skill_Registry_Audit]: (#EPIC-LeafcutterMVP/01)
#   Added "ticket_completion" to VALID_TYPES. The changelog-agent needed it
#   when generating the entry for PR #77 (single-ticket drive) — without it,
#   the agent fell back to "manual", which loses the semantic that this was
#   a completed-ticket entry. Shipped without type-specific required-field
#   validation. Mirror test in leafcutter/tests/test_emit_entry.py
#   updated to match.
# - 2026-05-14 15:00 [TICKET-20260514-Fix_Tooling_Gaps]: Tightened the (#EPIC-LeafcutterMVP/01)
#   13:30 addition by adding a symmetric conditional requirement on the
#   'ticket' field (mirrors the existing 'epic' requirement on
#   'epic_completion'). This is Call site 3 — the build-single-ticket
#   Step 5 success path now writes a per-file entry when a standalone-ticket
#   drive completes, closing the asymmetry where epic PRs had changelog
#   entries but single-ticket PRs did not. The 'ticket' requirement is a
#   strict superset of the 13:30 schema — every payload that validated
#   before still validates, provided callers supply a 'ticket' field
#   (which the new build-single-ticket Step 5b recipe does by design).
# - 2026-05-14 10:10 [python-coder/TICKET-20260514-Business_Language_Changelog_Format]: (#EPIC-LeafcutterMVP/01)
#   Added 'summary' to REQUIRED_FIELDS (business-language one-liner, making
#   changelog entries accessible to non-engineers). Added 'adrs' and 'diagrams'
#   to optional_order in build_frontmatter (structured traceability links to
#   architecture decisions and diagrams). Field naming resolved to 'diagrams'
#   per original spec (ticket Open Question §0). This is a breaking change for
#   all three call sites — changelog-agent, epic-supervisor, and
#   build-single-ticket Step 5b payloads are updated in the same PR.
# - 2026-05-18 14:05 [python-coder/TICKET-20260518-EmitEntry_CWD_SelfLocation]: (#TICKETLESS reason=standalone-ticket-closeout)
#   Replaced CWD-relative output resolution with __file__-based self-location.
#   Added _resolve_repo_root() (parents[3] from script's own path) and
#   _load_changelogs_dir(repo_root) (reads changelogs_dir from commit_guardian.json
#   template, falls back to "changelogs"). emit_entry() changelog_dir parameter
#   is now Optional; None triggers config-derived default. Relative paths
#   supplied by callers are resolved against repo root, not CWD. --changelog-dir
#   CLI flag changed from required=True to optional (default=None). The
#   changelogs_dir key was added to
#   leafcutter/templates/commit-guardian/commit_guardian.json.
#   All three existing call sites (changelog-agent, epic-supervisor,
#   build-single-ticket) supply --changelog-dir explicitly and continue to
#   work unchanged. Fix addresses EPIC-GlossaryAutomation friction point where
#   the script wrote into the main repo's changelogs/ instead of the worktree.
# - 2026-05-26 [python-coder/EPIC-LeafcutterVersioning/01]: (#EPIC-LeafcutterVersioning/01)
#   Added optional `breaking` (bool) and `migration_steps` (list[str]) fields
#   to support automated SemVer bump decisions. Cross-validation rule: when
#   `breaking=True`, `migration_steps` must be a non-empty list — otherwise
#   validate_payload raises ValueError. When `breaking` is absent or False,
#   no migration_steps requirement is enforced. Both fields added to
#   optional_order in build_frontmatter() for stable serialisation position.
#   Backwards-compatible: existing call sites that omit these fields continue
#   to work without modification.
# - 2026-06-05 11:00 [python-coder/TICKET-20260605-emit-entry-worktree-git-root]: (#TICKETLESS reason=standalone-ticket-fix)
#   Fixed _resolve_repo_root() to support git worktrees. In a worktree, .git
#   is a file (not a directory), so the original .is_dir() check returned
#   False and the function incorrectly fell through to parents[3]. Changed
#   .is_dir() to .exists() so the check passes for both directory (.git/ in
#   standard checkouts) and file (.git in worktrees). Updated docstring to
#   explain the worktree layout. Added # noqa: TRY003 to pre-existing
#   raise ValueError(...) calls in validate_payload() to satisfy the
#   PostToolUse ruff hook (TRY003 violations were pre-existing). Regression
#   tests added to test_emit_entry_cwd.py covering AC-1 (worktree file),
#   AC-2 (standard directory), and a source-inspection guard.
# ====================================================================
