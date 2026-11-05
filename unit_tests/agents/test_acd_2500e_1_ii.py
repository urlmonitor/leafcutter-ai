"""
MODULE: unit_tests/agents/test_acd_2500e_1_ii.py
COVERS: ACD-2500e-1-ii
GOAL: Red-first specification of ticket 27: the decision history of the agent self-description
    check (validate_agent_self_description) moves, verbatim and in order, from the module
    docstring of scripts/build_phases_profile_consistency.py into the docstring of the function
    that defines it, in scripts/build_phases_agent_validation.py.
DESIGN: the expected text is frozen here from commit 36e5303a9 (never read from git at run time):
    the "# DECISION HISTORY" heading and the five entries dated 2026-06-05 to 2026-08-25, and the
    module docstring's own description (MODULE: through template_compiler.parse_frontmatter.).
    Docstrings are read RAW from the source lines the ast node spans, never with
    ast.get_docstring, which strips indentation.
INTERPRETATION PINNED HERE: the test design names "lines 28-72" for the heading and the five
    entries; at 36e5303a9 the fifth entry ends on line 73 ("cross-module dependency and matches
    the AC text exactly."), and the AC's own range is "lines 24-73". The frozen block is lines
    28-73, the whole heading and all five entries, so a verbatim move can pass the "nothing but
    whitespace after them" assertion.
HONEST LIMIT: "no line of code in either file changes" has no test by design (test_intent
    needs_test false); the reachability test pins the two checks' results instead.
RED STATE: the two text tests fail on an assertion (the history is still in the profile module,
    and the function docstring has none); the results test pins today's behaviour and is green
    at baseline by design (it guards the move, it does not specify new behaviour).
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "scripts"
PROFILE_MODULE = SCRIPTS / "build_phases_profile_consistency.py"
VALIDATION_MODULE = SCRIPTS / "build_phases_agent_validation.py"
FUNCTION = "validate_agent_self_description"
INTRO_SENTENCE = (
    "The entry below was carried here verbatim from the docstring of "
    "validate_agent_self_description (build_phases_agent_validation.py) to restore headroom there."
)

# Lines 28-73 of scripts/build_phases_profile_consistency.py at 36e5303a9, byte for byte.
FROZEN_HISTORY = (
    '    # DECISION HISTORY',
    '    # - 2026-06-05 12:30 [python-coder/EPIC-SelfDescribingAgents/04]:',
    '    #   Added validate_agent_self_description() per INF-600g. Checks',
    '    #   frontmatter fields (behavioral_patterns, pre_flight_reads, inputs,',
    '    #   outputs, mutates), registry fields (category, skills_invoked,',
    '    #   knowledge_channels), skill_id resolvability (package + project-local),',
    '    #   and knowledge_channels range (1-11). Aggregated output. Two severity',
    "    #   modes: 'warning' returns (0, N); 'error' returns (N, 0).",
    '    #   (#EPIC-SelfDescribingAgents/04)',
    '    # - 2026-06-29 [python-coder/EPIC-SelfDescribingAgentsCorrections/05]:',
    '    #   Confirmed two-path resolution order per INF-600g-3-i:',
    '    #   1. templates/skills/{skill_id}/SKILL.md (package-level)',
    '    #   2. .claude/skills/{skill_id}/SKILL.md (project-local)',
    '    #   A project-local-only skill passes validation without error.',
    '    #   Only when neither path resolves is an error emitted.',
    '    #   (#EPIC-SelfDescribingAgentsCorrections/05)',
    '    # - 2026-07-08 [python-coder/TICKET-20260708-BP-1300a-descriptive-skills]:',
    '    #   Added descriptive_only: true support per INF-600d-1. When a skills_invoked',
    '    #   entry carries "descriptive_only": true, the validator skips skill-dir',
    '    #   resolution (the entry documents an inline capability — no deployed',
    '    #   templates/skills/<id>/ exists by design). The strict ``is True`` identity',
    '    #   test prevents accidental skipping when the key holds a string, int, or None.',
    '    #   Unmarked unresolvable entries continue to fail (guardrail preserved).',
    '    #   (#TICKET-20260708-BP-1300a-descriptive-skills)',
    '    # - 2026-08-18 [python-coder/EPIC-BuildPipelinePhantomRemediation/02_bp1300a1]:',
    '    #   Dropped the ``in_project`` (deployed ``.claude/skills/``) resolution leg',
    '    #   per BP-1300a-1 / -1-i / -1-ii. A stale local deploy previously resolved',
    '    #   ``in_project = True`` for a since-removed skill, masking a genuinely',
    '    #   dangling pointer in a local checkout while it still failed a fresh CI',
    '    #   clone — an environment-dependent verdict. Resolution is now against the',
    '    #   canonical source only (``templates/skills/``); the error message no',
    '    #   longer names the deployed path. (#02_bp1300a1_canonical_skill_resolution)',
    '    # - 2026-08-25 [python-coder/EPIC-BuildPipelinePhantomRemediation]:',
    "    #   Added the ``config/skill_registry.json`` resolution leg per BP-1300a-1's",
    '    #   literal wording — "canonical source (templates/skills plus the',
    '    #   registry)". Previously only ``templates/skills/<id>/`` was consulted;',
    '    #   a registry entry with ``portable: false`` and no ``template_path``',
    '    #   (a shape ``skill_registry.schema.json`` explicitly permits, for',
    '    #   domain-specific skills deployed only under ``.claude/skills``) was',
    '    #   falsely flagged as unresolvable. That gap was latent only because a',
    '    #   DIFFERENT module (``registry_validator.validate_skill_registry``,',
    '    #   asserted by ``tests/test_skill_registry.py::test_no_orphaned_entries``)',
    '    #   happens to enforce full bidirectional parity between the registry and',
    '    #   ``templates/skills/`` today — an invariant this guard did not name or',
    '    #   depend on explicitly. Adding the registry leg removes the hidden',
    '    #   cross-module dependency and matches the AC text exactly.',
)
# Lines 2-22 of the same file at 36e5303a9: the module docstring's own description.
FROZEN_DESCRIPTION = (
    'MODULE: build_phases_profile_consistency',
    'GOAL: List every agent whose template frontmatter `tools` can write or edit',
    '    files while its `mutates` declares it changes nothing, so a profile that',
    '    contradicts its own tool list is visible instead of drifting silently.',
    'BUSINESS CONTEXT: ACD-2500e-1 corrected the it-po profile, which had Write and',
    '    Edit tools yet declared `mutates: none`. ACD-2500e-1-i makes that fix',
    '    durable: the next profile that drifts the same way is reported at build',
    '    time. The check is advisory (ADR-026 warn-before-required): a flagged',
    '    agent never changes an exit code. An unreadable registry or template is an',
    '    error, never "zero flagged".',
    'ARCHITECTURE: One pure decision (`_is_flagged`), one I/O function',
    '    (`check_profiles`), a build wiring helper (`profile_warning_count`) and a',
    '    CLI (`main`). validate_agent_self_description in',
    '    build_phases_agent_validation.py calls `profile_warning_count` once at its',
    '    tail and adds the result to the warning count only. "Writes or edits" is',
    '    read from the template frontmatter `tools`; "changes nothing" means every',
    '    `mutates` entry is named `none`; no agent list is hard-coded. Severity is',
    '    the module constant `SEVERITY`, deliberately not',
    '    `self_description_enforcement` (that is `error` today and would make this',
    '    check blocking on day one). Frontmatter is read with',
    '    template_compiler.parse_frontmatter.',
)
HEADING = FROZEN_HISTORY[0]
ENTRIES = FROZEN_HISTORY[1:]
ENTRY_HEADINGS = tuple(line for line in ENTRIES if line.lstrip().startswith("# - 2026-"))


def _source_lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")


def _raw_docstring(path: Path, function: str | None = None) -> list[str]:
    """The raw source lines the docstring node spans (opening and closing quote lines included)."""
    lines = _source_lines(path)
    tree = ast.parse("\n".join(lines))
    owner: ast.AST = tree
    if function is not None:
        found = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == function]
        assert len(found) == 1, f"{path.name} must define {function} exactly once"
        owner = found[0]
    body = getattr(owner, "body")
    node = body[0]
    assert isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant), "no docstring"
    assert isinstance(node.value.value, str), "no docstring"
    return lines[node.lineno - 1: node.end_lineno]


def _find_run(lines: list[str], run: tuple[str, ...]) -> int:
    """Index where `run` occurs as one contiguous block of lines in `lines`, or -1."""
    for start in range(len(lines) - len(run) + 1):
        if tuple(lines[start: start + len(run)]) == run:
            return start
    return -1


# --------------------------------------------------------------------------
# the history lives in the file that defines the check
# --------------------------------------------------------------------------
def test_self_description_history_moved_verbatim_to_defining_file():
    # covers: ACD-2500e-1-ii
    # angle: criterion
    """The docstring of validate_agent_self_description (raw source, indentation kept) holds the
    five entries as ONE contiguous run of lines, byte for byte and in order, after a
    "# DECISION HISTORY" heading, with any entries already there ahead of them and nothing but
    whitespace after them up to the closing quotes. Wrong versions this catches: a retyped or
    re-wrapped entry, a dropped or reordered entry, the entries placed in the module docstring or
    a trailing comment block instead of the function's docstring, and new text after them. Red
    today: the docstring has no decision history."""
    assert HEADING.strip() == "# DECISION HISTORY" and len(ENTRY_HEADINGS) == 5, "frozen block broken"
    doc = _raw_docstring(VALIDATION_MODULE, FUNCTION)
    start = _find_run(doc, ENTRIES)
    assert start != -1, f"{FUNCTION}'s docstring does not hold the five entries verbatim and in order"
    headings = [i for i, line in enumerate(doc) if line.strip() == "# DECISION HISTORY"]
    assert headings and headings[0] < start, "the entries must follow a # DECISION HISTORY heading"
    tail = doc[start + len(ENTRIES):]
    closing = tail[-1].rstrip()
    assert closing.endswith('"""') and not closing[:-3].strip(), "text follows the moved entries"
    assert all(not line.strip() for line in tail[:-1]), f"text follows the moved entries: {tail}"


def test_profile_consistency_docstring_drops_the_carried_history():
    # covers: ACD-2500e-1-ii
    # angle: criterion
    """The module docstring of build_phases_profile_consistency.py (raw) holds none of the five
    entry heading lines, no "# DECISION HISTORY" line and not the introducing sentence (compared
    with whitespace collapsed); and its own description (lines 2-22 at 36e5303a9) is still one
    contiguous, unchanged run at its start. Wrong versions this catches: a half-done move (entries
    in both files), a move that leaves the introducing sentence, and an over-eager cut that
    trims or rewords the module's own description. Red today: the sentence and entries are there."""
    doc = _raw_docstring(PROFILE_MODULE)
    stripped = {line.strip() for line in doc}
    left = [heading for heading in ENTRY_HEADINGS if heading.strip() in stripped]
    assert left == [], f"carried entries still in the profile-consistency docstring: {left}"
    assert "# DECISION HISTORY" not in stripped, "the # DECISION HISTORY heading is still there"
    assert INTRO_SENTENCE not in " ".join(" ".join(doc).split()), "the introducing sentence is still there"
    assert tuple(doc[1: 1 + len(FROZEN_DESCRIPTION)]) == FROZEN_DESCRIPTION, (
        "the module's own description changed or no longer opens the docstring"
    )


# --------------------------------------------------------------------------
# reachability: both checks report what they reported before the move
# --------------------------------------------------------------------------
_BOILERPLATE_LISTS = ("behavioral_patterns", "pre_flight_reads", "inputs", "outputs")
WRITE_TOOLS = "Read, Write, Bash"
NONE_MUTATES = [{"name": "none", "surface": "none", "description": "Read-only agent"}]
# Deliberately NOT the requirement store: a surface there is ACD-2500f-1-i's business.
SOURCE_MUTATES = [{"name": "source_files", "surface": "scripts/ source files",
                   "description": "Edits Python modules"}]
FLAGGED_ID, HONEST_ID = "fx-writer-none", "fx-writer-honest"
_RUN = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "sys.path.insert(0, sys.argv[1])\n"
    "import build_phases_profile_consistency\n"
    "import build_phases_agent_validation as v\n"
    "out = {}\n"
    "for level in ('warning', 'error'):\n"
    "    out[level] = list(v.validate_agent_self_description(\n"
    "        Path(sys.argv[2]), {}, False, level, package_root=Path(sys.argv[2])))\n"
    "print('RESULT ' + json.dumps(out))\n"
)


def _env() -> dict:
    return {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}


def _profile(agent_id: str, mutates: list[dict]) -> dict:
    front = {"name": agent_id, "tools": WRITE_TOOLS, "mutates": mutates, "produces": "analysis"}
    front["description"] = f"{agent_id} fixture agent"
    front.update({field: [] for field in _BOILERPLATE_LISTS})
    return front


def _package(tmp_path: Path, profiles: list[dict]) -> Path:
    """Templates written with yaml.safe_dump, registry with json.dumps (the real serializers)."""
    root = tmp_path / "pkg"
    (root / "templates" / "agents").mkdir(parents=True)
    (root / "config").mkdir()
    entries = []
    for profile in profiles:
        agent_id = profile["name"]
        front = yaml.safe_dump(profile, sort_keys=False)
        (root / "templates" / "agents" / f"{agent_id}.md").write_text(
            f"---\n{front}---\n\nYou are {agent_id}.\n", encoding="utf-8")
        entry = {"id": agent_id, "template_path": f"templates/agents/{agent_id}.md", "portable": True}
        entry.update({"category": "planning", "produces": profile["produces"],
                      "description": profile["description"], "skills_invoked": [], "knowledge_channels": []})
        entries.append(entry)
    registry = {"self_description_enforcement": "warning", "agents": entries}
    (root / "config" / "agent_registry.json").write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return root


def test_profile_check_and_agent_validation_results_unchanged_after_move(tmp_path):
    # covers: ACD-2500e-1-ii
    # angle: reachability
    """Entry points: the profile-consistency CLI (the script as a subprocess with real argv) and
    validate_agent_self_description in a fresh interpreter that also imports both modules, so a
    docstring edit that breaks the syntax or turns code into text fails here. Fixture: one
    write-capable agent declaring mutates none, one declaring a (non-store) surface. The results
    the check gave before the move: exit 0, empty stderr, stdout exactly the header
    "Profile consistency: examined 2, warning: 1 flagged" plus one line naming the flagged agent;
    validate_agent_self_description returns [0, 1] in warning mode and in error mode."""
    root = _package(tmp_path, [_profile(FLAGGED_ID, NONE_MUTATES), _profile(HONEST_ID, SOURCE_MUTATES)])
    proc = subprocess.run(
        [sys.executable, str(PROFILE_MODULE), "--registry", str(root / "config" / "agent_registry.json"),
         "--templates", str(root / "templates" / "agents")],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env(), cwd=str(REPO),
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert proc.stderr == "", proc.stderr
    lines = proc.stdout.splitlines()
    assert len(lines) == 2, proc.stdout
    assert lines[0] == "Profile consistency: examined 2, warning: 1 flagged", proc.stdout
    assert FLAGGED_ID in lines[1] and HONEST_ID not in lines[1], proc.stdout

    run = subprocess.run(
        [sys.executable, "-c", _RUN, str(SCRIPTS), str(root)],
        capture_output=True, text=True, encoding="utf-8", timeout=120, env=_env(), cwd=str(REPO),
    )
    result = next((ln for ln in run.stdout.splitlines() if ln.startswith("RESULT ")), None)
    assert result, run.stdout + run.stderr
    assert json.loads(result[len("RESULT "):]) == {"warning": [0, 1], "error": [0, 1]}, result
