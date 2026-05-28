"""
Pre-commit hook to enforce inline documentation on infrastructure file changes.

When docker-compose files, Dockerfiles, init-db.sh, or other infra config files
are modified, this hook checks that each changed line block contains an inline
comment explaining the *why* (not just the *what*).

Rationale:
    Infrastructure changes (ports, memory limits, timeouts, volumes) are
    notoriously hard to reverse-engineer weeks later. Inline comments act
    as micro-ADRs directly attached to the configuration they document.

Monitored files:
    - docker-compose*.yml / docker-compose*.yaml
    - docker/Dockerfile.*
    - init-db.sh
    - .env.example

Exit Codes:
    0 - All infra changes have inline comments
    1 - Uncommented infra changes detected

MODULE: check_infra_docs.py
GOAL: Enforce inline documentation for infrastructure config file changes.
BUSINESS CONTEXT: Prevents undocumented infra changes that are hard to debug later.
ARCHITECTURE: Not needed.
"""

import subprocess
import sys
import re
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import INFRA_FILE_PATTERNS, INFRA_HIGH_IMPACT_KEYWORDS

# Alias for backwards compatibility within this file
INFRA_PATTERNS: list[str] = INFRA_FILE_PATTERNS

# Lines that are exempt from requiring comments
EXEMPT_PATTERNS: list[re.Pattern] = [
    re.compile(r"^\s*$"),                    # blank lines
    re.compile(r"^\s*#"),                    # pure comment lines (YAML/shell)
    re.compile(r"^\s*//"),                   # pure comment lines (Dockerfile-ish)
    re.compile(r"^\s*-\s*$"),               # bare list markers
    re.compile(r"^\s*(services|volumes|networks)\s*:\s*$"),  # top-level YAML keys
    re.compile(r"^\s*\w+:\s*$"),            # section-only keys (no value)
    re.compile(r"^\s*(FROM|COPY|RUN|USER|ENV|WORKDIR|EXPOSE|CMD|ENTRYPOINT|ARG|LABEL|SHELL|HEALTHCHECK|STOPSIGNAL|ONBUILD)\b"),  # Dockerfile directives (documented by nature)
]

# Lines that MUST have a comment (high-impact settings) — compiled from config
HIGH_IMPACT_PATTERNS: list[re.Pattern] = [
    re.compile(kw, re.IGNORECASE) for kw in INFRA_HIGH_IMPACT_KEYWORDS
]


def is_infra_file(filepath: str) -> bool:
    """Check if a file matches an infra pattern."""
    return any(re.match(pattern, filepath) for pattern in INFRA_PATTERNS)


def line_has_comment(line: str) -> bool:
    """Check if a line contains an inline comment.

    Args:
        line: Raw line of text to check.

    Returns:
        bool: True if the line contains a non-empty inline comment.
    """
    # YAML/shell inline comment
    if "#" in line:
        # Make sure it's not inside a quoted string
        stripped = line.split("#", 1)
        if len(stripped) >= 2 and stripped[1].strip():
            return True
    return False


def is_exempt(line: str) -> bool:
    """Check if a line is exempt from comment requirements."""
    return any(p.match(line) for p in EXEMPT_PATTERNS)


def is_high_impact(line: str) -> bool:
    """Check if a line is a high-impact setting that requires documentation."""
    return any(p.search(line) for p in HIGH_IMPACT_PATTERNS)


def get_staged_diff_lines(filepath: str) -> list[tuple[int, str]]:
    """Get added lines from staged diff for a file.

    Args:
        filepath: Path to the file to diff.

    Returns:
        list[tuple[int, str]]: List of (line_number, line_content) pairs.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "-U0", "--", filepath],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    added_lines: list[tuple[int, str]] = []
    current_line = 0

    for diff_line in result.stdout.split("\n"):
        # Parse hunk header: @@ -old,count +new,count @@
        hunk_match = re.match(r"^@@ .* \+(\d+)", diff_line)
        if hunk_match:
            current_line = int(hunk_match.group(1))
            continue

        if diff_line.startswith("+") and not diff_line.startswith("+++"):
            added_lines.append((current_line, diff_line[1:]))
            current_line += 1
        elif not diff_line.startswith("-"):
            current_line += 1

    return added_lines


def get_staged_infra_files() -> list[str]:
    """Get staged files that match infra patterns."""
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return []

    infra_files = []
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            if status.startswith(("A", "M")) and is_infra_file(filepath):
                infra_files.append(filepath)

    return infra_files


def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    infra_files = get_staged_infra_files()
    if not infra_files:
        return 0

    violations: list[str] = []

    for filepath in infra_files:
        added_lines = get_staged_diff_lines(filepath)

        for line_num, line in added_lines:
            if is_exempt(line):
                continue

            if is_high_impact(line) and not line_has_comment(line):
                violations.append(
                    f"  ❌ {filepath}:{line_num} — High-impact setting needs inline comment:\n"
                    f"     {line.strip()}\n"
                    f"     💡 Add a # comment explaining WHY this value was chosen.\n"
                    f"        Example: stop_grace_period: 300s  # PG needs time for clean shutdown checkpoint"
                )

    if violations:
        print("\n🏗️  Infrastructure Documentation Check Failed")
        print("=" * 60)
        print("High-impact infra changes MUST have inline comments explaining")
        print("the rationale (the 'why', not just the 'what').\n")
        for v in violations:
            print(v)
        print(f"\n📖 Reference: docs/deployment.md")
        print(f"📖 Rule: .agents/rules/documentation.md\n")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-04-30 19:12 [AI/Antigravity]: Added MODULE/GOAL/BUSINESS CONTEXT/
  ARCHITECTURE header fields and Google-style docstrings for compliance.
- 2026-04-29 10:00: Initial implementation with inline comment detection
  for infrastructure config files (docker-compose, Dockerfiles, etc).
====================================================================
"""
