"""
MODULE: scanner
GOAL: Audit project docs, Python, and SQL files for documentation traceability compliance violations.
BUSINESS CONTEXT: Surfaces missing frontmatter, missing DOC_LINKS, and broken bidirectional links so they can be fixed.
ARCHITECTURE: Not needed.
"""
import os
from collections import defaultdict
from pathlib import Path
from datetime import datetime, timezone

class Scanner:
    """Core scanner class that audits project files for documentation traceability compliance."""
    def __init__(self, config: dict, registry: dict) -> None:
        """Initialize the scanner with a config and component registry.

        Args:
            config: The parsed doc_compliance.json configuration dictionary.
            registry: The parsed components.json registry dictionary.
        """
        self.config = config
        self.registry = registry
        self.violations = []
        self.stats = {"docs": 0, "python": 0, "sql": 0}
        self.inbound_links = defaultdict(list)
        self.outbound_links = defaultdict(list)
        self.doc_frontmatter_missing = set()

    def is_ignored(self, path: Path) -> bool:
        """Check if a file path is ignored by the config.

        Args:
            path: The path to check.

        Returns:
            bool: True if the path is ignored, False otherwise.
        """
        path_str = str(path).replace('\\', '/')
        for ign in self.config.get("ignore", []):
            if ign in path_str:
                return True
        return False

    def scan_docs(self) -> None:
        """Scan markdown documents for compliance."""
        docs_paths = self.config.get("scan_paths", {}).get("docs", [])
        for dpath in docs_paths:
            for root, _, files in os.walk(dpath):
                for f in files:
                    if f.endswith(".md"):
                        p = Path(root) / f
                        if self.is_ignored(p): continue
                        self.stats["docs"] += 1
                        self.check_doc_frontmatter(p)

    def check_doc_frontmatter(self, path: Path) -> None:
        """Check a markdown file for valid YAML frontmatter.

        Args:
            path: Path to the markdown file to check.
        """
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        if not content.startswith("---"):
            self.doc_frontmatter_missing.add(str(path))
            self.violations.append({
                "file": str(path),
                "type": "Missing Frontmatter",
                # Priority will be upgraded to CRITICAL later if there are >3 inbound links
                "priority": "HIGH" if "docs" in path.parts else "MEDIUM",
                "suggestion": f"""---
title: "<INFER from file H1 heading or filename>"
type: <INFER: reference | how-to | explanation | tutorial>
status: draft
created: {today}
last_updated: {today}
components:
  - <INFER from docs/components.json — if new, see scripts/doc_compliance/BOOTSTRAP_GUIDE.md Step 2>
---
"""
            })
            return

        # Very simple validation
        if "title:" not in content or "components:" not in content:
            self.violations.append({
                "file": str(path),
                "type": "Invalid Frontmatter (missing required fields)",
                "priority": "HIGH",
                "suggestion": "Add missing required fields: title, type, status, created, last_updated, and components. See docs/FRONTMATTER.md for allowed values."
            })

        # Extract related_code links
        if "related_code:" in content:
            lines = content.split("---")[1].splitlines()
            in_related_code = False
            for line in lines:
                line_stripped = line.strip()
                if line_stripped == "related_code:":
                    in_related_code = True
                elif in_related_code and line_stripped.startswith("- "):
                    link = line_stripped[2:].strip(" '\"")
                    # Normalize path
                    self.outbound_links[str(path).replace('\\', '/')].append(link)
                elif in_related_code and ":" in line_stripped and not line_stripped.startswith("-"):
                    in_related_code = False

    def scan_python(self) -> None:
        """Scan python files for compliance."""
        py_paths = self.config.get("scan_paths", {}).get("python", [])
        pattern = self.config.get("code_header_pattern", "MODULE:")
        for py_path in py_paths:
            for root, _, files in os.walk(py_path):
                for f in files:
                    if f.endswith(".py"):
                        p = Path(root) / f
                        if self.is_ignored(p): continue
                        self.stats["python"] += 1
                        self.check_code_links(p, pattern, "python")

    def scan_sql(self) -> None:
        """Scan sql files for compliance."""
        sql_paths = self.config.get("scan_paths", {}).get("sql", [])
        pattern = self.config.get("sql_header_pattern", "Object Name:")
        for s_path in sql_paths:
            for root, _, files in os.walk(s_path):
                for f in files:
                    if f.endswith(".sql"):
                        p = Path(root) / f
                        if self.is_ignored(p): continue
                        self.stats["sql"] += 1
                        self.check_code_links(p, pattern, "sql")

    def check_code_links(self, path: Path, header_pattern: str, lang: str) -> None:
        """Check code files for doc link annotations in headers.

        Args:
            path: Path to the code file.
            header_pattern: The pattern indicating a file header.
            lang: Language type ('python' or 'sql').
        """
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        if header_pattern in content:
            link_pattern = "DOC_LINKS:" if lang == "python" else "Doc Links:"
            if link_pattern not in content:
                priority = "MEDIUM" if lang == "python" else "LOW"
                # Infer suggestion from folder path
                inferred_doc = f"docs/{path.parts[0]}/{path.stem}.md"
                self.violations.append({
                    "file": str(path),
                    "type": f"Missing {link_pattern}",
                    "priority": priority,
                    "suggestion": f"Add {link_pattern}\n    - {inferred_doc}"
                })
            else:
                # Extract links
                for line in content.splitlines():
                    line_stripped = line.strip()
                    if line_stripped.startswith("- docs/"):
                        link = line_stripped[2:].strip(" '\"")
                        self.inbound_links[link].append(str(path).replace('\\', '/'))

    def finalize_scan(self) -> None:
        """Cross-checks links and adjusts priorities based on references."""
        # 1. Upgrade frontmatter violations to CRITICAL if highly referenced
        for v in self.violations:
            if v["type"] == "Missing Frontmatter":
                doc_norm = v["file"].replace('\\', '/')
                # If this doc is referenced by >3 code files, it's CRITICAL
                inbound_count = len(self.inbound_links.get(doc_norm, []))
                if inbound_count > 3:
                    v["priority"] = "CRITICAL"

        # 2. Check bidirectional links
        for doc_path, code_links in self.outbound_links.items():
            for code_path in code_links:
                # Does code_path point back to doc_path?
                back_links = []
                for link, paths in self.inbound_links.items():
                    if link == doc_path and any(code_path in p for p in paths):
                        back_links.append(code_path)

                if not back_links:
                    self.violations.append({
                        "file": doc_path,
                        "type": "Bidirectional link missing",
                        "priority": "INFO",
                        "suggestion": f"Code file {code_path} is referenced in related_code, but doesn't have a {doc_path} back-link in its header."
                    })

"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-05-04 19:00 [Antigravity]: Initial creation. Extracted Scanner class from the
  monolithic doc_compliance_scanner.py to reduce file size below 400-line threshold.
- 2026-05-04 19:45 [Antigravity]: Fixed Windows path normalization — replaced all
  .replace('\\\\', '/') with .replace('\\', '/') so single-backslash paths are
  correctly normalized on Windows (str(path) returns single backslashes).
====================================================================
"""
