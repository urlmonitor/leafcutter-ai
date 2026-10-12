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
ARCHITECTURE: A refusal states "<function> has complexity X, only Y allowed". The next
    step (instruction, specialist, skills) is read at refusal time from this check's
    remedy declaration through the shared loader (_remedy_declarations): that
    declaration names the restructuring specialist and the complexity-reduction
    skill. No next-step text and no agent name is kept in this file, and nothing
    here varies by committer.
"""

import ast
import subprocess
import sys
from pathlib import Path

from _resolve_root import _deploy_root_for, find_project_root

project_root = find_project_root()

from config import MAX_COMPLEXITY_SCORE, COMPLEXITY_EXCLUDED_DIRS
from _complexity_ratchet import CouldNotCheck, Refusal, UnjudgeableError, judge_file
from _file_size_ratchet import PreviousLengthSourceError, resolve_parent_revisions
from _remedy_declarations import RemedyInputError, load as load_remedy

HOOK_ID = "check-complexity"

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

def process_staged_file(
    filepath: str, max_complexity: int, parents: list[str]
) -> list[Refusal] | CouldNotCheck:
    """Judge the STAGED version of a file against each function's ceiling.

    Args:
        filepath: Path to the Python file.
        max_complexity: The complexity limit (floor of every ceiling).
        parents: Parent revisions (HEAD, plus MERGE_HEAD lines in a merge).

    Returns:
        list[Refusal] | CouldNotCheck: Functions refused, or a could-not-check
        verdict naming the file when it cannot be parsed or read. Never an
        empty list for a file that could not be judged.
    """
    path = Path(filepath)
    # Exclude certain testing and legacy directories
    if any(ex in path.parts for ex in COMPLEXITY_EXCLUDED_DIRS):
        return []
    try:
        return judge_file(filepath, max_complexity, parents, ComplexityVisitor)
    except UnjudgeableError as exc:
        return CouldNotCheck(filepath, exc.why)

def read_remedy() -> tuple[dict | None, str | None]:
    """Read check-complexity's remedy declaration through the shared loader.

    The declaration is the only source of the next step: the project's own
    tables first (local table, then package seed), then the tables beside this
    deployed script. No text is kept inside the check.

    Returns:
        tuple[dict | None, str | None]: ``(declaration, None)`` when found, else
        ``(None, reason)`` naming why none could be read.
    """
    roots = [Path.cwd(), _deploy_root_for(Path(__file__).resolve())]
    reason = f"no remedy declaration for {HOOK_ID} in the local table or the package seed"
    for root in roots:
        try:
            found = load_remedy(HOOK_ID, root)
        except RemedyInputError as exc:
            reason = str(exc)
            continue
        if found:
            return found, None
    return None, reason


def remedy_lines(declaration: dict | None, reason: str | None) -> list[str]:
    """Render the declared next step (identical for every committer).

    Args:
        declaration: The remedy declaration, or None when none could be read.
        reason: Why no declaration was read (used when ``declaration`` is None).

    Returns:
        list[str]: Output lines; never an empty or stale next step.
    """
    if not declaration:
        return [f"❌ could not read the remedy declaration, so no next step is shown: {reason}"]
    lines = [f"Next step: {declaration['instruction']}"]
    agent = declaration.get("agent")
    skills = ", ".join(declaration.get("skills") or [])
    lines.append(f"   Handled by: {agent or 'the author'}" + (f"; skills: {skills}" if skills else ""))
    return lines


def report_refusal(failed_files: list, unchecked: list) -> int:
    """Print the refusal, the declared next step and the autofix hint.

    Args:
        failed_files: ``(filepath, failures)`` pairs for files over their ceiling.
        unchecked: ``CouldNotCheck`` verdicts for files that could not be judged.

    Returns:
        int: Always 1 (the commit is refused).
    """
    print("\n🧠 Code Complexity Check Failed\n")
    print(
        "Each function is held to the greater of the limit "
        f"({MAX_COMPLEXITY_SCORE}) and its own highest previous score (its ceiling)\n"
    )

    for filepath, failures in failed_files:
        print(f"❌ {filepath}:")
        for item in failures:
            print(f"   - {item.name} has complexity {item.score}, only {item.ceiling} allowed ({item.reason})")
        print()

    for item in unchecked:
        print(f"❌ could not check {item.path}: {item.why}")
    if unchecked:
        print()

    declaration, reason = read_remedy()
    for line in remedy_lines(declaration, reason):
        print(line)
    print("   A pure move or rename of an unchanged function: commit with SKIP=check-complexity.")

    # Machine-readable autofix hint, parsed by the precommit-autofix skill.
    # The agent comes from the declaration only (GE-132a-3): no extension
    # lookup and no fallback literal.
    if declaration and declaration.get("agent"):
        print(f"AUTOFIX_AGENT: {declaration['agent']}")
    return 1


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

    try:
        parents = resolve_parent_revisions()
    except PreviousLengthSourceError as exc:
        print(f"❌ could not check staged Python files: {exc.reason}")
        return 1

    failed_files = []
    unchecked = []
    passed_files_count = 0

    for filepath, status in staged_files.items():
        if not filepath.endswith(".py") or status.startswith("D"):
            continue

        verdict = process_staged_file(filepath, MAX_COMPLEXITY_SCORE, parents)

        if isinstance(verdict, CouldNotCheck):
            unchecked.append(verdict)
        elif verdict:
            failed_files.append((filepath, verdict))
        else:
            passed_files_count += 1

    if failed_files or unchecked:
        return report_refusal(failed_files, unchecked)

    if passed_files_count > 0:
        print(f"✅ PASSED: {passed_files_count} files passed complexity checks")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-10-12 [python-coder/GE-132a-3]: Refusal now reads "<function> has
  complexity X, only Y allowed". The hard-coded tip and the
  get_agent_for_extension() lookup with its python-coder fallback are gone;
  the next step and AUTOFIX_AGENT come from the remedy declaration only.
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
