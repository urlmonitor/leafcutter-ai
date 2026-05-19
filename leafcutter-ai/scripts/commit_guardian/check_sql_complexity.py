"""
Pre-commit hook to block SQL files with excessively complex functions or queries.

Checks:
- Uses an heuristic keyword-counting approach to estimate SQL Cyclomatic Complexity.
- Blocks commits if the file exceeds MAX_SQL_COMPLEXITY_SCORE (defined in config.py).

Usage:
    poetry run python scripts/commit_guardian/check_sql_complexity.py

MODULE: check_sql_complexity.py
GOAL: Enforce SQL cyclomatic complexity limits at commit time.
BUSINESS CONTEXT: Keeps SQL procedures maintainable by blocking overly complex logic.
ARCHITECTURE: Not needed.
"""

import re
import subprocess
import sys
from pathlib import Path

# Fix import path when running from root
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.commit_guardian.config import MAX_SQL_COMPLEXITY_SCORE, SQL_COMPLEXITY_EXCLUDED_DIRS

# Keywords that dramatically increase structural complexity in SQL / PL/pgSQL
COMPLEXITY_KEYWORDS = re.compile(
    r'\b(IF|ELSIF|CASE|WHEN|AND|OR|COALESCE|NULLIF|LEAST|GREATEST|LOOP|WHILE|FOR|EXCEPTION|WITH)\b',
    re.IGNORECASE
)

def calculate_sql_complexity(source_code: str) -> int:
    """Estimate SQL complexity by counting branching/logic keywords, and handling PL/Python via AST.

    Args:
        source_code: Raw SQL source code to analyse.

    Returns:
        int: Complexity score.
    """
    max_complexity = 1

    # Check for PL/Python functions
    plpython_bodies = re.findall(r'\$\$(.*?)\$\$\s+LANGUAGE\s+plpython3u\b', source_code, flags=re.IGNORECASE | re.DOTALL)
    if not plpython_bodies:
        # Check $BODY$ variation
        plpython_bodies = re.findall(r'\$BODY\$(.*?)\$BODY\$\s+LANGUAGE\s+plpython3u\b', source_code, flags=re.IGNORECASE | re.DOTALL)

    if plpython_bodies:
        from scripts.commit_guardian.check_complexity import calculate_complexities
        for body in plpython_bodies:
            # Wrap in dummy function to make indentation valid
            indented = "\n".join("    " + line for line in body.splitlines())
            wrapped_body = f"def __wrapped__():\n{indented}"
            
            res = calculate_complexities(wrapped_body)
            if res:
                for _, score in res:
                    if score > max_complexity:
                        max_complexity = score

    # Strip plpython bodies from source_code so they don't get counted as SQL keywords!
    source_no_plpython = re.sub(r'\$\$(.*?)\$\$\s+LANGUAGE\s+plpython3u\b', '$$ $$ LANGUAGE plpython3u', source_code, flags=re.IGNORECASE | re.DOTALL)
    source_no_plpython = re.sub(r'\$BODY\$(.*?)\$BODY\$\s+LANGUAGE\s+plpython3u\b', '$BODY$ $BODY$ LANGUAGE plpython3u', source_no_plpython, flags=re.IGNORECASE | re.DOTALL)
    
    # Strip block comments /* ... */
    code_no_block_comments = re.sub(r'/\*.*?\*/', '', source_no_plpython, flags=re.DOTALL)
    # Strip line comments -- ...
    code_no_comments = re.sub(r'--.*', '', code_no_block_comments)
    
    matches = COMPLEXITY_KEYWORDS.findall(code_no_comments)
    sql_complexity = len(matches) + 1
    
    return max(max_complexity, sql_complexity)

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

def main() -> int:
    """Run SQL complexity checks on all staged SQL files.

    Returns:
        int: Exit code (0 = pass, 1 = violations found).
    """
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except AttributeError:
            pass

    staged_files = get_staged_files()
    if not staged_files:
        return 0

    failed_files = []
    passed_files_count = 0
    
    for filepath, status in staged_files.items():
        if not filepath.endswith(".sql"):
            continue
            
        path = Path(filepath)
        # Exclude certain migration directories
        if any(ex in path.parts for ex in SQL_COMPLEXITY_EXCLUDED_DIRS):
            continue
            
        try:
            content = path.read_text(encoding="utf-8")
            complexity = calculate_sql_complexity(content)
            
            if complexity > MAX_SQL_COMPLEXITY_SCORE:
                failed_files.append((filepath, complexity))
            else:
                passed_files_count += 1
                
        except Exception:
            continue

    if failed_files:
        print("\n🧠 SQL Code Complexity Check Failed\n")
        print(f"Files exceed the maximum allowed SQL Cyclomatic Complexity of {MAX_SQL_COMPLEXITY_SCORE}\n")
        
        for filepath, score in failed_files:
            print(f"❌ {filepath}: Complexity score = {score}")
            
        print("\n💡 Tip: Try breaking large SQL procedures into smaller functions, or using temporary tables to simplify logic.")
        return 1

    if passed_files_count > 0:
        print(f"✅ PASSED: {passed_files_count} files passed SQL complexity checks")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-04-30 19:12 [AI/Antigravity]: Added MODULE/GOAL/BUSINESS CONTEXT/
  ARCHITECTURE header fields and Google-style docstrings for compliance.
- 2026-04-29 10:00: Initial implementation with heuristic keyword-counting
  approach for SQL cyclomatic complexity estimation.
====================================================================
"""
