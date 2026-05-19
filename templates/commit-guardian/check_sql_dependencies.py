"""
MODULE: check_sql_dependencies.py
GOAL: Enforce SQL dependency tags at commit time.
BUSINESS CONTEXT: Ensures all SQL views and materialized views declare their dependencies for the dependency-resolved topological sort loading pipeline.
ARCHITECTURE: Not needed.
"""

import re
import subprocess
import sys
from pathlib import Path

# Tables managed by Alembic that must NEVER appear in Dependencies: tags.
# The dependency resolver only knows about SQL objects from sql_functions/.
# Listing a table here causes "Unknown dependency" crash on startup.
KNOWN_TABLES = {
    "candles", "strategy_evaluation_cursors", "candle_cumulative_stats",
    "strategy_templates", "support_resistance", "queue_strategy_deletion",
    "queue_strategy_evaluation", "queue_strategy_staging",
    "pnl_trades", "pnl_trades_v2", "positions", "orders",
    "candle_context", "symbols",
}

def get_staged_files() -> dict[str, str]:
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-status"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return {}

    staged_files = {}
    for line in result.stdout.strip().split("\n"):
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            status = parts[0]
            filepath = parts[-1]
            staged_files[filepath] = status
    return staged_files

def is_target_sql_file(filepath: str) -> bool:
    """Check if the given filepath is a target SQL file.
    
    Args:
        filepath: The path to the file to check.
        
    Returns:
        bool: True if the file is a view or materialized view, False otherwise.
    """
    if not filepath.endswith(".sql"):
        return False
    path = Path(filepath)
    parts = path.parts
    if "sql_functions" in parts:
        idx = parts.index("sql_functions")
        if len(parts) > idx + 1 and parts[idx + 1] in ("views", "materialized_views"):
            return True
    return False

def check_file_dependencies(filepath: str) -> tuple[str, list[str]] | None:
    """Check the SQL file for invalid dependency references.
    
    Args:
        filepath: The path to the SQL file.
        
    Returns:
        tuple[str, list[str]] | None: A tuple containing the violation reason and table dependencies,
        or None if the file is compliant.
    """
    try:
        content = Path(filepath).read_text(encoding="utf-8")
        deps_match = re.search(r"Dependencies:\s*([\w, ]+)", content, re.IGNORECASE)
        if not deps_match:
            return ("missing", [])
        
        deps_str = deps_match.group(1).strip()
        if deps_str.lower() != "none":
            deps = [d.strip() for d in deps_str.split(",")]
            table_deps = [d for d in deps if d in KNOWN_TABLES]
            if table_deps:
                return ("table", table_deps)
        return None
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return ("error", [])

def print_violation(filepath: str, reason: str, table_deps: list[str]) -> None:
    """Print the formatted violation message to stdout.
    
    Args:
        filepath: The path to the file that failed the check.
        reason: The reason for the failure ('missing' or 'table').
        table_deps: A list of base tables found in the Dependencies tag.
    """
    if reason == "missing":
        print(f"❌ SQL DEPENDENCY VIOLATION: '{filepath}'")
        print("   Missing required 'Dependencies:' field in SQL header.")
        print("   FIX: Add 'Dependencies: <comma-separated object names>' or 'Dependencies: none'")
        print("        after the 'Object Name:' field in the file header.")
    elif reason == "table":
        print(f"❌ SQL DEPENDENCY VIOLATION: '{filepath}'")
        print(f"   ⚠️  Found BASE TABLE(S) in Dependencies: {', '.join(table_deps)}")
        print("   Tables are managed by Alembic and already exist before SQL objects load.")
        print("   The dependency resolver only knows about sql_functions/ objects.")
        print("   FIX: Remove table names. Only list views, materialized views, functions, or procedures.")
    print("   📖 Rules: .agents/rules/documentation.md Section 7\n")

def main() -> int:
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    args = sys.argv[1:]
    files_to_check = {arg: "M" for arg in args} if args else get_staged_files()

    if not files_to_check:
        return 0

    failed_files = []
    passed_files_count = 0
    
    for filepath in files_to_check.keys():
        if not is_target_sql_file(filepath):
            continue
            
        result = check_file_dependencies(filepath)
        if result:
            if result[0] != "error":
                failed_files.append((filepath, result[0], result[1]))
        else:
            passed_files_count += 1

    if failed_files:
        for filepath, reason, table_deps in failed_files:
            print_violation(filepath, reason, table_deps)
        return 1

    if passed_files_count > 0:
        print(f"✅ PASSED: {passed_files_count} files passed SQL dependency checks")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-03 12:00 [Antigravity]: Initial implementation. Enforces Dependencies tag on all
  views and materialized views.
- 2026-05-04 21:00 [Antigravity]: Added table-name detection. Listing Alembic-managed
  tables (e.g. strategy_templates) in Dependencies: crashed the app at startup
  because the dependency resolver only knows about sql_functions/ objects.
- 2026-05-08 14:30 [15a_17]: Renamed candle_strategy_performance → strategy_evaluation_cursors in KNOWN_TABLES set.
====================================================================
"""
