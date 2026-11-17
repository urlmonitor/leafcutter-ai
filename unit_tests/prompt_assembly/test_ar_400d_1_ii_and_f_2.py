"""AR-400d-1-ii (python-coder's trading-project collector-enforcer content is deleted)
and AR-400f-2 (ticket-supervisor's leftover llm-expert spawn_allowlist entry is removed
without losing the hand-off).

Source of truth: docs/acceptance-criteria/agent-registry/AR-400-sound-specialist-setup/
AR-400d-1-ii.yaml and AR-400f-2.yaml. Compiled-prompt tests use the real in-process
``build_agents`` over a copy of the real tree (every platform root).

DEFERRED / PARTIAL:
  * AR-400f-2 test_real_tree_has_no_redundant_entry_finding: the AR-400f-1 gate is not
    built, so a stand-in is asserted DIRECTLY on the templates + registry (the same
    redundancy rule INF-600g-2 describes: a macro plus an explicitly listed ticket-phase
    agent), over every real template.
  * AR-400f-2 test_ticket_supervisor_compiled_hand_off_set_is_unchanged: the set-equality
    half is GREEN today by design (the change must not alter the set); it goes red
    now through the declaration clause (llm-expert must leave the declaration).
  * AR-400d-1-ii test_consumer_config_still_setting_the_removed_key_builds: asserted via the
    real config loader/validator (a scratch build.py spawn is forbidden for non-mutating
    tests); GREEN-BY-DESIGN today -- it guards adopters when the schema property goes.
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _ar_400_support import (  # noqa: E402
    REPO_ROOT,
    TEMPLATES_AGENTS,
    built_prompts,
    installed_skill_ids,
    real_known_ids,
    real_registry,
    spawn_accounts,
    template_frontmatter,
)
from _ar_300ad_support import SCRIPTS_DIR, ability_rows, source_templates  # noqa: E402

MACRO = "__ticket_phase_agents__"
# python-coder's remaining grants, which must be untouched by the deletion.
PYTHON_CODER_GRANTS = {"signoff", "doc-enforcer", "complexity-reduction"}
# ticket-supervisor's compiled hand-off set BEFORE the AR-400f-2 change. HARD-CODED: captured on
# 2026-10-14 from the real compile (compile_agent_template over templates/agents/ticket-supervisor.md
# with config/agent_registry.json's agents) of the current tree; sorted. llm-expert appears once.
HAND_OFF_BEFORE = [
    "ac-fulfillment-gate", "ac-validator", "adr-author", "architect-review", "architecture-diagram-author",
    "brainstorm-lead", "change-scope-reviewer", "commit", "documentation-expert", "documentation-verifier",
    "explanation-author", "frontend-coder", "how-to-author", "live-surface-tester", "llm-expert",
    "pr-reviewer", "pull-request", "python-coder", "reference-author", "restructuring-specialist",
    "sql-coder", "sql-query", "status-checker", "test-breaker", "test-runner", "test-writer",
    "user-surface-smoker",
]


def test_compiled_python_coder_has_no_collector_enforcer_content():
    # covers: AR-400d-1-ii
    # angle: deployed
    # must_catch: the section is converted to a provided_by: project grant instead of deleted
    installed = installed_skill_ids(REPO_ROOT)
    for root, text in built_prompts("python-coder").items():
        assert "collector-enforcer" not in text.lower(), f"{root}: compiled python-coder still mentions collector-enforcer"
        assert "collector/" not in text, f"{root}: compiled python-coder still has a rule about paths under collector/"
        assert set(ability_rows(text, installed)) == PYTHON_CODER_GRANTS, (
            f"{root}: abilities section is {sorted(ability_rows(text, installed))}, want exactly {sorted(PYTHON_CODER_GRANTS)}")


def test_python_coder_declares_no_collector_setting():
    # covers: AR-400d-1-ii
    # angle: criterion
    fm = template_frontmatter(TEMPLATES_AGENTS / "python-coder.md")
    blob = json.dumps(fm.get("config_keys") or {}).lower()
    assert "collector" not in blob, f"python-coder config_keys still declares a collector setting: {blob[:200]}"
    grants = [e if isinstance(e, str) else e.get("skill_id") for e in (fm.get("skills") or [])]
    assert "collector-enforcer" not in grants, "python-coder still grants collector-enforcer"
    assert {g for g in grants} == PYTHON_CODER_GRANTS, f"python-coder grants changed: {grants}"


def test_consumer_config_still_setting_the_removed_key_builds(tmp_path):
    # covers: AR-400d-1-ii
    # angle: failure
    # Green-by-design control (see module docstring): a consumer config that still sets the removed
    # key must keep loading and validating with no error.
    sys.path.insert(0, str(SCRIPTS_DIR))
    from config_loader import load_config, validate_config

    cfg_path = tmp_path / "skills_config.json"
    cfg_path.write_text(json.dumps({"collector_enforcer_paths": ["collector/"]}, indent=2), encoding="utf-8")
    config = load_config(cfg_path, tmp_path)
    assert config.get("collector_enforcer_paths") == ["collector/"]
    assert validate_config(config) == [], f"consumer config rejected: {validate_config(config)}"


def _declared_spawn(stem: str) -> list[str]:
    return list(template_frontmatter(TEMPLATES_AGENTS / f"{stem}.md").get("spawn_allowlist") or [])


def test_ticket_supervisor_compiled_hand_off_set_is_unchanged():
    # covers: AR-400f-2
    # angle: deployed
    # must_catch: removing the entry drops llm-expert from the compiled hand-off list
    declared = _declared_spawn("ticket-supervisor")
    assert MACRO in declared and "brainstorm-lead" in declared, f"declaration lost an entry: {declared}"
    assert "llm-expert" not in declared, f"ticket-supervisor's spawn_allowlist still lists llm-expert: {declared}"
    known = real_known_ids()
    for root, text in built_prompts("ticket-supervisor").items():
        accounts = spawn_accounts(text, known)
        assert len(accounts) == 1, f"{root}: {len(accounts)} hand-off accounts"
        ids = accounts[0]["ids"]
        assert ids.count("llm-expert") == 1, f"{root}: llm-expert named {ids.count('llm-expert')}x in the hand-off list"
        assert sorted(set(ids)) == HAND_OFF_BEFORE, (
            f"{root}: hand-off set changed: lost={sorted(set(HAND_OFF_BEFORE) - set(ids))} "
            f"gained={sorted(set(ids) - set(HAND_OFF_BEFORE))}")


def test_real_tree_has_no_redundant_entry_finding():
    # covers: AR-400f-2
    # angle: real_artifact
    # Stand-in for the unbuilt AR-400f-1 gate: asserted directly on the real templates + registry.
    registry = {a["id"]: a for a in real_registry()}
    phase = {i for i, a in registry.items() if a.get("is_ticket_phase")}
    redundant = []
    for tpl in source_templates():
        declared = _declared_spawn(tpl.stem)
        if MACRO in declared:
            redundant += [(tpl.stem, e) for e in declared if e in phase]
    assert not redundant, f"entries redundant with {MACRO}: {redundant}"
    assert registry["ticket-supervisor"]["spawn_allowlist"] == _declared_spawn("ticket-supervisor"), (
        "registry spawn_allowlist for ticket-supervisor differs from its declaration")
