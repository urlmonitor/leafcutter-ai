"""
MODULE: test_enforcement
GOAL: Session-scoped AC linkage enforcement utilities for the pytest plugin.
BUSINESS CONTEXT: Tests that cover a not-yet-done AC should never block the
    CI run — they are reported informationally so the team can see them without
    treating an in-progress feature's tests as failures.
ARCHITECTURE: This module is the pure-logic layer called by conftest.py.
    It reads AC YAML files from the AC store, builds an in-memory work_status
    cache keyed on AC id, and classifies a given AC id as "informational" or
    "enforced". The conftest hook controls the pytest outcome; this module only
    classifies.

    Flow:
        conftest.py (session hook)
            └── build_ac_work_status_cache(ac_store_root) → cache dict
            └── classify_by_work_status(ac_id, cache) → "informational" | "enforced"
            └── extract_covers_tag(source_lines) → AC-ID | None
"""

from __future__ import annotations

import inspect
import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Matches "# covers: AC-ID" anywhere in a line, capturing the AC ID.
_COVERS_TAG_RE = re.compile(r"#\s*covers:\s*(\S+)")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def build_ac_work_status_cache(ac_store_root: str | Path) -> dict[str, str]:
    """Walk *ac_store_root* and return a mapping of AC id → work_status.

    Only YAML files that can be parsed and contain both an ``id`` and a
    ``work_status`` field are included.  Files that cannot be read or parsed
    are logged to stderr and skipped (no KeyError, no crash).

    Args:
        ac_store_root: Path to the root directory of the AC YAML store.

    Returns:
        Dict mapping AC id strings to their work_status strings.  An empty
        dict is returned when *ac_store_root* does not exist or contains no
        parseable YAML files.
    """
    root = Path(ac_store_root)
    cache: dict[str, str] = {}

    if not root.exists():
        print(
            f"WARNING: test_enforcement: AC store root does not exist: {root}",
            file=sys.stderr,
        )
        return cache

    for yaml_path in sorted(root.rglob("*.yaml")):
        try:
            with open(yaml_path, encoding="utf-8") as fh:
                data = yaml.safe_load(fh)
        except yaml.YAMLError as exc:
            print(
                f"WARNING: test_enforcement: YAML parse error in {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue
        except OSError as exc:
            print(
                f"WARNING: test_enforcement: cannot read {yaml_path}: {exc}",
                file=sys.stderr,
            )
            continue

        if not isinstance(data, dict):
            continue

        ac_id = data.get("id")
        work_status = data.get("work_status")
        if ac_id and work_status is not None:
            cache[str(ac_id)] = str(work_status)

    return cache


def classify_by_work_status(ac_id: str, cache: dict[str, str]) -> str:
    """Return ``"informational"`` or ``"enforced"`` for *ac_id*.

    Classification rules:

    * ``"informational"`` — the AC exists in *cache* and its work_status is
      anything other than ``"done"`` (e.g. ``"todo"``, ``"in_progress"``).
    * ``"enforced"`` — the AC's work_status is ``"done"``, OR the AC is
      absent from *cache* (fail-safe: unknown ACs are treated as enforced so
      regressions are never silently swallowed).

    Args:
        ac_id: The AC id string to classify (e.g. ``"TQ-100b-1"``).
        cache: Mapping of AC id → work_status built by
            :func:`build_ac_work_status_cache`.

    Returns:
        ``"informational"`` when the AC is not done; ``"enforced"`` otherwise.
    """
    work_status = cache.get(ac_id)
    if work_status is None:
        # AC not in store — treat as enforced (fail-safe)
        return "enforced"
    if work_status == "done":
        return "enforced"
    return "informational"


def extract_covers_tag(item: object) -> str | None:
    """Extract the AC ID from a ``# covers: <AC-ID>`` comment in *item*'s source.

    Accepts either a pytest ``Item`` (with a ``.function`` attribute) or any
    callable.  Falls back to inspecting ``item`` directly when ``.function``
    is unavailable.

    The tag is matched on any line of the function's source that contains the
    pattern ``# covers: <AC-ID>``.  Only the first match is returned.

    Args:
        item: A pytest test item or any callable whose source code contains
            a ``# covers:`` comment.

    Returns:
        The AC ID string (e.g. ``"TQ-100b-1"``), or ``None`` when no tag
        is found or the source cannot be retrieved.
    """
    func = getattr(item, "function", item)
    try:
        source = inspect.getsource(func)
    except (OSError, TypeError):
        return None

    for line in source.splitlines():
        match = _COVERS_TAG_RE.search(line)
        if match:
            return match.group(1)

    return None
