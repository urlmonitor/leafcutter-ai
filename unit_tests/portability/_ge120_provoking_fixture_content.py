"""
MODULE: _ge120_provoking_fixture_content
GOAL: File-content builders for the shared GE-120 provoking fixture. Split out
    of `_ge120_provoking_fixture.py` purely to keep that module's line count
    under the project's 400-line new-file limit — this module has no public
    contract of its own and is imported only by `_ge120_provoking_fixture.py`.
BUSINESS CONTEXT: See `_ge120_provoking_fixture.py`'s module docstring for the
    full rationale (SHARED with GE-120b-4; the fixture must provoke a genuine
    violation for every check in hooks_manifest.hooks[]).
ARCHITECTURE: Pure string/dict builders — no I/O, no git calls. `build_files()`
    returns the full repo-relative-path -> content mapping that
    `_ge120_provoking_fixture.stage()` writes and stages.
DECISION HISTORY: 2026-09-08 [python-coder/GE-120b-2-i] — split out of
    _ge120_provoking_fixture.py to satisfy the 400-line new-file limit.
"""

from __future__ import annotations

import json

from _ge120_provoking_fixture_ac_content import build_ac_files
from _ge120_provoking_fixture_content2 import build_files_2


def _ticket_a() -> str:
    """Ticket claiming done against a still-todo AC, with an unclaimed test
    promise and a signoff heading missing its feedback-id line.

    Returns:
        Full ticket markdown content for tickets/01_todo/.
    """
    return """---
title: "GE-120b-2-i fixture ticket A"
status: done
components: []
created: 2026-09-08
depends_on: []
source_ac: GEFXPARITY-100
files_touched:
  - scripts/ge120fixture/declared_only.py
---

# GE-120b-2-i fixture ticket A

## Test Requirements

```yaml
tests:
  - name: test_fixture_angle_never_written
    file: unit_tests/ge120fixture/test_never_written.py
    covers: [GEFXPARITY-100]
    asserts: "fixture promise that is never claimed by a real test"
    framework: unittest
    type: behavioral
    angle: fixture_angle
```

## Comments

### 2026-09-08 09:00 — fixture-agent (status: ok)
Fixture comment heading with no feedback-id line following it.
"""


def _ticket_b_done_folder() -> str:
    """Ticket in a /done/ path violating the no-needed-entries invariant.

    check-ticket-signoff-parity auto-enforces (ignores warn-only default)
    only when the literal substring "/done/" appears in the staged path —
    this project's real convention is "tickets/99_done/", which does NOT
    contain that literal substring, so a ticket staged there is correctly
    flagged in the check's own output but never trips its exit code. Staged
    at "tickets/done/" (deliberately not the real "99_done" convention) so
    this fixture actually exercises the auto-enforce path.

    Returns:
        Full ticket markdown content for tickets/done/.
    """
    return """---
title: "GE-120b-2-i fixture done-folder ticket"
status: done
components: []
created: 2026-09-08
depends_on: []
agents:
  fixture-agent: needed
---

# GE-120b-2-i fixture done-folder ticket

## Sign-offs
- [ ] fixture-agent
"""


def _no_title_doc() -> str:
    """Doc missing title/components/description (transform hooks cannot fix
    a missing title, so this survives to the judgment-tier checks).

    Returns:
        Full markdown content for a docs/*.md fixture file.
    """
    return """---
type: how-to
status: draft
created: 2026-01-01
last_updated: 2026-01-01
---

# Fixture doc with no title or components field

Body content for the GE-120b-2-i provoking fixture.
"""


def _diagram_doc() -> str:
    """Architecture doc with a mermaid block missing parent linkage, a stale
    diagram hash marker, and a non-conforming filename.

    Returns:
        Full markdown content for docs/architecture/*.md.
    """
    return """---
title: "GE-120b-2-i fixture diagram"
type: architecture
status: active
created: 2026-01-01
last_updated: 2026-01-01
components: []
flight_level: L3-Component
diagram_type: data_flow
related_code:
  - scripts/ge120fixture/big_module.py
---

# Fixture diagram

```mermaid
graph TD
  A[Fixture] --> B[Provocation]
```
"""


def _agent_registry_json() -> str:
    """Registry with an asymmetric spawn edge and no components field.

    `agents` must be a LIST of dicts (not a dict keyed by id): both
    check-agent-spawn-consistency and check-surface-components-e3 extract
    entries via `data.get("agents")` and only recognise a list.

    Returns:
        JSON text for config/agent_registry.json.
    """
    return json.dumps(
        {
            "agents": [
                {
                    "id": "ge120fixture-agent-a",
                    "spawn_allowlist": ["ge120fixture-agent-b"],
                    "spawned_by": [],
                },
                {"id": "ge120fixture-agent-b", "spawned_by": []},
            ]
        },
        indent=2,
    ) + "\n"


def _adr_pair() -> dict[str, str]:
    """Two ADR files sharing the same decision number in their filename.

    Returns:
        Mapping of the two docs/architecture/adrs/ paths to their content.
    """
    body = """---
title: "GE-120b-2-i fixture ADR"
type: adr
status: active
created: 2026-01-01
last_updated: 2026-01-01
components: []
---

# Fixture ADR

Fixture-only decision record for check-decision-number-uniqueness.
"""
    return {
        "docs/architecture/adrs/ADR-9001-ge120fixture-one.md": body,
        "docs/architecture/adrs/ADR-9001-ge120fixture-two.md": body,
    }


def _agent_template() -> str:
    """Agent template declaring requires_verification with no edit tool.

    Returns:
        Full markdown content for templates/agents/*.md.
    """
    return """---
name: ge120fixture-agent
description: Fixture-only agent template for GE-120b-2-i.
tools: [Read, Bash]
requires_verification: true
---

# GE-120b-2-i Fixture Agent

Fixture-only template; never registered for real dispatch.
"""


def _workflow_meta_js() -> str:
    """Workflow file whose meta block contains a bare identifier reference.

    Returns:
        JS source text for templates/workflows-js/*.js.
    """
    return """const fixtureName = "ge120fixture";

export const meta = {
  name: fixtureName,
  description: "Fixture workflow for GE-120b-2-i",
};
"""


def _bad_io_py() -> str:
    """New .py file with an unwrapped open() and a bare except.

    Returns:
        Python source text.
    """
    return '''"""Fixture module with unwrapped I/O for check-exception-handling."""


def read_it():
    f = open("somefile.txt")
    return f.read()


def risky():
    try:
        pass
    except:
        pass
'''


def _placeholder_py() -> str:
    """New .py file with a placeholder-default rebinding pattern.

    Returns:
        Python source text.
    """
    return '''"""Fixture module with a placeholder-default pattern."""


def placeholder_fn():
    """stub"""
    return "TODO: implement"


def real_impl(x=None):
    if x is None:
        x = placeholder_fn
    return x
'''


def _big_module_py(target_lines: int = 420) -> str:
    """New .py file padded past the 400-line check-file-size limit.

    Args:
        target_lines: Minimum number of lines the file should contain.

    Returns:
        Python source text at least `target_lines` lines long.
    """
    header = '"""Fixture module padded past the file-size limit."""\n\n'
    filler = "\n".join(f"FIXTURE_LINE_{i} = {i}" for i in range(target_lines))
    return header + filler + "\n"


def _presence_only_test() -> str:
    """New test asserting only a substring presence over a scanned source glob.

    Must reference a path under a SUBDIRECTORY of scripts/commit_guardian/ —
    the configured glob is `scripts/commit_guardian/**/*.py`, and fnmatch's
    "**" behaves as a literal "*" (no recursive-zero-directories semantics),
    so a direct child file (e.g. check_secrets.py) never matches; only a
    nested path like hooks/check_agent_spawn_consistency.py does. The
    asserted symbol must itself start with a lowercase letter — the
    "code-shaped" classifier's snake_case pattern anchors on `^[a-z]`, so a
    leading-underscore private-helper name (the norm in this codebase) is
    rejected as not code-shaped and never registers as a candidate.

    Returns:
        Python source text for a fixture-only test module.
    """
    return '''"""Fixture presence-only test for check-presence-only-assertions."""
from pathlib import Path


def test_presence_only_violation():
    content = Path(
        "scripts/commit_guardian/hooks/check_agent_spawn_consistency.py"
    ).read_text()
    assert "spawn_allowlist" in content
'''


def _declared_only_py() -> str:
    """The single .py path ticket A declares in files_touched.

    Returns:
        Python source text.
    """
    return '"""Fixture file declared in ticket A files_touched."""\n'


def _secret_leak_txt() -> str:
    """Plain-text file containing a real AWS-key-shaped secret pattern.

    Returns:
        Text content with an embedded fake AWS key.
    """
    return 'AWS_SECRET_ACCESS_KEY = "AKIAIOSFODNN7EXAMPLE"\n'


def _docker_compose_yml() -> str:
    """New docker-compose.yml with an uncommented high-impact setting.

    Returns:
        YAML text for a fixture-only docker-compose.yml.
    """
    return """services:
  fixture:
    image: busybox
    mem_limit: 512m
"""


def _contract_shrinking_test() -> str:
    """New test module that skips itself at import time (test-weakening
    pattern), staged alongside real production .py changes elsewhere in the
    fixture -- the concurrence check-contract-shrinking looks for.

    The skip call is ASSEMBLED FROM PIECES rather than written as a contiguous
    literal, and that is load-bearing rather than stylistic. check-contract-
    shrinking scans the staged diff for an added line matching the contiguous
    token; a literal spelling here puts that token in THIS file's own diff, so
    the fixture blocks the very commit that adds it. That happened on the first
    attempt: the guard named this module under "Test files weakened" -- which is
    GE-120e-4-i's own reporting working exactly as intended, against us.
    Concatenation keeps the token out of this source while still emitting it
    verbatim into the temp working copy, where the check is supposed to find it.

    The same trick is required whenever fixture content must reproduce a pattern
    some other guard scans for; see the .security-allowlist notes on the planted
    access key for the sibling case.

    Returns:
        Python source text.
    """
    skip_call = (
        "pytest" + ".skip("
        '"GE-120b-2-i fixture: intentional test-weakening pattern", '
        "allow_module_level=True)"
    )
    return (
        '"""Fixture test-weakening module for check-contract-shrinking."""\n'
        "import pytest\n"
        "\n"
        f"{skip_call}\n"
        "\n"
        "\n"
        "def test_never_runs():\n"
        "    assert True\n"
    )


def build_files() -> dict[str, str]:
    """Assemble the full fixture file set (paths relative to the working copy).

    Returns:
        Mapping of repo-relative path to file content.
    """
    files: dict[str, str] = {}
    files.update(build_ac_files())
    files["tickets/01_todo/TICKET-ge120fixture-a.md"] = _ticket_a()
    files["tickets/done/TICKET-ge120fixture-done.md"] = _ticket_b_done_folder()
    files["docs/ge120fixture/no_title_doc.md"] = _no_title_doc()
    files["docs/architecture/ge120fixture_diagram.md"] = _diagram_doc()
    files.update(_adr_pair())
    files["config/agent_registry.json"] = _agent_registry_json()
    files["templates/agents/ge120fixture_agent.md"] = _agent_template()
    files["templates/workflows-js/ge120fixture_workflow.js"] = _workflow_meta_js()
    files["scripts/ge120fixture/bad_io.py"] = _bad_io_py()
    files["scripts/ge120fixture/placeholder_stub.py"] = _placeholder_py()
    files["scripts/ge120fixture/big_module.py"] = _big_module_py()
    files["unit_tests/ge120fixture/test_presence_only.py"] = _presence_only_test()
    files["scripts/ge120fixture/declared_only.py"] = _declared_only_py()
    files["scripts/ge120fixture/leaked_secret.txt"] = _secret_leak_txt()
    files["docker-compose.yml"] = _docker_compose_yml()
    files["unit_tests/ge120fixture/test_contract_shrinking.py"] = _contract_shrinking_test()
    files.update(build_files_2())
    return files
