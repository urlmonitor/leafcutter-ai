"""
MODULE: unit_tests/ac_store/_tkt_500f_support.py
GOAL: Single facade the six TKT-500f-5 / TKT-500f-6 test files import from.
      Re-exports the fixture builders (_tkt_500f_fixtures) and the real
      generator entry points (_tkt_500f_generators), and owns the two
      real-artifact readers the ACs need: the on-disk agent registry, and an
      AST scan for the shared implementation-.py classification predicate.
BUSINESS CONTEXT: One import line per test file keeps the six sibling suites
      genuinely interchangeable, which matters because the cluster's subject is
      that two generators must not drift — the tests proving it must not either.
ARCHITECTURE: Nothing in this family patches anything; see
      _tkt_500f_generators' ARCHITECTURE note on the 8b2b899ae module split.
COVERS: (support module — no test functions live here)
"""

from __future__ import annotations

import ast
import json

from _tkt_500f_fixtures import (
    CONFIG_JSON,
    DOCS_MD,
    IMPL_PY,
    REPO_ROOT,
    SKILL_TEMPLATE_MD,
    TEMPLATE_MD,
    TEST_PY_PREFIX,
    TEST_PY_SUFFIX,
    TICKETS_PY,
    edit_surface_links,
    make_ac,
    write_ac_store,
)
from _tkt_500f_generators import (
    Generated,
    extract_requirements_section,
    generate_dry_run,
    generate_for_absent_ac,
    generate_via_goal_path,
    generate_written,
    parse_frontmatter,
)

from check_ticket_test_requirements import (  # noqa: E402
    _has_populated_test_requirements as consumer_reads_requirements_present,
)
from check_ticket_test_requirements import (  # noqa: E402
    check_ticket_has_test_requirements as consumer_verdict,
)

__all__ = [
    "CONFIG_JSON",
    "DOCS_MD",
    "Generated",
    "IMPL_PY",
    "REPO_ROOT",
    "SKILL_TEMPLATE_MD",
    "TEMPLATE_MD",
    "TEST_PY_PREFIX",
    "TEST_PY_SUFFIX",
    "TICKETS_PY",
    "agent_registry_entries",
    "consumer_reads_requirements_present",
    "consumer_verdict",
    "edit_surface_links",
    "extract_requirements_section",
    "generate_dry_run",
    "generate_for_absent_ac",
    "generate_via_goal_path",
    "generate_written",
    "make_ac",
    "parse_frontmatter",
    "predicate_owning_functions",
    "write_ac_store",
]


# ---------------------------------------------------------------------------
# Real-artifact readers
# ---------------------------------------------------------------------------


def agent_registry_entries() -> list[dict]:
    """Return every entry of the REAL ``config/agent_registry.json``.

    Read off disk rather than hand-typed, so a test built on it tracks the
    registry as it actually is — which is the property TKT-500f-5's
    real_artifact descriptor asks for.

    Returns:
        list[dict]: The registry's agent entries.

    Raises:
        OSError: When the registry cannot be read.
        ValueError: When the registry is not valid JSON or has no agent list.
    """
    registry_path = REPO_ROOT / "config" / "agent_registry.json"
    try:
        raw = json.loads(registry_path.read_text(encoding="utf-8"))
    except OSError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"{registry_path} is not valid JSON: {exc}") from exc
    entries = raw.get("agents") if isinstance(raw, dict) else raw
    if not isinstance(entries, list) or not entries:
        raise ValueError(f"{registry_path} contains no agent entries")  # noqa: TRY003
    return entries


#: Literals that together fingerprint the qualifying-implementation-.py
#: predicate TKT-500f-6 / -6-ii / -6-iii-a define. A function that excludes
#: ``*_test.py`` basenames, ``test_*`` basenames AND ``tickets/`` paths is, by
#: construction, an implementation of that predicate; nothing else in
#: ``scripts/`` has a reason to mention all three.
_PREDICATE_MARKERS = ("_test.py", "test_", "tickets")


def predicate_owning_functions() -> list[str]:
    """Return every function under ``scripts/`` that implements the impl-.py predicate.

    Walks the AST of each module rather than grepping, so a marker that appears
    only in a module docstring or an unrelated string constant elsewhere in the
    file does not count — the three markers must co-occur inside one function.

    Returns:
        list[str]: ``"<repo-relative path>::<function name>"`` for each match,
        sorted. An empty list means the predicate is not implemented anywhere;
        more than one entry means it has been duplicated or inlined.
    """
    found: list[str] = []
    for module in sorted((REPO_ROOT / "scripts").rglob("*.py")):
        try:
            source = module.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError, UnicodeDecodeError):
            # An unreadable or unparseable module cannot own the predicate;
            # skipping it is correct and must not fail the scan.
            continue
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            segment = ast.get_source_segment(source, node) or ""
            if all(marker in segment for marker in _PREDICATE_MARKERS):
                found.append(f"{module.relative_to(REPO_ROOT)}::{node.name}")
    return sorted(found)


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-5 / -6 cluster/test-writer]: Created as the shared
  harness for the six sibling test files, then reduced to a facade when it
  reached 601 lines against the 400-line .py limit in
  scripts/commit_guardian/commit_guardian.json (which exempts no test files).
  Fixtures moved to _tkt_500f_fixtures.py and entry-point invocation to
  _tkt_500f_generators.py; the six test files' import lines were left unchanged,
  so the split cost them nothing.
====================================================================
"""
