"""
MODULE: cli
GOAL: Parse CLI arguments and route execution to the appropriate doc_compliance sub-module.
BUSINESS CONTEXT: Provides the user-facing interface for the documentation compliance scanner tool.
ARCHITECTURE: Not needed.
"""
import argparse
import sys
from pathlib import Path
import json

from scripts.doc_compliance.bootstrap import init_config, bootstrap, discover_components
from scripts.doc_compliance.generator import review_registry, generate_orders
from scripts.doc_compliance.verifier import verify_batch
from scripts.doc_compliance.scanner import Scanner
from scripts.doc_compliance.config import DEFAULT_CONFIG_FILE, DEFAULT_COMPONENTS_FILE

# Ensure stdout uses UTF-8 to prevent charmap errors on Windows when printing emojis
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def summary(project_root: str = ".") -> None:
    """Print a compliance violation summary.

    Args:
        project_root: Root directory of the target project.
    """
    config_file = Path(project_root) / DEFAULT_CONFIG_FILE
    components_file = Path(project_root) / DEFAULT_COMPONENTS_FILE
    if not config_file.exists() or not components_file.exists():
        print("Config missing. Run bootstrap and discover-components first.")
        return

    with open(config_file, "r", encoding="utf-8") as f:
        config = json.load(f)
    with open(components_file, "r", encoding="utf-8") as f:
        registry = json.load(f)

    scanner = Scanner(config, registry)
    scanner.scan_docs()
    scanner.scan_python()
    scanner.scan_sql()

    print("Documentation Compliance Report")
    print(chr(9473) * 33)
    print(f"\nScanned: {scanner.stats['docs'] + scanner.stats['python'] + scanner.stats['sql']} files ({scanner.stats['docs']} docs, {scanner.stats['python']} Python, {scanner.stats['sql']} SQL)")
    print(f"Violations: {len(scanner.violations)} total")

def main() -> None:
    """CLI entrypoint for the Documentation Compliance Scanner."""
    parser = argparse.ArgumentParser(description="Documentation Compliance Scanner")
    parser.add_argument("--init", action="store_true", help="Generate a blank, project-agnostic doc_compliance.json template")
    parser.add_argument("--bootstrap", action="store_true", help="Generate draft config")
    parser.add_argument("--discover-components", action="store_true", help="Generate draft component registry")
    parser.add_argument("--review-registry", action="store_true", help="Check registry readiness or generate review work order")
    parser.add_argument("--generate-orders", action="store_true", help="Scan and generate work orders (requires reviewed registry)")
    parser.add_argument("--verify-batch", type=str, help="Verify a specific batch ID")
    parser.add_argument("--summary", action="store_true", help="Show violation summary")
    parser.add_argument("--batch-size", type=int, default=10, help="Items per work order")
    parser.add_argument("--output", type=str, default="reports", help="Output directory for work orders")
    parser.add_argument("--project-root", type=str, default=".",
                        help="Root directory of the target project (where docs/components.json lives)")

    args = parser.parse_args()

    if args.init:
        init_config(project_root=args.project_root)
    elif args.bootstrap:
        bootstrap()
    elif args.discover_components:
        discover_components(project_root=args.project_root)
    elif args.review_registry:
        review_registry(output_dir=args.output, project_root=args.project_root)
    elif args.generate_orders:
        generate_orders(batch_size=args.batch_size, output_dir=args.output, project_root=args.project_root)
    elif args.verify_batch:
        verify_batch(args.verify_batch)
    elif args.summary:
        summary(project_root=args.project_root)
    else:
        parser.print_help()

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-12 10:30 [Agent]: Added --init flag and import of init_config() from bootstrap. (#EPIC-LeafcutterMVP/01)
  --init dispatches before --bootstrap so it takes precedence when both are supplied (ticket 14).
- 2026-05-04 19:00 [Antigravity]: Initial creation. Extracted CLI argument parsing and (#EPIC-LeafcutterMVP/01)
  routing from the monolithic doc_compliance_scanner.py to reduce file size below threshold.
- 2026-05-04 19:45 [Antigravity]: Fixed escaped \\n in print statement inside summary(). (#EPIC-LeafcutterMVP/01)
====================================================================
"""
