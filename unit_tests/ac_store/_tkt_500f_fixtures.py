"""
MODULE: unit_tests/ac_store/_tkt_500f_fixtures.py
GOAL: Fixture construction for the TKT-500f-5 / TKT-500f-6 generator test
      families — the canonical paths the ACs name, the minimal leaf AC record,
      and the throwaway on-disk AC store the generators are pointed at.
BUSINESS CONTEXT: Six ACs in the TKT-500f cluster constrain the same two
      generators. Their fixtures must be identical or the tests prove nothing
      about drift between them, which is the cluster's whole subject.
ARCHITECTURE: Also owns the sys.path setup for the family, because it is the
      module every other one imports first. Fixture bytes are produced by
      ``yaml.dump`` — the real serializer the AC store is written with — never a
      hand-typed literal, so the loader under test sees the real on-disk format.
COVERS: (support module — no test functions live here)
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Path setup: unit_tests/ac_store/ is 3 levels below the repo root. Done here
# because every other module in this family imports this one first.
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
for _dir in (
    REPO_ROOT / "scripts" / "ac_store",
    REPO_ROOT / "scripts" / "commit_guardian",
):
    if str(_dir) not in sys.path:
        sys.path.insert(0, str(_dir))

# ---------------------------------------------------------------------------
# Canonical fixture paths, copied verbatim from the ACs' Gherkin
# ---------------------------------------------------------------------------

#: The qualifying implementation .py named by TKT-500f-6 / -6-i / -6-ii / -6-iii-a.
IMPL_PY = "scripts/ac_store/generate_ticket_from_ac.py"
#: The documentation path named by TKT-500f-6-i.
DOCS_MD = "docs/reference/ac-schema.md"
#: The configuration path named by TKT-500f-6-i.
CONFIG_JSON = "config/agent_registry.json"
#: A ``test_*.py`` basename — TKT-500f-6-ii's first exclusion form.
TEST_PY_PREFIX = "unit_tests/test_generate_ticket.py"
#: A ``*_test.py`` basename — TKT-500f-6-ii's second exclusion form.
TEST_PY_SUFFIX = "scripts/ac_store/generator_test.py"
#: A ``.py`` under ``tickets/`` — TKT-500f-6-ii's path-based exclusion.
TICKETS_PY = "tickets/00_inbox/helper.py"
#: An agent-template edit surface — TKT-500f-5's llm-expert substitution branch.
TEMPLATE_MD = "templates/agents/ticket-supervisor.md"
#: A skill-template edit surface — the second half of the same branch.
SKILL_TEMPLATE_MD = "templates/skills/signoff/SKILL.md"

#: Minimal three-line Gherkin. Every fixture AC shares it so that differences
#: in generator output are attributable to files_touched / assigned_agent alone.
_FIXTURE_CRITERIA = (
    "Given a fixture acceptance criterion\n"
    "When a ticket is generated from it\n"
    "Then the generator behaves as the AC under test requires.\n"
)


def edit_surface_links(*paths: str) -> list[dict[str, str]]:
    """Return ``doc_links`` entries that land *paths* in the ticket's files_touched.

    ``constrains`` is one of the generator's edit-surface relationships, so each
    path becomes a ``files_touched`` entry. This is the only supported lever for
    controlling a generated ticket's files_touched list: an AC record has no
    ``files_touched`` field of its own — the generator derives it.

    Args:
        *paths: Repo-relative path strings to declare as edit surfaces.

    Returns:
        A ``doc_links`` list, one ``constrains`` entry per path.
    """
    return [{"path": p, "relationship": "constrains"} for p in paths]


def make_ac(
    *,
    assigned_agent: str = "python-coder",
    files_touched: tuple[str, ...] | list[str] = (),
    level: str = "L2",
    title: str = "TKT-500f fixture AC",
) -> dict:
    """Build a minimal leaf AC record for the generator to consume.

    Args:
        assigned_agent: Value for the AC's ``assigned_agent`` field.
        files_touched: Paths to declare as edit surfaces via ``doc_links``.
        level: AC flight level.
        title: AC title.

    Returns:
        An AC record dict, ready to be serialized into a throwaway store.
    """
    return {
        "title": title,
        "level": level,
        "status": "active",
        "req_status": "active",
        "work_status": "todo",
        "component": "ticket-creation",
        "assigned_agent": assigned_agent,
        "criteria": _FIXTURE_CRITERIA,
        "doc_links": edit_surface_links(*files_touched),
    }


def write_ac_store(root: Path, ac_id: str, ac: dict) -> Path:
    """Serialize *ac* into a throwaway AC store rooted at *root*.

    The bytes are written by ``yaml.dump`` — the real serializer — rather than a
    hand-typed literal, so the record the generator loads has the real on-disk
    shape (block lists at column 0, folded strings, and all).

    Args:
        root: Directory that will become ``--ac-root``.
        ac_id: The AC id; also the file stem.
        ac: The AC record to serialize.

    Returns:
        Path: The ``--ac-root`` directory.
    """
    component_dir = root / "fixture-component"
    component_dir.mkdir(parents=True, exist_ok=True)
    record = dict(ac)
    record["id"] = ac_id
    (component_dir / f"{ac_id}.yaml").write_text(
        yaml.dump(record, allow_unicode=True), encoding="utf-8"
    )
    return root


"""
====================================================================
DECISION HISTORY
====================================================================
- 2026-09-14 [TKT-500f-5 / -6 cluster/test-writer]: Split out of
  _tkt_500f_support.py, which reached 601 lines against the 400-line .py limit
  in scripts/commit_guardian/commit_guardian.json (no test-file exemption
  exists). Split by concern rather than by line count: this module owns
  fixtures, _tkt_500f_generators.py owns entry-point invocation, and
  _tkt_500f_support.py remains the single facade the test files import.
====================================================================
"""
