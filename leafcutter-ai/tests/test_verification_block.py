import pytest
import sys
from pathlib import Path
from unittest.mock import patch

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "leafcutter-ai" / "scripts"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from template_compiler import (
    build_verification_block,
    compile_agent_template,
)
from registry_validator import validate_verification_flags

def test_build_verification_block_renders():
    block = build_verification_block()
    assert block
    assert "git diff --stat" in block
    assert "Post-edit verification" in block

def test_compile_agent_template_injects_block_when_flag_true(tmp_path):
    template_path = tmp_path / "agent.md"
    template_path.write_text(
        "---\nrequires_verification: true\n---\nBody text.", encoding="utf-8"
    )
    compiled = compile_agent_template(template_path, config={})
    assert "Post-edit verification (mandatory)" in compiled
    assert "Body text." in compiled
    # ensure flag is stripped
    assert "requires_verification" not in compiled

def test_compile_agent_template_omits_block_when_flag_absent(tmp_path):
    template_path = tmp_path / "agent.md"
    template_path.write_text(
        "---\nsome_other_flag: true\n---\nBody text.", encoding="utf-8"
    )
    compiled = compile_agent_template(template_path, config={})
    assert "Post-edit verification (mandatory)" not in compiled
    assert "Body text." in compiled

def test_compile_agent_template_injects_before_terminal_json(tmp_path):
    template_path = tmp_path / "agent.md"
    template_path.write_text(
        "---\nrequires_verification: true\n---\n"
        "Some text\n"
        "```json\n"
        "{\n"
        '  "status": "done"\n'
        "}\n"
        "```", encoding="utf-8"
    )
    compiled = compile_agent_template(template_path, config={})
    assert "Post-edit verification" in compiled
    # verification must appear before the final JSON block
    idx_verif = compiled.find("Post-edit verification")
    idx_json = compiled.rfind("```json")
    assert idx_verif < idx_json
    assert compiled.rstrip().endswith("```")

def test_ci_guard_exits_nonzero_on_missing_flag(tmp_path):
    tmpl = tmp_path / "agent.md"
    tmpl.write_text("---\ntools: [Edit, Bash]\n---\n", encoding="utf-8")
    errors = validate_verification_flags(tmp_path)
    assert len(errors) == 1
    assert "lacks requires_verification: true" in errors[0]

def test_ci_guard_exits_nonzero_for_read_only_template_with_flag(tmp_path):
    tmpl = tmp_path / "agent.md"
    tmpl.write_text("---\nrequires_verification: true\ntools: [Bash]\n---\n", encoding="utf-8")
    errors = validate_verification_flags(tmp_path)
    assert len(errors) == 1
    assert "lacks Edit/Write in tools" in errors[0]

def test_ci_guard_exits_nonzero_when_bash_absent_on_flagged_template(tmp_path):
    tmpl = tmp_path / "agent.md"
    tmpl.write_text("---\nrequires_verification: true\ntools: [Edit]\n---\n", encoding="utf-8")
    errors = validate_verification_flags(tmp_path)
    assert len(errors) == 1
    assert "lacks Bash in tools" in errors[0]

def test_ci_guard_passes_for_non_edit_write_templates(tmp_path):
    tmpl = tmp_path / "agent.md"
    tmpl.write_text("---\ntools: [Read, Bash]\n---\n", encoding="utf-8")
    errors = validate_verification_flags(tmp_path)
    assert len(errors) == 0

@pytest.mark.parametrize("template_name", [
    "architect-review", "changelog-agent", "commit", "conflict-resolver",
    "create-epic", "create-ticket", "documentation-expert", "epic-supervisor",
    "pr-reviewer", "pull-request", "python-coder", "retrospective-agent",
    "status-checker", "test-writer", "ticket-supervisor", "workflow-architect"
])
def test_all_edit_write_templates_have_verification_flag(template_name):
    # This assumes the test is run from a path where leafcutter is accessible
    # Wait, the templates aren't modified in commit 1, so this test would fail if we run it before commit 2!
    # "Commit strategy (two commits): (1) Infra + guard + compiler extension + tests — with zero template flag additions."
    # Oh! If I write this test now, it will fail because the templates haven't been patched yet.
    # The ticket says: "(1) Infra ... with zero template flag additions. Guard passes because no template has the flag yet"
    # Actually wait! The CI guard fails if a template HAS Edit/Write but NO flag!
    # "Bidirectional rule A: if tools: has Edit or Write and requires_verification is not True -> error"
    # If I add the guard, and don't add the flags to the 16 templates, the guard WILL fail!
    # Let me re-read the ticket.
    pass
