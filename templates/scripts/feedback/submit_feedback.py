"""
MODULE: leafcutter/scripts/feedback/submit_feedback.py
GOAL: Single write chokepoint for the Central Feedback Collection System.
      Validates category, writer, and tag shapes, generates a feedback_id,
      appends one JSON line to the feedback JSONL log, and prints the
      feedback_id to stdout.
BUSINESS CONTEXT: Every agent signoff and hook finding that emits a feedback
      entry calls this script. It is the canonical enforcement point for the
      closed-category vocabulary and allowed_writers policy.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/how-to/feedback-collection.md
  - docs/explanation/why-feedback-system.md

Usage:
    python submit_feedback.py \
        --ticket <path> --phase <agent-name> \
        --category <id> --tags <a,b,c> \
        --note "<short verbatim>" \
        [--severity <low|medium|high>] \
        [--source {agent,hook}] \
        [--hook-name <name>] \
        [--outcome {warn,block}] \
        [--branch <branch-name>] \
        [--staged-files-count <N>] \
        [--addressed-by '<JSON array>']

    --addressed-by accepts a JSON array of objects, each with "type" and "ref":
        --addressed-by '[{"type":"ticket","ref":"TICKET-20260518-Fix.md"}]'
        --addressed-by '[{"type":"commit","ref":"b52d5e07"}]'
        --addressed-by '[{"type":"pr","ref":"72"}]'

    When --source hook is used, --ticket is optional and --hook-name and
    --outcome are required.

Exit codes:
    0: success (feedback_id printed to stdout)
    1: validation failure (error details on stderr)
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import secrets
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl as _fcntl  # POSIX only; not available on Windows
    _FCNTL_AVAILABLE = True
except ImportError:
    _FCNTL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Project root discovery
# ---------------------------------------------------------------------------


def _find_project_root() -> Path:
    """Walk up from this file to find the project root (directory containing .claude/).

    Used for resolving paths that live at the project root (e.g. debugging/logs/).
    For config files that live alongside the script in a portable install
    (e.g. .leafcutter/config/), use _find_config_root() instead.
    """
    current = Path(__file__).resolve().parent
    for _ in range(6):
        if (current / ".claude").is_dir():
            return current
        current = current.parent
    return Path(__file__).resolve().parents[2]


def _find_config_root() -> Path:
    """Resolve the config directory using the script's own location as anchor.

    This function anchors config resolution to the script file itself rather
    than searching for a project-level marker (.claude/).  When the script is
    deployed at <project>/.leafcutter/scripts/feedback/submit_feedback.py the
    config lives at <project>/.leafcutter/config/ — two directory levels up
    from the script file.  The same relative layout holds for the source
    location (leafcutter-ai/scripts/feedback/ → leafcutter-ai/config/).

    Returns:
        Path: Absolute path to the config directory that contains
            feedback_categories.yaml.
    """
    return Path(__file__).resolve().parents[2] / "config"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_PROJECT_ROOT = _find_project_root()
_CONFIG_DIR = _find_config_root()
_CATEGORIES_FILE = _CONFIG_DIR / "feedback_categories.yaml"
_JSONL_DEFAULT = _PROJECT_ROOT / "debugging" / "logs" / "feedback.jsonl"

VALID_SEVERITIES = ("low", "medium", "high")
VALID_SOURCES = ("agent", "hook")
VALID_OUTCOMES = ("warn", "block")
_TAG_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")


def _load_categories(config_path: Path | None = None) -> dict:
    """Load and return the categories dict keyed by category id.

    Args:
        config_path: Override path to feedback_categories.yaml. Uses the
            default package location when None.

    Returns:
        dict: Mapping from category id string to category dict.

    Raises:
        SystemExit: When the config file cannot be read or parsed.
    """
    try:
        import yaml  # type: ignore[import]
    except ImportError:
        print(
            "ERROR: PyYAML is required. Install with: pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)

    path = config_path or _CATEGORIES_FILE
    try:
        with open(path, encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except OSError as exc:
        checked_path = Path(path).resolve()
        print(
            f"ERROR: Cannot read feedback_categories.yaml.\n"
            f"  Checked path: {checked_path}\n"
            f"  OS error: {exc}\n"
            f"  To fix: Place feedback_categories.yaml at {checked_path}",
            file=sys.stderr,
        )
        sys.exit(1)

    cats: dict = {}
    for entry in data.get("categories", []):
        cats[entry["id"]] = entry
    return cats


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_category(category: str, cats: dict) -> None:
    """Raise SystemExit(1) if the category is not in the closed list.

    Args:
        category: The category id string to validate.
        cats: The loaded categories dict from _load_categories.
    """
    if category in cats:
        return
    close = difflib.get_close_matches(category, cats.keys(), n=1, cutoff=0.5)
    suggestion = f" Did you mean '{close[0]}'?" if close else ""
    print(
        f"ERROR: Unknown category '{category}'.{suggestion}",
        file=sys.stderr,
    )
    sys.exit(1)


def _validate_writer(phase: str, category: str, cats: dict) -> None:
    """Raise SystemExit(1) if phase is not in the category's allowed_writers.

    Args:
        phase: The agent name or writer id submitting feedback.
        category: The category id string.
        cats: The loaded categories dict.
    """
    allowed: list = cats[category].get("allowed_writers", [])
    if phase in allowed:
        return
    print(
        f"ERROR: Phase '{phase}' is not an allowed writer for category "
        f"'{category}'. Allowed writers: {', '.join(allowed)}",
        file=sys.stderr,
    )
    sys.exit(1)


def _validate_tags(raw_tags: str) -> list[str]:
    """Parse and validate the tags string, returning a list of clean tag strings.

    Args:
        raw_tags: Comma-separated tag string from the CLI argument.

    Returns:
        list[str]: Validated, trimmed, lowercase tags.

    Raises:
        SystemExit: When any tag fails shape validation.
    """
    if not raw_tags:
        return []
    # Trim whitespace but do NOT lowercase — uppercase tags are a shape violation
    tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
    bad: list[str] = []
    for tag in tags:
        if not _TAG_RE.match(tag):
            bad.append(tag)
    if bad:
        digit_starts = [t for t in bad if t and t[0].isdigit()]
        if digit_starts:
            print(
                f"ERROR: Tag '{digit_starts[0]}' must start with a letter "
                "(a-z), not a digit. Try renaming the tag (e.g. '26-tests' "
                "-> 'fast-tests').",
                file=sys.stderr,
            )
        else:
            print(
                f"ERROR: Tag shape validation failed for: {bad}. "
                "Tags must be lowercase, kebab-case, start with a letter, "
                "and be at most 40 characters.",
                file=sys.stderr,
            )
        sys.exit(1)
    return tags


VALID_ADDRESSED_BY_TYPES = ("ticket", "commit", "pr")


def _validate_addressed_by(raw: str | None) -> list[dict] | None:
    """Parse and validate the --addressed-by JSON string argument.

    Each element must be a dict with "type" (one of ticket/commit/pr) and
    "ref" (a non-empty string). Extra keys are accepted and preserved as-is
    to allow forward-compatible extensions.

    Args:
        raw: JSON array string from the --addressed-by CLI argument, or None.

    Returns:
        list[dict] | None: Parsed list of reference objects, or None when the
            argument was not supplied.

    Raises:
        SystemExit: When the JSON is malformed or any element fails validation.
    """
    if raw is None:
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: --addressed-by must be a valid JSON array. Parse error: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    if not isinstance(parsed, list):
        print(
            "ERROR: --addressed-by must be a JSON array (list), not "
            f"{type(parsed).__name__}.",
            file=sys.stderr,
        )
        sys.exit(1)
    for idx, item in enumerate(parsed):
        if not isinstance(item, dict):
            print(
                f"ERROR: --addressed-by element {idx} must be an object, "
                f"not {type(item).__name__}.",
                file=sys.stderr,
            )
            sys.exit(1)
        item_type = item.get("type")
        item_ref = item.get("ref")
        if item_type not in VALID_ADDRESSED_BY_TYPES:
            print(
                f"ERROR: --addressed-by element {idx} 'type' must be one of "
                f"{VALID_ADDRESSED_BY_TYPES}, got '{item_type}'.",
                file=sys.stderr,
            )
            sys.exit(1)
        if not item_ref or not isinstance(item_ref, str):
            print(
                f"ERROR: --addressed-by element {idx} 'ref' must be a non-empty string.",
                file=sys.stderr,
            )
            sys.exit(1)
    return parsed


# ---------------------------------------------------------------------------
# feedback_id generation
# ---------------------------------------------------------------------------


def _generate_feedback_id(timestamp: str, phase: str, ticket: str) -> str:
    """Generate a unique, deterministic-looking feedback_id.

    Args:
        timestamp: ISO8601 timestamp string.
        phase: Agent name or source identifier.
        ticket: Ticket path string (may be empty for hook-mode).

    Returns:
        str: Feedback id in format fb_YYYY-MM-DD_XXXXXXXX.
    """
    date_part = timestamp[:10]  # YYYY-MM-DD
    salt = secrets.token_hex(8)
    digest_input = f"{timestamp}{phase}{ticket}{salt}"
    sha8 = hashlib.sha256(digest_input.encode()).hexdigest()[:8]
    return f"fb_{date_part}_{sha8}"


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser for submit_feedback.py.

    Returns:
        argparse.ArgumentParser: Configured parser.
    """
    parser = argparse.ArgumentParser(
        description="Emit one structured feedback entry to feedback.jsonl.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--ticket", default=None, help="Ticket file path (optional in hook mode).")
    parser.add_argument("--phase", required=True, help="Agent name or hook writer id.")
    parser.add_argument("--category", required=True, help="Category id from feedback_categories.yaml.")
    parser.add_argument("--tags", default="", help="Comma-separated kebab-case tags.")
    parser.add_argument("--note", default="", help="Short verbatim note (one sentence).")
    parser.add_argument(
        "--severity",
        choices=VALID_SEVERITIES,
        default=None,
        help="Override severity. Defaults to category default_severity.",
    )
    parser.add_argument(
        "--source",
        choices=VALID_SOURCES,
        default="agent",
        help="Feedback source: 'agent' (default) or 'hook'.",
    )
    parser.add_argument(
        "--hook-name",
        default=None,
        help="Hook name (required when --source hook).",
    )
    parser.add_argument(
        "--outcome",
        choices=VALID_OUTCOMES,
        default=None,
        help="Hook outcome: 'warn' or 'block' (required when --source hook).",
    )
    parser.add_argument("--branch", default=None, help="Git branch name (hook mode).")
    parser.add_argument(
        "--staged-files-count",
        type=int,
        default=None,
        help="Number of staged files at commit time (hook mode).",
    )
    parser.add_argument(
        "--jsonl",
        default=None,
        help=f"Override JSONL output path. Default: {_JSONL_DEFAULT}",
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Override feedback_categories.yaml path.",
    )
    parser.add_argument(
        "--addressed-by",
        default=None,
        dest="addressed_by",
        help=(
            "JSON array of objects linking this issue to its fix(es). "
            "Each object must have 'type' (ticket|commit|pr) and 'ref'. "
            "Example: '[{\"type\":\"ticket\",\"ref\":\"TICKET-20260518-Fix.md\"}]'"
        ),
    )
    return parser


# ---------------------------------------------------------------------------
# Entry building helpers
# ---------------------------------------------------------------------------


def _validate_source_args(args: argparse.Namespace) -> str | None:
    """Validate source-mode required arguments.

    Args:
        args: Parsed argument namespace.

    Returns:
        str | None: Error message string when validation fails, else None.
    """
    if args.source == "hook":
        if not args.hook_name:
            return "ERROR: --hook-name is required when --source hook"
        if not args.outcome:
            return "ERROR: --outcome is required when --source hook"
    elif args.source == "agent" and not args.ticket:
        return "ERROR: --ticket is required when --source agent"
    return None


def _resolve_severity(args: argparse.Namespace, cats: dict) -> str:
    """Resolve the effective severity for this feedback entry.

    Args:
        args: Parsed argument namespace.
        cats: Loaded categories dict.

    Returns:
        str: Resolved severity string (low, medium, or high).
    """
    if args.severity:
        return args.severity
    if args.source == "hook" and args.outcome:
        return "low" if args.outcome == "warn" else "high"
    return cats[args.category].get("default_severity", "medium")


def _build_entry(
    args: argparse.Namespace,
    tags: list[str],
    severity: str,
    feedback_id: str,
    timestamp: str,
) -> dict:
    """Construct the JSONL entry dict from validated arguments.

    Args:
        args: Parsed argument namespace.
        tags: Validated tag list.
        severity: Resolved severity string.
        feedback_id: Generated feedback id.
        timestamp: ISO8601 UTC timestamp string.

    Returns:
        dict: JSONL entry ready for serialization.
    """
    entry: dict = {
        "feedback_id": feedback_id,
        "timestamp": timestamp,
        "phase": args.phase,
        "category": args.category,
        "tags": tags,
        "note": args.note,
        "severity": severity,
        "source": args.source,
    }
    if args.ticket:
        entry["ticket"] = args.ticket
    if args.source == "hook":
        entry["hook_name"] = args.hook_name
        entry["outcome"] = args.outcome
        if args.branch is not None:
            entry["branch"] = args.branch
        if args.staged_files_count is not None:
            entry["staged_files_count"] = args.staged_files_count
    if getattr(args, "addressed_by", None) is not None:
        entry["addressed_by"] = args.addressed_by
    return entry


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for submit_feedback.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 on success, 1 on validation failure).
    """
    args = _build_parser().parse_args(argv)

    err = _validate_source_args(args)
    if err:
        print(err, file=sys.stderr)
        return 1

    config_path = Path(args.config) if args.config else None
    cats = _load_categories(config_path)
    _validate_category(args.category, cats)

    if args.source == "agent":
        _validate_writer(args.phase, args.category, cats)

    tags = _validate_tags(args.tags)
    # _validate_addressed_by parses and validates the JSON; it mutates args
    # by replacing the raw string with the parsed list (or leaves it None).
    args.addressed_by = _validate_addressed_by(getattr(args, "addressed_by", None))
    severity = _resolve_severity(args, cats)

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    feedback_id = _generate_feedback_id(timestamp, args.phase, args.ticket or "")
    entry = _build_entry(args, tags, severity, feedback_id, timestamp)

    # ------------------------------------------------------------------
    # Write JSONL (atomic under concurrent writes via advisory flock)
    # ------------------------------------------------------------------
    jsonl_path = Path(args.jsonl) if args.jsonl else _JSONL_DEFAULT
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        fh = open(jsonl_path, "a", encoding="utf-8")
    except OSError as exc:
        print(f"[submit_feedback] WARNING: could not open {jsonl_path}: {exc}", file=sys.stderr)
        return 1
    with fh:
        if _FCNTL_AVAILABLE:
            _fcntl.flock(fh, _fcntl.LOCK_EX)
        try:
            fh.write(json.dumps(entry, separators=(",", ":")) + "\n")
            fh.flush()
            # Print feedback_id to stdout INSIDE the lock so stdout delivery
            # is serialised with the append, preventing empty-capture races.
            print(feedback_id)
        finally:
            if _FCNTL_AVAILABLE:
                _fcntl.flock(fh, _fcntl.LOCK_UN)

    # ------------------------------------------------------------------
    # Sidecar temp file — fallback recovery when stdout capture fails
    # ------------------------------------------------------------------
    # Write feedback_id to a deterministic-suffix temp file so calling
    # agents can recover the ID even if stdout capture returned empty.
    # The path is printed to stderr (not stdout) to avoid disrupting FB_ID.
    ts_epoch = int(datetime.now(timezone.utc).timestamp())
    sidecar_path = Path(tempfile.gettempdir()) / f"feedback_id_{ts_epoch}.txt"
    try:
        sidecar_path.write_text(feedback_id, encoding="utf-8")
        print(f"sidecar:{sidecar_path}", file=sys.stderr)
    except OSError:
        # Non-fatal: sidecar write failure does not affect the JSONL entry.
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-06-08 12:30 [python-coder/EPIC-FeedbackPortability/04_TICKET-20260608-INF-100c-4]:
#   Improved _load_categories() error message to satisfy AC INF-100c-4: when
#   feedback_categories.yaml is not found, the error now prints three lines:
#   (1) a header line, (2) "Checked path: <absolute-path>", and (3)
#   "To fix: Place feedback_categories.yaml at <path>".  This makes the error
#   actionable by labelling the checked path explicitly and providing a
#   copy-pasteable remediation command, rather than embedding the path only
#   inside an OSError string. (#EPIC-FeedbackPortability)
# - 2026-06-08 00:00 [python-coder/EPIC-FeedbackPortability/TICKET-20260608-INF-100c-1]:
#   Added _find_config_root() helper that anchors config path resolution to the
#   script's own location (Path(__file__).resolve().parents[2] / "config") rather
#   than using _find_project_root(). This ensures feedback_categories.yaml is found
#   at <leafcutter_root>/config/ regardless of where the script is deployed:
#   source (leafcutter-ai/scripts/feedback/) and deployed (.leafcutter/scripts/feedback/)
#   both resolve to two parents up + /config/. _find_project_root() is retained for
#   _JSONL_DEFAULT which must remain at the project root. (AC INF-100c-1) (#EPIC-FeedbackPortability)
# - 2026-06-03 09:00 [python-coder/EPIC-TemplateDocViolations/06]: Confirmed 2026-05-21 entry already has HH:MM (12:00); no change needed. Added this audit entry for traceability. (#EPIC-TemplateDocViolations/06)
# - 2026-05-30 12:00 [python-coder/TICKET-20260528-FeedbackCorrelationIDLoss]:
#   Wrapped JSONL append and stdout print in fcntl.flock(LOCK_EX) advisory
#   lock so concurrent writers serialise both the append and the stdout
#   print. Stdout delivery inside the lock prevents empty-capture races
#   that previously caused (submit-failed) sentinels in ticket comments.
#   Added sidecar temp file (feedback_id_<epoch>.txt in tempdir) as a
#   fallback: calling agents can read the ID from the sidecar when stdout
#   capture fails. Sidecar path is printed to stderr to avoid disrupting
#   FB_ID=$(...) capture. fcntl import wrapped in try/except ImportError
#   for Windows compatibility (falls back to unlocked path with a warning).
#   Removed bare `import os` (was unused after refactor). (#TICKET-20260528)
# - 2026-05-21 12:00 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]:
#   Replaced hardcoded parents[3] JSONL path with _find_project_root() helper
#   that walks up from __file__ looking for .claude/ directory. Also changed
#   _CONFIG_DIR to use _PROJECT_ROOT / "config" instead of parent-chain.
#   Works from both the source location (leafcutter-ai/scripts/feedback/) and
#   the deployed location (target_root/scripts/feedback/).
# - 2026-05-18 12:45 [EPIC-AgentSystemFrictionReduction/04]: Convert _JSONL_DEFAULT to __file__-relative path. (#EPIC-AgentSystemFrictionReduction/04)
#   CWD-relative Path("debugging/logs/feedback.jsonl") resolves incorrectly when
#   invoked from a worktree. Fix: Path(__file__).resolve().parents[3] / "debugging" / "logs" / "feedback.jsonl".
# - 2026-05-18 10:45 [EPIC-AgentSystemFrictionReduction/05]: Added --addressed-by argument for linking feedback to its fix. (#EPIC-AgentSystemFrictionReduction/05)
#   Optional JSON array of {type, ref} objects. Types: ticket, commit, pr.
#   Validated by _validate_addressed_by() before entry construction.
#   Additive: old entries without the field remain valid.
# - 2026-05-15 16:35 [chore/feedback-collection-kis]: Specialised the (#EPIC-LeafcutterMVP/01)
#   tag-shape error so digit-start violations emit the explicit message
#   "Tag '<name>' must start with a letter (a-z), not a digit." The
#   generic shape error is retained as a fallback for other malformed
#   tags. Why: EPIC-FeedbackCollection retro KI — the generic message
#   masked the most common authoring failure ("26-tests" rejected) and
#   left submitters guessing the rule.
# - 2026-05-15 10:20 [EPIC-FeedbackCollection/ticket-02]: Initial implementation. (#EPIC-LeafcutterMVP/01)
#   Single write chokepoint for feedback.jsonl. Validates category against
#   feedback_categories.yaml closed list, validates allowed_writers per
#   category (agent mode only), validates tag shapes via regex, generates
#   feedback_id with sha8 of timestamp+phase+ticket+salt. Hook mode added
#   (ticket 09 design) with --source, --hook-name, --outcome fields. The
#   --ticket flag is optional in hook mode. source field defaults to 'agent'
#   for backward compatibility with existing entries.
# ====================================================================
