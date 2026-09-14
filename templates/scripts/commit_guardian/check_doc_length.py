"""
Pre-commit hook to block documentation files that exceed length thresholds.

Checks, each RATCHETED against the file's size at every parent of the commit:
- Line count (excluding YAML frontmatter) against max_lines / max_lines_adr.
- Section count (## headings) against max_sections.
- Suggests which top-level sections could be extracted into linked docs.

A doc is refused when it CROSSES its limit, or when it is already over and
GROWS further. A doc that is already over and shrinks, or stays the same
size, passes — so the 59 docs over the limit when this gate started blocking
stay editable, and only new length is stopped. The counting rule is applied
to the staged content and to every parent revision through ONE function
(_doc_length_ratchet.measure_doc_lines / measure_doc_sections) so the two
sides of the comparison can never drift apart. See _file_size_ratchet.py for
the git plumbing this shares with check_file_size.py, and that module's
MERGE COMMITS note for why a merge's baseline is the maximum across parents.

Usage:
    poetry run python scripts/commit_guardian/check_doc_length.py

MODULE: check_doc_length.py
GOAL: Prevent documentation files from growing beyond maintainable size.
BUSINESS CONTEXT: Mirrors the complexity/line-length enforcement for Python and SQL
    files. Forces authors to decompose large docs into focused, interlinked pages.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/architecture/adrs/ADR-033-agent-model-tiers.md
"""

import re
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()

from config import (
    DOC_LENGTH_MAX_LINES,
    DOC_LENGTH_MAX_LINES_ADR,
    DOC_LENGTH_MAX_SECTIONS,
    DOC_LENGTH_SEVERITY,
    DOC_LENGTH_EXCLUDED_FILES,
)
from doc_length_helpers import (
    lookup_writer_agent,
    read_frontmatter_type,
)
from _file_size_ratchet import CurrentLengthUnmeasurableError, PreviousLengthSourceError
from _doc_length_ratchet import (
    classify_dimension,
    count_lines_and_sections,
    is_adr_file,
    is_checked,
    read_doc_content,
    resolve_doc_ratchet,
    strip_frontmatter,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Minimum lines for a section to be flagged as "extractable"
_MIN_EXTRACTABLE_SECTION_LINES = 30

# DECISION HISTORY and related non-content blocks that should not be suggested for extraction
_NON_EXTRACTABLE_PATTERNS = frozenset({
    "decision history",
    "cross-references",
    "cross references",
    "file touchpoints",
    "compatibility",
})

# Linking template shown to the user — PARENT side (links down to child)
_PARENT_LINK_TEMPLATE = """\
## {section_title}

> See [{linked_filename}]({linked_filename}) for full details.\
"""

# Linking template — CHILD side (links back up to parent)
_CHILD_LINK_TEMPLATE = """\
> **Parent document:** [{parent_filename}]({parent_filename})\
"""


# ---------------------------------------------------------------------------
# Core analysis
# ---------------------------------------------------------------------------

def find_extractable_sections(
    sections: list[tuple[str, int, int]],
    min_lines: int = _MIN_EXTRACTABLE_SECTION_LINES,
) -> list[tuple[str, int, int]]:
    """Identify sections that are large enough and suitable for extraction.

    Filters out non-extractable sections (Decision History, Cross-References, etc.)
    and returns sections above the minimum line threshold, sorted largest first.

    Args:
        sections: List of (title, start_line, line_count) tuples.
        min_lines: Minimum section size to consider extractable.

    Returns:
        list[tuple[str, int, int]]: Extractable sections sorted by size descending.
    """
    extractable = []
    for title, start, span in sections:
        # Skip non-extractable sections
        if title.lower().strip("— -").strip() in _NON_EXTRACTABLE_PATTERNS:
            continue
        # Skip sections wrapped in HTML comments or that are just links
        if span < min_lines:
            continue
        extractable.append((title, start, span))

    # Sort by size descending — suggest the biggest sections first
    extractable.sort(key=lambda x: x[2], reverse=True)
    return extractable


def suggest_filename(section_title: str) -> str:
    """Generate a suggested filename for an extracted section.

    Args:
        section_title: The markdown section heading text.

    Returns:
        str: A snake_case .md filename derived from the title.
    """
    # Remove markdown formatting, emojis, special chars
    clean = re.sub(r"[^\w\s-]", "", section_title)
    clean = re.sub(r"[\s-]+", "_", clean.strip()).lower()
    # Truncate to reasonable length
    clean = clean[:60].rstrip("_")
    return f"{clean}.md"


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_violation(
    filepath: str,
    line_count: int,
    max_lines: int,
    section_count: int,
    max_sections: int,
    extractable: list[tuple[str, int, int]],
    autofix_agent: str = "documentation-expert",
) -> str:
    """Format a single file's violation report with actionable guidance.

    Args:
        filepath: Path to the offending file.
        line_count: Actual content line count.
        max_lines: Configured line limit.
        section_count: Number of ## sections.
        max_sections: Configured section limit.
        extractable: List of (title, start_line, span) for suggested extractions.
        autofix_agent: The agent name to dispatch to for autofix. Emitted as
            ``AUTOFIX_AGENT: <agent>`` so that ``precommit-autofix`` can parse
            and route directly to the correct writer.

    Returns:
        str: Formatted violation report.
    """
    lines_over = line_count > max_lines
    sections_over = section_count > max_sections
    parts = [f"\n📄 {filepath}"]

    if lines_over:
        parts.append(f"   📏 {line_count} lines (limit: {max_lines}) — {line_count - max_lines} lines over")
    if sections_over:
        parts.append(f"   📑 {section_count} sections (limit: {max_sections}) — too many concerns in one file")

    # WHY it should be split
    parts.append("\n   ❓ WHY split this file?")
    if lines_over and sections_over:
        parts.append("      This doc is both too long AND covers too many topics.\n"
                      "      Large docs are hard to navigate, slow to load in editors,\n"
                      "      and create merge conflicts when multiple authors edit them.")
    elif lines_over:
        parts.append("      This doc exceeds the line limit. Long docs become hard\n"
                      "      to navigate and maintain. Extracting self-contained sections\n"
                      "      into linked docs keeps each file focused and scannable.")
    else:
        parts.append("      This doc has too many separate concerns (## sections).\n"
                      "      Group related sections into standalone linked docs\n"
                      "      so each file covers one coherent topic.")

    # Extraction suggestions (top 3) + linking guide
    if extractable:
        parts.append("\n   💡 Suggested sections to extract:")
        for title, start, span in extractable[:3]:
            parts.append(f"      → \"{title}\" (~{span} lines, starting line {start})")
            parts.append(f"        Extract to: {suggest_filename(title)}")

        # Bidirectional cross-referencing guide
        first_title = extractable[0][0]
        first_file = suggest_filename(first_title)
        parent_basename = Path(filepath).name
        parent_example = _PARENT_LINK_TEMPLATE.format(
            section_title=first_title, linked_filename=first_file,
        )
        child_example = _CHILD_LINK_TEMPLATE.format(parent_filename=parent_basename)

        parts.append("\n   🔗 HOW to link after extraction (bidirectional):")
        parts.append("\n      STEP 1 — PARENT doc: Replace extracted section with a link:\n")
        parts.extend(f"      {ln}" for ln in parent_example.split("\n"))
        parts.append("\n      STEP 2 — CHILD doc: Add a back-link at the top:\n")
        parts.extend(f"      {ln}" for ln in child_example.split("\n"))
        parts.append("\n      Both docs must cross-reference each other so readers\n"
                      "      can navigate up (child → parent) and down (parent → child).\n"
                      "      The child file keeps the same YAML frontmatter format\n"
                      "      and should add `related_docs:` in frontmatter pointing\n"
                      "      back to the parent document.")
    else:
        parts.append("\n   💡 No obvious self-contained sections found for extraction.\n"
                      "      Consider reorganising the document into focused subsections\n"
                      "      that each cover one topic, then extract the largest ones.")

    # Machine-readable autofix hint — parsed by precommit-autofix skill to route
    # directly to the correct writer agent without going through documentation-expert.
    parts.append(f"AUTOFIX_AGENT: {autofix_agent}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def get_staged_files() -> dict[str, str]:
    """Get all staged files with their git status.

    Returns:
        dict[str, str]: Mapping of filepath to git status.

    Raises:
        PreviousLengthSourceError: the staged set could not be read at all
            (not a git repository, or git unavailable). This must REFUSE
            rather than return an empty mapping: an empty staged set is
            main()'s "nothing to check, exit 0" shortcut, so returning {}
            here turns a gate that could not look into a gate that looked
            and approved — the fail-open shape KI-CG-034, KI-CG-012 and
            KI-CG-018 each shipped, and one this gate demonstrably had while
            it was warn-only and the distinction could not change an outcome.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise PreviousLengthSourceError(
            f"the staged file set could not be read: git exited {exc.returncode} "
            f"({(exc.stderr or '').strip()})"
        ) from exc
    except (OSError, subprocess.SubprocessError) as exc:
        raise PreviousLengthSourceError(
            f"the staged file set could not be read: git could not be invoked ({exc})"
        ) from exc

    staged = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            staged[parts[-1]] = parts[0]
    return staged


# ---------------------------------------------------------------------------
# Analysis function (testable without git)
# ---------------------------------------------------------------------------

def analyze_file(
    filepath: str,
    content: str,
    previous_lines: int | None = None,
    previous_sections: int | None = None,
) -> dict | None:
    """Analyze a documentation file for length and section violations.

    This is the core analysis function, separated from git I/O for testability.

    Both dimensions are judged through ``classify_dimension``, so an
    already-oversized doc is measured against its OWN previous value rather
    than the fixed limit — it may shrink or hold steady, but not grow. When
    both previous values are omitted the file is judged against the limits
    alone, which is the correct reading for a doc that existed at no parent.

    Args:
        filepath: Relative file path (used for ADR detection).
        content: Full file content as a string.
        previous_lines: The doc's line count at the most permissive parent,
            or None when it existed at no parent.
        previous_sections: The doc's section count at the most permissive
            parent, or None when it existed at no parent.

    Returns:
        dict | None: Violation details if either dimension is refused, else
            None. Keys: filepath, line_count, max_lines, section_count,
            max_sections, extractable, lines_over, sections_over,
            lines_verdict, sections_verdict, previous_lines,
            previous_sections.
    """
    max_lines = DOC_LENGTH_MAX_LINES_ADR if is_adr_file(filepath) else DOC_LENGTH_MAX_LINES
    max_sections = DOC_LENGTH_MAX_SECTIONS

    body = strip_frontmatter(content)
    line_count, sections = count_lines_and_sections(body)
    section_count = len(sections)

    lines_verdict = classify_dimension(line_count, previous_lines, max_lines)
    sections_verdict = classify_dimension(section_count, previous_sections, max_sections)

    if lines_verdict == "pass" and sections_verdict == "pass":
        return None

    return {
        "filepath": filepath,
        "line_count": line_count,
        "max_lines": max_lines,
        "section_count": section_count,
        "max_sections": max_sections,
        "extractable": find_extractable_sections(sections),
        "lines_over": lines_verdict != "pass",
        "sections_over": sections_verdict != "pass",
        "lines_verdict": lines_verdict,
        "sections_verdict": sections_verdict,
        "previous_lines": previous_lines,
        "previous_sections": previous_sections,
    }


def format_growth_note(violation: dict) -> str | None:
    """Describe a ratchet refusal, or None when neither dimension grew.

    A "grew" refusal needs different wording from a "crossed the limit" one:
    the author is not being told to get under 300 lines, they are being told
    not to make an already-long doc longer in this commit.

    Args:
        violation: A violation dict from ``analyze_file``.

    Returns:
        The explanatory line, or None when no dimension grew.
    """
    grew = []
    if violation.get("lines_verdict") == "grew":
        grew.append(f"lines {violation['previous_lines']} → {violation['line_count']}")
    if violation.get("sections_verdict") == "grew":
        grew.append(f"sections {violation['previous_sections']} → {violation['section_count']}")
    if not grew:
        return None
    return (
        f"   📈 Already over its limit and grew further in this commit ({', '.join(grew)}).\n"
        "      Shrinking it, or leaving its size unchanged, is allowed — growing it is not."
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Run documentation length checks on all staged docs/*.md files.

    Returns:
        int: Exit code. 0 = clean run (nothing crossed its limit, nothing
        already-over grew, or the previous-value history is empty), 1 = a
        refused finding when severity is ``block`` (always 0 under ``warn``),
        2 = INDETERMINATE — the previous-value source could not be reached or
        interpreted, or a staged doc's current content could not be read.
    """
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    excluded_files = set(DOC_LENGTH_EXCLUDED_FILES)
    try:
        staged_files = get_staged_files()
    except PreviousLengthSourceError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return 2

    if not staged_files:
        return 0

    # Resolve doc_types.json path relative to this script's project root
    # (same resolution pattern used for sys.path above).
    doc_types_path = project_root / "leafcutter" / "config" / "doc_types.json"

    checked_paths = [
        filepath
        for filepath, status in staged_files.items()
        if status != "D" and is_checked(filepath, excluded_files)
    ]

    previous_values, indeterminate_exit = resolve_doc_ratchet(checked_paths, excluded_files)
    if indeterminate_exit is not None:
        return indeterminate_exit
    previous_lines, previous_sections = previous_values

    violations = []
    try:
        for filepath in checked_paths:
            content = read_doc_content(filepath)
            result = analyze_file(
                filepath,
                content,
                previous_lines.get(filepath),
                previous_sections.get(filepath),
            )
            if result:
                # Compute the autofix agent from frontmatter type before content was stripped.
                doc_type = read_frontmatter_type(content)
                result["autofix_agent"] = lookup_writer_agent(doc_type, doc_types_path)
                violations.append(result)
    except CurrentLengthUnmeasurableError as exc:
        print(f"INDETERMINATE: reason={exc.reason}", file=sys.stderr)
        return 2

    checked_count = len(checked_paths)
    if not violations:
        if checked_count > 0:
            print(f"✅ PASSED: compared {checked_count} doc files against their length limits")
        return 0

    # Report violations
    is_blocking = DOC_LENGTH_SEVERITY == "block"
    severity_label = "BLOCKED" if is_blocking else "Advisory Warnings"
    emoji = "❌" if is_blocking else "⚠️"

    print(f"\n{emoji}  Documentation Length Check — {severity_label}\n")
    print(
        "Documentation files should be focused and link to each other"
    )
    print(
        "rather than growing into monoliths. Extract self-contained"
    )
    print(
        "sections into separate docs and replace with a one-line link.\n"
    )

    for v in violations:
        report = format_violation(
            filepath=v["filepath"],
            line_count=v["line_count"],
            max_lines=v["max_lines"],
            section_count=v["section_count"],
            max_sections=v["max_sections"],
            extractable=v["extractable"],
            autofix_agent=v.get("autofix_agent", "documentation-expert"),
        )
        print(report)
        growth_note = format_growth_note(v)
        if growth_note:
            print(growth_note)

    print()
    print(
        f"📊 Summary: {len(violations)} file(s) refused out of {checked_count} compared"
    )

    if is_blocking:
        print(
            "\n🛑 Commit blocked. Split the file(s) above before committing.\n"
            "   DO NOT simply delete content to bypass this check.\n"
            "   Use the `@documentation-expert` agent to intelligently split\n"
            "   and cross-reference these sections without losing context.\n"
            "   A doc that is ALREADY over its limit is judged against its own\n"
            "   previous size, so shrinking it or leaving it unchanged passes."
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-13 10:20 [Antigravity]: Initial implementation. Enforces
  doc length limits (300 lines for docs, 400 for ADRs) and section
  density (25 max). Starts in warn-only mode. Outputs actionable
  extraction suggestions with concrete linking examples.
- 2026-05-14 09:45 [ticket-11]: Add AUTOFIX_AGENT hint emission.
  Added read_frontmatter_type() and lookup_writer_agent() to read
  the file's frontmatter type: field, look up the writer_agent in
  doc_types.json, and emit AUTOFIX_AGENT: <agent> at the end of
  each violation report. Falls back to documentation-expert when
  type is absent, unknown, null, or doc_types.json is missing.
  AUTOFIX_AGENT is only emitted on violation; clean files are
  unaffected. Exact type string used for lookup (no normalisation
  needed — deprecated aliases preserved in doc_types.json).
- 2026-09-14 [doc-length ratchet]: Made the gate actually refuse. The
  "warn-only mode" the 2026-05-13 entry above describes as a starting
  point was never left: `doc_length` had no section in
  commit_guardian.json, so DOC_LENGTH_SEVERITY took its "warn" default
  and main() returned 0 on every run for sixteen months. Three
  known-issues registers reached ~4,500 lines against the 300-line
  limit without one commit being stopped. severity is now "block" and
  every threshold is pinned explicitly in the config rather than left
  to a default, so the posture is legible in the file that sets it.
  Blocking is ratcheted, not absolute: 59 of 339 tracked docs were
  already over the limit, and refusing all of them would have frozen
  the append-heavy registers and got the gate switched off again. Both
  dimensions now route through _doc_length_ratchet.classify_dimension,
  so a doc is refused only when it CROSSES its limit or GROWS while
  already over — the same GE-127a-1 / GE-127b-1 posture check_file_size
  .py takes for code, reusing that gate's _file_size_ratchet module
  (merge-parent resolution, INDETERMINATE floor, empty-history
  classification) rather than a second copy of it.
  Two fail-opens closed on the way, both previously harmless because a
  warn-only gate cannot change an outcome and now not: read_file_content
  () returned None on an unreadable doc and the loop skipped it, and
  get_staged_files() returned {} when git failed, which main() reads as
  "nothing staged, exit 0" — a gate that could not look reporting as a
  gate that looked and approved. Both now raise and surface as
  INDETERMINATE (exit 2). Covered behaviourally by
  unit_tests/commit_guardian/test_doc_length_blocking_ratchet.py and
  spot-checked against the real 4,388-line commit-guardian.md register.
====================================================================
"""
