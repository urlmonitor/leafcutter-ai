"""
MODULE: check_schema_ddl_drift.py
GOAL: Pre-commit guard that detects DDL vs actual DB column drift.
BUSINESS CONTEXT: EPIC-SecSchemaReconciliation ticket 08. The sec.parent_id column
    was silently absent from prod for 10+ days because CREATE TABLE IF NOT EXISTS
    never re-applied the new column. This guard compares CREATE TABLE column
    declarations in sql_functions/schema/tables/*.sql against information_schema.columns
    in the local DB and fails if any declared column is absent. Prevents the same
    class of drift in future.
ARCHITECTURE: Not needed.

Usage:
    python leafcutter/scripts/commit_guardian/check_schema_ddl_drift.py

Exit Codes:
    0 - No drift detected (or guard skipped due to trigger config / unreachable DB)
    1 - DDL drift detected: at least one declared column is absent from local DB

Trigger modes (configured via commit_guardian.json → ddl_drift_check.trigger):
    "always"              — run on every pre-commit (default)
    "schema_files_changed" — only run when sql_functions/schema/tables/*.sql is in
                             the staged diff; skip silently otherwise

Graceful skip:
    When DATABASE_URL is not set and the local default is unreachable, the guard
    exits 0 with a warning. A dev without a running DB should not be blocked.

Portable constraint:
    No project-specific imports. Reads only sql_functions/schema/tables/*.sql and
    queries information_schema.columns.
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config loader (inline — avoids importing config.py for portable constraint)
# ---------------------------------------------------------------------------

def _load_ddl_drift_config(script_dir: Path) -> dict[str, Any]:
    """Load ddl_drift_check section from commit_guardian.json.

    Args:
        script_dir: Directory containing commit_guardian.json.

    Returns:
        dict with ddl_drift_check config, or defaults if section is absent.
    """
    import json

    config_path = script_dir / "commit_guardian.json"
    if not config_path.exists():
        return {}
    try:
        with open(config_path, encoding="utf-8") as fh:
            full = json.load(fh)
        return full.get("ddl_drift_check", {})
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# DDL parser: extract table name and column names from CREATE TABLE blocks
# ---------------------------------------------------------------------------

def parse_create_table_columns(sql_content: str) -> dict[str, list[str]]:
    """Parse CREATE TABLE blocks and extract column names.

    Uses a simple line-by-line scan — does not require a full SQL parser.
    Handles:
        - CREATE TABLE IF NOT EXISTS table_name (
        - CREATE TABLE table_name (
        - Inline CONSTRAINT / PRIMARY KEY / UNIQUE — skipped
        - Block comments (/* ... */) stripped before parsing

    Args:
        sql_content: Raw SQL file content.

    Returns:
        dict mapping table_name (str) to list of column names (str).
        Multiple CREATE TABLE blocks in one file are each captured.
    """
    # Strip block comments first to avoid false column extractions
    sql_content = re.sub(r"/\*.*?\*/", "", sql_content, flags=re.DOTALL)

    result: dict[str, list[str]] = {}

    # Match CREATE TABLE ... (
    create_pattern = re.compile(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(?:\w+\.)?([\w]+)\s*\(",
        re.IGNORECASE,
    )

    lines = sql_content.splitlines()
    i = 0
    while i < len(lines):
        m = create_pattern.search(lines[i])
        if m:
            table_name = m.group(1).lower()
            columns: list[str] = []
            paren_depth = lines[i].count("(") - lines[i].count(")")
            i += 1
            while i < len(lines) and paren_depth > 0:
                line = lines[i].strip()
                paren_depth += line.count("(") - line.count(")")
                if paren_depth > 0 or (paren_depth == 0 and line.rstrip(")").strip()):
                    # Skip constraints, comments, empty lines
                    # A column line starts with an identifier (not a keyword like CONSTRAINT, PRIMARY, UNIQUE, CHECK, FOREIGN)
                    col_match = re.match(
                        r"^([a-z_][a-z0-9_]*)\s+\S",
                        line,
                        re.IGNORECASE,
                    )
                    if col_match:
                        word = col_match.group(1).lower()
                        # Skip SQL structural keywords that appear at column position
                        if word not in (
                            "constraint", "primary", "unique", "check", "foreign",
                            "index", "key", "exclude",
                        ):
                            columns.append(word)
                i += 1
            if columns:
                result[table_name] = columns
        else:
            i += 1

    return result


# ---------------------------------------------------------------------------
# Staged files detector
# ---------------------------------------------------------------------------

def get_staged_schema_files(repo_root: Path) -> list[Path]:
    """Return list of staged sql_functions/schema/tables/*.sql files.

    Args:
        repo_root: Absolute path to the repository root.

    Returns:
        List of Path objects for staged schema SQL files.
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True,
            text=True,
            check=True,
            cwd=str(repo_root),
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        return []

    staged: list[Path] = []
    for line in result.stdout.strip().splitlines():
        p = Path(line)
        # Match sql_functions/schema/tables/*.sql
        parts = p.parts
        if (
            len(parts) >= 4
            and parts[0] == "sql_functions"
            and parts[1] == "schema"
            and parts[2] == "tables"
            and p.suffix == ".sql"
        ):
            staged.append(repo_root / p)
    return staged


# ---------------------------------------------------------------------------
# DB checker
# ---------------------------------------------------------------------------

def get_db_columns(table_name: str, database_url: str) -> list[str] | None:
    """Fetch column names for a table from information_schema.

    Args:
        table_name: Name of the table to check (public schema only).
        database_url: psycopg2-compatible database URL.

    Returns:
        List of column names (lowercase), or None if DB is unreachable or
        the table does not exist in the DB (table may not have been created yet).
    """
    try:
        import psycopg2  # type: ignore[import-untyped]

        conn = psycopg2.connect(database_url)
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public'
                  AND table_name = %s
                ORDER BY ordinal_position
                """,
                (table_name,),
            )
            rows = cur.fetchall()
        conn.close()
        return [r[0].lower() for r in rows]
    except Exception:  # noqa: BLE001 — graceful skip on any DB error
        return None


# ---------------------------------------------------------------------------
# Per-file drift helper (extracted to reduce run_check complexity)
# ---------------------------------------------------------------------------

def _collect_violations_for_file(
    sql_file: Path,
    database_url: str,
    verbose: bool,
) -> list[str]:
    """Parse one SQL file and return DDL drift violation strings.

    Args:
        sql_file: Path to a sql_functions/schema/tables/*.sql file.
        database_url: psycopg2-compatible database URL.
        verbose: If True, print skip notices when DB is unreachable.

    Returns:
        List of human-readable violation strings (empty if no drift detected).
    """
    try:
        content = sql_file.read_text(encoding="utf-8")
    except OSError:
        return []

    table_map = parse_create_table_columns(content)
    if not table_map:
        return []

    violations: list[str] = []
    for table_name, declared_cols in table_map.items():
        db_cols = get_db_columns(table_name, database_url)
        if db_cols is None:
            if verbose:
                print(
                    f"Schema DDL drift check: cannot reach DB or table '{table_name}' "
                    f"not found — skipping '{sql_file.name}'."
                )
            continue
        if not db_cols:
            # Table exists but has no columns — temp table or view alias; skip
            continue
        for col in declared_cols:
            if col not in db_cols:
                violations.append(
                    f"DDL drift detected: table '{table_name}' declares column "
                    f"'{col}' but it is absent from the local DB. "
                    f"Run the migration or reload schema. (Source: {sql_file.name})"
                )
    return violations


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------

def run_check(
    schema_dir: Path,
    database_url: str,
    trigger: str,
    repo_root: Path,
    verbose: bool = True,
) -> bool:
    """Run the DDL drift check.

    Args:
        schema_dir: Path to sql_functions/schema/tables/ containing *.sql files.
        database_url: psycopg2-compatible database URL.
        trigger: "always" or "schema_files_changed".
        repo_root: Repository root for git diff --cached.
        verbose: If True, print progress and results.

    Returns:
        True if no drift detected (pass), False if drift detected (fail).
    """
    # Trigger gate: when "schema_files_changed", only run if a schema file is staged
    if trigger == "schema_files_changed":
        staged = get_staged_schema_files(repo_root)
        if not staged:
            if verbose:
                print("Schema DDL drift check: no sql_functions/schema/tables/*.sql staged — skipping.")
            return True
        sql_files = staged
    else:
        sql_files = list(schema_dir.glob("*.sql"))

    if not sql_files:
        if verbose:
            print("Schema DDL drift check: no SQL files to check.")
        return True

    violations: list[str] = []
    for sql_file in sql_files:
        violations.extend(_collect_violations_for_file(sql_file, database_url, verbose))

    if violations:
        print("\nSchema DDL Drift Check Failed\n")
        for v in violations:
            print(f"  {v}")
        print(
            "\nFIX: Apply the Alembic migration that adds the missing column, "
            "or run the schema reload to update the local DB.\n"
        )
        return False

    if verbose:
        print("Schema DDL drift check passed.")
    return True


def main() -> None:
    """Entry point for pre-commit invocation."""
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent  # leafcutter/scripts/commit_guardian → repo root

    cfg = _load_ddl_drift_config(script_dir)
    trigger = cfg.get("trigger", "always")

    database_url = (
        os.environ.get("DATABASE_URL")
        or "postgresql://trader:trader@localhost:5403/LIVE"
    )

    # Locate the schema tables directory relative to repo root
    schema_dir = repo_root / "sql_functions" / "schema" / "tables"
    if not schema_dir.exists():
        print("Schema DDL drift check: sql_functions/schema/tables/ not found — skipping.")
        sys.exit(0)

    passed = run_check(
        schema_dir=schema_dir,
        database_url=database_url,
        trigger=trigger,
        repo_root=repo_root,
    )
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()

# ====================================================================
# DECISION HISTORY
# ====================================================================
# - 2026-05-18 18:30 [epic-supervisor]: Created as EPIC-SecSchemaReconciliation ticket 08. (#EPIC-SecSchemaReconciliation/08)
#   Trigger locked to "schema_files_changed" per user decision Q3 (only fires when a
#   sql_functions/schema/tables/*.sql file is staged). Graceful DB-unreachable exit
#   ensures no false-positive blocks in dev environments without a running DB.
#   No project-specific imports (leafcutter constraint).
# ====================================================================
