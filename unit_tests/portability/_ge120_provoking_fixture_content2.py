"""
MODULE: _ge120_provoking_fixture_content2
GOAL: Second batch of file-content builders for the shared GE-120 provoking
    fixture, added to push more `hooks_manifest.hooks[]` checks from `clean`
    to `violation` (GE-120b-2-i baseline-strengthening pass). Split out of
    `_ge120_provoking_fixture_content.py` purely to respect the project's
    400-line new-file limit — that module was already at 387 lines with no
    headroom for this batch.
BUSINESS CONTEXT: See `_ge120_provoking_fixture.py`'s module docstring for the
    full rationale. A check that stays clean against the fixture proves
    nothing about whether it still runs; every check moved here from clean to
    violation makes the GE-120b-2-i baseline a stronger regression signal.
ARCHITECTURE: Pure string/dict builders — no I/O, no git calls. `build_files_2()`
    returns the repo-relative-path -> content mapping this batch adds;
    `_ge120_provoking_fixture_content.build_files()` merges it into the full
    fixture file set.
DECISION HISTORY: 2026-09-28 [python-coder/GE-120b-2-i, second pass] — added to
    provoke check-debug-scripts, check-root-files, check-sql-complexity,
    check-doc-types-agents, check-roadmap-schema, check-paths-integrity,
    check-architecture-scaffolds, check-doc-length, check-ticket-test-
    requirements, and check-ticket-ac-limits, plus a folder-density stress
    attempt whose actual result is reported empirically rather than assumed.
"""

from __future__ import annotations

import json


def _debug_script_untagged() -> str:
    """New debugging/scripts/ file with a docstring but no required tags.

    Returns:
        Python source text for check-debug-scripts to reject.
    """
    return '''"""Fixture debug script with no metadata tags at all."""


def main():
    pass
'''


def _root_junk_file() -> str:
    """New root-level file with a disallowed name and extension.

    Returns:
        Plain text content for check-root-files to reject.
    """
    return "GE-120b-2-i fixture junk file at repo root.\n"


def _high_complexity_sql() -> str:
    """New .sql file whose keyword count exceeds MAX_SQL_COMPLEXITY_SCORE (75).

    Returns:
        SQL source text with 89 ``AND`` keywords in one condition — complexity
        score 90 (89 matches + 1), comfortably over the 75 threshold.
    """
    condition = " AND ".join(["TRUE"] * 90)
    return f"""-- Fixture SQL for check-sql-complexity (GE-120b-2-i)
CREATE OR REPLACE FUNCTION ge120fixture_high_complexity() RETURNS void AS $$
BEGIN
  IF {condition} THEN
    NULL;
  END IF;
END;
$$ LANGUAGE plpgsql;
"""


def _doc_types_json_mismatch() -> str:
    """Nested-path doc_types.json referencing a writer_agent absent from the
    paired nested agent_registry.json.

    Returns:
        JSON text for leafcutter/config/doc_types.json.
    """
    return json.dumps(
        {"doc_types": {"how-to": {"writer_agent": "ge120fixture-ghost-agent"}}},
        indent=2,
    ) + "\n"


def _agent_registry_nested_minimal() -> str:
    """Minimal nested-path agent_registry.json that does NOT define the
    writer_agent the paired doc_types.json references.

    Returns:
        JSON text for leafcutter/config/agent_registry.json.
    """
    return json.dumps(
        {"agents": [{"id": "ge120fixture-agent-a", "produces": "production_code"}]},
        indent=2,
    ) + "\n"


def _bad_roadmap_json() -> str:
    """docs/roadmap.json missing every required top-level field.

    Returns:
        JSON text for check-roadmap-schema to reject.
    """
    return json.dumps({"current_phase": "phase_ge120fixture"}, indent=2) + "\n"


def _bad_paths_json() -> str:
    """leafcutter/config/paths.json with a missing target and a duplicate pair.

    Returns:
        JSON text for check-paths-integrity to reject on two independent
        grounds (missing directory, duplicate resolved path).
    """
    return json.dumps(
        {
            "paths": {
                "ge120fixture_missing": "ge120fixture/does_not_exist/",
                "ge120fixture_dup_a": "ge120fixture/dup_target",
                "ge120fixture_dup_b": "ge120fixture/dup_target",
            }
        },
        indent=2,
    ) + "\n"


def _architecture_scaffold_no_frontmatter() -> str:
    """Scaffold file under leafcutter/templates/docs/architecture/ with no
    YAML frontmatter at all.

    Returns:
        Markdown content for check-architecture-scaffolds to reject.
    """
    return "# GE-120b-2-i fixture scaffold with no frontmatter\n\nBody content only.\n"


def _long_doc_md() -> str:
    """New docs/*.md file padded past the 300-line check-doc-length limit.

    Returns:
        Markdown content (frontmatter + ~320 body lines) for check-doc-length
        to reject. The doc has no previous-length history (a new file), so it
        is judged by crossing the limit outright.
    """
    header = (
        '---\n'
        'title: "GE-120b-2-i fixture long doc"\n'
        'type: how-to\n'
        'status: draft\n'
        'created: 2026-01-01\n'
        'last_updated: 2026-01-01\n'
        'components: []\n'
        'description: "Fixture doc padded past the doc-length limit."\n'
        '---\n\n'
        '# Fixture long doc\n\n'
    )
    body = "\n".join(f"Padding line {i} for the doc-length fixture." for i in range(320))
    return header + body + "\n"


def _ticket_c_missing_test_requirements() -> str:
    """Code ticket (python-coder: needed) with no Test Requirements section.

    Returns:
        Ticket markdown content for check-ticket-test-requirements to reject.
    """
    return """---
title: "GE-120b-2-i fixture ticket C"
status: todo
components: []
created: 2026-09-08
depends_on: []
agents:
  python-coder: needed
---

# GE-120b-2-i fixture ticket C

No Test Requirements section anywhere in this ticket body.
"""


def _ticket_d_ac_overflow() -> str:
    """v1-flat ticket with 25 unchecked AC lines, over the 20-total cap.

    Returns:
        Ticket markdown content for check-ticket-ac-limits to reject.
    """
    ac_lines = "\n".join(
        f"- [ ] AC-{100 + i}: Fixture overflow criterion {i}." for i in range(25)
    )
    return f"""---
title: "GE-120b-2-i fixture ticket D"
status: todo
components: []
created: 2026-09-08
depends_on: []
---

# GE-120b-2-i fixture ticket D

{ac_lines}
"""


def _density_filler_files() -> dict[str, str]:
    """16 tiny new files in a brand-new folder, stress-testing check-folder-
    density's before/after crossing logic.

    Returns:
        Mapping of 16 repo-relative paths to trivial content. Whether this
        actually provokes a `violation` status (rather than a non-blocking
        `warning`) is reported empirically, not assumed — see this AC's
        sign-off comment for the measured outcome.
    """
    return {
        f"scripts/ge120fixture/density/filler_{i}.txt": f"filler {i}\n"
        for i in range(16)
    }


def build_files_2() -> dict[str, str]:
    """Assemble the second-batch fixture file set (paths relative to the
    working copy).

    Returns:
        Mapping of repo-relative path to file content.
    """
    files: dict[str, str] = {}
    files["debugging/scripts/ge120fixture_untagged.py"] = _debug_script_untagged()
    files["GE120FIXTURE_ROOT_JUNK.txt"] = _root_junk_file()
    files["scripts/ge120fixture/high_complexity.sql"] = _high_complexity_sql()
    files["leafcutter/config/doc_types.json"] = _doc_types_json_mismatch()
    files["leafcutter/config/agent_registry.json"] = _agent_registry_nested_minimal()
    files["docs/roadmap.json"] = _bad_roadmap_json()
    files["leafcutter/config/paths.json"] = _bad_paths_json()
    files["leafcutter/templates/docs/architecture/ge120fixture_scaffold.md"] = (
        _architecture_scaffold_no_frontmatter()
    )
    files["docs/ge120fixture/long_doc.md"] = _long_doc_md()
    files["tickets/01_todo/TICKET-ge120fixture-c.md"] = _ticket_c_missing_test_requirements()
    files["tickets/01_todo/TICKET-ge120fixture-d.md"] = _ticket_d_ac_overflow()
    files.update(_density_filler_files())
    return files
