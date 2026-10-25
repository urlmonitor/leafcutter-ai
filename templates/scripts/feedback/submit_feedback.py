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

    --jsonl <path> overrides the sink and is honoured as given. Without it the
    sink is ``feedback_sink`` from the install's build-time declaration,
    ``<output_root>/config/knowledge_sink.json`` (ADR-069; ``feedback_sink.py``).

Exit codes:
    0: success (feedback_id printed to stdout)
    1: validation failure, or the declared sink cannot be determined (error
       details on stderr; nothing on stdout, nothing written)

Output streams on success (callers parse these -- keep them stable):
    stdout: exactly one line, the feedback_id (fb_YYYY-MM-DD_xxxxxxxx).
    stderr: "sidecar:<tmpdir>/feedback_id_<epoch>.txt" -- the id-recovery
        fallback the signoff skill greps for (KI-FC-002); then
        "[submit_feedback] sink: <absolute path>" -- the resolved file the
        record was appended to (AC INF-500d-4-ii, KI-FC-001). The sink line
        is on stderr, never stdout, because callers capture stdout verbatim
        as the id; its prefix is not "sidecar:", so the recovery grep does
        not pick it up. 2026-10-08 [quick-fix/INF-500d-4-ii].

Refusal (AC INF-500d-4-i): when the declaration is absent, unreadable,
    unparseable, lacks ``feedback_sink`` / ``operational_log_root``, holds a
    relative value, names a ``feedback_sink`` that is not directly under
    ``operational_log_root``, or is stale (the enduring root holding the log
    directory is gone), stdout is empty, stderr carries exactly one
    "[submit_feedback] ERROR: destination could not be written: ..." line
    naming the expected declaration and the failed condition, the exit code is
    1, and no file or directory is created (no sidecar either).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

try:
    import fcntl as _fcntl  # POSIX only; not available on Windows
    _FCNTL_AVAILABLE = True
except ImportError:
    _FCNTL_AVAILABLE = False

# Sibling modules are imported by name: emit_hook_finding loads this file by path,
# which leaves its directory off sys.path.
_HERE = str(Path(__file__).resolve().parent)
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import feedback_sink  # noqa: E402
import feedback_validation as _fv  # noqa: E402

# ---------------------------------------------------------------------------
# Configuration root discovery
# ---------------------------------------------------------------------------


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
    # abspath, not resolve(): a symlinked deployed script must stay anchored at
    # the invoked .leafcutter/ rather than follow the link out of it. (AC INF-100c-1-i)
    return Path(os.path.abspath(__file__)).parents[2] / "config"


# ---------------------------------------------------------------------------
# Config loading
# ---------------------------------------------------------------------------

_CONFIG_DIR = _find_config_root()
_CATEGORIES_FILE = _CONFIG_DIR / "feedback_categories.yaml"

VALID_SEVERITIES = ("low", "medium", "high")
VALID_SOURCES = ("agent", "hook")
VALID_OUTCOMES = ("warn", "block")


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
        "--jsonl", default=None,
        help="Override JSONL output path. Default: feedback_sink from the build-time declaration.",
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


def _prepare_sink(jsonl_arg: str | None) -> Path | None:
    """Return the file to append to, or None after reporting why there is none.

    An explicit ``--jsonl`` is the caller's own responsibility and is never
    refused. Otherwise the sink is the declared ``feedback_sink``; when the
    declaration is unusable one refusal line goes to stderr and nothing is
    created. ``resolve_feedback_sink`` has established that the enduring root
    holding the log directory is live, so only the missing log directory (and
    ``debugging`` above it, on a fresh install) is created -- never a project.
    """
    if jsonl_arg:
        path = Path(jsonl_arg)
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    path, refusal = feedback_sink.resolve_feedback_sink(_CONFIG_DIR.parent)
    if path is None:
        print(refusal, file=sys.stderr)
        return None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        print(f"[submit_feedback] ERROR: destination could not be written: {path.parent}: {exc}", file=sys.stderr)
        return None
    return path


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Entry point for submit_feedback.py.

    Args:
        argv: Argument list. When None, uses sys.argv[1:].

    Returns:
        int: Exit code (0 on success, 1 on validation failure or when the
            declared sink cannot be determined).
    """
    args = _build_parser().parse_args(argv)

    err = _validate_source_args(args)
    if err:
        print(err, file=sys.stderr)
        return 1

    config_path = Path(args.config) if args.config else None
    cats = _load_categories(config_path)
    _fv.validate_category(args.category, cats)

    if args.source == "agent":
        _fv.validate_writer(args.phase, args.category, cats)

    tags = _fv.validate_tags(args.tags)
    # validate_addressed_by parses and validates the JSON; it mutates args
    # by replacing the raw string with the parsed list (or leaves it None).
    args.addressed_by = _fv.validate_addressed_by(getattr(args, "addressed_by", None))
    severity = _resolve_severity(args, cats)

    jsonl_path = _prepare_sink(args.jsonl)
    if jsonl_path is None:
        return 1

    now = datetime.now(timezone.utc)
    timestamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    feedback_id = _fv.generate_feedback_id(timestamp, args.phase, args.ticket or "")
    entry = _build_entry(args, tags, severity, feedback_id, timestamp)

    # ------------------------------------------------------------------
    # Write JSONL (atomic under concurrent writes via advisory flock)
    # ------------------------------------------------------------------
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
    except OSError as exc:
        print(f"[submit_feedback] WARNING: sidecar write failed: {exc}", file=sys.stderr)

    print(f"[submit_feedback] sink: {jsonl_path.resolve()}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-10-12 [python-coder/EPIC-OneDurableLogRootForEveryWorkspace/02_INF-500d-4-i]:
#   Without --jsonl the sink is now the declared feedback_sink (feedback_sink.py,
#   which reads config/knowledge_sink.json through the shared sink_resolution
#   reader); an absent / unreadable / unparseable / keyless / relative / stale
#   declaration is REFUSED -- one stderr line, exit 1, empty stdout, no sidecar,
#   nothing created. Removed _find_project_root and _JSONL_DEFAULT (the upward
#   walk for .claude/ that KI-FC-001 names as the root cause); _find_config_root
#   is unchanged. An explicit --jsonl is still honoured and still creates its
#   parent. Only the final log directory is created for a declared sink. To
#   stay within the GE-127b-1 ratchet the validators and the id generator moved
#   verbatim into feedback_validation.py (measured length 463 -> 371).
#   (AC INF-500d-4-i, ADR-069)
# - 2026-07-08 [python-coder/EPIC-Phase1ReadyHardening/03_InfrastructureFixes]:
#   Promoted scripts/feedback/submit_feedback.py to a tracked source file
#   (removed scripts/feedback/ from .gitignore). The file was previously
#   classified as a build output but tests reference it directly. The template
#   at templates/scripts/feedback/submit_feedback.py remains the canonical
#   source; this file is kept in sync with it. (AC INF-100c-1)
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
#   both resolve to two parents up + /config/. _find_project_root() was retained for
#   _JSONL_DEFAULT, which no longer exists (see 2026-10-12). (AC INF-100c-1) (#EPIC-FeedbackPortability)
# - 2026-06-03 09:00 [python-coder/EPIC-TemplateDocViolations/06]: Confirmed 2026-05-21 entry already has HH:MM (12:00); no change needed. Added this audit entry for traceability. (#EPIC-TemplateDocViolations/06)
# - 2026-05-30 12:00 [python-coder/TICKET-20260528-FeedbackCorrelationIDLoss]:
#   Wrapped JSONL append and stdout print in fcntl.flock(LOCK_EX) advisory
#   lock so concurrent writers serialise both the append and the stdout
#   print. Stdout delivery inside the lock prevents empty-capture races
#   that previously caused (submit-failed) sentinels in ticket comments.
#   Added sidecar temp file (feedback_id_<epoch>.txt in tempdir) as a
#   fallback: calling agents can read the ID from the sidecar when stdout
#   capture fails. Sidecar path is printed to stderr (not stdout) to avoid
#   disrupting FB_ID=$(...) capture. fcntl import wrapped in try/except ImportError
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
#   Validated by validate_addressed_by() before entry construction.
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
