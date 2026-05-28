"""
Pre-commit hook to block Python files with excessively complex functions or methods.

Checks:
- Uses the `ast` module to calculate Cyclomatic Complexity for each function/method.
- Blocks commits if any function exceeds MAX_COMPLEXITY_SCORE (defined in config.py).

Usage:
    poetry run python scripts/commit_guardian/check_complexity.py

MODULE: check_complexity.py
GOAL: Enforce cyclomatic complexity limits on Python functions at commit time.
BUSINESS CONTEXT: Keeps codebase maintainable by preventing overly complex functions.
ARCHITECTURE: Not needed.
"""

import ast
import json
import subprocess
import sys
from pathlib import Path

from _resolve_root import find_project_root

project_root = find_project_root()

from config import MAX_COMPLEXITY_SCORE, COMPLEXITY_EXCLUDED_DIRS

class ComplexityVisitor(ast.NodeVisitor):
    """AST visitor that calculates cyclomatic complexity by counting branches."""

    def __init__(self) -> None:
        """Initialize with a base complexity of 1."""
        self.complexity = 1

    def visit_If(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_For(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_While(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_With(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node):
        self.complexity += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node):
        self.complexity += len(node.values) - 1
        self.generic_visit(node)

    def visit_Match(self, node):
        self.complexity += len(node.cases)
        self.generic_visit(node)

    def visit_comprehension(self, node):
        self.complexity += 1
        self.generic_visit(node)


def calculate_complexities(source_code: str) -> list[tuple[str, int]]:
    """Calculate cyclomatic complexity for every function in the source.

    Args:
        source_code: Python source code to analyse.

    Returns:
        list[tuple[str, int]]: Pairs of (function_name, complexity_score).
    """
    try:
        tree = ast.parse(source_code)
    except SyntaxError:
        return []

    results = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            visitor = ComplexityVisitor()
            # Visit the body of the function
            for stmt in node.body:
                visitor.visit(stmt)
            results.append((node.name, visitor.complexity))
            
    return results

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

def process_staged_file(filepath: str, max_complexity: int) -> list[tuple[str, int]]:
    """Check a single file for functions exceeding complexity threshold.

    Args:
        filepath: Path to the Python file.
        max_complexity: Maximum allowed cyclomatic complexity.

    Returns:
        list[tuple[str, int]]: Functions that exceed the threshold.
    """
    path = Path(filepath)
    # Exclude certain testing and legacy directories
    if any(ex in path.parts for ex in COMPLEXITY_EXCLUDED_DIRS):
        return []
        
    try:
        content = path.read_text(encoding="utf-8")
        function_complexities = calculate_complexities(content)
        
        file_failures = []
        for func_name, score in function_complexities:
            if score > max_complexity:
                file_failures.append((func_name, score))
        return file_failures
    except Exception:
        return []

def get_agent_for_extension(
    ext: str,
    registry_path: Path | None = None,
) -> str | None:
    """Return the agent id whose owns_file_extensions contains the given extension.

    Reads ``agent_registry.json`` and iterates entries, returning the agent id
    whose ``owns_file_extensions`` array contains the requested extension.
    Fails open: returns ``None`` (no exception) when the registry is missing,
    unreadable, or contains no matching entry.

    Args:
        ext: File extension with leading dot, e.g. ``".py"`` or ``".sql"``.
        registry_path: Optional path to ``agent_registry.json``. Defaults to
            ``leafcutter/config/agent_registry.json`` relative to
            this script's location.

    Returns:
        str | None: Agent id (e.g. ``"python-coder"``) if a match is found,
            else ``None``.
    """
    if registry_path is None:
        registry_path = (
            find_project_root()
            / "leafcutter"
            / "config"
            / "agent_registry.json"
        )
    try:
        with open(registry_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    for entry in data.get("agents", []):
        extensions = entry.get("owns_file_extensions") or []
        if ext in extensions:
            return entry.get("id")
    return None


def main() -> int:
    """Run complexity checks on all staged Python files.

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
        if not filepath.endswith(".py"):
            continue
            
        file_failures = process_staged_file(filepath, MAX_COMPLEXITY_SCORE)
        
        if file_failures:
            failed_files.append((filepath, file_failures))
        else:
            passed_files_count += 1

    if failed_files:
        print("\n🧠 Code Complexity Check Failed\n")
        print(f"Functions exceed the maximum allowed Cyclomatic Complexity of {MAX_COMPLEXITY_SCORE}\n")
        
        for filepath, failures in failed_files:
            print(f"❌ {filepath}:")
            for func_name, score in failures:
                print(f"   - Function '{func_name}' has complexity {score}")
            print()
            
        print("💡 Tip: Try breaking these large functions into smaller, private helper functions.")
        print("   Use the `complexity-reduction` skill to safely refactor and extract components.")

        # Machine-readable autofix hint — parsed by the precommit-autofix skill
        # to route directly to the correct coder. Looked up from agent_registry.json
        # via owns_file_extensions; falls back to python-coder when the lookup
        # returns None (complexity violations are always Python).
        agent = get_agent_for_extension(".py") or "python-coder"
        print(f"AUTOFIX_AGENT: {agent}")
        return 1

    if passed_files_count > 0:
        print(f"✅ PASSED: {passed_files_count} files passed complexity checks")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-15 07:35 [ticket-12]: Added AUTOFIX_AGENT hint emission via
  the new get_agent_for_extension() helper, which reads
  leafcutter/config/agent_registry.json and matches the
  .py extension against the owns_file_extensions field. Falls back to
  python-coder when the lookup returns None (registry missing,
  unreadable, or no matching entry). AUTOFIX_AGENT is only emitted on
  violation; clean files are unaffected. Mirrors the pattern
  established by ticket 11 for check_doc_length.py.
- 2026-04-30 19:12 [AI/Antigravity]: Added MODULE/GOAL/BUSINESS CONTEXT
  header fields and -> None to __init__ for type annotation compliance.
- 2026-04-29 10:00: Initial implementation using AST-based cyclomatic
  complexity scoring.
====================================================================
"""
