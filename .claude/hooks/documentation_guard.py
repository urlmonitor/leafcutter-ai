"""
PreToolUse hook: Documentation sync reminder (blocking for arch-tagged files).

MODULE: documentation_guard
GOAL: Ensure code edits that touch paths mapped to architecture docs force a
      doc update in the same Claude Code session. Blocking only fires for docs
      with flight_level L1/L2/L3; informational reminder for all other mappings.
BUSINESS CONTEXT: Prevents architecture docs from drifting silently when code
      changes. The hook fires before every Edit/Write tool call that touches a
      .py or .sql file whose path is in DOC_MAPPING.
ARCHITECTURE: Claude Code PreToolUse hook — session-side, not pre-commit.

Logic:
    1. Parse the incoming tool_input for file_path.
    2. Match the path against DOC_MAPPING using longest-prefix matching.
    3. For each matched doc:
       a. If the doc has flight_level L1/L2/L3 (arch-tagged):
          - If CLAUDE_NO_DOC_UPDATE=1 env var is set: pass (escape hatch).
          - If the doc's last_updated equals today's date: pass.
          - Otherwise: block (exit 1) with a message naming the doc.
       b. Otherwise: print a reminder only (exit 0, informational).
    4. If any doc blocks: exit 1 after printing all blocking messages.

Escape hatch (arch-tagged docs only):
    Set env var CLAUDE_NO_DOC_UPDATE=1 to skip the blocking check.
    Use for trivial edits (typo fixes, comments) that genuinely don't
    affect the component's architecture.

DOC_LINKS: None
DECISION HISTORY:
  - 2026-05-12 00:00 [Agent]: Promoted documentation_guard.py from informational
    to blocking for arch-tagged (flight_level L1/L2/L3) docs (EPIC-ArchitectureDocs
    ticket 24). Updated DOC_MAPPING for new L1/L2/L3 architecture docs.
  - 2026-05-01 00:00 [Agent]: Created documentation_guard.py as informational
    PreToolUse reminder hook.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# DOC_MAPPING: code path prefix → list of related doc paths
# ---------------------------------------------------------------------------

DOC_MAPPING: dict[str, list[str]] = {
    # ---- Arch-tagged (L1/L2/L3) docs (Phase 3/4 additions) ----
    "live_trader/": [
        "docs/architecture/L3_database_phase_flows.md",
    ],
    "collector/": [
        "docs/architecture/collector_services.md",
    ],
    "models/": [
        "models/README.md",
        "docs/database-domain.md",
        "docs/architecture/L3_core_domain_erd.md",
    ],
    # ---- Existing informational mappings ----
    "live_trader/context/divergence_detector.py": [
        "docs/logic/divergence_detection.md",
        "docs/trading-strategies.md",
    ],
    "live_trader/context/sfp_detector.py": [
        "docs/logic/sfp_strategy.md",
        "docs/trading-strategies.md",
    ],
    "live_trader/context/sr_bucket_classifier.py": [
        "docs/logic/sr_classification_buckets.md",
    ],
    "live_trader/context/": [
        "docs/trading-strategies.md",
        "docs/logic/candle_context.md",
    ],
    "live_trader/logic/strategy_engine.py": [
        "docs/logic/strategy_discovery.md",
        "docs/trading-strategies.md",
    ],
    "live_trader/logic/": [
        "docs/trading-strategies.md",
        "live_trader/logic/README.md",
    ],
    "live_trader/main.py": [
        "live_trader/README.md",
        "docs/trading-strategies.md",
    ],
    "sql_functions/procedures/": [
        "docs/database-domain.md",
    ],
    "sql_functions/views/": [
        "sql_functions/views/README.md",
    ],
    "sql_functions/materialized_views/": [
        "sql_functions/materialized_views/README.md",
    ],
    "sql_functions/functions/": [
        "sql_functions/functions/README.md",
    ],
    "sql_functions/schema/": [
        "sql_functions/schema/README.md",
    ],
    "sql_functions/": [
        "docs/database-domain.md",
        "sql_functions/README.md",
    ],
    "alembic/": [
        "docs/database-domain.md",
        "models/README.md",
    ],
    "dashboards/": [
        "dashboards/edge_explorer/README.md",
    ],
    "docker-compose": [
        "docs/deployment.md",
    ],
    ".env": [
        "docs/deployment.md",
    ],
    "settings.py": [
        "docs/deployment.md",
    ],
    "ml_models/": [
        "docs/ml-pipeline.md",
    ],
    "trading_model/": [
        "docs/ml-pipeline.md",
    ],
    "backtesting/": [
        "docs/logic/backtest_framework.md",
        "backtesting/README.md",
    ],
    # ---- Collector workers (ticket 07: extend sparse DOC_MAPPING) ----
    "collector/services/feature_sync_worker/": [
        "docs/architecture/collector_services.md",
    ],
    "collector/services/thread_registry/": [
        "docs/architecture/collector_services.md",
    ],
    "collector/services/data_fixing/": [
        "docs/architecture/components/data_fixing.md",
    ],
    "collector/services/cme_gap/": [
        "docs/architecture/collector_services.md",
    ],
}

_BLOCKING_FLIGHT_LEVELS = {"L1-Context", "L2-Container", "L3-Component"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def find_project_root() -> Path:
    """Walk up from this script to find the project root (pyproject.toml).

    Returns:
        Absolute Path to the project root directory.
    """
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / "pyproject.toml").exists():
            return current
        current = current.parent
    return Path(__file__).resolve().parent.parent.parent


def get_related_docs(rel_path: str, project_root: Path) -> list[str]:
    """Find documentation files related to the edited file by prefix matching.

    More specific paths are checked first so that e.g.
    live_trader/context/divergence_detector.py matches its specific entry
    before the generic live_trader/context/ entry.

    Args:
        rel_path: Repo-relative path of the file being edited (posix slashes).
        project_root: Absolute path to the project root.

    Returns:
        List of doc paths (relative to project root) that exist on disk.
    """
    matched: list[str] = []
    seen: set[str] = set()
    sorted_keys = sorted(DOC_MAPPING.keys(), key=len, reverse=True)
    for pattern in sorted_keys:
        if rel_path.startswith(pattern) or rel_path == pattern.rstrip("/"):
            for doc in DOC_MAPPING[pattern]:
                if doc not in seen:
                    doc_path = project_root / doc
                    if doc_path.exists():
                        matched.append(doc)
                        seen.add(doc)
    return matched


def _read_frontmatter(doc_path: Path) -> dict:
    """Parse YAML frontmatter from a markdown doc.

    Args:
        doc_path: Absolute path to the markdown file.

    Returns:
        Parsed frontmatter dict; empty dict on error or missing frontmatter.
    """
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    try:
        fm = yaml.safe_load(text[3:end])
        return fm if isinstance(fm, dict) else {}
    except yaml.YAMLError:
        return {}


def _is_arch_tagged(fm: dict) -> bool:
    """Return True if frontmatter flight_level is in the blocking tier set.

    Args:
        fm: Parsed frontmatter dict.

    Returns:
        True if flight_level is L1-Context, L2-Container, or L3-Component.
    """
    return fm.get("flight_level", "") in _BLOCKING_FLIGHT_LEVELS


def _last_updated_today(fm: dict) -> bool:
    """Return True if frontmatter last_updated matches today's date.

    Args:
        fm: Parsed frontmatter dict.

    Returns:
        True if last_updated (string or date) equals today's ISO date.
    """
    last_updated = fm.get("last_updated", "")
    today = date.today().isoformat()
    return str(last_updated) == today


def classify_docs(
    related_docs: list[str],
    project_root: Path,
) -> tuple[list[str], list[str]]:
    """Classify related docs into blocking and informational groups.

    Args:
        related_docs: List of relative doc paths to classify.
        project_root: Absolute path to the project root.

    Returns:
        Tuple of (blocking_docs, informational_docs) — lists of relative paths.
        blocking_docs: docs that are arch-tagged and not updated today.
        informational_docs: all other docs (just remind, don't block).
    """
    blocking: list[str] = []
    informational: list[str] = []
    for doc in related_docs:
        fm = _read_frontmatter(project_root / doc)
        if _is_arch_tagged(fm) and not _last_updated_today(fm):
            blocking.append(doc)
        else:
            informational.append(doc)
    return blocking, informational


def _format_reminder(rel_path: str, related_docs: list[str]) -> str:
    """Build the informational reminder message string.

    Args:
        rel_path: Repo-relative path of the file being edited.
        related_docs: List of related doc paths to list in the reminder.

    Returns:
        Formatted reminder string for stderr output.
    """
    doc_lines = "\n".join(f"  -> {d}" for d in related_docs)
    return (
        f"\nDOCUMENTATION CHECK\n"
        f"{'=' * 40}\n"
        f"\nYou are editing: {rel_path}\n"
        f"\nRelated documentation that may need updating:\n"
        f"{doc_lines}\n"
        f"\nDocumentation standards (Diataxis framework):\n"
        f"  - Tutorials: Step-by-step learning (docs/tutorials/)\n"
        f"  - How-To: Task-oriented guides (docs/how-to/)\n"
        f"  - Reference: Technical details (docs/reference/)\n"
        f"  - Explanation: Conceptual understanding (docs/explanation/)\n"
    )


def _format_blocking_message(rel_path: str, blocking_docs: list[str]) -> str:
    """Build the blocking error message for arch-tagged docs not updated today.

    Args:
        rel_path: Repo-relative path of the file being edited.
        blocking_docs: List of arch-tagged doc paths that need updating.

    Returns:
        Formatted error string for stderr output.
    """
    doc_lines = "\n".join(f"  • {d}" for d in blocking_docs)
    return (
        f"\n🔒 ARCHITECTURE DOC UPDATE REQUIRED\n"
        f"{'=' * 40}\n"
        f"\nYou are editing: {rel_path}\n"
        f"\nThe following architecture docs (L1/L2/L3) must be updated in\n"
        f"the same session (bump last_updated to today's date):\n"
        f"{doc_lines}\n"
        f"\nTo skip this check (trivial edits that don't affect architecture):\n"
        f"  Set env var: CLAUDE_NO_DOC_UPDATE=1\n"
    )


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the documentation guard check on the incoming tool call.

    Reads JSON from stdin (Claude Code PreToolUse hook format).
    Exits 1 if blocking arch-tagged docs require updating; 0 otherwise.
    """
    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except Exception:
        sys.exit(0)

    tool_input = data.get("tool_input", {})
    file_path_str = tool_input.get("file_path", "")
    if not file_path_str:
        sys.exit(0)

    file_path = Path(file_path_str).resolve()
    project_root = find_project_root()

    if file_path.suffix.lower() not in (".py", ".sql"):
        sys.exit(0)

    try:
        rel_path = file_path.relative_to(project_root).as_posix()
    except ValueError:
        sys.exit(0)

    related_docs = get_related_docs(rel_path, project_root)
    if not related_docs:
        sys.exit(0)

    # Escape hatch: skip blocking check entirely
    if os.environ.get("CLAUDE_NO_DOC_UPDATE") == "1":
        all_docs_str = "\n".join(f"  -> {d}" for d in related_docs)
        print(
            f"\n[documentation_guard] CLAUDE_NO_DOC_UPDATE=1 — skipping check.\n"
            f"Reminder: these docs may still need updating:\n{all_docs_str}\n",
            file=sys.stderr,
        )
        sys.exit(0)

    blocking, informational = classify_docs(related_docs, project_root)

    if informational:
        print(_format_reminder(rel_path, informational), file=sys.stderr)

    if blocking:
        print(_format_blocking_message(rel_path, blocking), file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
