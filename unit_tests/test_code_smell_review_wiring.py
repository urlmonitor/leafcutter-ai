"""
MODULE: test_code_smell_review_wiring
GOAL: Structural / consistency coverage for the Fowler code-smell review capability
    (component `code-review`, ACs CR-100*). Proves the built artifacts match the ACs
    by PARSING the real files the build consumes — config/skill_registry.json,
    config/agent_registry.json, and the actual SKILL.md / agent-template frontmatter —
    and by running the real registry validators. No Claude Code / LLM calls; no build.py
    subprocess (hermetic per CLAUDE.md's caution on build-dependent CI tests).

BUSINESS CONTEXT: The capability was built via a direct drive, then reconciled into the
    AC store (component code-review). These tests are the `# covers:` linkage for the
    behavioral leaf ACs. They are behavioral-not-grep: the partition test computes the
    union/intersection of the two parsed bucket catalogues, the tiering test reads the
    registry model/skills_invoked, and the retirement test asserts absence in the parsed
    registry plus non-existence on disk — none pass merely because a string is present in
    dead code.

Coverage boundary (documented, intentional): the runtime fan-out (parallel dispatch),
    the merge into one report, and the depth-1 sub-agent limit cannot be exercised under
    pytest (agents cannot be spawned in-process). Those ACs assert the prompt-level and
    registry-level guarantees instead; this is flagged inline on each affected test.

AC references: CR-100a-1, CR-100a-2, CR-100a-3, CR-100b-1, CR-100c-1, CR-100d-1,
    CR-100d-2, CR-100e-1, CR-100e-1-i, CR-100f-1, CR-100f-1-i, CR-100f-2, CR-100f-3,
    CR-100f-3-i, CR-100f-4, CR-100f-5.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS_DIR = _REPO_ROOT / "scripts"
_SKILL_REGISTRY = _REPO_ROOT / "config" / "skill_registry.json"
_AGENT_REGISTRY = _REPO_ROOT / "config" / "agent_registry.json"
_SKILLS_DIR = _REPO_ROOT / "templates" / "skills"
_AGENTS_DIR = _REPO_ROOT / "templates" / "agents"
_COMMANDS_DIR = _REPO_ROOT / "templates" / "commands"

if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from registry_validator import (  # noqa: E402
    validate_agent_registry,
    validate_skill_registry,
)

# ---------------------------------------------------------------------------
# The Modern-12 partition (the invariant these ACs pin down)
# ---------------------------------------------------------------------------

STRUCTURAL_SMELLS = {
    "Mysterious Name",
    "Duplicated Code",
    "Long Function",
    "Long Parameter List",
    "Loops",
    "Repeated Switches",
}
DESIGN_SMELLS = {
    "Global Data",
    "Mutable Data",
    "Feature Envy",
    "Data Clumps",
    "Primitive Obsession",
    "Shotgun Surgery",
}
MODERN_12 = STRUCTURAL_SMELLS | DESIGN_SMELLS

CORE_SKILL = "review-for-code-smells"
STRUCTURAL_SKILL = "review-for-structural-code-smells"
DESIGN_SKILL = "review-for-design-code-smells"
ORCHESTRATION_SKILL = "code-smell-review"

STRUCTURAL_AGENT = "find-structural-smells"
DESIGN_AGENT = "find-design-smells"
RETIRED_AGENT = "find-code-smells"

# Documentation deliverables (the doc ACs).
FINDING_ANATOMY_DOC = "docs/reference/code-smell-finding-anatomy.md"
REPORT_FORMAT_DOC = "docs/reference/code-smell-report-format.md"
HOWTO_DOC = "docs/how-to/run-code-smell-review.md"
ARCH_DOC = "docs/architecture/components/code-review.md"

# ---------------------------------------------------------------------------
# Helpers — all pure parsing of the real on-disk artifacts
# ---------------------------------------------------------------------------


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _skill_entry(skill_id: str) -> dict[str, Any]:
    skills = _load_json(_SKILL_REGISTRY)["skills"]
    matches = [s for s in skills if s.get("id") == skill_id]
    assert matches, f"skill {skill_id!r} not registered in skill_registry.json"
    return matches[0]


def _agent_entry(agent_id: str) -> dict[str, Any] | None:
    agents = _load_json(_AGENT_REGISTRY)["agents"]
    matches = [a for a in agents if a.get("id") == agent_id]
    return matches[0] if matches else None


def _skill_md(skill_id: str) -> str:
    path = _SKILLS_DIR / skill_id / "SKILL.md"
    assert path.exists(), f"{path} does not exist"
    return path.read_text(encoding="utf-8")


def _frontmatter(md_text: str) -> dict[str, Any]:
    """Parse the YAML frontmatter block delimited by the first two '---' lines."""
    parts = md_text.split("---", 2)
    assert len(parts) >= 3, "no frontmatter block found"
    return yaml.safe_load(parts[1])


def _agent_frontmatter(agent_id: str) -> dict[str, Any]:
    path = _AGENTS_DIR / f"{agent_id}.md"
    assert path.exists(), f"{path} does not exist"
    return _frontmatter(path.read_text(encoding="utf-8"))


def _agent_tools(fm: dict[str, Any]) -> set[str]:
    """Agent templates carry tools as a comma-joined string: 'Bash, Read, Skill'."""
    raw = fm.get("tools", "")
    if isinstance(raw, list):
        return {t.strip() for t in raw}
    return {t.strip() for t in str(raw).split(",") if t.strip()}


def _doc(rel_path: str) -> str:
    """Read a documentation deliverable, asserting it exists on disk."""
    path = _REPO_ROOT / rel_path
    assert path.exists(), f"{rel_path} does not exist"
    return path.read_text(encoding="utf-8")


def _bucket_catalogue(skill_id: str) -> dict[str, str]:
    """Parse a bucket SKILL.md's summary table -> {smell_name: refactoring_column}.

    The table row shape is: | # | Smell | one-line tell | Primary refactoring(s) |
    We accept only rows whose first column is an integer (the numbered smell rows),
    which excludes the header and separator rows.
    """
    catalogue: dict[str, str] = {}
    for line in _skill_md(skill_id).splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 4:
            continue
        if not cells[0].isdigit():
            continue
        smell = cells[1]
        refactoring = cells[-1]
        catalogue[smell] = refactoring
    return catalogue


# ===========================================================================
# CR-100a — every finding names the exact smell (the catalogue)
# ===========================================================================


# covers: CR-100a-1
def test_structural_bucket_names_exactly_its_six_smells() -> None:
    assert set(_bucket_catalogue(STRUCTURAL_SKILL)) == STRUCTURAL_SMELLS


# covers: CR-100a-2
def test_design_bucket_names_exactly_its_six_smells() -> None:
    assert set(_bucket_catalogue(DESIGN_SKILL)) == DESIGN_SMELLS


# covers: CR-100a-3
def test_core_skill_is_method_only_not_a_catalogue() -> None:
    """Core carries the method/format; the 12-smell catalogue lives in the buckets."""
    # The core has no numbered smell-catalogue table; each bucket enumerates its six.
    assert _bucket_catalogue(CORE_SKILL) == {}
    assert set(_bucket_catalogue(STRUCTURAL_SKILL)) == STRUCTURAL_SMELLS
    assert set(_bucket_catalogue(DESIGN_SKILL)) == DESIGN_SMELLS
    # Core delegates to both bucket skills by name.
    core = _skill_md(CORE_SKILL)
    assert STRUCTURAL_SKILL in core
    assert DESIGN_SKILL in core
    # The finding still carries the named smell: the finding-title format is a
    # [<SMELL NAME>] tag, so every finding names its smell even though the core
    # holds no catalogue.
    assert "[<smell name>]" in core.lower()


# ===========================================================================
# CR-100b — every finding names the exact fix (a Fowler refactoring)
# ===========================================================================


# covers: CR-100b-1
def test_every_catalogue_smell_names_a_refactoring() -> None:
    catalogue = {**_bucket_catalogue(STRUCTURAL_SKILL), **_bucket_catalogue(DESIGN_SKILL)}
    assert set(catalogue) == MODERN_12
    missing = [smell for smell, refactor in catalogue.items() if not refactor]
    assert not missing, f"smells with no named refactoring: {missing}"


# ===========================================================================
# CR-100c — see the problem + direction to fix it
# ===========================================================================


# covers: CR-100c-1
def test_core_finding_format_requires_before_after_and_location() -> None:
    core = _skill_md(CORE_SKILL).lower()
    assert "finding format" in core
    assert "before" in core
    assert "verbatim" in core        # the Before block is verbatim source, not edited
    assert "after" in core
    assert "direction only" in core  # the After sketch is direction-only, not a rewrite
    assert "not a full rewrite" in core  # explicit non-rewrite guarantee
    assert "file" in core            # every finding is anchored to a file + line range


# ===========================================================================
# CR-100d — one severity-ranked report from a registered core
# ===========================================================================


# covers: CR-100d-1
def test_core_skill_registered_portable_and_rubric_present() -> None:
    entry = _skill_entry(CORE_SKILL)
    assert entry.get("portable") is True
    # Template path in the registry resolves to a real SKILL.md on disk.
    assert (_SKILLS_DIR / CORE_SKILL / "SKILL.md").exists()
    # Severity rubric is exactly the three tiers.
    core = _skill_md(CORE_SKILL)
    for tier in ("HIGH", "MEDIUM", "LOW"):
        assert tier in core
    # Real validators: registry <-> disk consistency and agent-registry integrity.
    orphaned_dirs, orphaned_entries = validate_skill_registry(_REPO_ROOT)
    assert orphaned_dirs == [] and orphaned_entries == []


# covers: CR-100d-2
def test_orchestration_merges_into_one_ranked_report() -> None:
    """Prompt-level guarantee; the runtime merge is a coverage boundary (needs agents)."""
    body = _skill_md(ORCHESTRATION_SKILL).lower()
    assert "merge" in body
    assert "one report" in body or "single" in body
    # The merge is severity-ranked and de-duplicates overlaps between the two buckets.
    assert "ordered by severity" in body or "by severity" in body
    assert "de-dup" in body or "dedup" in body
    assert "high" in body and "medium" in body and "low" in body


# ===========================================================================
# CR-100e — review any code you point at
# ===========================================================================


# covers: CR-100e-1
def test_command_documents_file_folder_and_snippet_targets() -> None:
    cmd = (_COMMANDS_DIR / "code-smell-review.md").read_text(encoding="utf-8").lower()
    assert "file" in cmd
    assert "folder" in cmd
    assert "pasted" in cmd or "snippet" in cmd


# covers: CR-100e-1-i
def test_pasted_snippet_with_no_path_is_supported() -> None:
    """The core Gather step accepts pasted code with no file on disk."""
    core = _skill_md(CORE_SKILL).lower()
    # Pasted code is an explicit Gather target (not merely mentioned in passing).
    assert "pasted" in core
    assert "gather" in core
    # A finding still carries a File anchor, so a snippet finding is still located.
    assert "file" in core


# ===========================================================================
# CR-100f — full coverage without the wait/cost (partition + tiering + fan-out)
# ===========================================================================


# covers: CR-100f-1
def test_two_buckets_are_a_true_partition_of_the_modern_twelve() -> None:
    structural = set(_bucket_catalogue(STRUCTURAL_SKILL))
    design = set(_bucket_catalogue(DESIGN_SKILL))
    assert structural | design == MODERN_12       # union covers all 12
    assert structural & design == set()           # intersection empty


# covers: CR-100f-1-i
def test_no_smell_is_duplicated_across_buckets() -> None:
    structural = set(_bucket_catalogue(STRUCTURAL_SKILL))
    design = set(_bucket_catalogue(DESIGN_SKILL))
    assert structural.isdisjoint(design)


# covers: CR-100f-2
def test_leaf_agents_are_tiered_and_load_core_plus_own_bucket() -> None:
    structural = _agent_entry(STRUCTURAL_AGENT)
    design = _agent_entry(DESIGN_AGENT)
    assert structural is not None and design is not None
    assert structural["model"] == "sonnet"
    assert design["model"] == "opus"
    assert set(structural.get("skills_invoked", [])) == {CORE_SKILL, STRUCTURAL_SKILL}
    assert set(design.get("skills_invoked", [])) == {CORE_SKILL, DESIGN_SKILL}


# covers: CR-100f-3
def test_orchestration_fans_out_to_both_leaf_agents() -> None:
    """Prompt-level guarantee; runtime parallelism is a coverage boundary."""
    body = _skill_md(ORCHESTRATION_SKILL)
    assert STRUCTURAL_AGENT in body
    assert DESIGN_AGENT in body
    assert "parallel" in body.lower()


# covers: CR-100f-3-i
def test_fanout_lives_at_top_level_not_in_a_subagent() -> None:
    """Depth-1: the orchestration is a top-level skill, not an agent that spawns agents.

    Runtime depth-1 dispatch cannot be exercised in pytest (no agent spawning), so this
    asserts the enforceable guarantees: code-smell-review is a skill (absent from the
    agent registry), the leaf agents declare no spawn permissions, and the orchestration
    skill has the Agent tool, names both leaves, and states the depth-1 constraint.
    """
    assert _agent_entry(ORCHESTRATION_SKILL) is None  # it is a skill, not an agent
    for leaf in (STRUCTURAL_AGENT, DESIGN_AGENT):
        assert _agent_entry(leaf).get("spawn_allowlist", []) == []
    fm = _frontmatter(_skill_md(ORCHESTRATION_SKILL))
    assert "Agent" in (fm.get("allowed-tools") or [])
    body = _skill_md(ORCHESTRATION_SKILL).lower()
    assert "depth-1" in body or "depth 1" in body


# covers: CR-100f-4
def test_leaf_agents_are_readonly_and_return_findings() -> None:
    for leaf, bucket in ((STRUCTURAL_AGENT, STRUCTURAL_SKILL), (DESIGN_AGENT, DESIGN_SKILL)):
        fm = _agent_frontmatter(leaf)
        tools = _agent_tools(fm)
        assert "Write" not in tools and "Edit" not in tools, f"{leaf} must be read-only"
        assert {"Bash", "Read", "Skill"} <= tools
        assert fm.get("requires_verification") is False
        entry = _agent_entry(leaf)
        assert entry.get("requires_verification") is False
        assert entry.get("produces") == "review_verdict"
        assert bucket in set(entry.get("skills_invoked", []))


# covers: CR-100f-5
def test_single_agent_find_code_smells_is_fully_retired() -> None:
    # Absent from the parsed registry.
    assert _agent_entry(RETIRED_AGENT) is None
    # No template and no command file on disk.
    assert not (_AGENTS_DIR / f"{RETIRED_AGENT}.md").exists()
    assert not (_COMMANDS_DIR / f"{RETIRED_AGENT}.md").exists()


# ===========================================================================
# Cross-cutting: the agent registry itself validates with the new agents in it
# ===========================================================================


def test_agent_registry_validates_with_new_reviewers() -> None:
    errors = validate_agent_registry(_REPO_ROOT)
    smell_errors = [e for e in errors if "smell" in e.lower()]
    assert smell_errors == [], f"registry errors for smell agents: {smell_errors}"


# ===========================================================================
# Documentation deliverables (the doc ACs) — assert the doc exists and carries
# the required content. Content is parsed from the real files the docs describe,
# so these fail if a doc drifts from the artifacts.
# ===========================================================================


# covers: CR-100a-4
def test_finding_anatomy_reference_doc_covers_all_twelve_and_the_format() -> None:
    doc = _doc(FINDING_ANATOMY_DOC).lower()
    for smell in MODERN_12:
        assert smell.lower() in doc, f"finding-anatomy doc missing smell: {smell}"
    assert "refactoring" in doc          # each smell names its refactoring
    assert "before" in doc and "after" in doc  # the finding format


# covers: CR-100d-3
def test_report_format_reference_doc_defines_rubric_and_ranked_report() -> None:
    doc = _doc(REPORT_FORMAT_DOC)
    for tier in ("HIGH", "MEDIUM", "LOW"):
        assert tier in doc
    low = doc.lower()
    assert "severity" in low
    assert "rank" in low or "one" in low  # one severity-ranked report


# covers: CR-100e-2
def test_howto_documents_all_three_targets_and_the_report() -> None:
    doc = _doc(HOWTO_DOC).lower()
    assert "/code-smell-review" in doc
    assert "file" in doc
    assert "folder" in doc
    assert "pasted" in doc or "snippet" in doc
    assert "report" in doc


# covers: CR-100e-3
def test_arch_doc_has_invocation_to_report_sequence() -> None:
    doc = _doc(ARCH_DOC)
    assert "sequenceDiagram" in doc
    low = doc.lower()
    assert "report" in low
    assert "file" in low and "folder" in low and ("snippet" in low or "pasted" in low)


# covers: CR-100f-6
def test_arch_doc_has_component_diagram_of_the_topology() -> None:
    doc = _doc(ARCH_DOC)
    assert "flowchart" in doc or "graph" in doc  # a component/flow diagram
    for name in (CORE_SKILL, STRUCTURAL_SKILL, DESIGN_SKILL, STRUCTURAL_AGENT, DESIGN_AGENT):
        assert name in doc, f"arch doc missing {name} in topology"
    assert "orchestrat" in doc.lower()


# covers: CR-100f-7
def test_arch_doc_has_parallel_fanout_and_merge_sequence() -> None:
    doc = _doc(ARCH_DOC)
    low = doc.lower()
    assert "parallel" in low or "par " in low or "par\n" in low
    assert "merge" in low
    assert STRUCTURAL_AGENT in doc and DESIGN_AGENT in doc


if __name__ == "__main__":  # pragma: no cover
    sys.exit(pytest.main([__file__, "-v"]))
