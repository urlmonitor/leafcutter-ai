"""
MODULE: leafcutter/scripts/feedback/feedback_validation.py
GOAL: Validate the shapes ``submit_feedback.py`` accepts -- category, writer,
      tags and ``--addressed-by`` -- and generate the feedback id.
BUSINESS CONTEXT: The closed-category vocabulary and the ``allowed_writers``
      policy are enforced here, at the single write chokepoint. Extracted
      verbatim from ``submit_feedback.py`` (no behaviour change) so that file
      could shrink under the GE-127b-1 file-size ratchet while taking on the
      declared-sink refusal of AC INF-500d-4-i.
ARCHITECTURE: Sibling of ``submit_feedback.py``; the build deploys
      ``templates/scripts/feedback/`` whole, so no deploy-map entry is needed.
      Every validator prints its error to stderr and raises ``SystemExit(1)``,
      exactly as it did inside ``submit_feedback.py``.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import re
import secrets
import sys

VALID_ADDRESSED_BY_TYPES = ("ticket", "commit", "pr")
_TAG_RE = re.compile(r"^[a-z][a-z0-9-]{0,39}$")
# The one writer id that names no agent: ``submit_feedback.py --source hook``
# bypasses ``validate_writer`` and the process-finding list carries it. The
# build's writer check imports this rather than keeping a sentinel of its own.
HOOK_WRITER = "hook"


def validate_category(category: str, cats: dict) -> None:
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


def writer_allowed(phase: str, category: str, cats: dict) -> bool:
    """Return True when ``phase`` is a literal member of the category's allowed_writers.

    This is the ONE writer rule: ``validate_writer`` (submission) and the build's
    writer-consistency check (INF-100c-5) both call it, so they cannot drift.
    There is no sentinel expansion; a name is admitted only if it is listed.

    Args:
        phase: The agent name or writer id submitting feedback.
        category: The category id string.
        cats: The loaded categories dict.

    Returns:
        bool: True when the writer is listed for the category.
    """
    return phase in cats[category].get("allowed_writers", [])


def validate_writer(phase: str, category: str, cats: dict) -> None:
    """Raise SystemExit(1) if phase is not in the category's allowed_writers.

    Args:
        phase: The agent name or writer id submitting feedback.
        category: The category id string.
        cats: The loaded categories dict.
    """
    allowed: list = cats[category].get("allowed_writers", [])
    if writer_allowed(phase, category, cats):
        return
    print(
        f"ERROR: Phase '{phase}' is not an allowed writer for category "
        f"'{category}'. Allowed writers: {', '.join(allowed)}",
        file=sys.stderr,
    )
    sys.exit(1)


def validate_tags(raw_tags: str) -> list[str]:
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
    # Trim whitespace but do NOT lowercase -- uppercase tags are a shape violation
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


def validate_addressed_by(raw: str | None) -> list[dict] | None:
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


def generate_feedback_id(timestamp: str, phase: str, ticket: str) -> str:
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
