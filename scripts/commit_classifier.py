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
ARCHITECTURE: Pure utility module — no I/O side-effects, no filesystem writes.
      Callers obtain the staged file list via `git diff --cached --name-only`
      and pass it in; this module performs all classification logic in memory.

Used by:
  - templates/agents/commit.md (Step 2 message-drafting branch)
  - unit_tests/test_commit_classifier.py
  - unit_tests/test_mixed_set_detection.py
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Sequence


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
# Per-group message patterns (the "proven patterns" referenced in BO-1100a)
# ---------------------------------------------------------------------------

#: Maps each FileGroup to the commit subject prefix template.
#: Callers may override these by passing ``patterns`` to classify_staged_files().
DEFAULT_PATTERNS: dict[FileGroup, str] = {
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
# Path-matching rules (declaration order = priority)
# ---------------------------------------------------------------------------

#: Each entry is (pattern, FileGroup).  The patterns are applied in order;
#: the first match wins for a given file path.
_PATH_RULES: list[tuple[re.Pattern[str], FileGroup]] = [
    # Ticket inbox / done folders
    (re.compile(r"tickets/"), FileGroup.TICKETS),
    # AC store YAML files that appear to be new (net-new keys)
    # We cannot tell "new" vs "shipped" from the path alone; callers that
    # inspect the diff content can use group_files_by_type() directly and
    # then override.  Path heuristic: new_ prefix or added status.
    (re.compile(r"config/ac_store/"), FileGroup.SHIPPED_ACS),
    # Any other AC-store paths
    (re.compile(r"config/ac"), FileGroup.SHIPPED_ACS),
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
    # Configuration files
    (re.compile(r"(^|/)config/"), FileGroup.CONFIG),
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

    Returns
    -------
    ClassificationResult with:
        - primary_group: the FileGroup with the most files.
        - groups: the full grouped dict.
        - suggested_subject: the formatted commit subject.
        - specific_pattern_matched: True unless the UNKNOWN fallback fired.
    """
    effective_patterns = dict(DEFAULT_PATTERNS)
    if patterns:
        effective_patterns.update(patterns)

    groups = group_files_by_type(staged_paths)

    if not groups:
        # Nothing staged — return a neutral fallback.
        return ClassificationResult(
            primary_group=FileGroup.UNKNOWN,
            groups={},
            suggested_subject="chore: update files",
            specific_pattern_matched=False,
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
    group_summaries = []
    for group in unrelated:
        file_list = groups.get(group, [])
        file_count = len(file_list)
        label = group.value.replace("_", " ")
        if file_count == 1:
            sample = file_list[0].split("/")[-1]
            group_summaries.append(f"{label} ({sample})")
        else:
            group_summaries.append(f"{label} ({file_count} files)")

    groups_str = ", ".join(group_summaries)
    warning = (
        f"Mixed staged set detected: unrelated groups present — {groups_str}. "
        "A single commit message cannot accurately describe all of these changes."
    )
    recommendation = (
        "Split the commit into separate commits by group "
        "(e.g. `git reset HEAD <file>` to unstage unrelated files), "
        "or confirm the mixed set intentionally if you are certain they belong together."
    )

    return MixedSetWarning(
        is_mixed=True,
        unrelated_groups=unrelated,
        warning=warning,
        recommendation=recommendation,
    )
