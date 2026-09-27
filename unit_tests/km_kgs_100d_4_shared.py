"""
MODULE: km_kgs_100d_4_shared
GOAL: Shared temp-project fixture builders and CLI runner for the
      KM-KGS-100d-4 family of tests (file-path values resolve to real
      files-surface graph nodes instead of surviving only as an exemption).
BUSINESS CONTEXT: KM-KGS-100d-4's test_rationale asks that "the temp-project
    builder and the CLI runner should live in one shared helper module in
    unit_tests/ reused by -i/-ii/-iii and KM-KGS-100b-2-i/-ii, so the
    duplicate-code check does not fire." This module is that helper. It is
    intentionally NOT named test_*.py so pytest's collector never treats it
    as a test module in its own right; it carries no # covers:/# angle:
    tags because it contains no test functions.
    Every fixture here is built from a BYTE COPY of the real
    config/paths.json (never a hand-authored surfaces dict), per the
    "REAL CONFIG, NOT A SYNTHETIC ONE" it_requirement on KM-KGS-100d-4: a
    config that fails to declare a file-path field must not be able to pass
    these tests.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "scripts"
KNOWLEDGE_QUERY_SCRIPT = SCRIPTS_DIR / "knowledge_query.py"
REAL_PATHS_JSON = REPO_ROOT / "config" / "paths.json"

sys.path.insert(0, str(SCRIPTS_DIR))


def subprocess_env() -> dict:
    """Environment for subprocess CLI runs: real environ plus forced UTF-8."""
    env = dict(os.environ)
    env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
    return env


def copy_real_paths_json(tmp_path: Path) -> Path:
    """Byte-copy the real config/paths.json into a temp project and return it."""
    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    dest = config_dir / "paths.json"
    dest.write_bytes(REAL_PATHS_JSON.read_bytes())
    return dest


def write_ac_yaml(acs_dir: Path, ac_id: str, **fields) -> Path:
    """Write a minimal AC YAML with the four relationship fields.

    Any of implemented_by/covered_by/depends_on/components not passed as a
    kwarg is written as an empty list, so every fixture AC is well-formed
    for extract_edges() regardless of which fields the test cares about.
    """
    acs_dir.mkdir(parents=True, exist_ok=True)
    lines = [f"id: {ac_id}\n", f"title: Fixture criterion {ac_id}\n"]
    for field in ("implemented_by", "covered_by", "depends_on", "components"):
        values = fields.get(field) or []
        if values:
            lines.append(f"{field}:\n")
            for value in values:
                lines.append(f"  - {value}\n")
        else:
            lines.append(f"{field}: []\n")
    path = acs_dir / f"{ac_id}.yaml"
    path.write_text("".join(lines), encoding="utf-8")
    return path


def write_ticket(tickets_dir: Path, ticket_id: str, files_touched=None, filename=None) -> Path:
    """Write a minimal ticket .md with an id and an optional files_touched list."""
    tickets_dir.mkdir(parents=True, exist_ok=True)
    files_touched = files_touched or []
    lines = [
        "---\n",
        f"id: {ticket_id}\n",
        f"title: Fixture ticket {ticket_id}\n",
        "agents:\n",
        "  python-coder: needed\n",
        "depends_on: []\n",
    ]
    if files_touched:
        lines.append("files_touched:\n")
        for value in files_touched:
            lines.append(f"  - {value}\n")
    else:
        lines.append("files_touched: []\n")
    lines += ["---\n\n", f"# {ticket_id}\n\nFixture body.\n"]
    path = tickets_dir / (filename or f"{ticket_id}.md")
    path.write_text("".join(lines), encoding="utf-8")
    return path


def build_criteria_fixture(tmp_path: Path, km_ex_010_extra: dict | None = None) -> Path:
    """Build the KM-KGS-100d-4 Gherkin's "criteria fixture" project.

    Criteria KM-EX-010 (implemented_by "./scripts/foo.py#_check_limits"),
    KM-EX-011 (covered_by "unit_tests/test_foo.py::test_limits" and child
    KM-EX-011-i), KM-EX-011-i, KM-EX-012 (implemented_by "tickets/T-1.md"),
    ticket T-1 at tickets/T-1.md (files_touched "scripts/foo.py" and the
    backslash-separated "unit_tests\\test_foo.py"), plus real files
    scripts/foo.py, unit_tests/test_foo.py and an unreferenced
    scripts/unreferenced.py. config/paths.json is a byte copy of the real
    one, so acs/tickets file_path_fields declarations are the real ones.

    Args:
        tmp_path: The temp project root to build into.
        km_ex_010_extra: Optional extra AC-YAML fields (e.g.
            ``{"depends_on": [...], "components": [...]}``) merged onto
            KM-EX-010's frontmatter, on top of its default implemented_by.
            Callers that omit this argument get the exact fixture that
            existed before this parameter was added (KM-KGS-100b-2's
            test_spec: "The fixture itself is not changed").
    """
    copy_real_paths_json(tmp_path)
    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    km_ex_010_fields = {"implemented_by": ["./scripts/foo.py#_check_limits"]}
    if km_ex_010_extra:
        km_ex_010_fields.update(km_ex_010_extra)
    write_ac_yaml(acs_dir, "KM-EX-010", **km_ex_010_fields)
    write_ac_yaml(
        acs_dir,
        "KM-EX-011",
        covered_by=["unit_tests/test_foo.py::test_limits", "KM-EX-011-i"],
    )
    write_ac_yaml(acs_dir, "KM-EX-011-i")
    write_ac_yaml(acs_dir, "KM-EX-012", implemented_by=["tickets/T-1.md"])

    write_ticket(
        tmp_path / "tickets",
        "T-1",
        files_touched=["scripts/foo.py", "unit_tests\\test_foo.py"],
        filename="T-1.md",
    )

    (tmp_path / "scripts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "scripts" / "foo.py").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "scripts" / "unreferenced.py").write_text("# fixture\n", encoding="utf-8")
    (tmp_path / "unit_tests").mkdir(parents=True, exist_ok=True)
    (tmp_path / "unit_tests" / "test_foo.py").write_text("# fixture\n", encoding="utf-8")

    return tmp_path


def write_registry_json(path: Path, key: str, entries: list[dict]) -> Path:
    """Write a minimal {<key>: [...]} registry JSON (agents/skills shape)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({key: entries}), encoding="utf-8")
    return path


def build_ambiguity_fixture(tmp_path: Path) -> Path:
    """Build KM-KGS-100d-4-i's "ambiguity fixture" project.

    A skill 'it-po', two agents sharing config/agent_registry.json as their
    source path, a ticket T-3 whose id collides with a docs-surface node
    read from a differently-pathed file, a uniquely-named ticket T-4, plus
    AC criteria KM-EX-030/031/032 naming each of those files in
    implemented_by, exactly as KM-KGS-100d-4-i's Gherkin states.
    """
    copy_real_paths_json(tmp_path)
    write_registry_json(
        tmp_path / "config" / "skill_registry.json",
        "skills",
        [{"id": "it-po", "name": "IT PO"}],
    )
    write_registry_json(
        tmp_path / "config" / "agent_registry.json",
        "agents",
        [
            {"id": "agent-one", "name": "Agent One"},
            {"id": "agent-two", "name": "Agent Two"},
        ],
    )

    commands_dir = tmp_path / ".claude" / "commands"
    commands_dir.mkdir(parents=True, exist_ok=True)
    (commands_dir / "it-po.md").write_text("# it-po command\n", encoding="utf-8")

    write_ticket(tmp_path / "tickets", "T-3", filename="T-3.md")
    write_ticket(tmp_path / "tickets", "T-4", filename="T-4.md")

    retro_dir = tmp_path / "docs" / "retrospectives"
    retro_dir.mkdir(parents=True, exist_ok=True)
    (retro_dir / "T-3.md").write_text(
        "# Retrospective\n\nNo frontmatter id -- the filename stem 'T-3' "
        "becomes this node's id, colliding with the ticket's own id.\n",
        encoding="utf-8",
    )

    acs_dir = tmp_path / "docs" / "acceptance-criteria" / "example-component"
    write_ac_yaml(acs_dir, "KM-EX-030", implemented_by=[".claude/commands/it-po.md"])
    write_ac_yaml(acs_dir, "KM-EX-031", implemented_by=["config/agent_registry.json"])
    write_ac_yaml(acs_dir, "KM-EX-032", implemented_by=["tickets/T-3.md"])

    return tmp_path


def run_cli(project_root: Path, extra_args=None, cwd=None, timeout=60):
    """Run the shipped knowledge_query.py CLI as a real subprocess."""
    args = [
        sys.executable,
        str(KNOWLEDGE_QUERY_SCRIPT),
        "--project-root",
        str(project_root),
    ]
    args += list(extra_args or [])
    return subprocess.run(
        args,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=subprocess_env(),
        cwd=str(cwd) if cwd else None,
    )


def run_cli_json(project_root: Path, extra_args=None, cwd=None, timeout=60) -> dict:
    """Run the CLI with --format json and return the parsed payload."""
    args = ["--format", "json"] + list(extra_args or [])
    result = run_cli(project_root, args, cwd=cwd, timeout=timeout)
    assert result.returncode == 0, (
        f"knowledge_query.py must exit 0; stderr: {result.stderr}"
    )
    return json.loads(result.stdout)
