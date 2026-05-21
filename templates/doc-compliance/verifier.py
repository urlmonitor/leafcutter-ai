"""
MODULE: verifier
GOAL: Re-scan a batch of files and confirm all violations from a work order have been resolved.
BUSINESS CONTEXT: Closes the fix loop — the AI agent runs this after applying fixes to prove compliance.
ARCHITECTURE: Not needed.
"""
import sys
import typing
from pathlib import Path
import json

from scripts.doc_compliance.config import _load_config_and_registry
from scripts.doc_compliance.scanner import Scanner

def _parse_files_from_batch(batch_file: typing.Union[str, Path]) -> set[str]:
    """Extract paths to be verified from a batch work order file.

    Args:
        batch_file: Path to the batch markdown file.

    Returns:
        set[str]: Set of file paths found in the batch file.
    """
    files_to_check = set()
    with open(batch_file, "r", encoding="utf-8") as f:
        for line in f:
            if line.startswith("### Fix "):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    file_path = parts[1].strip().replace('**', '')
                    files_to_check.add(file_path)
    return files_to_check

def _report_verification_results(scanner: Scanner, files_to_check: set[str]) -> int:
    """Compare checked files against scanner violations and report results.

    Args:
        scanner: The Scanner instance that has been run.
        files_to_check: Set of file paths to verify.

    Returns:
        int: Number of files that failed verification.
    """
    passed = 0
    failed = 0
    print("\nVerification Results:\n" + chr(9473) * 19)
    for f in files_to_check:
        normalized_f = f.replace('\\', '/')
        v = next((v for v in scanner.violations if v["file"].replace('\\', '/') == normalized_f), None)
        if v:
            print(f"FAILED: {f}")
            print(f"   Still has violation: {v['type']}")
            failed += 1
        else:
            print(f"PASSED: {f}")
            passed += 1

    print(f"\nSummary: {passed} passed, {failed} failed.")
    return failed

def verify_batch(batch_id: str, output_dir: str = "reports", project_root: str = ".") -> None:
    """Verifies if fixes from a batch were applied.

    Args:
        batch_id: Batch identifier (e.g., '001').
        output_dir: Directory containing the reports.
        project_root: Root directory of the target project.
    """
    print(f"Verifying batch {batch_id}...")
    batch_file = Path(project_root) / output_dir / f"doc_compliance_batch_{batch_id}.md"
    if not batch_file.exists():
        print(f"Batch file {batch_file} not found.")
        return

    config, registry = _load_config_and_registry(project_root)
    if config is None or registry is None:
        print("Config missing. Run bootstrap and discover-components first.")
        return

    files_to_check = _parse_files_from_batch(batch_file)
    if not files_to_check:
        print("No files found in batch to verify.")
        return

    print(f"Found {len(files_to_check)} files to verify. Scanning...")
    scanner = Scanner(config, registry)
    scanner.scan_docs()
    scanner.scan_python()
    scanner.scan_sql()
    scanner.finalize_scan()

    failed = _report_verification_results(scanner, files_to_check)
    if failed > 0:
        sys.exit(1)

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-04 19:00 [Antigravity]: Initial creation. Extracted verify_batch() from the
  monolithic doc_compliance_scanner.py to reduce file size below 400-line threshold.
- 2026-05-04 19:45 [Antigravity]: Fixed Windows path normalization (single backslash) and
  fixed escaped \\n in print statements that were printing as literals instead of newlines.
====================================================================
"""
