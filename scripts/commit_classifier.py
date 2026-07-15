"""
commit_classifier — staged-file grouping and commit message pattern selection.

MODULE: scripts/commit_classifier.py
GOAL: Examine the staged file set, group files by recognised type, and select
      the appropriate commit message pattern for the group. The commit agent
      calls classify_staged_files() to obtain a suggested subject line that
      is more specific than "update files". Also detects mixed staged sets
      (AC BO-1100b) and warns the user when unrelated groups are staged together.
BUSINESS CONTEXT: AC BO-1100a — the right message style is chosen automatically
      based on what changed. Each recognised group (tickets, new ACs, shipped
      ACs, implementation code, status changes) gets its own proven message
      pattern applied automatically.
      AC BO-1100b — when staged files span multiple unrelated groups, the user
      is warned before a misleading commit message is produced, giving them the
      opportunity to split the commit or confirm the mixed set intentionally.
      AC BO-1100c — message patterns are defined in one place you can read and
      edit: config/commit_message_patterns.json. Adding a new pattern is a
      one-line edit to that file; no code change is required.
ARCHITECTURE: Patterns are loaded at module-import time from
      config/commit_message_patterns.json (resolved relative to this file's
      location). If the config file is absent or malformed, the module falls
      back to compiled-in defaults so callers are never broken by a missing
      config. The classification logic itself remains pure (no filesystem
      writes, no network I/O).

Used by:
  - templates/agents/commit.md (Step 2 message-drafting branch)
  - unit_tests/test_commit_classifier.py
  - unit_tests/test_mixed_set_detection.py
  - unit_tests/test_commit_patterns_config.py
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Sequence

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config file location
# ---------------------------------------------------------------------------

#: Default path to the external commit-message patterns config file.
#: Resolved relative to the directory that contains this script so the module
#: works regardless of the caller's working directory.
_PATTERNS_CONFIG_PATH: Path = (
    Path(__file__).resolve().parent.parent / "config" / "commit_message_patterns.json"
)


# ---------------------------------------------------------------------------
# Group enum
# ---------------------------------------------------------------------------


class FileGroup(Enum):
    """Recognised groups of staged files."""

    TICKETS = "tickets"
    NEW_ACS = "new_acs"
    SHIPPED_ACS = "shipped_acs"
    IMPLEMENTATION_CODE = "implementation_code"
    STATUS_CHANGES = "status_changes"
    TESTS = "tests"
    DOCS = "docs"
    CONFIG = "config"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Compiled-in fallback patterns (used only when the config file is absent)
# ---------------------------------------------------------------------------

#: Fallback pattern map.  These values are intentionally identical to the
#: shipped config/commit_message_patterns.json so that a missing config file
#: produces the same behaviour as a present one.  Do NOT change these values
#: without updating the JSON config as well — the JSON file is the single
#: source of truth per AC BO-1100c.
_FALLBACK_PATTERNS: dict[FileGroup, str] = {
    FileGroup.TICKETS: "chore(tickets): {detail}",
    FileGroup.NEW_ACS: "feat(ac-store): {detail}",
    FileGroup.SHIPPED_ACS: "chore(ac-store): {detail}",
    FileGroup.IMPLEMENTATION_CODE: "feat: {detail}",
    FileGroup.STATUS_CHANGES: "chore(status): {detail}",
    FileGroup.TESTS: "test: {detail}",
    FileGroup.DOCS: "docs: {detail}",
    FileGroup.CONFIG: "chore(config): {detail}",
    FileGroup.UNKNOWN: "chore: {detail}",
}


# ---------------------------------------------------------------------------
# Config-file loader (AC BO-1100c)
# ---------------------------------------------------------------------------


def load_patterns(config_path: Path | None = None) -> dict[FileGroup, str]:
    """Load commit-message patterns from the external config file.

    Reads ``config/commit_message_patterns.json`` (or the caller-supplied
    ``config_path``) and converts the JSON top-level array of routing entries
    into a ``FileGroup``-keyed dict.

    The config file is the **single source of truth** for all routing patterns
    (AC BO-1100c).  It must be a top-level JSON array where each entry is an
    object with at minimum ``group`` and ``template`` keys (AC BO-1100c-1).
    Callers that want to add or modify a pattern should edit the JSON file;
    this function picks up the change on the next invocation.

    The legacy flat-object schema (``{"patterns": {...}}``) is no longer
    supported.  When the loaded JSON is not a list, the function falls back to
    compiled-in defaults and logs a warning so the misconfiguration is visible.

    Args:
        config_path: Optional explicit path to the patterns JSON file.
            Defaults to ``config/commit_message_patterns.json`` in the repo
            root resolved relative to this module's location.

    Returns:
        Dict mapping each FileGroup to its commit-subject template string.
        Falls back to the compiled-in ``_FALLBACK_PATTERNS`` when the config
        file is absent, unreadable, or structurally invalid.
    """
    path = config_path if config_path is not None else _PATTERNS_CONFIG_PATH
    try:
        with path.open("r", encoding="utf-8") as fh:
            raw = json.load(fh)
    except FileNotFoundError:
        logger.warning(
            "commit_message_patterns.json not found at %s — using compiled-in defaults",
            path,
        )
        return dict(_FALLBACK_PATTERNS)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed to load commit_message_patterns.json (%s: %s) — using compiled-in defaults",
            type(exc).__name__,
            exc,
        )
        return dict(_FALLBACK_PATTERNS)

    if not isinstance(raw, list):
        logger.warning(
            "commit_message_patterns.json is not a top-level array "
            "(legacy dict format is stale per AC BO-1100c-1) — using compiled-in defaults"
        )
        return dict(_FALLBACK_PATTERNS)

    result: dict[FileGroup, str] = dict(_FALLBACK_PATTERNS)
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        key = entry.get("group", "")
        template = entry.get("template", "")
        if not key or not template:
            continue
        try:
            group = FileGroup(key)
        except ValueError:
            logger.warning(
                "Unknown FileGroup key %r in commit_message_patterns.json — skipped",
                key,
            )
            continue
        if not isinstance(template, str):
            logger.warning(
                "Pattern for %r is not a string in commit_message_patterns.json — skipped",
                key,
            )
            continue
        result[group] = template
    return result


# ---------------------------------------------------------------------------
# Per-group message patterns (loaded from config; AC BO-1100c)
# ---------------------------------------------------------------------------

#: Maps each FileGroup to the commit subject prefix template.
#: Populated once at import time for callers that import this symbol directly.
#: ``classify_staged_files()`` does NOT read from this constant — it calls
#: ``load_patterns()`` on every invocation so that on-disk changes to
#: ``config/commit_message_patterns.json`` are reflected immediately
#: (AC BO-1100c-4 — pattern config reflects current file on every call).
DEFAULT_PATTERNS: dict[FileGroup, str] = load_patterns()


def _get_current_patterns() -> dict[FileGroup, str]:
    """Return freshly loaded patterns from the on-disk config file.

    Called on every invocation of ``classify_staged_files()`` so that edits to
    ``config/commit_message_patterns.json`` are picked up without requiring a
    Python process restart.

    Returns
    -------
    Dict mapping each FileGroup to its commit-subject template string, as
    returned by ``load_patterns()``.
    """
    return load_patterns()

# ---------------------------------------------------------------------------
# Path-matching rules (declaration order = priority)
# ---------------------------------------------------------------------------

#: Each entry is (pattern, FileGroup).  The patterns are applied in order;
#: the first match wins for a given file path.
_PATH_RULES: list[tuple[re.Pattern[str], FileGroup]] = [
    # Ticket inbox / done folders — anchored to top-level only (^tickets/)
    # prevents matching mid-path segments like 'archived/old-tickets/readme.md'.
    (re.compile(r"^tickets/"), FileGroup.TICKETS),
    # AC store YAML files — exact path 'config/ac_store/' only.
    # The pattern is anchored to ^config/ac_store/ so that:
    #   - 'config/ac_store_backup/' does NOT match (directory name is not ac_store)
    #   - 'config/accounting/' does NOT match (not the ac_store subdirectory)
    #   - 'my-config/ac_store/' does NOT match (top-level dir is not config)
    (re.compile(r"^config/ac_store/"), FileGroup.SHIPPED_ACS),
    # Status-only files (set_ticket_status outputs, known-failing baseline)
    (re.compile(r"known_failing_tests\.json$"), FileGroup.STATUS_CHANGES),
    # Test files
    (re.compile(r"(^|/)unit_tests/"), FileGroup.TESTS),
    (re.compile(r"(^|/)tests/"), FileGroup.TESTS),
    (re.compile(r"test_[^/]+\.py$"), FileGroup.TESTS),
    (re.compile(r"[^/]+_test\.py$"), FileGroup.TESTS),
    # Documentation
    (re.compile(r"(^|/)docs/"), FileGroup.DOCS),
    (re.compile(r"\.md$"), FileGroup.DOCS),
    # Configuration files — anchored to top-level only (^config/) to prevent
    # matching 'vendor/some-lib/config/setup.py' via a mid-path segment.
    (re.compile(r"^config/"), FileGroup.CONFIG),
    (re.compile(r"\.json$"), FileGroup.CONFIG),
    (re.compile(r"\.ya?ml$"), FileGroup.CONFIG),
    (re.compile(r"pyproject\.toml$"), FileGroup.CONFIG),
    (re.compile(r"\.pre-commit-config\.yaml$"), FileGroup.CONFIG),
    # Implementation code (Python scripts, agents, skills)
    (re.compile(r"(^|/)scripts/"), FileGroup.IMPLEMENTATION_CODE),
    (re.compile(r"(^|/)templates/"), FileGroup.IMPLEMENTATION_CODE),
    (re.compile(r"\.py$"), FileGroup.IMPLEMENTATION_CODE),
]


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class ClassificationResult:
    """Result returned by classify_staged_files()."""

    #: Primary group identified (highest-count group, ties broken by priority).
    primary_group: FileGroup
    #: All groups that had at least one file.
    groups: dict[FileGroup, list[str]]
    #: Suggested commit subject line (uses DEFAULT_PATTERNS or caller-supplied patterns).
    suggested_subject: str
    #: True when a specific pattern was matched; False when the fallback was used.
    specific_pattern_matched: bool
    #: True when the staging area is empty (no staged files). AC BO-1100a-2-i:
    #: the commit agent must not produce a commit message when this is True.
    no_staged_files: bool = False


# Groups that are considered "naturally co-occurring" and therefore NOT flagged
# as a mixed set when staged together.  Any pair NOT listed here will trigger
# a mixed-set warning when both groups are present in the staged file set.
#
# Rationale for each exemption:
#   TICKETS + DOCS       — ticket files are markdown; docs are markdown; they
#                          often move together when a feature lands.
#   IMPLEMENTATION_CODE + TESTS
#                        — TDD workflow: production code and its tests are
#                          almost always committed together.
#   IMPLEMENTATION_CODE + DOCS
#                        — module-level docstring updates land with the code.
#   IMPLEMENTATION_CODE + CONFIG
#                        — a new script commonly ships with a companion config
#                          entry (e.g. a new paths.json key).
#   TESTS + DOCS         — test files that double as runnable examples, or
#                          README updates that accompany test additions.
#   SHIPPED_ACS + TICKETS
#                        — AC-store YAML and the ticket that ships it often
#                          land in the same commit.
#   CONFIG + DOCS        — config files (YAML/JSON) and their companion docs
#                          update together (e.g. README or reference docs).
RELATED_GROUP_PAIRS: frozenset[frozenset[FileGroup]] = frozenset(
    {
        frozenset({FileGroup.TICKETS, FileGroup.DOCS}),
        frozenset({FileGroup.IMPLEMENTATION_CODE, FileGroup.TESTS}),
        frozenset({FileGroup.IMPLEMENTATION_CODE, FileGroup.DOCS}),
        frozenset({FileGroup.IMPLEMENTATION_CODE, FileGroup.CONFIG}),
        frozenset({FileGroup.TESTS, FileGroup.DOCS}),
        frozenset({FileGroup.SHIPPED_ACS, FileGroup.TICKETS}),
        frozenset({FileGroup.CONFIG, FileGroup.DOCS}),
    }
)


@dataclass
class MixedSetWarning:
    """Returned by detect_mixed_set() when unrelated groups are staged together.

    ``is_mixed`` is the primary signal: when True the caller should warn the
    user before letting the commit proceed.  When False, the staged set is
    either homogeneous or composed of groups that are known to co-occur.
    """

    #: True when staged files span two or more unrelated groups.
    is_mixed: bool
    #: The FileGroup buckets that are present and considered unrelated to each other.
    #: Empty when is_mixed is False.
    unrelated_groups: list[FileGroup]
    #: Human-readable warning message, or empty string when is_mixed is False.
    warning: str
    #: Recommendation for the user (split vs confirm), or empty string when is_mixed is False.
    recommendation: str


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _classify_single_file(path: str) -> FileGroup:
    """Return the FileGroup for a single file path.

    Applies _PATH_RULES in declaration order; first match wins.
    Falls through to FileGroup.UNKNOWN when no rule matches.
    """
    for pattern, group in _PATH_RULES:
        if pattern.search(path):
            return group
    return FileGroup.UNKNOWN


def _derive_detail(
    primary_group: FileGroup,
    groups: dict[FileGroup, list[str]],
) -> str:
    """Derive a short human-readable detail clause for the subject line.

    Returns a concise summary of what changed in the primary group.
    """
    files_in_group = groups.get(primary_group, [])
    count = len(files_in_group)

    if count == 0:
        return "update files"

    if count == 1:
        # Single file — use its basename for a more informative subject.
        basename = files_in_group[0].split("/")[-1]
        # Strip extension for cleanliness in the subject line.
        name_no_ext = re.sub(r"\.[^.]+$", "", basename)
        return name_no_ext

    # Multiple files — describe them by group and count.
    group_label_map = {
        FileGroup.TICKETS: "tickets",
        FileGroup.NEW_ACS: "new ACs",
        FileGroup.SHIPPED_ACS: "AC entries",
        FileGroup.IMPLEMENTATION_CODE: "scripts",
        FileGroup.STATUS_CHANGES: "status files",
        FileGroup.TESTS: "test files",
        FileGroup.DOCS: "docs",
        FileGroup.CONFIG: "config files",
        FileGroup.UNKNOWN: "files",
    }
    label = group_label_map.get(primary_group, "files")
    total_files = sum(len(v) for v in groups.values())

    # If there are multiple groups, note the mixed nature.
    num_groups = sum(1 for v in groups.values() if v)
    if num_groups > 1:
        return f"{count} {label} + {total_files - count} other changes"
    return f"{count} {label}"


# ---------------------------------------------------------------------------
# Array-format routing (AC BO-1100c-2)
# ---------------------------------------------------------------------------


def _compile_routing_rule(
    rule: object,
) -> "tuple[re.Pattern[str], str] | None":
    """Validate and compile a single array routing-rule entry.

    Extracts ``path_pattern`` and ``template`` from ``rule``, compiles the
    pattern, and returns the pair.  Returns ``None`` when the entry is invalid
    (wrong type, missing keys, or un-compilable regex) and logs a warning so
    the misconfiguration is visible.

    Args:
        rule: A single element from the routing-rule array.  Expected to be a
            dict with ``path_pattern`` (regex string) and ``template`` keys.

    Returns:
        ``(compiled_pattern, template)`` on success; ``None`` on any failure.
    """
    if not isinstance(rule, dict):
        return None
    path_pattern = rule.get("path_pattern", "")
    template = rule.get("template", "")
    if not path_pattern or not template:
        return None
    try:
        compiled = re.compile(path_pattern)
    except re.error as exc:
        logger.warning(
            "Invalid path_pattern %r in array routing rule: %s", path_pattern, exc
        )
        return None
    return compiled, template


def _classify_with_array_config(
    staged_paths: Sequence[str],
    config_path: Path,
) -> "ClassificationResult | None":
    """Apply array-format routing rules from ``config_path`` to staged files.

    Implements AC BO-1100c-2: when the caller supplies a ``patterns_config_path``
    containing a JSON array of ``{group, path_pattern, template}`` entries,
    files are matched against ``path_pattern`` (regex) in array order — first
    match wins.  The matched entry's ``template`` is used for the subject.

    Per-rule validation and pattern compilation is delegated to
    ``_compile_routing_rule`` so that this function stays within the project's
    cyclomatic-complexity threshold.

    Args:
        staged_paths: Iterable of file paths to classify.
        config_path: Path to a JSON file that contains a top-level array of
            routing-rule objects, each with at minimum ``group``,
            ``path_pattern``, and ``template`` keys.

    Returns:
        A ``ClassificationResult`` with ``specific_pattern_matched=True`` when
        at least one staged file matches a rule; ``None`` when no rule matches
        or when the config cannot be loaded.
    """
    try:
        with config_path.open("r", encoding="utf-8") as fh:
            rules = json.load(fh)
    except FileNotFoundError:
        logger.warning(
            "Array-format patterns config not found at %s — skipping array routing",
            config_path,
        )
        return None
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning(
            "Failed to load array-format patterns config at %s (%s: %s) — skipping",
            config_path,
            type(exc).__name__,
            exc,
        )
        return None

    if not isinstance(rules, list):
        logger.warning(
            "Array-format patterns config at %s is not a list — skipping array routing",
            config_path,
        )
        return None

    if not staged_paths:
        return None

    for rule in rules:
        compiled_pair = _compile_routing_rule(rule)
        if compiled_pair is None:
            continue
        compiled, template = compiled_pair

        matched = [p for p in staged_paths if compiled.search(p)]
        if not matched:
            continue

        # First matching rule wins — build the result from this rule.
        groups_for_detail: dict[FileGroup, list[str]] = {
            FileGroup.UNKNOWN: list(matched)
        }
        detail = _derive_detail(FileGroup.UNKNOWN, groups_for_detail)
        subject = template.format(detail=detail)
        if len(subject) > 72:
            subject = subject[:69] + "..."

        return ClassificationResult(
            primary_group=FileGroup.UNKNOWN,
            groups=groups_for_detail,
            suggested_subject=subject,
            specific_pattern_matched=True,  # Array rule matched explicitly.
        )

    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def group_files_by_type(
    staged_paths: Sequence[str],
) -> dict[FileGroup, list[str]]:
    """Group a list of staged file paths into FileGroup buckets.

    Parameters
    ----------
    staged_paths:
        Iterable of file paths as returned by ``git diff --cached --name-only``.

    Returns
    -------
    dict mapping FileGroup → list of matching paths.
    Only groups with at least one file are included in the result.
    """
    groups: dict[FileGroup, list[str]] = {}
    for path in staged_paths:
        grp = _classify_single_file(path)
        groups.setdefault(grp, []).append(path)
    return groups


def classify_staged_files(
    staged_paths: Sequence[str],
    patterns: dict[FileGroup, str] | None = None,
    patterns_config_path: Path | None = None,
) -> ClassificationResult:
    """Classify a staged file set and return the best commit message pattern.

    Staged files are grouped by type (tickets, new ACs, shipped ACs,
    implementation code, status changes, tests, docs, config).  The group
    with the most files is designated the primary group and its proven
    message pattern is applied automatically.

    The commit agent MUST use this function when staging files — it should
    never produce a bare "update files" subject when a specific pattern matches.

    Parameters
    ----------
    staged_paths:
        Paths returned by ``git diff --cached --name-only``.
    patterns:
        Optional override map.  Keys are FileGroup members; values are
        Python format strings with a ``{detail}`` placeholder.  Defaults
        to DEFAULT_PATTERNS for any group not present in the override.
    patterns_config_path:
        Optional path to a JSON file containing an **array** of routing-rule
        objects, each with ``group``, ``path_pattern``, and ``template`` keys.
        When provided, the array rules are applied first (first-match wins).
        If no array rule matches, the function falls back to the standard
        enum-based classification.  Supports AC BO-1100c-2: a new routing
        rule is activated by appending an entry to this file — no code change
        required.

    Returns
    -------
    ClassificationResult with:
        - primary_group: the FileGroup with the most files.
        - groups: the full grouped dict.
        - suggested_subject: the formatted commit subject.
        - specific_pattern_matched: True unless the UNKNOWN fallback fired.
        - no_staged_files: True when ``staged_paths`` is empty (AC BO-1100a-2-i).
    """
    # AC BO-1100c-2 — when an array-format patterns config is supplied, try it
    # first.  Array routing rules support custom path_pattern regexes that can
    # be added via config without a code change.
    if patterns_config_path is not None:
        array_result = _classify_with_array_config(staged_paths, patterns_config_path)
        if array_result is not None:
            return array_result

    # Re-read patterns from disk on every call so that changes to
    # config/commit_message_patterns.json are reflected without a restart
    # (AC BO-1100c-4).
    effective_patterns = _get_current_patterns()
    if patterns:
        effective_patterns.update(patterns)

    # Derive the empty-staging flag from the INPUT, not from the grouping output,
    # so no_staged_files always means exactly what its name says even if grouping
    # behaviour changes in future (review finding L-5).
    no_staged = not staged_paths

    groups = group_files_by_type(staged_paths)

    if not groups:
        # Nothing staged — return a neutral fallback (AC BO-1100a-2-i).
        return ClassificationResult(
            primary_group=FileGroup.UNKNOWN,
            groups={},
            suggested_subject="chore: update files",
            specific_pattern_matched=False,
            no_staged_files=no_staged,
        )

    # Pick the primary group: highest file count; ties broken by FileGroup
    # declaration order (lower ordinal = higher priority).
    primary_group = max(
        groups,
        key=lambda g: (len(groups[g]), -list(FileGroup).index(g)),
    )

    detail = _derive_detail(primary_group, groups)
    pattern_template = effective_patterns.get(primary_group, DEFAULT_PATTERNS[FileGroup.UNKNOWN])
    subject = pattern_template.format(detail=detail)

    # Ensure subject line does not exceed 72 chars (conventional limit).
    if len(subject) > 72:
        subject = subject[:69] + "..."

    specific = primary_group is not FileGroup.UNKNOWN

    return ClassificationResult(
        primary_group=primary_group,
        groups=groups,
        suggested_subject=subject,
        specific_pattern_matched=specific,
    )


def detect_mixed_set(
    groups: dict[FileGroup, list[str]],
) -> MixedSetWarning:
    """Detect whether staged files span multiple unrelated groups.

    Uses the grouping output from group_files_by_type() and the
    RELATED_GROUP_PAIRS exemption table to decide whether the staged set is
    "mixed" (i.e. likely to produce a misleading commit message).

    A staged set is considered mixed when:
      - It contains files from two or more distinct FileGroups, AND
      - At least one pair of those groups is NOT listed in RELATED_GROUP_PAIRS.

    The function is intentionally conservative: if every pair of present groups
    appears in RELATED_GROUP_PAIRS, no warning is issued even if three or more
    groups are present (e.g. implementation code + tests + docs is a common
    TDD pattern).

    Parameters
    ----------
    groups:
        Mapping of FileGroup → list of paths as returned by group_files_by_type().
        Groups with empty path lists are ignored.

    Returns
    -------
    MixedSetWarning with is_mixed=False when the staged set is homogeneous or
    composed of known-related groups; is_mixed=True with a populated warning and
    recommendation otherwise.

    Examples
    --------
    Clean TDD commit — not mixed:
        groups = {
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
            FileGroup.TESTS: ["unit_tests/test_build.py"],
        }
        result = detect_mixed_set(groups)
        assert not result.is_mixed  # IMPLEMENTATION_CODE + TESTS is exempted

    Mixed commit — ticket move plus unrelated code change:
        groups = {
            FileGroup.TICKETS: ["tickets/00_inbox/my_ticket.md"],
            FileGroup.IMPLEMENTATION_CODE: ["scripts/build.py"],
        }
        result = detect_mixed_set(groups)
        assert result.is_mixed  # TICKETS + IMPLEMENTATION_CODE is not exempted
    """
    # Only consider groups that actually contain at least one file.
    present_groups = [g for g, paths in groups.items() if paths]

    if len(present_groups) <= 1:
        # Homogeneous or empty — never mixed.
        return MixedSetWarning(
            is_mixed=False,
            unrelated_groups=[],
            warning="",
            recommendation="",
        )

    # Check every pair of present groups.  If any pair is NOT in
    # RELATED_GROUP_PAIRS, the staged set is considered mixed.
    unrelated: list[FileGroup] = []
    seen_unrelated: set[FileGroup] = set()

    for i, group_a in enumerate(present_groups):
        for group_b in present_groups[i + 1 :]:
            pair = frozenset({group_a, group_b})
            if pair not in RELATED_GROUP_PAIRS:
                if group_a not in seen_unrelated:
                    unrelated.append(group_a)
                    seen_unrelated.add(group_a)
                if group_b not in seen_unrelated:
                    unrelated.append(group_b)
                    seen_unrelated.add(group_b)

    if not unrelated:
        return MixedSetWarning(
            is_mixed=False,
            unrelated_groups=[],
            warning="",
            recommendation="",
        )

    # Build a human-readable summary of the unrelated groups and the files in each.
    # AC BO-1100b-2: list every individual filename per group, not just a count.
    group_summaries = []
    for group in unrelated:
        file_list = groups.get(group, [])
        file_count = len(file_list)
        label = group.value.replace("_", " ")
        if file_count == 1:
            sample = file_list[0].split("/")[-1]
            group_summaries.append(f"{label} ({sample})")
        else:
            # List every basename so the user sees exactly which files are in each group.
            basenames = ", ".join(f.split("/")[-1] for f in file_list)
            group_summaries.append(f"{label} ({basenames})")

    groups_str = ", ".join(group_summaries)
    warning = (
        f"Mixed staged set detected: unrelated groups present — {groups_str}. "
        "A single commit message cannot accurately describe all of these changes."
    )
    # AC BO-1100b-3: offer explicit Proceed and Abort options so the user sees
    # unambiguous decision labels rather than free-form "confirm" language.
    recommendation = (
        "Proceed (confirm that the mixed changes are intentional and keep the commit as-is). "
        "Abort: split the commit into separate commits by group "
        "(e.g. `git reset HEAD <file>` to unstage unrelated files). "
        "If you are certain these changes belong together, confirm and proceed."
    )

    return MixedSetWarning(
        is_mixed=True,
        unrelated_groups=unrelated,
        warning=warning,
        recommendation=recommendation,
    )
