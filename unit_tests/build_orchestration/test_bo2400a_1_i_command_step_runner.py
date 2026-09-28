"""
MODULE: unit_tests/build_orchestration/test_bo2400a_1_i_command_step_runner.py
GOAL: RED failing tests for BO-2400a-1-i -- the fast lane's one dedicated
      command-step-runner agent: a registry entry (permits_shell true, all
      four step_kinds), a template (least-privilege tools, the result/decline
      contract, non-zero-exit-is-a-result, runs-in-named-workspace-regardless-
      of-launch-checkout), a docs/agents/README.md index row, and a real
      build.py deploy to .claude/agents/command-step-runner.md.
TICKET: none (hand-driven build; AC YAML is the spec) -- see
    docs/acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400a-1-i.yaml

ASSUMED PRODUCTION API (none of this exists yet -- python-coder/llm-expert must
implement this shape):
  - config/agent_registry.json gains ONE new entry:
        {"id": "command-step-runner", "permits_shell": true,
         "step_kinds": ["reads_store", "changes_store", "changes_repository",
                        "publishes"],
         "template_path": "templates/agents/command-step-runner.md",
         "portable": true, "is_ticket_phase": false, "spawn_allowlist": [],
         "tier": "utility", ...}
    No other entry gains step_kinds or permits_shell in this change.
  - templates/agents/command-step-runner.md: frontmatter name ==
    "command-step-runner", tools includes the shell tool (Bash) and excludes
    Edit and Write. Body states the request/reply contract in the AC's own
    field names and the non-zero-exit / wrong-checkout clauses in prose.
  - docs/agents/README.md gains one table row for command-step-runner in the
    agent index (mirroring the existing worktree-agent row).
  - scripts/build.py, run against an empty target directory, compiles the new
    template to <target>/.claude/agents/command-step-runner.md.

This record does NOT touch config/agent_registry.schema.json or the
step_kinds gate itself (scripts/step_kinds_validator.py /
scripts/registry_validator.py) -- both already exist and are exercised
read-only here (BO-2400a-1-iii, already merged at the root this worktree is
based on).

RED BASELINE (empirically confirmed by running this file, unmodified, against
today's worktree -- see the test-writer report for the full pytest
transcript):
  - config/agent_registry.json has 60 entries and none of them has
    id == "command-step-runner" and none of them has a step_kinds key at all.
  - templates/agents/command-step-runner.md does not exist.
  - docs/agents/README.md has no "command-step-runner" table row.
  - A real `python scripts/build.py --target-dir <empty tmp dir>` run
    completes (exit 0) but produces no
    <target>/.claude/agents/command-step-runner.md file.
"""
# covers: BO-2400a-1-i

from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS_DIR = REPO_ROOT / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from registry_validator import validate_agent_registry  # noqa: E402
from step_kinds_validator import get_agent_step_kinds  # noqa: E402

_REGISTRY_PATH = REPO_ROOT / "config" / "agent_registry.json"
_TEMPLATE_PATH = REPO_ROOT / "templates" / "agents" / "command-step-runner.md"
_README_PATH = REPO_ROOT / "docs" / "agents" / "README.md"
_AGENT_ID = "command-step-runner"
_EXPECTED_KINDS = frozenset(
    {"reads_store", "changes_store", "changes_repository", "publishes"}
)

# The AC's it_requirements state a decline "never contains an exit_status
# key" / the criteria state it "carries no exit status". The template body
# must state this exclusion using one of these two phrasings (implementer
# assumption -- see the test-writer report).
_DECLINE_NO_EXIT_STATUS_RE = re.compile(
    r"(no\s+exit_status|never\s+contains?\s+an?\s+exit_status\s+key)",
    re.IGNORECASE,
)

# The AC's must_catch names the exact wrong phrasing a plausible-but-wrong
# implementation would use for a failed (non-zero-exit) command.
_WRONG_FAILURE_PHRASE = "could not complete this step"


def _load_registry_agents() -> list[dict[str, Any]]:
    """Load the real, shipped agents list from config/agent_registry.json."""
    raw = yaml.safe_load(_REGISTRY_PATH.read_text(encoding="utf-8"))
    return raw["agents"]


def _find_agent(agents: list[dict[str, Any]], agent_id: str) -> dict[str, Any] | None:
    """Return the entry whose id matches agent_id, or None if absent."""
    for agent in agents:
        if agent.get("id") == agent_id:
            return agent
    return None


def _read_frontmatter(path: Path) -> dict[str, Any]:
    """Parse a template's YAML frontmatter block (between the first two '---').

    Returns {} if the file has no frontmatter delimiters at all -- callers must
    fail on a missing/empty dict themselves so the failure names the real
    cause (e.g. "file does not exist" or "no frontmatter"), not a KeyError.
    """
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    return yaml.safe_load(parts[1]) or {}


def _read_template_body(path: Path) -> str:
    """Return the template's body text (after the frontmatter block).

    Falls back to the full file text when no frontmatter delimiter is found,
    so a prose-search test still runs (and still fails meaningfully) against
    a template file that exists but has no frontmatter yet.
    """
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    return parts[2] if len(parts) >= 3 else text


# ---------------------------------------------------------------------------
# 1. Registry entry exists and declares permits_shell true
# ---------------------------------------------------------------------------


def test_registry_declares_command_step_runner_with_permits_shell_true():
    # covers: BO-2400a-1-i
    # angle: criterion
    """AC BO-2400a-1-i: config/agent_registry.json has an entry with id
    'command-step-runner' whose permits_shell is the boolean True -- not
    absent, not a truthy string, not False.

    must_catch:
      - no registry entry for the command-step-runner exists (today's state)
      - the entry exists but permits_shell is absent
      - the entry exists but permits_shell is false
    """
    agents = _load_registry_agents()
    entry = _find_agent(agents, _AGENT_ID)
    assert entry is not None, (
        f"No registry entry with id '{_AGENT_ID}' in {_REGISTRY_PATH} -- "
        "the command-step-runner has not been added to the registry yet."
    )
    assert entry.get("permits_shell") is True, (
        f"'{_AGENT_ID}'.permits_shell must be the boolean True exactly "
        f"(not absent, not False, not a truthy string); "
        f"got {entry.get('permits_shell')!r}."
    )


# ---------------------------------------------------------------------------
# 2. Registry entry declares all four step kinds
# ---------------------------------------------------------------------------


def test_command_step_runner_declares_all_four_step_kinds():
    # covers: BO-2400a-1-i
    # angle: criterion
    """The command-step-runner registry entry's step_kinds lists exactly
    reads_store, changes_store, changes_repository and publishes."""
    agents = _load_registry_agents()
    entry = _find_agent(agents, _AGENT_ID)
    assert entry is not None, (
        f"No registry entry with id '{_AGENT_ID}' -- cannot check step_kinds."
    )
    kinds = get_agent_step_kinds(entry)
    assert kinds == _EXPECTED_KINDS, (
        f"'{_AGENT_ID}'.step_kinds must be exactly {sorted(_EXPECTED_KINDS)}; "
        f"got {sorted(kinds)}."
    )


# ---------------------------------------------------------------------------
# 4. Seam: the shipped registry (with the entry present) passes the real
#    BO-2400a-1-iii step_kinds gate.
# ---------------------------------------------------------------------------


def test_shipped_registry_with_command_step_runner_passes_the_step_kinds_gate():
    # covers: BO-2400a-1-i
    # covers: BO-2400a-1-iii
    # angle: seam
    """Running BO-2400a-1-iii's real registry gate (validate_agent_registry)
    over the shipped config/agent_registry.json, with the command-step-runner
    entry present and declaring all four kinds, reports no step_kinds
    violation for it.

    This is the seam between this record (the entry) and BO-2400a-1-iii (the
    gate): it pipes the real producer (the shipped registry file) into the
    real consumer (validate_agent_registry), not a hand-built fixture dict on
    either side.
    """
    agents = _load_registry_agents()
    entry = _find_agent(agents, _AGENT_ID)
    assert entry is not None, (
        f"No registry entry with id '{_AGENT_ID}' -- the gate cannot be "
        "meaningfully exercised before the entry exists."
    )
    assert get_agent_step_kinds(entry) == _EXPECTED_KINDS, (
        "precondition failed: command-step-runner must declare all four "
        "step kinds before this test can prove the gate accepts them."
    )

    errors = validate_agent_registry(REPO_ROOT)
    step_kind_errors = [
        e for e in errors if "step_kinds" in e and _AGENT_ID in e
    ]
    assert step_kind_errors == [], (
        "validate_agent_registry() reported step_kinds violation(s) for "
        f"'{_AGENT_ID}': {step_kind_errors}"
    )


# ---------------------------------------------------------------------------
# 5. docs/agents/README.md agent index lists command-step-runner
# ---------------------------------------------------------------------------


def test_agent_index_readme_lists_command_step_runner():
    # covers: BO-2400a-1-i
    # angle: real_artifact
    """docs/agents/README.md has a table row for command-step-runner.

    must_catch:
      - the agent is registered and deployed but missing from the package's
        agent index
    """
    readme_text = _README_PATH.read_text(encoding="utf-8")
    expected_link = f"[{_AGENT_ID}](coding/{_AGENT_ID}.md)"
    assert expected_link in readme_text, (
        f"docs/agents/README.md has no agent-index row for '{_AGENT_ID}' "
        f"(expected the link form '{expected_link}', mirroring the existing "
        "worktree-agent row)."
    )


# ---------------------------------------------------------------------------
# 6. Seam: the registry entry and the template are one agent.
# ---------------------------------------------------------------------------


def test_command_step_runner_entry_and_template_are_one_agent():
    # covers: BO-2400a-1-i
    # angle: seam
    """The entry's template_path exists, the template frontmatter name equals
    the registry id, portable is true, is_ticket_phase is false and
    spawn_allowlist is empty."""
    agents = _load_registry_agents()
    entry = _find_agent(agents, _AGENT_ID)
    assert entry is not None, (
        f"No registry entry with id '{_AGENT_ID}' -- cannot cross-check "
        "against a template."
    )

    template_rel = entry.get("template_path")
    assert template_rel, (
        f"'{_AGENT_ID}' registry entry has no template_path field."
    )
    template_path = REPO_ROOT / template_rel
    assert template_path.exists(), (
        f"'{_AGENT_ID}'.template_path ({template_rel}) does not resolve to "
        f"a real file at {template_path}."
    )

    frontmatter = _read_frontmatter(template_path)
    assert frontmatter.get("name") == _AGENT_ID, (
        f"Template frontmatter 'name' must equal the registry id "
        f"'{_AGENT_ID}'; got {frontmatter.get('name')!r}."
    )
    assert entry.get("portable") is True, (
        f"'{_AGENT_ID}' registry entry must declare portable: true; "
        f"got {entry.get('portable')!r}."
    )
    assert entry.get("is_ticket_phase") is False, (
        f"'{_AGENT_ID}' registry entry must declare is_ticket_phase: false "
        f"(it never appears in a ticket agents: map); "
        f"got {entry.get('is_ticket_phase')!r}."
    )
    assert entry.get("spawn_allowlist") == [], (
        f"'{_AGENT_ID}' registry entry must declare an empty spawn_allowlist "
        f"(it spawns nothing); got {entry.get('spawn_allowlist')!r}."
    )


# ---------------------------------------------------------------------------
# 7. Least privilege: shell yes, file-editing tools no.
# ---------------------------------------------------------------------------


def test_command_step_runner_template_grants_shell_but_no_file_editing_tool():
    # covers: BO-2400a-1-i
    # angle: failure
    """The template frontmatter tools include the shell tool and include none
    of the file-editing or file-creating tools, so a request to edit by hand
    cannot be carried out even if the prompt were ignored.

    must_catch:
      - the template inherits a default tool set that includes Edit or Write
    """
    assert _TEMPLATE_PATH.exists(), (
        f"Template not found at {_TEMPLATE_PATH} -- command-step-runner has "
        "not been authored yet."
    )
    frontmatter = _read_frontmatter(_TEMPLATE_PATH)
    tools_raw = frontmatter.get("tools", "")
    tools = {t.strip() for t in str(tools_raw).split(",") if t.strip()}

    assert "Bash" in tools, (
        f"'{_AGENT_ID}' template tools must include 'Bash' (the shell tool) "
        f"so it can run the requested command; got tools={sorted(tools)}."
    )
    assert "Edit" not in tools, (
        f"'{_AGENT_ID}' template tools must NOT include 'Edit' -- least "
        f"privilege requires the decline-on-hand-edit scenario to be backed "
        f"by what the agent CAN do, not only by what it is told; "
        f"got tools={sorted(tools)}."
    )
    assert "Write" not in tools, (
        f"'{_AGENT_ID}' template tools must NOT include 'Write' -- same "
        f"least-privilege rationale as Edit above; got tools={sorted(tools)}."
    )


# ---------------------------------------------------------------------------
# 8. The template states the result and decline shapes.
# ---------------------------------------------------------------------------


def test_command_step_runner_template_states_result_and_decline_shapes():
    # covers: BO-2400a-1-i
    # angle: criterion
    """The template body names every result field (command, workspace,
    exit_status, stdout, stderr) and every decline field (declined, step,
    agent, reason), and states that a decline carries no exit_status."""
    assert _TEMPLATE_PATH.exists(), (
        f"Template not found at {_TEMPLATE_PATH} -- cannot check its body "
        "for the result/decline contract."
    )
    body = _read_template_body(_TEMPLATE_PATH)

    for field in ("command", "workspace", "exit_status", "stdout", "stderr"):
        assert field in body, (
            f"Template body is missing the result field name '{field}' -- "
            "the result shape must be spelled out in the agent's own words."
        )
    for field in ("declined", "step", "agent", "reason"):
        assert field in body, (
            f"Template body is missing the decline field name '{field}' -- "
            "the decline shape must be spelled out in the agent's own words."
        )

    assert _DECLINE_NO_EXIT_STATUS_RE.search(body), (
        "Template body must state that a decline carries no exit_status key "
        "(e.g. 'no exit_status' or 'never contains an exit_status key') -- "
        "the presence of exit_status is the one signal used to tell a "
        "result from a decline, and the template must not blur it."
    )


# ---------------------------------------------------------------------------
# 9. Non-zero exit is a result, never a decline (discrimination).
# ---------------------------------------------------------------------------


def test_command_step_runner_template_treats_nonzero_exit_as_a_result():
    # covers: BO-2400a-1-i
    # angle: discrimination
    """The template tells the agent that a command which ran and exited
    non-zero is reported as a result with that exit_status, and never as a
    decline.

    must_catch:
      - the template tells the agent to report a failed command as 'could
        not complete this step'
    """
    assert _TEMPLATE_PATH.exists(), (
        f"Template not found at {_TEMPLATE_PATH} -- cannot check the "
        "non-zero-exit clause."
    )
    body = _read_template_body(_TEMPLATE_PATH)
    body_lower = body.lower()

    assert re.search(r"non-?zero exit", body, re.IGNORECASE), (
        "Template body must explicitly discuss a non-zero exit status "
        "(e.g. 'non-zero exit' or 'nonzero exit')."
    )
    assert "result" in body_lower, (
        "Template body must state that a non-zero exit is reported as a "
        "result (the word 'result' does not even appear)."
    )
    assert _WRONG_FAILURE_PHRASE not in body_lower, (
        f"Template body must NOT tell the agent to report a failed command "
        f"as '{_WRONG_FAILURE_PHRASE}' -- that turns every real command "
        "failure into a decline, which BO-2400f-5-iii would then report as "
        "a declined step instead of the step's own failure."
    )


# ---------------------------------------------------------------------------
# 10. Runs in the named workspace regardless of the launch checkout.
# ---------------------------------------------------------------------------


def test_command_step_runner_template_runs_in_named_workspace_regardless_of_launch_checkout():
    # covers: BO-2400a-1-i
    # angle: criterion
    """The template tells the agent to run in the named workspace even when
    it started in a different checkout, and not to call such a request
    misrouted or injected, relocate the command, or alter it."""
    assert _TEMPLATE_PATH.exists(), (
        f"Template not found at {_TEMPLATE_PATH} -- cannot check the "
        "launch-checkout clause."
    )
    body = _read_template_body(_TEMPLATE_PATH)

    assert re.search(
        r"different checkout|another checkout|sibling worktree|main checkout",
        body,
        re.IGNORECASE,
    ), (
        "Template body must discuss running when the agent was started in a "
        "different checkout (main checkout or a sibling worktree) than the "
        "one the request names."
    )
    assert re.search(r"misrouted", body, re.IGNORECASE), (
        "Template body must state that such a request is not called "
        "misrouted."
    )
    assert re.search(r"injected", body, re.IGNORECASE), (
        "Template body must state that such a request is not called "
        "injected."
    )


# ---------------------------------------------------------------------------
# 11. Deployed: a fresh build compiles the template into .claude/agents/.
# ---------------------------------------------------------------------------


def test_fresh_build_deploys_the_command_step_runner_agent_definition():
    # covers: BO-2400a-1-i
    # angle: deployed
    """Building the package into an empty temporary target directory produces
    .claude/agents/command-step-runner.md whose frontmatter name is
    command-step-runner.

    Runs the REAL scripts/build.py as a subprocess against a fresh, empty
    target directory -- a source-tree read of templates/agents/ is
    structurally blind to a deploy-manifest gap (the entry and the template
    could both exist while build.py never compiles them, e.g. if the
    template file name does not match the registry's template_path, or the
    template is accidentally prefixed with '_' and skipped as a helper file).
    """
    build_script = REPO_ROOT / "scripts" / "build.py"
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp)
        result = subprocess.run(
            [sys.executable, str(build_script), "--target-dir", str(target)],
            cwd=str(target),
            capture_output=True,
            text=True,
            timeout=180,
        )
        assert result.returncode == 0, (
            "scripts/build.py failed against a fresh empty target directory "
            f"(exit {result.returncode}).\n"
            f"--- stdout (tail) ---\n{result.stdout[-4000:]}\n"
            f"--- stderr (tail) ---\n{result.stderr[-4000:]}"
        )

        deployed_path = target / ".claude" / "agents" / f"{_AGENT_ID}.md"
        assert deployed_path.exists(), (
            f"Expected {deployed_path} to exist after a fresh build, but it "
            "does not -- the command-step-runner agent definition was not "
            "deployed."
        )

        frontmatter = _read_frontmatter(deployed_path)
        assert frontmatter.get("name") == _AGENT_ID, (
            f"Deployed agent file's frontmatter 'name' must equal "
            f"'{_AGENT_ID}'; got {frontmatter.get('name')!r}."
        )
