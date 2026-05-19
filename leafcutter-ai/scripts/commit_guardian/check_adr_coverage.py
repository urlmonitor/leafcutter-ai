"""
Pre-commit hook that warns when major structural changes land without a new or updated ADR.

MODULE: check_adr_coverage
GOAL: Detect commits that add major structural changes (new dependencies, database
    migrations, infrastructure services, or core registry components) without an
    accompanying new or updated ADR in the same commit.
BUSINESS CONTEXT: Ensures architectural context is never lost. Large structural
    changes are meaningless to future maintainers without the "why" — ADRs provide
    that durable context.
ARCHITECTURE: Not needed.

Triggers (any staged file matching these patterns fires the warning):
    1. pyproject.toml (tool.poetry.dependencies changes) — new external dependencies
    2. alembic/versions/*.py — new database migrations / schema additions
    3. models/*.py — new ORM model files (new tables)
    4. docker-compose*.yml — new service added to infrastructure
    5. docs/components.json — new component with type "core" or "service"

The hook is ADVISORY only (exit code always 0). It emits AGENT_HINT context so
AI agents can decide whether the change requires an ADR or not.

Exit Codes:
    0 — Always (advisory-only hook)
"""

import json
import re
import subprocess
import sys
from pathlib import Path


def get_staged_files() -> list[str]:
    """Return the list of staged file paths.

    Returns:
        list[str]: List of relative file paths staged for the current commit.
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True, text=True, check=False
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def has_adr_staged(staged: list[str]) -> bool:
    """Check if any ADR file is staged in the current commit.

    Args:
        staged: List of staged file paths.

    Returns:
        bool: True if at least one file in adr/ is staged.
    """
    return any(f.startswith("adr/") and f.endswith(".md") for f in staged)


def check_pyproject_deps(staged: list[str]) -> str | None:
    """Warn if pyproject.toml is staged (possible new dependency).

    Args:
        staged: List of staged file paths.

    Returns:
        str | None: Warning message if triggered, None otherwise.
    """
    if "pyproject.toml" not in staged:
        return None
    diff = subprocess.run(
        ["git", "diff", "--cached", "pyproject.toml"],
        capture_output=True, text=True, check=False
    ).stdout
    added_lines = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    dep_section = False
    for line in added_lines:
        if "[tool.poetry.dependencies]" in line or "[tool.poetry.dev-dependencies]" in line:
            dep_section = True
        if dep_section and re.match(r'^\+[a-zA-Z]', line):
            return "pyproject.toml: new dependency added"
    return None


def check_alembic_migration(staged: list[str]) -> str | None:
    """Warn if a new alembic migration is staged.

    Args:
        staged: List of staged file paths.

    Returns:
        str | None: Warning message if triggered, None otherwise.
    """
    for f in staged:
        if f.startswith("alembic/versions/") and f.endswith(".py"):
            return f"alembic/versions/: new migration {Path(f).name}"
    return None


def check_new_models(staged: list[str]) -> str | None:
    """Warn if a new ORM model file is staged.

    Args:
        staged: List of staged file paths.

    Returns:
        str | None: Warning message if triggered, None otherwise.
    """
    new_models = [
        f for f in staged
        if f.startswith("models/") and f.endswith(".py")
        and f not in ("models/__init__.py", "models/base.py")
    ]
    if new_models:
        return f"models/: new model file(s): {', '.join(new_models)}"
    return None


def check_docker_compose(staged: list[str]) -> str | None:
    """Warn if docker-compose is staged with a new service.

    Args:
        staged: List of staged file paths.

    Returns:
        str | None: Warning message if triggered, None otherwise.
    """
    dc_files = [f for f in staged if re.match(r"docker-compose.*\.ya?ml", f)]
    if not dc_files:
        return None
    for f in dc_files:
        diff = subprocess.run(
            ["git", "diff", "--cached", f],
            capture_output=True, text=True, check=False
        ).stdout
        added = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
        # Heuristic: a new service block starts with an indented key at level 1
        for line in added:
            if re.match(r'^\+  [a-zA-Z][a-zA-Z0-9_-]+:$', line):
                return f"{f}: possible new Docker service added"
    return None


def check_components_registry(staged: list[str]) -> str | None:
    """Warn if a new core/service component is added to components.json.

    Args:
        staged: List of staged file paths.

    Returns:
        str | None: Warning message if triggered, None otherwise.
    """
    if "docs/components.json" not in staged:
        return None
    diff = subprocess.run(
        ["git", "diff", "--cached", "docs/components.json"],
        capture_output=True, text=True, check=False
    ).stdout
    added = "\n".join(l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++"))
    if '"type": "core"' in added or '"type": "service"' in added:
        return "docs/components.json: new core/service component registered"
    return None


def main() -> None:
    """Run all ADR coverage checks and emit advisory warnings."""
    staged = get_staged_files()
    if not staged:
        sys.exit(0)

    checks = [
        check_pyproject_deps(staged),
        check_alembic_migration(staged),
        check_new_models(staged),
        check_docker_compose(staged),
        check_components_registry(staged),
    ]
    triggered = [c for c in checks if c is not None]

    if not triggered:
        sys.exit(0)

    if has_adr_staged(staged):
        # An ADR is already in the commit — suppress the warning
        sys.exit(0)

    for trigger in triggered:
        print(f"\033[93mWARNING [check_adr_coverage] {trigger}\033[0m")
        print(
            "\033[96m  AGENT_HINT: This change may warrant an ADR. "
            "If it introduces a new architectural decision (new dependency, "
            "new infrastructure service, new core component, or new schema entity), "
            "scaffold an ADR in adr/ and include it in this commit. "
            "Skip if this is a patch, rename, or dependency version bump with no "
            "architectural impact.\033[0m"
        )

    print(f"\n\033[93m[!] ADR Coverage: {len(triggered)} structural change(s) without an ADR in this commit.\033[0m")
    sys.exit(0)  # Always advisory


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-12 10:45 [Agent]: Initial creation. Advisory pre-commit hook that detects (#EPIC-LeafcutterMVP/01)
  major structural changes (new dependencies, migrations, models, docker services,
  core registry components) without an ADR in the same commit. Always exits 0
  (advisory only). Ticket 16 EPIC-DocTraceability.
- 2026-05-13 08:50 [CC-42 autofix]: Replaced U+26A0 emoji in summary print with ASCII (#EPIC-LeafcutterMVP/01)
  [!] to avoid UnicodeEncodeError on Windows (cp1252 terminal). Hook was crashing
  with exit code 1 instead of advisory exit 0.
====================================================================
"""
