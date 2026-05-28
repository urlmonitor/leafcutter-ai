"""
Pre-commit hook to warn/block documentation files that exceed length thresholds.

Checks:
- Line count (excluding YAML frontmatter) against max_lines / max_lines_adr.
- Section count (## headings) against max_sections.
- Suggests which top-level sections could be extracted into linked docs.

Usage:
    poetry run python scripts/commit_guardian/check_doc_length.py

MODULE: check_doc_length.py
GOAL: Prevent documentation files from growing beyond maintainable size.
BUSINESS CONTEXT: Mirrors the complexity/line-length enforcement for Python and SQL
    files. Forces authors to decompose large docs into focused, interlinked pages.
ARCHITECTURE: Not needed.
DOC_LINKS:
  - docs/architecture/adrs/ADR-006-agent-model-tiers.md
"""

import re
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import (
    DOC_LENGTH_MAX_LINES,
    DOC_LENGTH_MAX_LINES_ADR,
    DOC_LENGTH_MAX_SECTIONS,
    DOC_LENGTH_SEVERITY,
    DOC_LENGTH_EXCLUDED_FILES,
)
from scripts.commit_guardian.doc_length_helpers import (
    lookup_writer_agent,
    read_frontmatter_type,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Minimum lines for a section to be flagged as "extractable"
_MIN_EXTRACTABLE_SECTION_LINES = 30

# YAML frontmatter regex (opening --- to closing ---)
_FRONTMATTER_RE = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)

# Top-level sections: lines starting with ## (but not ###)
_SECTION_RE = re.compile(r"^##\s+(.+)$")

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

def strip_frontmatter(content: str) -> str:
    """Remove YAML frontmatter from the beginning of a markdown file.

    Args:
        content: Full file content as a string.

    Returns:
        str: Content with frontmatter stripped.
    """
    return _FRONTMATTER_RE.sub("", content, count=1)


def count_lines_and_sections(content: str) -> tuple[int, list[tuple[str, int, int]]]:
    """Count content lines and identify top-level (##) sections with their spans.

    Args:
        content: Markdown content with frontmatter already stripped.

    Returns:
        tuple: (line_count, sections) where sections is a list of
            (title, start_line, line_count) tuples.
    """
    lines = content.split("\n")
    line_count = len(lines)

    # Find all ## sections with their line numbers
    section_starts: list[tuple[str, int]] = []
    for i, line in enumerate(lines):
        match = _SECTION_RE.match(line)
        if match:
            section_starts.append((match.group(1).strip(), i + 1))

    # Calculate section spans
    sections: list[tuple[str, int, int]] = []
    for idx, (title, start) in enumerate(section_starts):
        if idx + 1 < len(section_starts):
            end = section_starts[idx + 1][1] - 1
        else:
            end = line_count
        span = end - start + 1
        sections.append((title, start, span))

    return line_count, sections


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
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return {}

    staged = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            staged[parts[-1]] = parts[0]
    return staged


def is_doc_file(filepath: str) -> bool:
    """Check whether a file path is a documentation markdown file in docs/.

    Args:
        filepath: Relative file path from the project root.

    Returns:
        bool: True if the file is a docs/*.md file.
    """
    return filepath.startswith("docs/") and filepath.endswith(".md")


def is_adr_file(filepath: str) -> bool:
    """Check whether a file path is an Architecture Decision Record.

    Args:
        filepath: Relative file path from the project root.

    Returns:
        bool: True if the file is in docs/architecture/adrs/.
    """
    return filepath.startswith("docs/architecture/adrs/")


def is_excluded(filepath: str, excluded_files: set[str]) -> bool:
    """Check whether a file should be excluded from checking.

    Args:
        filepath: Relative file path from the project root.
        excluded_files: Set of filenames (basenames) to exclude.

    Returns:
        bool: True if the file should be skipped.
    """
    return Path(filepath).name in excluded_files


# ---------------------------------------------------------------------------
# Analysis function (testable without git)
# ---------------------------------------------------------------------------

def analyze_file(filepath: str, content: str) -> dict | None:
    """Analyze a documentation file for length and section violations.

    This is the core analysis function, separated from git I/O for testability.

    Args:
        filepath: Relative file path (used for ADR detection).
        content: Full file content as a string.

    Returns:
        dict | None: Violation details if thresholds exceeded, else None.
            Keys: filepath, line_count, max_lines, section_count, max_sections,
                  extractable, lines_over, sections_over.
    """
    max_lines = DOC_LENGTH_MAX_LINES_ADR if is_adr_file(filepath) else DOC_LENGTH_MAX_LINES
    max_sections = DOC_LENGTH_MAX_SECTIONS

    body = strip_frontmatter(content)
    line_count, sections = count_lines_and_sections(body)
    section_count = len(sections)

    lines_over = line_count > max_lines
    sections_over = section_count > max_sections

    if not lines_over and not sections_over:
        return None

    extractable = find_extractable_sections(sections)

    return {
        "filepath": filepath,
        "line_count": line_count,
        "max_lines": max_lines,
        "section_count": section_count,
        "max_sections": max_sections,
        "extractable": extractable,
        "lines_over": lines_over,
        "sections_over": sections_over,
    }


# ---------------------------------------------------------------------------
# File I/O helper (mockable in tests)
# ---------------------------------------------------------------------------

def read_file_content(filepath: str) -> str | None:
    """Read file content, returning None on error.

    Args:
        filepath: Relative file path from the project root.

    Returns:
        str | None: File content, or None if file cannot be read.
    """
    try:
        return Path(filepath).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    """Run documentation length checks on all staged docs/*.md files.

    Returns:
        int: Exit code. 0 = pass (or warn-only), 1 = violations in block mode.
    """
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    excluded_files = set(DOC_LENGTH_EXCLUDED_FILES)
    staged_files = get_staged_files()
    if not staged_files:
        return 0

    # Resolve doc_types.json path relative to this script's project root
    # (same resolution pattern used for sys.path above).
    doc_types_path = project_root / "leafcutter" / "config" / "doc_types.json"

    violations = []
    checked_count = 0

    for filepath, status in staged_files.items():
        if status == "D":  # Deleted files — skip
            continue
        if not is_doc_file(filepath):
            continue
        if is_excluded(filepath, excluded_files):
            continue

        checked_count += 1
        content = read_file_content(filepath)
        if content is None:
            continue

        result = analyze_file(filepath, content)
        if result:
            # Compute the autofix agent from frontmatter type before content was stripped.
            doc_type = read_frontmatter_type(content)
            result["autofix_agent"] = lookup_writer_agent(doc_type, doc_types_path)
            violations.append(result)

    if not violations:
        if checked_count > 0:
            print(f"✅ PASSED: {checked_count} doc files within length limits")
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

    print()
    print(f"📊 Summary: {len(violations)} file(s) exceed limits out of {checked_count} checked")

    if is_blocking:
        print(
            "\n🛑 Commit blocked. Split the file(s) above before committing.\n"
            "   DO NOT simply delete content to bypass this check.\n"
            "   Use the `@documentation-expert` agent to intelligently split\n"
            "   and cross-reference these sections without losing context."
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
====================================================================
"""
